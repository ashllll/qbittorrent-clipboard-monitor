"""
网站特定适配器模块

为不同网站提供可配置的适配器，支持动态适配和配置驱动的扩展。

设计模式:
- 策略模式: 不同网站使用不同的适配策略
- 适配器模式: 统一不同网站的接口
- 工厂模式: 根据配置创建对应的适配器
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import re
import json
from urllib.parse import urlparse

from .models import SiteConfig


class SiteType(Enum):
    """网站类型枚举"""
    GENERIC = "generic"
    TORRENT = "torrent"
    MAGNET = "magnet"
    INDEX = "index"
    DIRECTORY = "directory"


@dataclass
class SelectorConfig:
    """选择器配置"""
    name: str
    selector: str
    attribute: Optional[str] = None
    multiple: bool = False
    required: bool = True
    post_process: Optional[Callable[[str], Any]] = None


class SiteAdapter:
    """网站适配器基类"""

    def __init__(self, config: SiteConfig):
        """
        初始化适配器

        Args:
            config: 网站配置
        """
        self.config = config
        self.name = config.name
        self.site_type = SiteType.GENERIC
        self.selectors: Dict[str, SelectorConfig] = {}
        self._initialize_selectors()

    def _initialize_selectors(self):
        """初始化选择器配置"""
        # 子类可以重写此方法来定义特定的选择器
        pass

    def can_handle(self, url: str) -> bool:
        """
        检查是否能够处理指定的URL

        Args:
            url: 目标URL

        Returns:
            bool: 是否可以处理
        """
        return self._match_url_pattern(url)

    def _match_url_pattern(self, url: str) -> bool:
        """
        匹配URL模式

        Args:
            url: 目标URL

        Returns:
            bool: 是否匹配
        """
        if not self.config.url_pattern:
            return False

        # 如果是正则表达式
        if self.config.url_pattern.startswith('regex:'):
            pattern = self.config.url_pattern[6:]
            return bool(re.search(pattern, url))

        # 如果是通配符模式
        if '*' in self.config.url_pattern:
            import fnmatch
            return fnmatch.fnmatch(url, self.config.url_pattern)

        # 直接匹配
        return url == self.config.url_pattern

    def extract_content(self, html: str, base_url: str) -> Dict[str, Any]:
        """
        提取内容

        Args:
            html: HTML内容
            base_url: 基础URL

        Returns:
            Dict[str, Any]: 提取的内容
        """
        # 这里使用简化实现，实际项目中可能需要BeautifulSoup或类似库
        result = {}

        for name, selector_config in self.selectors.items():
            try:
                # 简化实现：使用正则表达式匹配
                # 实际生产环境应该使用专业的HTML解析器
                if selector_config.selector.startswith('regex:'):
                    pattern = selector_config.selector[6:]
                    matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)

                    if selector_config.multiple:
                        result[name] = matches
                    elif matches:
                        value = matches[0]
                        if selector_config.post_process:
                            value = selector_config.post_process(value)
                        result[name] = value
                    elif selector_config.required:
                        result[name] = None
                else:
                    # 简化实现：使用字符串查找
                    # 生产环境应使用CSS选择器或XPath
                    if selector_config.selector in html:
                        start = html.find(selector_config.selector)
                        if start != -1:
                            if selector_config.multiple:
                                result[name] = [selector_config.selector]
                            else:
                                result[name] = selector_config.selector
                    elif selector_config.required:
                        result[name] = None

            except Exception as e:
                if selector_config.required:
                    result[name] = None

        return result

    def transform_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换内容

        Args:
            content: 原始内容

        Returns:
            Dict[str, Any]: 转换后的内容
        """
        # 子类可以重写此方法来进行特定的内容转换
        return content

    def validate_content(self, content: Dict[str, Any]) -> bool:
        """
        验证内容

        Args:
            content: 待验证的内容

        Returns:
            bool: 是否有效
        """
        # 检查必需字段
        for name, selector_config in self.selectors.items():
            if selector_config.required and (name not in content or content[name] is None):
                return False

        return True


class GenericSiteAdapter(SiteAdapter):
    """通用网站适配器"""

    def __init__(self, config: SiteConfig):
        self.site_type = SiteType.GENERIC
        super().__init__(config)

    def _initialize_selectors(self):
        """初始化通用选择器"""
        # 默认选择器
        self.selectors = {
            'title': SelectorConfig(
                name='title',
                selector='regex:<title>(.*?)</title>',
                required=True
            ),
            'links': SelectorConfig(
                name='links',
                selector='regex:href=[\"\']([^\"\']+)[\"\']',
                multiple=True,
                required=False
            ),
        }


class TorrentSiteAdapter(SiteAdapter):
    """种子网站适配器"""

    def __init__(self, config: SiteConfig):
        self.site_type = SiteType.TORRENT
        super().__init__(config)

    def _initialize_selectors(self):
        """初始化种子网站选择器"""
        self.selectors = {
            'title': SelectorConfig(
                name='title',
                selector='regex:<title>(.*?)</title>',
                required=True,
                post_process=lambda x: x.strip() if x else ''
            ),
            'magnet_links': SelectorConfig(
                name='magnet_links',
                selector=r'regex:magnet:\?[^"\'\s<>\]]+',
                multiple=True,
                required=False,
                post_process=lambda x: x.strip()
            ),
            'file_list': SelectorConfig(
                name='file_list',
                selector=r'regex:<a[^>]+href=[\"\']([^\"\']+\.(torrent|zip|rar|7z))[\"\']',
                multiple=True,
                required=False
            ),
            'description': SelectorConfig(
                name='description',
                selector=r'regex:<div[^>]+class=[\"\'][^\"\']*desc[^\"\']*[\"\'](.*?)</div>',
                required=False
            ),
            'size': SelectorConfig(
                name='size',
                selector=r'regex:(\d+(?:\.\d+)?\s*(?:GB|MB|KB|TB))',
                required=False
            ),
        }

    def extract_magnets(self, html: str) -> List[str]:
        """
        专门提取磁力链接

        Args:
            html: HTML内容

        Returns:
            List[str]: 磁力链接列表
        """
        content = self.extract_content(html, '')
        return content.get('magnet_links', [])


class MagnetLinkAdapter(SiteAdapter):
    """磁力链接页面适配器"""

    def __init__(self, config: SiteConfig):
        self.site_type = SiteType.MAGNET
        super().__init__(config)

    def _initialize_selectors(self):
        """初始化磁力链接选择器"""
        self.selectors = {
            'magnet_link': SelectorConfig(
                name='magnet_link',
                selector=r'regex:magnet:\?[^"\'\s<>\]]+',
                required=True
            ),
            'title': SelectorConfig(
                name='title',
                selector=r'regex:<title>(.*?)(?:\s*-\s*magnet|\s*-\s*torrent)?</title>',
                required=False
            ),
            'announce': SelectorConfig(
                name='announce',
                selector=r'regex:urn:btih:([A-Fa-f0-9]{32,40})',
                required=False
            ),
        }

    def extract_magnets(self, html: str) -> List[str]:
        """提取磁力链接"""
        content = self.extract_content(html, '')
        if content.get('magnet_link'):
            return [content['magnet_link']]
        return []


class IndexSiteAdapter(SiteAdapter):
    """索引网站适配器"""

    def __init__(self, config: SiteConfig):
        self.site_type = SiteType.INDEX
        super().__init__(config)

    def _initialize_selectors(self):
        """初始化索引网站选择器"""
        self.selectors = {
            'entries': SelectorConfig(
                name='entries',
                selector=r'regex:<a[^>]+href=[\"\']([^\"\']+)[\"\'][^>]*>([^<]+)</a>',
                multiple=True,
                required=False
            ),
            'directories': SelectorConfig(
                name='directories',
                selector=r'regex:<[^>]+class=[\"\'][^\"\']*dir[^\"\']*[\"\'][^>]*href=[\"\']([^\"\']+)[\"\']',
                multiple=True,
                required=False
            ),
            'parent_link': SelectorConfig(
                name='parent_link',
                selector=r'regex:<a[^>]+href=[\"\']([^\"\']*)\.\.[^\"\']*[\"\'][^>]*>.*?parent',
                required=False
            ),
        }


class DirectoryAdapter(SiteAdapter):
    """目录页面适配器"""

    def __init__(self, config: SiteConfig):
        self.site_type = SiteType.DIRECTORY
        super().__init__(config)

    def _initialize_selectors(self):
        """初始化目录选择器"""
        self.selectors = {
            'files': SelectorConfig(
                name='files',
                selector=r'regex:<a[^>]+href=[\"\']([^\"\']+\.(torrent|magnet))[\"\'][^>]*>([^<]+)</a>',
                multiple=True,
                required=False
            ),
            'folders': SelectorConfig(
                name='folders',
                selector=r'regex:<[^>]+class=[\"\'][^\"\']*folder[^\"\']*[\"\'][^>]*href=[\"\']([^\"\']+)[\"\']',
                multiple=True,
                required=False
            ),
        }


class AdapterFactory:
    """适配器工厂"""

    # 适配器映射
    _adapters: Dict[SiteType, type] = {
        SiteType.GENERIC: GenericSiteAdapter,
        SiteType.TORRENT: TorrentSiteAdapter,
        SiteType.MAGNET: MagnetLinkAdapter,
        SiteType.INDEX: IndexSiteAdapter,
        SiteType.DIRECTORY: DirectoryAdapter,
    }

    @classmethod
    def create_adapter(cls, config: SiteConfig) -> SiteAdapter:
        """
        创建适配器

        Args:
            config: 网站配置

        Returns:
            SiteAdapter: 适配器实例
        """
        # 根据配置确定网站类型
        site_type = cls._detect_site_type(config)

        # 获取适配器类
        adapter_class = cls._adapters.get(site_type, GenericSiteAdapter)

        # 创建实例
        return adapter_class(config)

    @classmethod
    def _detect_site_type(cls, config: SiteConfig) -> SiteType:
        """
        检测网站类型

        Args:
            config: 网站配置

        Returns:
            SiteType: 网站类型
        """
        # 检查配置中的提示
        if hasattr(config, 'site_type') and config.site_type:
            try:
                return SiteType(config.site_type)
            except ValueError:
                pass

        # 根据URL模式检测
        url = config.url_pattern.lower()

        # 种子相关
        if any(keyword in url for keyword in ['torrent', 'tracker', 'seed', 'leech']):
            return SiteType.TORRENT

        # 磁力链接
        if 'magnet' in url:
            return SiteType.MAGNET

        # 索引
        if any(keyword in url for keyword in ['index', 'list', 'browse']):
            return SiteType.INDEX

        # 目录
        if any(keyword in url for keyword in ['dir', 'folder', 'directory']):
            return SiteType.DIRECTORY

        return SiteType.GENERIC

    @classmethod
    def register_adapter(cls, site_type: SiteType, adapter_class: type):
        """
        注册自定义适配器

        Args:
            site_type: 网站类型
            adapter_class: 适配器类
        """
        cls._adapters[site_type] = adapter_class

    @classmethod
    def get_available_types(cls) -> List[SiteType]:
        """
        获取可用的网站类型

        Returns:
            List[SiteType]: 网站类型列表
        """
        return list(cls._adapters.keys())


class AdaptiveParser:
    """自适应解析器

    智能选择合适的适配器进行内容提取
    """

    def __init__(self, configs: List[SiteConfig]):
        """
        初始化解析器

        Args:
            configs: 网站配置列表
        """
        self.configs = configs
        self.adapters: List[SiteAdapter] = [
            AdapterFactory.create_adapter(config) for config in configs
        ]

    def parse(self, url: str, html: str) -> Optional[Dict[str, Any]]:
        """
        解析内容

        Args:
            url: 源URL
            html: HTML内容

        Returns:
            Optional[Dict[str, Any]]: 解析结果
        """
        # 尝试使用适配器解析
        for adapter in self.adapters:
            if adapter.can_handle(url):
                try:
                    content = adapter.extract_content(html, url)
                    if adapter.validate_content(content):
                        return adapter.transform_content(content)
                except Exception as e:
                    # 记录错误，继续尝试下一个适配器
                    continue

        # 如果没有适配器可以处理，返回基本内容
        return self._fallback_parse(url, html)

    def _fallback_parse(self, url: str, html: str) -> Dict[str, Any]:
        """
        备用解析方法

        Args:
            url: 源URL
            html: HTML内容

        Returns:
            Dict[str, Any]: 基础解析结果
        """
        # 提取基本信息
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ''

        # 提取链接
        links = re.findall(r'href=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE)

        # 提取磁力链接
        magnets = re.findall(r'magnet:\?[^"\'\s<>\]]+', html, re.IGNORECASE)

        return {
            'url': url,
            'title': title,
            'links': list(set(links)),
            'magnet_links': list(set(magnets)),
            'adapter_used': None,
        }

    def add_config(self, config: SiteConfig):
        """
        添加网站配置

        Args:
            config: 网站配置
        """
        adapter = AdapterFactory.create_adapter(config)
        self.adapters.append(adapter)

    def get_adapter_for_url(self, url: str) -> Optional[SiteAdapter]:
        """
        获取适合的适配器

        Args:
            url: 目标URL

        Returns:
            Optional[SiteAdapter]: 适配器或None
        """
        for adapter in self.adapters:
            if adapter.can_handle(url):
                return adapter
        return None


# 导出
__all__ = [
    'SiteAdapter',
    'GenericSiteAdapter',
    'TorrentSiteAdapter',
    'MagnetLinkAdapter',
    'IndexSiteAdapter',
    'DirectoryAdapter',
    'AdapterFactory',
    'AdaptiveParser',
    'SiteType',
    'SelectorConfig',
]
