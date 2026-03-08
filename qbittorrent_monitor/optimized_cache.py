"""分层缓存系统 - 多级缓存策略"""
import sys
import time
import weakref
from typing import Dict, Optional, Generic, TypeVar, Any
from collections import OrderedDict
import functools

T = TypeVar('T')


class TieredCache(Generic[T]):
    """分层缓存系统
    
    L1: 热缓存 (内存，LRU，最常用)
    L2: 温缓存 (内存，LFU，偶尔用)
    """
    
    def __init__(
        self,
        l1_size: int = 100,      # 热缓存大小
        l2_size: int = 1000,     # 温缓存大小
        max_memory_mb: int = 100  # 最大内存限制
    ):
        self.l1_size = l1_size
        self.l2_size = l2_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        
        # L1: 热缓存 (OrderedDict 实现 LRU)
        self._l1: OrderedDict[str, T] = OrderedDict()
        
        # L2: 温缓存 (频率计数 + 时间戳)
        self._l2: Dict[str, tuple[T, int, float]] = {}  # value, freq, last_access
        
        # 内存使用跟踪
        self._current_memory = 0
        self._memory_estimates: Dict[str, int] = {}
        
        # 统计
        self._l1_hits = 0
        self._l2_hits = 0
        self._misses = 0
    
    def _estimate_size(self, value: T) -> int:
        """估算值占用的内存大小"""
        try:
            return sys.getsizeof(value)
        except:
            return 100  # 默认值
    
    def get(self, key: str) -> Optional[T]:
        """获取缓存值"""
        # L1 查找
        if key in self._l1:
            self._l1.move_to_end(key)
            self._l1_hits += 1
            return self._l1[key]
        
        # L2 查找
        if key in self._l2:
            value, freq, _ = self._l2[key]
            self._l2[key] = (value, freq + 1, time.time())
            self._l2_hits += 1
            
            # 提升到 L1
            self._promote_to_l1(key, value)
            return value
        
        self._misses += 1
        return None
    
    def put(self, key: str, value: T) -> None:
        """添加缓存"""
        # 估算内存
        size = self._estimate_size(value)
        
        # 检查内存限制
        while (self._current_memory + size > self.max_memory_bytes and 
               (self._l1 or self._l2)):
            self._evict_oldest()
        
        # 放入 L1
        if key in self._l1:
            old_size = self._memory_estimates.get(key, 0)
            self._current_memory -= old_size
        
        self._l1[key] = value
        self._l1.move_to_end(key)
        self._memory_estimates[key] = size
        self._current_memory += size
        
        # 如果 L1 满了，降级最旧的到 L2
        while len(self._l1) > self.l1_size:
            self._demote_l1_oldest()
    
    def _promote_to_l1(self, key: str, value: T) -> None:
        """将 L2 中的值提升到 L1"""
        # 从 L2 移除
        if key in self._l2:
            del self._l2[key]
        
        # 放入 L1
        self._l1[key] = value
        self._l1.move_to_end(key)
        
        # 如果 L1 满了，降级最旧的
        while len(self._l1) > self.l1_size:
            self._demote_l1_oldest()
    
    def _demote_l1_oldest(self) -> None:
        """将 L1 中最旧的降级到 L2"""
        if not self._l1:
            return
        
        oldest_key, oldest_value = self._l1.popitem(last=False)
        
        # 如果 L2 满了，清理低频数据
        while len(self._l2) >= self.l2_size:
            self._evict_l2_lfu()
        
        # 放入 L2
        self._l2[oldest_key] = (oldest_value, 1, time.time())
    
    def _evict_l2_lfu(self) -> None:
        """淘汰 L2 中最低频的数据"""
        if not self._l2:
            return
        
        # 找到频率最低的
        min_key = min(self._l2.items(), key=lambda x: (x[1][1], x[1][2]))[0]
        
        # 释放内存
        size = self._memory_estimates.get(min_key, 0)
        self._current_memory -= size
        
        del self._l2[min_key]
        del self._memory_estimates[min_key]
    
    def _evict_oldest(self) -> None:
        """淘汰最旧的数据（L1 和 L2）"""
        if self._l1:
            key, _ = self._l1.popitem(last=False)
        elif self._l2:
            key = min(self._l2.items(), key=lambda x: x[1][2])[0]
            del self._l2[key]
        else:
            return
        
        size = self._memory_estimates.get(key, 0)
        self._current_memory -= size
        del self._memory_estimates[key]
    
    def clear(self) -> None:
        """清空缓存"""
        self._l1.clear()
        self._l2.clear()
        self._memory_estimates.clear()
        self._current_memory = 0
        self._l1_hits = 0
        self._l2_hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_hits = self._l1_hits + self._l2_hits
        total_requests = total_hits + self._misses
        
        return {
            "l1_size": len(self._l1),
            "l2_size": len(self._l2),
            "memory_bytes": self._current_memory,
            "memory_mb": round(self._current_memory / 1024 / 1024, 2),
            "l1_hits": self._l1_hits,
            "l2_hits": self._l2_hits,
            "misses": self._misses,
            "hit_rate": round(total_hits / total_requests, 4) if total_requests > 0 else 0,
            "l1_hit_rate": round(self._l1_hits / total_hits, 4) if total_hits > 0 else 0,
        }


class MemoryConstrainedCache:
    """内存受限缓存 - 自动适应系统内存"""
    
    def __init__(self, max_memory_percent: float = 10.0):
        """
        Args:
            max_memory_percent: 最大使用系统内存百分比
        """
        try:
            import psutil
            total_memory = psutil.virtual_memory().total
            max_memory_bytes = int(total_memory * max_memory_percent / 100)
        except ImportError:
            # 默认 100MB
            max_memory_bytes = 100 * 1024 * 1024
        
        self._cache = TieredCache(
            l1_size=100,
            l2_size=10000,
            max_memory_mb=max_memory_bytes // 1024 // 1024
        )


# ========== 装饰器缓存 ==========

def lru_cache_with_size(maxsize: int = 128, typed: bool = False):
    """带大小限制的 LRU 缓存装饰器"""
    def decorator(func):
        cache = OrderedDict()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 构建缓存键
            key = args + tuple(sorted(kwargs.items())) if kwargs else args
            if typed:
                key += tuple(type(v) for v in args)
            
            key_str = str(key)
            
            # 检查缓存
            if key_str in cache:
                cache.move_to_end(key_str)
                return cache[key_str]
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 添加缓存
            cache[key_str] = result
            cache.move_to_end(key_str)
            
            # 清理旧缓存
            while len(cache) > maxsize:
                cache.popitem(last=False)
            
            return result
        
        def cache_info():
            return {
                'size': len(cache),
                'maxsize': maxsize
            }
        
        def cache_clear():
            cache.clear()
        
        wrapper.cache_info = cache_info
        wrapper.cache_clear = cache_clear
        
        return wrapper
    return decorator


# ========== 全局缓存实例 ==========

# 分类结果缓存
_classification_cache = TieredCache[str](l1_size=100, l2_size=1000, max_memory_mb=50)

# 磁力链接哈希缓存
_magnet_cache = TieredCache[list](l1_size=200, l2_size=2000, max_memory_mb=100)

def get_classification_cache() -> TieredCache[str]:
    """获取分类结果缓存"""
    return _classification_cache

def get_magnet_cache() -> TieredCache[list]:
    """获取磁力链接缓存"""
    return _magnet_cache
