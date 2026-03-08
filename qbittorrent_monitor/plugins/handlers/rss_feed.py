"""RSS 订阅处理器插件

支持解析和处理 RSS 订阅源，自动下载其中的种子。
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp

from ..base import HandlerPlugin, PluginMetadata, PluginType, HandlerResult
from ...security import validate_url

logger = logging.getLogger(__name__)


@dataclass
class RSSItem:
    """RSS 条目"""
    title: str
    link: str
    description: str = ""
    pub_date: Optional[datetime] = None
    enclosure_url: Optional[str] = None
    guid: str = ""
    categories: List[str] = field(default_factory=list)
    
    @property
    def is_torrent(self) -> bool:
        """检查是否为种子链接"""
        url = self.enclosure_url or self.link
        if not url:
            return False
        return (
            url.startswith("magnet:?") or
            url.endswith(".torrent") or
            "torrent" in url.lower()
        )
    
    def get_download_url(self) -> Optional[str]:
        """获取下载 URL"""
        return self.enclosure_url or self.link


class RSSFeedHandler(HandlerPlugin):
    """RSS 订阅处理器插件
    
    解析 RSS 订阅源并提取种子链接进行下载。
    
    配置项:
        - feeds: RSS 订阅源列表，每项包含 url 和可选的 category、filter
        - check_interval: 检查间隔（分钟），默认 30
        - max_items_per_feed: 每次最多处理条目数，默认 10
        - timeout: 请求超时时间（秒），默认 30
        - user_agent: 自定义 User-Agent
        - auto_download: 是否自动下载，默认 True
        - filters: 全局过滤器配置
    
    Example:
        >>> plugin = RSSFeedHandler()
        >>> plugin.configure({
        ...     "feeds": [
        ...         {
        ...             "url": "https://example.com/rss",
        ...             "category": "movies",
        ...             "filter": {"min_size": "1GB", "keywords": ["1080p"]}
        ...         }
        ...     ],
        ...     "check_interval": 60
        ... })
    """
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="rss_feed_handler",
            version="1.0.0",
            description="解析和处理 RSS 订阅源",
            author="qBittorrent Monitor",
            plugin_type=PluginType.HANDLER,
            config_schema={
                "feeds": {
                    "type": "list",
                    "required": True,
                    "description": "RSS 订阅源列表"
                },
                "check_interval": {
                    "type": "integer",
                    "required": False,
                    "description": "检查间隔（分钟）"
                },
                "max_items_per_feed": {
                    "type": "integer",
                    "required": False,
                    "description": "每次最多处理条目数"
                },
                "timeout": {
                    "type": "integer",
                    "required": False,
                    "description": "请求超时时间（秒）"
                },
                "user_agent": {
                    "type": "string",
                    "required": False,
                    "description": "自定义 User-Agent"
                },
                "auto_download": {
                    "type": "boolean",
                    "required": False,
                    "description": "是否自动下载"
                },
                "filters": {
                    "type": "dict",
                    "required": False,
                    "description": "全局过滤器配置"
                }
            }
        )
    
    def __init__(self):
        super().__init__()
        self._session: Optional[aiohttp.ClientSession] = None
        self._processed_guids: set = set()  # 已处理的条目
        self._last_check: Dict[str, datetime] = {}  # 上次检查时间
    
    async def initialize(self) -> bool:
        """初始化处理器"""
        try:
            timeout = aiohttp.ClientTimeout(
                total=self._config.get("timeout", 30)
            )
            headers = {
                "User-Agent": self._config.get(
                    "user_agent",
                    "qBittorrent-Monitor/1.0 RSS Handler"
                )
            }
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers
            )
            
            # 加载已处理的 GUID（持久化）
            await self._load_processed_guids()
            
            logger.info("RSSFeedHandler 初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"RSSFeedHandler 初始化失败: {e}")
            return False
    
    async def shutdown(self) -> None:
        """关闭处理器"""
        # 保存已处理的 GUID
        await self._save_processed_guids()
        
        if self._session:
            await self._session.close()
            self._session = None
            
        logger.debug("RSSFeedHandler 已关闭")
    
    async def can_handle(self, content: str, **kwargs) -> bool:
        """检查是否可以处理该内容
        
        支持 RSS URL 和 XML 内容。
        
        Args:
            content: 要检查的内容
            **kwargs: 额外参数
            
        Returns:
            是否可以处理
        """
        # 检查是否为 RSS URL
        if content.startswith(("http://", "https://")):
            if any(x in content.lower() for x in ["rss", "feed", "atom", ".xml"]):
                return True
        
        # 检查是否为 XML 内容
        if content.strip().startswith("<?xml") or content.strip().startswith("<rss"):
            return True
            
        return False
    
    async def handle(self, content: str, **kwargs) -> HandlerResult:
        """处理 RSS 内容
        
        Args:
            content: RSS URL 或 XML 内容
            **kwargs: 额外参数，可包含 category 等
            
        Returns:
            处理结果
        """
        try:
            if content.startswith(("http://", "https://")):
                # 获取 RSS 内容
                rss_content = await self._fetch_feed(content)
                if not rss_content:
                    return HandlerResult(
                        success=False,
                        message=f"无法获取 RSS: {content}"
                    )
            else:
                rss_content = content
            
            # 解析 RSS
            items = self._parse_rss(rss_content, content)
            
            # 过滤条目
            filtered_items = self._filter_items(items, kwargs.get("filter", {}))
            
            # 获取新条目
            new_items = [item for item in filtered_items 
                        if item.guid not in self._processed_guids]
            
            # 限制数量
            max_items = self._config.get("max_items_per_feed", 10)
            items_to_process = new_items[:max_items]
            
            # 处理条目
            processed = []
            for item in items_to_process:
                result = await self._process_item(item, **kwargs)
                if result:
                    processed.append(item.title)
                    self._processed_guids.add(item.guid)
            
            # 保存状态
            await self._save_processed_guids()
            
            return HandlerResult(
                success=True,
                message=f"处理了 {len(processed)}/{len(items)} 个条目",
                data={
                    "total_items": len(items),
                    "new_items": len(new_items),
                    "processed": len(processed),
                    "titles": processed
                }
            )
            
        except Exception as e:
            logger.exception(f"处理 RSS 失败: {e}")
            return HandlerResult(
                success=False,
                message=f"处理失败: {str(e)}"
            )
    
    async def check_all_feeds(self) -> Dict[str, HandlerResult]:
        """检查所有配置的 RSS 订阅源
        
        Returns:
            每个订阅源的处理结果
        """
        feeds = self._config.get("feeds", [])
        results = {}
        
        for feed_config in feeds:
            url = feed_config.get("url")
            if not url:
                continue
                
            try:
                result = await self.handle(url, **feed_config)
                results[url] = result
            except Exception as e:
                results[url] = HandlerResult(
                    success=False,
                    message=f"检查失败: {str(e)}"
                )
        
        return results
    
    async def _fetch_feed(self, url: str) -> Optional[str]:
        """获取 RSS 内容
        
        Args:
            url: RSS URL
            
        Returns:
            RSS 内容或 None
        """
        if not self._session:
            return None
        
        # 验证 URL
        try:
            validate_url(url, "RSS_URL")
        except Exception as e:
            logger.warning(f"RSS URL 验证失败: {e}")
            return None
        
        try:
            async with self._session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"获取 RSS 失败: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"请求 RSS 失败: {e}")
            return None
    
    def _parse_rss(self, content: str, base_url: str) -> List[RSSItem]:
        """解析 RSS 内容
        
        Args:
            content: RSS XML 内容
            base_url: 基础 URL（用于解析相对链接）
            
        Returns:
            RSS 条目列表
        """
        items = []
        
        try:
            root = ET.fromstring(content)
            
            # 处理 RSS 2.0
            if root.tag == "rss":
                channel = root.find("channel")
                if channel is not None:
                    for item_elem in channel.findall("item"):
                        item = self._parse_rss_item(item_elem, base_url)
                        if item:
                            items.append(item)
            
            # 处理 Atom
            elif "feed" in root.tag:
                for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                    item = self._parse_atom_entry(entry, base_url)
                    if item:
                        items.append(item)
                        
        except ET.ParseError as e:
            logger.error(f"解析 RSS XML 失败: {e}")
        
        return items
    
    def _parse_rss_item(self, elem: ET.Element, base_url: str) -> Optional[RSSItem]:
        """解析 RSS 2.0 item 元素
        
        Args:
            elem: XML 元素
            base_url: 基础 URL
            
        Returns:
            RSSItem 或 None
        """
        try:
            title = elem.findtext("title", "")
            link = elem.findtext("link", "")
            description = elem.findtext("description", "")
            guid = elem.findtext("guid", link)
            pub_date_str = elem.findtext("pubDate")
            
            # 解析 enclosure
            enclosure_url = None
            enclosure = elem.find("enclosure")
            if enclosure is not None:
                enclosure_url = enclosure.get("url")
            
            # 解析分类
            categories = [cat.text for cat in elem.findall("category") if cat.text]
            
            # 解析日期
            pub_date = None
            if pub_date_str:
                try:
                    pub_date = self._parse_date(pub_date_str)
                except Exception:
                    pass
            
            # 规范化 URL
            if link and not link.startswith(("http://", "https://", "magnet:")):
                link = urljoin(base_url, link)
            if enclosure_url and not enclosure_url.startswith(("http://", "https://")):
                enclosure_url = urljoin(base_url, enclosure_url)
            
            return RSSItem(
                title=title,
                link=link,
                description=description,
                pub_date=pub_date,
                enclosure_url=enclosure_url,
                guid=guid or link,
                categories=categories
            )
            
        except Exception as e:
            logger.warning(f"解析 RSS item 失败: {e}")
            return None
    
    def _parse_atom_entry(self, elem: ET.Element, base_url: str) -> Optional[RSSItem]:
        """解析 Atom entry 元素
        
        Args:
            elem: XML 元素
            base_url: 基础 URL
            
        Returns:
            RSSItem 或 None
        """
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        
        try:
            title = elem.findtext("atom:title", "", ns)
            link_elem = elem.find("atom:link", ns)
            link = link_elem.get("href") if link_elem is not None else ""
            description = elem.findtext("atom:summary", "", ns) or elem.findtext("atom:content", "", ns)
            guid = elem.findtext("atom:id", link)
            updated = elem.findtext("atom:updated")
            
            # 解析日期
            pub_date = None
            if updated:
                try:
                    pub_date = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                except Exception:
                    pass
            
            return RSSItem(
                title=title,
                link=link,
                description=description,
                pub_date=pub_date,
                guid=guid or link
            )
            
        except Exception as e:
            logger.warning(f"解析 Atom entry 失败: {e}")
            return None
    
    def _filter_items(
        self, 
        items: List[RSSItem], 
        filter_config: Dict[str, Any]
    ) -> List[RSSItem]:
        """过滤 RSS 条目
        
        Args:
            items: 条目列表
            filter_config: 过滤器配置
            
        Returns:
            过滤后的条目列表
        """
        result = items
        
        # 关键词过滤
        keywords = filter_config.get("keywords", [])
        if keywords:
            result = [
                item for item in result
                if any(kw.lower() in item.title.lower() for kw in keywords)
            ]
        
        # 排除关键词
        exclude = filter_config.get("exclude", [])
        if exclude:
            result = [
                item for item in result
                if not any(ex.lower() in item.title.lower() for ex in exclude)
            ]
        
        # 分类过滤
        categories = filter_config.get("categories", [])
        if categories:
            result = [
                item for item in result
                if any(cat in item.categories for cat in categories)
            ]
        
        return result
    
    async def _process_item(self, item: RSSItem, **kwargs) -> bool:
        """处理单个 RSS 条目
        
        Args:
            item: RSS 条目
            **kwargs: 额外参数
            
        Returns:
            处理是否成功
        """
        url = item.get_download_url()
        if not url:
            return False
        
        # 触发事件，让外部处理下载
        self.emit_event("rss_item_found", {
            "title": item.title,
            "url": url,
            "category": kwargs.get("category", "other"),
            "rss_item": item
        })
        
        logger.info(f"发现 RSS 条目: {item.title}")
        return True
    
    def _parse_date(self, date_str: str) -> datetime:
        """解析 RSS 日期字符串
        
        Args:
            date_str: 日期字符串
            
        Returns:
            datetime 对象
        """
        # 尝试多种格式
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"无法解析日期: {date_str}")
    
    async def _load_processed_guids(self) -> None:
        """加载已处理的 GUID"""
        import json
        from pathlib import Path
        
        guid_file = self.config_dir / "rss_processed_guids.json"
        
        if guid_file.exists():
            try:
                with open(guid_file, "r") as f:
                    data = json.load(f)
                    self._processed_guids = set(data.get("guids", []))
                    self._last_check = {
                        k: datetime.fromisoformat(v)
                        for k, v in data.get("last_check", {}).items()
                    }
            except Exception as e:
                logger.warning(f"加载已处理 GUID 失败: {e}")
    
    async def _save_processed_guids(self) -> None:
        """保存已处理的 GUID"""
        import json
        from pathlib import Path
        
        guid_file = self.config_dir / "rss_processed_guids.json"
        
        try:
            # 限制 GUID 数量，避免文件过大
            max_guids = 10000
            guids = list(self._processed_guids)
            if len(guids) > max_guids:
                guids = guids[-max_guids:]
            
            data = {
                "guids": guids,
                "last_check": {
                    k: v.isoformat()
                    for k, v in self._last_check.items()
                }
            }
            
            with open(guid_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"保存已处理 GUID 失败: {e}")
    
    @property
    def config_dir(self) -> Path:
        """获取配置目录"""
        return Path.home() / ".config" / "qb-monitor" / "plugins" / "config"
