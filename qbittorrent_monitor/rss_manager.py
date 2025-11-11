"""
RSS订阅自动下载管理模块

提供：
- RSS/Atom 源解析
- 定时检查更新
- 智能内容过滤
- 自动下载匹配
- 订阅管理
"""

import asyncio
import logging
import aiohttp
from datetime import datetime, timedelta

# 可选导入
try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from pathlib import Path
import re

from .intelligent_filter import get_intelligent_filter, FilterResult
from .workflow_engine import get_workflow_engine
from .utils import parse_magnet, validate_magnet_link


logger = logging.getLogger(__name__)


@dataclass
class RSSItem:
    """RSS项目"""
    id: str
    title: str
    link: str
    description: str
    pub_date: Optional[datetime] = None
    magnet_link: Optional[str] = None
    size: Optional[int] = None
    seeders: int = 0
    leechers: int = 0
    category: str = ""
    tags: List[str] = field(default_factory=list)
    quality_score: float = 0.0
    filtered: bool = False
    download_status: str = "pending"  # pending, downloaded, skipped, failed


@dataclass
class RSSSource:
    """RSS源配置"""
    name: str
    url: str
    enabled: bool = True
    check_interval: int = 1800  # 30分钟
    last_check: Optional[datetime] = None
    download_enabled: bool = True
    category: str = "rss"
    filters: List[Dict[str, Any]] = field(default_factory=list)
    max_items_per_check: int = 50
    items: List[RSSItem] = field(default_factory=list)
    downloaded_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class RSSManager:
    """
    RSS订阅管理器

    功能：
    1. 管理多个RSS/Atom源
    2. 定期抓取更新
    3. 解析磁力链接
    4. 智能过滤
    5. 自动下载
    """

    def __init__(self, qbt_client, config):
        self.qbt_client = qbt_client
        self.config = config
        self.intelligent_filter = get_intelligent_filter()
        self.workflow_engine = get_workflow_engine()

        # RSS源存储
        self.sources: Dict[str, RSSSource] = {}
        self.is_running = False

        # 统计信息
        self.stats = {
            "total_sources": 0,
            "active_sources": 0,
            "total_items": 0,
            "downloaded_items": 0,
            "skipped_items": 0,
            "failed_items": 0,
            "last_check_time": None
        }

        # 下载历史（去重）
        self.downloaded_ids: Set[str] = set()

    def add_source(
        self,
        name: str,
        url: str,
        enabled: bool = True,
        check_interval: int = 1800,
        category: str = "rss",
        download_enabled: bool = True,
        filters: Optional[List[Dict[str, Any]]] = None
    ) -> RSSSource:
        """添加RSS源"""
        if filters is None:
            filters = [
                {"field": "title", "operator": "contains", "value": "magnet"},
                {"field": "description", "operator": "contains", "value": "magnet"}
            ]

        source = RSSSource(
            name=name,
            url=url,
            enabled=enabled,
            check_interval=check_interval,
            category=category,
            download_enabled=download_enabled,
            filters=filters
        )

        self.sources[name] = source
        self.stats["total_sources"] += 1
        if enabled:
            self.stats["active_sources"] += 1

        logger.info(f"添加RSS源: {name} ({url})")
        return source

    def remove_source(self, name: str):
        """移除RSS源"""
        if name in self.sources:
            source = self.sources[name]
            if source.enabled:
                self.stats["active_sources"] -= 1
            del self.sources[name]
            self.stats["total_sources"] -= 1
            logger.info(f"移除RSS源: {name}")

    def get_source(self, name: str) -> Optional[RSSSource]:
        """获取RSS源"""
        return self.sources.get(name)

    def get_all_sources(self) -> List[RSSSource]:
        """获取所有RSS源"""
        return list(self.sources.values())

    async def start(self):
        """启动RSS管理器"""
        if self.is_running:
            return

        self.is_running = True
        self.logger = logging.getLogger(f"{__name__}.RSSManager")

        # 启动所有启用的源的检查任务
        tasks = []
        for source in self.sources.values():
            if source.enabled:
                task = asyncio.create_task(self._source_check_loop(source))
                tasks.append(task)

        if tasks:
            self.logger.info(f"启动RSS管理器和 {len(tasks)} 个检查任务")
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            self.logger.warning("没有启用的RSS源")

    async def stop(self):
        """停止RSS管理器"""
        self.is_running = False
        self.logger.info("RSS管理器已停止")

    async def _source_check_loop(self, source: RSSSource):
        """单个源的检查循环"""
        while self.is_running and source.enabled:
            try:
                await self.check_source(source)
                # 等待指定的检查间隔
                await asyncio.sleep(source.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                source.error_count += 1
                self.logger.error(f"检查RSS源 {source.name} 失败: {e}")
                # 失败后等待1分钟再试
                await asyncio.sleep(60)

    async def check_source(self, source: RSSSource) -> bool:
        """检查单个RSS源"""
        try:
            if not HAS_FEEDPARSER:
                self.logger.error("feedparser模块未安装，无法检查RSS源")
                return False

            self.logger.info(f"检查RSS源: {source.name}")

            # 获取RSS内容
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            ) as session:
                async with session.get(source.url) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")

                    content = await response.text()

            # 解析RSS
            feed = feedparser.parse(content)

            if not feed.entries:
                self.logger.warning(f"RSS源 {source.name} 没有内容")
                return False

            # 处理新项目
            new_items = 0
            for entry in feed.entries[:source.max_items_per_check]:
                # 生成项目ID
                item_id = self._generate_item_id(source, entry)
                if item_id in self.downloaded_ids:
                    continue

                # 创建RSSItem
                item = await self._parse_rss_entry(source, entry, item_id)
                if not item:
                    continue

                # 智能过滤
                filter_result = await self._filter_item(item)
                if not filter_result.allowed:
                    item.filtered = True
                    self.logger.info(f"过滤项目: {item.title[:50]}... - {', '.join(filter_result.reasons)}")
                    source.items.append(item)
                    self.downloaded_ids.add(item_id)
                    continue

                # 保存项目
                item.quality_score = filter_result.score
                source.items.append(item)
                self.downloaded_ids.add(item_id)
                new_items += 1
                self.stats["total_items"] += 1

                # 自动下载
                if source.download_enabled and item.magnet_link:
                    success = await self._download_item(source, item)
                    if success:
                        source.downloaded_count += 1
                        self.stats["downloaded_items"] += 1
                    else:
                        source.skipped_count += 1
                        self.stats["skipped_items"] += 1

            # 更新源信息
            source.last_check = datetime.now()
            self.stats["last_check_time"] = source.last_check

            # 清理旧项目（保留最近1000个）
            if len(source.items) > 1000:
                source.items = source.items[-1000:]

            self.logger.info(
                f"RSS源 {source.name} 检查完成: "
                f"新项目 {new_items}, 总项目 {len(source.items)}"
            )

            return True

        except Exception as e:
            source.error_count += 1
            self.logger.error(f"检查RSS源 {source.name} 失败: {e}")
            return False

    def _generate_item_id(self, source: RSSSource, entry) -> str:
        """生成项目ID"""
        # 优先使用GUID，其次使用链接，最后使用标题
        item_id = getattr(entry, 'id', '') or getattr(entry, 'link', '') or entry.title
        return f"{source.name}:{hash(item_id)}"

    async def _parse_rss_entry(
        self,
        source: RSSSource,
        entry,
        item_id: str
    ) -> Optional[RSSItem]:
        """解析RSS条目"""
        try:
            title = entry.title if hasattr(entry, 'title') else "未知标题"
            link = entry.link if hasattr(entry, 'link') else ""
            description = entry.description if hasattr(entry, 'description') else ""

            # 提取磁力链接
            magnet_link = self._extract_magnet_link(description or link)
            if not magnet_link:
                # 尝试从全文内容中提取
                if hasattr(entry, 'content') and entry.content:
                    for content in entry.content:
                        magnet_link = self._extract_magnet_link(content.value)
                        if magnet_link:
                            break

            # 解析发布日期
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime.fromtimestamp(datetime(*entry.published_parsed[:6]).timestamp())
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_date = datetime.fromtimestamp(datetime(*entry.updated_parsed[:6]).timestamp())

            # 提取元数据
            size, seeders, leechers = self._extract_metadata(description or link)

            # 提取标签
            tags = self._extract_tags(description or link)

            item = RSSItem(
                id=item_id,
                title=title,
                link=link,
                description=description,
                pub_date=pub_date,
                magnet_link=magnet_link,
                size=size,
                seeders=seeders,
                leechers=leechers,
                category=source.category,
                tags=tags
            )

            return item

        except Exception as e:
            self.logger.error(f"解析RSS条目失败: {e}")
            return None

    def _extract_magnet_link(self, text: str) -> Optional[str]:
        """从文本中提取磁力链接"""
        if not text:
            return None

        # 匹配磁力链接
        magnet_pattern = r'magnet:\?[^<>\s]+'
        matches = re.findall(magnet_pattern, text, re.IGNORECASE)

        if matches:
            magnet_link = matches[0]
            if validate_magnet_link(magnet_link):
                return magnet_link

        return None

    def _extract_metadata(self, text: str) -> tuple:
        """提取元数据（大小、做种数、下载数）"""
        size = seeders = leechers = 0

        # 提取大小
        size_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:GB|MB|KB|TB)',
            r'size[:\s]*(\d+(?:\.\d+)?)\s*(?:GB|MB|KB|TB)',
            r'文件大小[:\s]*(\d+(?:\.\d+)?)\s*(?:GB|MB|KB|TB)'
        ]
        for pattern in size_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                size_str = match.group(1)
                unit = re.search(pattern, text, re.IGNORECASE).group(2)
                try:
                    size_value = float(size_str)
                    multipliers = {'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
                    size = int(size_value * multipliers.get(unit.upper(), 1))
                except Exception:
                    logger.debug(f"解析大小失败: {size_str}")
                break

        # 提取做种数
        seeder_patterns = [
            r'(\d+)\s*个做种',
            r'seeders?[:\s]*(\d+)',
            r'做种[:\s]*(\d+)',
            r'种子[:\s]*(\d+)'
        ]
        for pattern in seeder_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                seeders = int(match.group(1))
                break

        # 提取下载数
        leecher_patterns = [
            r'(\d+)\s*个下载',
            r'leechers?[:\s]*(\d+)',
            r'下载[:\s]*(\d+)'
        ]
        for pattern in leecher_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                leechers = int(match.group(1))
                break

        return size, seeders, leechers

    def _extract_tags(self, text: str) -> List[str]:
        """提取标签"""
        tags = []

        # 质量标签
        quality_tags = ['720p', '1080p', '4K', 'BluRay', 'WEB-DL', 'HDTV', 'Dolby', 'Atmos']
        for tag in quality_tags:
            if tag.lower() in text.lower():
                tags.append(f"quality:{tag.lower()}")

        # 格式标签
        format_tags = ['.mkv', '.mp4', '.avi', '.rmvb', '.flac', '.mp3']
        for tag in format_tags:
            if tag in text.lower():
                tags.append(f"format:{tag[1:]}")

        return tags

    async def _filter_item(self, item: RSSItem) -> FilterResult:
        """过滤RSS项目"""
        try:
            # 使用智能过滤器
            filter_result = await self.intelligent_filter.filter_content(
                title=item.title,
                magnet_link=item.magnet_link or "",
                size=item.size,
                seeders=item.seeders,
                leechers=item.leechers,
                category=item.category
            )

            # 应用自定义过滤器
            for filter_rule in self.sources.get(item.category, RSSSource("", "")).filters:
                field = filter_rule.get("field")
                operator = filter_rule.get("operator")
                value = filter_rule.get("value")

                if not self._evaluate_filter(item, field, operator, value):
                    filter_result.allowed = False
                    filter_result.reasons.append(f"自定义过滤器: {field} {operator} {value}")
                    break

            return filter_result

        except Exception as e:
            self.logger.error(f"过滤项目失败: {e}")
            # 过滤失败时允许通过
            # 生成size字符串
            size_str = ""
            if item.size:
                if item.size >= 1024**3:  # >= 1GB
                    size_str = f"{item.size / (1024**3):.1f}GB"
                elif item.size >= 1024**2:  # >= 1MB
                    size_str = f"{item.size / (1024**2):.1f}MB"
                else:
                    size_str = f"{item.size}B"
            
            return FilterResult(
                content=item,
                allowed=True,
                action=None,
                score=0.0,
                quality_level=None,
                size=size_str
            )

    def _evaluate_filter(self, item: RSSItem, field: str, operator: str, value: Any) -> bool:
        """评估单个过滤器"""
        try:
            field_value = getattr(item, field, "")

            if operator == "contains":
                return str(value).lower() in str(field_value).lower()
            elif operator == "not_contains":
                return str(value).lower() not in str(field_value).lower()
            elif operator == "equals":
                return str(field_value) == str(value)
            elif operator == "not_equals":
                return str(field_value) != str(value)
            elif operator == "greater_than":
                return float(field_value) > float(value)
            elif operator == "less_than":
                return float(field_value) < float(value)
            elif operator == "regex":
                return bool(re.search(str(value), str(field_value)))

            return True

        except Exception as e:
            self.logger.error(f"评估过滤器失败: {e}")
            return True

    async def _download_item(self, source: RSSSource, item: RSSItem) -> bool:
        """下载RSS项目"""
        try:
            if not item.magnet_link:
                return False

            # 添加到qBittorrent
            success = await self.qbt_client.add_torrent(
                item.magnet_link,
                source.category
            )

            if success:
                item.download_status = "downloaded"
                self.logger.info(f"RSS下载成功: {item.title[:50]}...")
                return True
            else:
                item.download_status = "failed"
                self.logger.error(f"RSS下载失败: {item.title[:50]}...")
                return False

        except Exception as e:
            item.download_status = "failed"
            self.logger.error(f"RSS下载异常: {e}")
            return False

    async def force_check_all(self):
        """强制检查所有源"""
        self.logger.info("强制检查所有RSS源")

        tasks = []
        for source in self.sources.values():
            if source.enabled:
                task = asyncio.create_task(self.check_source(source))
                tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "sources": {
                name: {
                    "name": source.name,
                    "url": source.url,
                    "enabled": source.enabled,
                    "item_count": len(source.items),
                    "downloaded_count": source.downloaded_count,
                    "skipped_count": source.skipped_count,
                    "error_count": source.error_count,
                    "last_check": source.last_check.isoformat() if source.last_check else None
                }
                for name, source in self.sources.items()
            }
        }

    def get_recent_items(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的项目"""
        all_items = []
        for source in self.sources.values():
            for item in source.items[-limit:]:
                all_items.append({
                    "id": item.id,
                    "title": item.title,
                    "source": source.name,
                    "pub_date": item.pub_date.isoformat() if item.pub_date else None,
                    "download_status": item.download_status,
                    "filtered": item.filtered,
                    "quality_score": item.quality_score,
                    "has_magnet": bool(item.magnet_link)
                })

        # 按发布日期排序
        all_items.sort(key=lambda x: x["pub_date"] or "", reverse=True)
        return all_items[:limit]

    def save_config(self, config_path: str):
        """保存配置到文件"""
        if not HAS_YAML:
            self.logger.warning("yaml模块未安装，无法保存配置")
            return

        config_data = {
            "sources": []
        }

        for source in self.sources.values():
            config_data["sources"].append({
                "name": source.name,
                "url": source.url,
                "enabled": source.enabled,
                "check_interval": source.check_interval,
                "download_enabled": source.download_enabled,
                "category": source.category,
                "filters": source.filters,
                "max_items_per_check": source.max_items_per_check
            })

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        self.logger.info(f"RSS配置已保存到: {config_path}")

    def load_config(self, config_path: str):
        """从文件加载配置"""
        if not HAS_YAML:
            self.logger.warning("yaml模块未安装，无法加载配置")
            return

        if not Path(config_path).exists():
            self.logger.warning(f"RSS配置文件不存在: {config_path}")
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)

            for source_data in config_data.get("sources", []):
                self.add_source(
                    name=source_data["name"],
                    url=source_data["url"],
                    enabled=source_data.get("enabled", True),
                    check_interval=source_data.get("check_interval", 1800),
                    category=source_data.get("category", "rss"),
                    download_enabled=source_data.get("download_enabled", True),
                    filters=source_data.get("filters", [])
                )

            self.logger.info(f"RSS配置已从 {config_path} 加载")

        except Exception as e:
            self.logger.error(f"加载RSS配置失败: {e}")


# 全局RSS管理器实例
_rss_manager: Optional[RSSManager] = None


def get_rss_manager() -> Optional[RSSManager]:
    """获取全局RSS管理器"""
    return _rss_manager


async def initialize_rss_manager(qbt_client, config) -> RSSManager:
    """初始化全局RSS管理器"""
    global _rss_manager
    _rss_manager = RSSManager(qbt_client, config)
    return _rss_manager
