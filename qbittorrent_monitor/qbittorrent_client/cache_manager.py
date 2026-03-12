"""缓存管理器 - 请求缓存和性能优化

此模块提供缓存管理功能，包括LRU缓存和缓存统计。
"""

import hashlib
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple


class CacheManager:
    """LRU缓存管理器
    
    基于OrderedDict实现的LRU缓存，支持TTL过期。
    
    Attributes:
        max_size: 最大缓存大小
        ttl_seconds: 缓存项TTL（秒）
    
    Example:
        >>> cache = CacheManager(max_size=1000, ttl_seconds=300)
        >>> cache.set("key", value)
        >>> value = cache.get("key")
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """初始化缓存管理器
        
        Args:
            max_size: 最大缓存大小
            ttl_seconds: 缓存项TTL（秒）
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
    
    def get_cache_key(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> str:
        """生成缓存键
        
        Args:
            method: HTTP方法
            url: 请求URL
            params: 查询参数
            data: 请求数据
        
        Returns:
            MD5哈希缓存键
        """
        key_data = f"{method}:{url}"
        if params:
            key_data += f":params:{sorted(params.items())}"
        if data:
            key_data += f":data:{sorted(data.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值
        
        Args:
            key: 缓存键
        
        Returns:
            缓存值，如果不存在或已过期返回 None
        """
        if key not in self._cache:
            return None
        
        value, timestamp = self._cache[key]
        if time.time() - timestamp > self.ttl_seconds:
            del self._cache[key]
            return None
        
        # 移动到末尾（LRU）
        self._cache.move_to_end(key)
        return value
    
    def set(self, key: str, value: Any) -> None:
        """设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
        """
        if len(self._cache) >= self.max_size:
            # 移除最旧的项
            self._cache.popitem(last=False)
        
        self._cache[key] = (value, time.time())
        self._cache.move_to_end(key)
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
    
    def __len__(self) -> int:
        """获取缓存项数量"""
        return len(self._cache)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计
        
        Returns:
            包含缓存统计的字典
        """
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'usage_percent': len(self._cache) / self.max_size * 100,
        }


class CacheStats:
    """缓存统计
    
    跟踪缓存命中和未命中次数。
    """
    
    def __init__(self):
        """初始化缓存统计"""
        self.hits = 0
        self.misses = 0
    
    def hit(self) -> None:
        """记录缓存命中"""
        self.hits += 1
    
    def miss(self) -> None:
        """记录缓存未命中"""
        self.misses += 1
    
    @property
    def hit_rate(self) -> float:
        """计算缓存命中率
        
        Returns:
            命中率（0.0 - 1.0）
        """
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            包含统计信息的字典
        """
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hit_rate,
            'total': self.hits + self.misses,
        }
