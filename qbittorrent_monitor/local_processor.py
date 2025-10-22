"""
本地处理器

实现所有不涉及 qBittorrent API 的本地功能：
- 剪贴板内容处理
- 磁力链接解析和验证
- 协议转换（磁力链接格式统一）
- 内容智能分类
- 本地缓存管理

这些功能完全不调用 qBittorrent API，确保 100% API 合规
"""

import re
import time
import logging
import hashlib
import urllib.parse
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from .core.link_parser import get_magnet_parser
from .core.protocols.protocol_manager import get_protocol_manager
from .config import CategoryConfig


class ContentType(Enum):
    """内容类型枚举"""
    MOVIE = "movie"
    TV = "tv"
    ANIME = "anime"
    SOFTWARE = "software"
    GAME = "game"
    MUSIC = "music"
    DOCUMENT = "document"
    OTHER = "unknown"


@dataclass
class ProcessedContent:
    """处理后的内容"""
    original_content: str
    magnet_link: Optional[str]
    content_type: ContentType
    display_name: Optional[str]
    file_size: Optional[int]
    protocol_type: Optional[str]
    confidence: float
    processing_time: float


class LocalClipboardProcessor:
    """
    本地剪贴板处理器

    完全不涉及 qBittorrent API，只进行本地内容处理
    """

    def __init__(self):
        self.logger = logging.getLogger('LocalClipboardProcessor')

        # 初始化解析器
        self.magnet_parser = get_magnet_parser()
        self.protocol_manager = get_protocol_manager()

        # 缓存最近处理的内容
        self._processed_cache: Dict[str, float] = {}
        self._cache_ttl = 300  # 5分钟缓存

        # 性能统计
        self._stats = {
            'total_processed': 0,
            'magnet_found': 0,
            'protocol_converted': 0,
            'processing_errors': 0,
            'cache_hits': 0
        }

    def process_clipboard_content(self, content: str) -> Optional[ProcessedContent]:
        """
        处理剪贴板内容

        完全本地处理，不涉及任何 API 调用
        """
        if not content or not isinstance(content, str):
            return None

        # 缓存检查
        content_hash = self._get_content_hash(content)
        if self._is_cached(content_hash):
            self._stats['cache_hits'] += 1
            return None  # 缓存命中，避免重复处理

        start_time = time.time()
        self._stats['total_processed'] += 1

        try:
            # 1. 提取磁力链接或协议链接
            magnet_link, protocol_info = self._extract_download_link(content)
            if not magnet_link:
                return None

            # 2. 分析内容类型
            content_type = self._classify_content(content, magnet_link)

            # 3. 提取显示名称和文件大小
            display_name, file_size = self._extract_metadata(content, magnet_link)

            # 4. 计算置信度
            confidence = self._calculate_confidence(content, magnet_link, protocol_info)

            result = ProcessedContent(
                original_content=content,
                magnet_link=magnet_link,
                content_type=content_type,
                display_name=display_name,
                file_size=file_size,
                protocol_type=protocol_info.get('protocol_type', 'magnet') if protocol_info else None,
                confidence=confidence,
                processing_time=time.time() - start_time
            )

            # 缓存结果
            self._cache_processed_content(content_hash)

            if protocol_info and protocol_info.get('converted'):
                self._stats['protocol_converted'] += 1
            else:
                self._stats['magnet_found'] += 1

            self.logger.debug(f"处理完成: {result.display_name} ({result.content_type.value})")
            return result

        except Exception as e:
            self._stats['processing_errors'] += 1
            self.logger.error(f"处理剪贴板内容失败: {e}")
            return None

    def _extract_download_link(self, content: str) -> Tuple[Optional[str], Optional[Dict]]:
        """提取下载链接（磁力链接或协议链接）"""
        # 1. 首先查找标准磁力链接
        magnet_pattern = r'magnet:\?xt=[^\s]+'
        magnet_match = re.search(magnet_pattern, content, re.IGNORECASE)
        if magnet_match:
            magnet_link = magnet_match.group(0)
            self.logger.debug("找到标准磁力链接")
            return magnet_link, None

        # 2. 尝试协议转换
        protocol_result = self.protocol_manager.parse_protocol_url(content)
        if protocol_result.is_valid and protocol_result.converted_magnet:
            self.logger.debug(f"协议转换成功: {protocol_result.protocol_type.value}")
            return protocol_result.converted_magnet, {
                'protocol_type': protocol_result.protocol_type.value,
                'converted': True,
                'confidence': protocol_result.confidence
            }

        return None, None

    def _classify_content(self, content: str, magnet_link: str) -> ContentType:
        """本地内容分类"""
        # 优先使用磁力链接中的信息
        display_name = self._extract_display_name_from_magnet(magnet_link)
        if display_name:
            return self._classify_by_name(display_name)

        # 回退到原始内容分类
        return self._classify_by_name(content)

    def _classify_by_name(self, name: str) -> ContentType:
        """基于名称进行分类"""
        name_lower = name.lower()

        # 电影关键词
        movie_keywords = [
            r'\b(movie|film|cinema)\b',
            r'\.1080p\b', r'\.720p\b', r'\.4k\b',
            r'\.blu-ray\b', r'\.bdrip\b', r'\.web-dl\b',
            r'\.(avi|mkv|mp4|mov|wmv)\b'
        ]

        # 电视剧关键词
        tv_keywords = [
            r'\b(tv|series|season|episode|s\d{1,2}|e\d{1,3})\b',
            r'\b(season\s*\d+|episode\s*\d+)\b',
            r'\.s\d{1,2}e\d{1,3}\b'
        ]

        # 动漫关键词
        anime_keywords = [
            r'\b(anime|animation|cartoon|manga)\b',
            r'\b[\u4e00-\u9fff].*\d{2,3}\b',  # 中文字符+数字
            r'\.(mkv|mp4).*\b(good|sub|raw)\b'
        ]

        # 软件关键词
        software_keywords = [
            r'\b(software|app|application|program|tool|utility)\b',
            r'\.(exe|msi|dmg|pkg|deb|rpm|zip|rar|7z)\b',
            r'\b(install|setup|portable|crack|keygen|patch)\b'
        ]

        # 游戏关键词
        game_keywords = [
            r'\b(game|gaming|play)\b',
            r'\.(iso|cso|gog|steam|origin)\b',
            r'\b(pc|ps4|ps5|xbox|switch)\b'
        ]

        # 检查关键词匹配
        if any(re.search(keyword, name_lower) for keyword in software_keywords):
            return ContentType.SOFTWARE
        elif any(re.search(keyword, name_lower) for keyword in game_keywords):
            return ContentType.GAME
        elif any(re.search(keyword, name_lower) for keyword in anime_keywords):
            return ContentType.ANIME
        elif any(re.search(keyword, name_lower) for keyword in tv_keywords):
            return ContentType.TV
        elif any(re.search(keyword, name_lower) for keyword in movie_keywords):
            return ContentType.MOVIE

        return ContentType.OTHER

    def _extract_metadata(self, content: str, magnet_link: str) -> Tuple[Optional[str], Optional[int]]:
        """提取元数据（显示名称和文件大小）"""
        # 从磁力链接解析
        try:
            magnet_info = self.magnet_parser.parse(magnet_link)
            if magnet_info.is_valid:
                display_name = magnet_info.display_name
                file_size = magnet_info.file_size
                return display_name, file_size
        except Exception as e:
            self.logger.warning(f"解析磁力链接失败: {e}")

        # 回退：从内容中提取
        display_name = self._extract_display_name_from_content(content)
        file_size = self._extract_file_size_from_content(content)

        return display_name, file_size

    def _extract_display_name_from_magnet(self, magnet_link: str) -> Optional[str]:
        """从磁力链接提取显示名称"""
        dn_match = re.search(r'dn=([^&]+)', magnet_link)
        if dn_match:
            try:
                return urllib.parse.unquote_plus(dn_match.group(1))
            except Exception:
                return dn_match.group(1)
        return None

    def _extract_display_name_from_content(self, content: str) -> Optional[str]:
        """从内容中提取可能的显示名称"""
        # 查找可能的文件名模式
        patterns = [
            r'\b([A-Za-z0-9._\-\s\u4e00-\u9fff]+\.(?:mkv|mp4|avi|mov|wmv|flv))\b',
            r'\b([A-Za-z0-9._\-\s\u4e00-\u9fff]+\.(?:exe|iso|rar|zip|7z))\b',
            r'\b([^\s]+\.(?:torrent))\b'
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _extract_file_size_from_content(self, content: str) -> Optional[int]:
        """从内容中提取文件大小"""
        # 查找文件大小模式
        size_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:GB|G|gigabyte)s?\b',  # GB
            r'(\d+(?:\.\d+)?)\s*(?:MB|M|megabyte)s?\b',  # MB
            r'(\d+(?:\.\d+)?)\s*(?:KB|K|kilobyte)s?\b',  # KB
            r'xl=(\d+)'  # 磁力链接中的 xl 参数
        ]

        for pattern in size_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                try:
                    size_value = float(matches[0])
                    if 'gb' in pattern.lower() or 'gigabyte' in pattern.lower():
                        return int(size_value * 1024 * 1024 * 1024)
                    elif 'mb' in pattern.lower() or 'megabyte' in pattern.lower():
                        return int(size_value * 1024 * 1024)
                    elif 'kb' in pattern.lower() or 'kilobyte' in pattern.lower():
                        return int(size_value * 1024)
                    else:  # xl 参数，单位为字节
                        return int(size_value)
                except ValueError:
                    continue

        return None

    def _calculate_confidence(
        self,
        content: str,
        magnet_link: str,
        protocol_info: Optional[Dict]
    ) -> float:
        """计算处理置信度"""
        confidence = 0.0

        # 磁力链接有效性
        if magnet_link.startswith('magnet:'):
            confidence += 0.4
            if 'xt=urn:btih:' in magnet_link:
                confidence += 0.3

        # 协议转换成功
        if protocol_info and protocol_info.get('converted'):
            confidence += 0.2

        # 内容分类明确
        display_name = self._extract_display_name_from_magnet(magnet_link) or \
                     self._extract_display_name_from_content(content)
        if display_name:
            confidence += 0.1

        # 文件大小信息
        file_size = self._extract_file_size_from_content(content)
        if file_size:
            confidence += 0.1

        return min(confidence, 1.0)

    def _get_content_hash(self, content: str) -> str:
        """获取内容哈希"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _is_cached(self, content_hash: str) -> bool:
        """检查是否在缓存中"""
        if content_hash in self._processed_cache:
            cache_time = self._processed_cache[content_hash]
            if time.time() - cache_time < self._cache_ttl:
                return True
            else:
                # 缓存过期，删除
                del self._processed_cache[content_hash]
        return False

    def _cache_processed_content(self, content_hash: str):
        """缓存处理过的内容"""
        self._processed_cache[content_hash] = time.time()

        # 清理过期缓存
        self._cleanup_cache()

    def _cleanup_cache(self):
        """清理过期的缓存项"""
        current_time = time.time()
        expired_keys = [
            key for key, cache_time in self._processed_cache.items()
            if current_time - cache_time > self._cache_ttl
        ]

        for key in expired_keys:
            del self._processed_cache[key]

    def get_statistics(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        return {
            **self._stats,
            'cache_size': len(self._processed_cache),
            'cache_hit_rate': (
                self._stats['cache_hits'] /
                max(1, self._stats['total_processed'])
            ) * 100,
            'magnet_detection_rate': (
                self._stats['magnet_found'] /
                max(1, self._stats['total_processed'])
            ) * 100,
            'protocol_conversion_rate': (
                self._stats['protocol_converted'] /
                max(1, self._stats['total_processed'])
            ) * 100
        }

    def clear_cache(self):
        """清空缓存"""
        self._processed_cache.clear()
        self.logger.info("本地处理器缓存已清空")


class LocalCategoryMapper:
    """
    本地分类映射器

    将内容类型映射到 qBittorrent 分类名称
    """

    def __init__(self, categories: Dict[str, CategoryConfig]):
        self.categories = categories
        self.logger = logging.getLogger('LocalCategoryMapper')

        # 构建反向映射
        self.type_to_category = {
            ContentType.MOVIE: self._find_category_for_type('movie'),
            ContentType.TV: self._find_category_for_type('tv'),
            ContentType.ANIME: self._find_category_for_type('anime'),
            ContentType.SOFTWARE: self._find_category_for_type('software'),
            ContentType.GAME: self._find_category_for_type('game'),
            ContentType.MUSIC: self._find_category_for_type('music'),
            ContentType.DOCUMENT: self._find_category_for_type('document'),
            ContentType.OTHER: self._find_category_for_type('other')
        }

    def map_to_category(self, content_type: ContentType) -> Optional[str]:
        """
        将内容类型映射到 qBittorrent 分类

        纯本地操作，不涉及 API 调用
        """
        return self.type_to_category.get(content_type)

    def _find_category_for_type(self, type_name: str) -> Optional[str]:
        """查找匹配的分类"""
        # 查找关键词匹配
        for category_name, category_config in self.categories.items():
            if type_name in category_config.keywords:
                return category_name

        # 查找名称匹配
        for category_name in self.categories:
            if type_name.lower() in category_name.lower():
                return category_name

        return None

    def get_available_categories(self) -> List[str]:
        """获取可用的分类列表"""
        return list(self.categories.keys())

    def validate_category(self, category: str) -> bool:
        """验证分类是否存在"""
        return category in self.categories


class LocalDuplicateDetector:
    """
    本地重复检测器

    使用布隆过滤器和哈希表进行快速重复检测
    """

    def __init__(self):
        self.logger = logging.getLogger('LocalDuplicateDetector')

        # 哈希存储
        self._seen_hashes: Dict[str, float] = {}
        self._hash_ttl = 86400  # 24小时

        # 统计信息
        self._stats = {
            'total_checks': 0,
            'duplicates_found': 0,
            'hashes_stored': 0
        }

    def is_duplicate(self, magnet_link: str) -> bool:
        """
        检查磁力链接是否重复

        纯本地检测，不调用 API
        """
        self._stats['total_checks'] += 1

        # 提取哈希值
        torrent_hash = self._extract_hash_from_magnet(magnet_link)
        if not torrent_hash:
            return False

        # 检查是否已存在
        if torrent_hash in self._seen_hashes:
            self._stats['duplicates_found'] += 1
            return True

        # 存储新哈希
        self._seen_hashes[torrent_hash] = time.time()
        self._stats['hashes_stored'] += 1

        # 清理过期哈希
        self._cleanup_expired_hashes()

        return False

    def _extract_hash_from_magnet(self, magnet_link: str) -> Optional[str]:
        """从磁力链接提取哈希值"""
        hash_match = re.search(r'xt=urn:btih:([a-fA-F0-9]{40})', magnet_link)
        if hash_match:
            return hash_match.group(1).lower()
        return None

    def _cleanup_expired_hashes(self):
        """清理过期的哈希值"""
        current_time = time.time()
        expired_hashes = [
            hash_val for hash_val, timestamp in self._seen_hashes.items()
            if current_time - timestamp > self._hash_ttl
        ]

        for hash_val in expired_hashes:
            del self._seen_hashes[hash_val]

    def get_statistics(self) -> Dict[str, Any]:
        """获取检测统计信息"""
        return {
            **self._stats,
            'stored_hashes': len(self._seen_hashes),
            'duplicate_rate': (
                self._stats['duplicates_found'] /
                max(1, self._stats['total_checks'])
            ) * 100
        }

    def clear_hashes(self):
        """清空存储的哈希值"""
        self._seen_hashes.clear()
        self.logger.info("重复检测器哈希值已清空")


# 工厂函数
def create_local_processor(categories: Dict[str, CategoryConfig]) -> Tuple[LocalClipboardProcessor, LocalCategoryMapper, LocalDuplicateDetector]:
    """创建本地处理器实例"""
    processor = LocalClipboardProcessor()
    category_mapper = LocalCategoryMapper(categories)
    duplicate_detector = LocalDuplicateDetector()

    return processor, category_mapper, duplicate_detector