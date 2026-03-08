"""剪贴板缓存模块

提供剪贴板内容的哈希缓存，避免重复解析。
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Dict, Optional
from collections import OrderedDict

logger = logging.getLogger(__name__)


class ClipboardCache:
    """剪贴板内容哈希缓存 - 避免重复解析
    
    使用 MD5 哈希（缓存场景不需要加密安全）以获得更好性能。
    添加内存限制防止内存泄漏，使用 LRU 策略。
    
    Attributes:
        max_size: 最大缓存条目数
        max_memory_mb: 最大内存使用（MB）
    
    Example:
        >>> cache = ClipboardCache(max_size=1000, max_memory_mb=50)
        >>> result = cache.get(content)
        >>> if result is None:
        ...     result = process_content(content)
        ...     cache.put(content, result)
    """

    def __init__(self, max_size: int = 1000, max_memory_mb: int = 50):
        """初始化缓存
        
        Args:
            max_size: 最大缓存条目数
            max_memory_mb: 最大内存使用（MB）
        """
        self._cache: OrderedDict[str, str] = OrderedDict()  # LRU 缓存
        self._max_size = max_size
        self._max_memory_bytes = max_memory_mb * 1024 * 1024
        self._total_content_size = 0
        
        # 访问时间跟踪（用于 LRU）
        self._access_times: Dict[str, float] = {}
        
        # 统计
        self._hits = 0
        self._misses = 0

    def _compute_hash(self, content: str) -> str:
        """计算内容哈希
        
        使用 MD5（性能优化，缓存场景安全）。
        短内容直接哈希，长内容使用采样哈希。
        
        Args:
            content: 内容字符串
            
        Returns:
            哈希字符串
        """
        if len(content) <= 1000:
            return hashlib.md5(content.encode('utf-8')).hexdigest()
        
        # 长内容：哈希前1KB + 长度作为指纹
        return hashlib.md5(
            content[:1000].encode('utf-8') + str(len(content)).encode()
        ).hexdigest()

    def get(self, content: str) -> Optional[str]:
        """获取缓存的哈希，如果存在则更新访问时间
        
        Args:
            content: 原始内容
            
        Returns:
            缓存的结果，如果不存在返回 None
        """
        content_hash = self._compute_hash(content)
        
        if content_hash in self._cache:
            # 更新访问时间并移到末尾（最近使用）
            self._access_times[content_hash] = time.time()
            self._cache.move_to_end(content_hash)
            self._hits += 1
            return self._cache[content_hash]
        
        self._misses += 1
        return None

    def put(self, content: str, result_hash: str) -> None:
        """添加缓存项
        
        Args:
            content: 原始内容
            result_hash: 结果哈希
        """
        # 检查内容大小
        content_size = len(content.encode('utf-8'))
        if content_size > 10 * 1024 * 1024:  # 10MB 限制
            logger.debug(f"剪贴板内容过大 ({content_size} 字节)，跳过缓存")
            return
        
        content_hash = self._compute_hash(content)
        
        # 如果已存在，更新大小
        if content_hash in self._cache:
            old_size = len(self._cache[content_hash].encode('utf-8'))
            self._total_content_size -= old_size
            # 移除旧项以便重新添加（更新顺序）
            del self._cache[content_hash]
        else:
            # 清理旧缓存
            while (len(self._cache) >= self._max_size or 
                   self._total_content_size > self._max_memory_bytes):
                self._evict_oldest()
        
        # 添加新项
        self._cache[content_hash] = result_hash
        self._cache.move_to_end(content_hash)
        self._access_times[content_hash] = time.time()
        self._total_content_size += len(result_hash.encode('utf-8'))

    def _evict_oldest(self) -> None:
        """淘汰最久未访问的缓存项（LRU）"""
        if not self._cache:
            return
        
        # 弹出最旧的项（OrderedDict 的第一个）
        oldest_hash, oldest_value = self._cache.popitem(last=False)
        self._total_content_size -= len(oldest_value.encode('utf-8'))
        del self._access_times[oldest_hash]
        
        logger.debug(f"淘汰缓存项: {oldest_hash[:16]}...")

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._access_times.clear()
        self._total_content_size = 0
        logger.debug("剪贴板缓存已清空")

    def get_stats(self) -> Dict[str, any]:
        """获取缓存统计信息
        
        Returns:
            统计字典
        """
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "memory_bytes": self._total_content_size,
            "memory_mb": round(self._total_content_size / (1024 * 1024), 2),
        }

    def __len__(self) -> int:
        """返回缓存条目数"""
        return len(self._cache)

    def __contains__(self, content: str) -> bool:
        """检查内容是否在缓存中"""
        content_hash = self._compute_hash(content)
        return content_hash in self._cache
