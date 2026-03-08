"""TTL缓存优化模块

提供带生存时间(TTL)的缓存、内存监控和缓存预热机制。

性能对比:
    - 无缓存: 每次操作需要完整计算/查询
    - 普通缓存: 无限期保存，可能导致内存泄漏
    - TTL缓存: 自动过期清理，平衡性能和内存使用

特性:
    - 支持每个键独立TTL
    - 后台自动清理过期条目
    - 内存使用监控和限制
    - 缓存预热机制
"""

import asyncio
import logging
import time
import tracemalloc
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, Optional, TypeVar, Callable, Tuple
from typing import overload

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """缓存条目"""
    value: T
    expires_at: float  # 过期时间戳
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    size_bytes: int = 0  # 估算的内存大小


@dataclass
class CacheStats:
    """缓存统计信息"""
    size: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    total_memory_bytes: int = 0
    hit_rate: float = 0.0
    avg_entry_size_bytes: float = 0.0
    oldest_entry_age_seconds: float = 0.0


class MemoryMonitor:
    """内存监控器
    
    监控缓存的内存使用情况，当超过阈值时触发清理。
    
    Example:
        >>> monitor = MemoryMonitor(max_memory_mb=100)
        >>> monitor.start()
        >>> 
        >>> # 检查内存
        >>> is_ok = monitor.check_memory()
        >>> usage = monitor.get_memory_usage()
        >>> print(f"当前使用: {usage['current_mb']:.2f} MB")
    """
    
    def __init__(
        self,
        max_memory_mb: float = 100.0,
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.95,
        check_interval: float = 10.0,
    ):
        """初始化内存监控器
        
        Args:
            max_memory_mb: 最大内存使用（MB）
            warning_threshold: 警告阈值（相对于最大值的比例）
            critical_threshold: 临界阈值
            check_interval: 检查间隔（秒）
        """
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.check_interval = check_interval
        
        self._current_memory_bytes = 0
        self._peak_memory_bytes = 0
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[str, float], None]] = []
        
        # 启动 tracemalloc
        if not tracemalloc.is_tracing():
            tracemalloc.start()
    
    def add_callback(self, callback: Callable[[str, float], None]) -> None:
        """添加内存告警回调
        
        Args:
            callback: 回调函数，参数为(level, usage_ratio)
        """
        self._callbacks.append(callback)
    
    def start(self) -> None:
        """启动内存监控"""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(),
            name="memory_monitor"
        )
        logger.debug(f"内存监控已启动 (max={self.max_memory_bytes / 1024 / 1024:.1f}MB)")
    
    def stop(self) -> None:
        """停止内存监控"""
        if not self._running:
            return
        
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
    
    def check_memory(self) -> Tuple[bool, str]:
        """检查内存使用情况
        
        Returns:
            (是否安全, 状态级别)
        """
        self._update_memory_stats()
        ratio = self._current_memory_bytes / self.max_memory_bytes
        
        if ratio >= self.critical_threshold:
            return False, "critical"
        elif ratio >= self.warning_threshold:
            return True, "warning"
        else:
            return True, "normal"
    
    def get_memory_usage(self) -> Dict[str, float]:
        """获取内存使用详情
        
        Returns:
            内存使用统计字典
        """
        self._update_memory_stats()
        
        return {
            "current_mb": self._current_memory_bytes / 1024 / 1024,
            "peak_mb": self._peak_memory_bytes / 1024 / 1024,
            "max_mb": self.max_memory_bytes / 1024 / 1024,
            "usage_ratio": self._current_memory_bytes / self.max_memory_bytes,
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
        }
    
    def _update_memory_stats(self) -> None:
        """更新内存统计"""
        current, peak = tracemalloc.get_traced_memory()
        self._current_memory_bytes = current
        self._peak_memory_bytes = peak
    
    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)
                
                is_safe, level = self.check_memory()
                ratio = self._current_memory_bytes / self.max_memory_bytes
                
                if level != "normal":
                    logger.warning(
                        f"内存使用{level}: {ratio * 100:.1f}% "
                        f"({self._current_memory_bytes / 1024 / 1024:.1f} MB)"
                    )
                    
                    # 触发回调
                    for callback in self._callbacks:
                        try:
                            callback(level, ratio)
                        except Exception as e:
                            logger.error(f"内存回调错误: {e}")
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"内存监控错误: {e}")


class TTLCache(Generic[T]):
    """TTL缓存实现
    
    带生存时间的缓存，自动清理过期条目，支持内存限制。
    
    特性:
        - 每个键可设置独立TTL
        - 惰性过期清理（访问时检查）
        - 后台主动清理
        - LRU淘汰策略
        - 内存使用限制
    
    Attributes:
        max_size: 最大条目数
        default_ttl: 默认TTL（秒）
        max_memory_bytes: 最大内存使用
    
    Example:
        >>> cache = TTLCache[str](max_size=1000, default_ttl=3600)
        >>> cache.start()
        >>> 
        >>> # 设置值（使用默认TTL）
        >>> cache.set("key1", "value1")
        >>> 
        >>> # 设置值（自定义TTL 5分钟）
        >>> cache.set("key2", "value2", ttl=300)
        >>> 
        >>> # 获取值
        >>> value = cache.get("key1")
        >>> 
        >>> # 获取统计
        >>> stats = cache.get_stats()
        >>> print(f"命中率: {stats.hit_rate:.2%}")
        >>> 
        >>> cache.stop()
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 3600,
        max_memory_mb: float = 50.0,
        cleanup_interval: float = 60.0,
        eviction_policy: str = "lru",  # lru, lfu, fifo
    ):
        """初始化TTL缓存
        
        Args:
            max_size: 最大条目数
            default_ttl: 默认TTL（秒）
            max_memory_mb: 最大内存使用（MB）
            cleanup_interval: 清理间隔（秒）
            eviction_policy: 淘汰策略 (lru, lfu, fifo)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cleanup_interval = cleanup_interval
        self.eviction_policy = eviction_policy
        
        # 使用 OrderedDict 实现 LRU
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        
        # 统计
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0
        
        # 运行状态
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # 内存监控
        self._memory_monitor = MemoryMonitor(
            max_memory_mb=max_memory_mb,
            warning_threshold=0.8,
            critical_threshold=0.95,
        )
        self._memory_monitor.add_callback(self._on_memory_alert)
    
    def start(self) -> None:
        """启动缓存"""
        if self._running:
            return
        
        self._running = True
        self._memory_monitor.start()
        
        # 启动后台清理任务
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(),
            name="ttl_cache_cleanup"
        )
        
        logger.debug(
            f"TTL缓存已启动 (max_size={self.max_size}, "
            f"default_ttl={self.default_ttl}s)"
        )
    
    def stop(self) -> None:
        """停止缓存"""
        if not self._running:
            return
        
        self._running = False
        self._memory_monitor.stop()
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        logger.debug("TTL缓存已停止")
    
    @overload
    def get(self, key: str) -> Optional[T]: ...
    
    @overload
    def get(self, key: str, default: T) -> T: ...
    
    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """获取缓存值
        
        Args:
            key: 缓存键
            default: 默认值
            
        Returns:
            缓存值或默认值
        """
        entry = self._cache.get(key)
        
        if entry is None:
            self._misses += 1
            return default
        
        # 检查是否过期
        if time.time() > entry.expires_at:
            # 惰性删除
            del self._cache[key]
            self._expirations += 1
            self._misses += 1
            return default
        
        # 更新访问信息（LRU）
        entry.access_count += 1
        entry.last_access = time.time()
        
        if self.eviction_policy == "lru":
            # 移动到末尾（最近使用）
            self._cache.move_to_end(key)
        
        self._hits += 1
        return entry.value
    
    def set(
        self,
        key: str,
        value: T,
        ttl: Optional[float] = None,
        size_bytes: int = 0,
    ) -> None:
        """设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间（秒），None使用默认值
            size_bytes: 值的大小（字节），用于内存限制
        """
        ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + ttl
        
        # 估算大小
        if size_bytes == 0:
            size_bytes = self._estimate_size(value)
        
        # 检查是否需要清理
        if len(self._cache) >= self.max_size:
            self._evict_entries(1)
        
        # 检查内存限制
        current_memory = sum(e.size_bytes for e in self._cache.values())
        while (current_memory + size_bytes > self.max_memory_bytes and 
               len(self._cache) > 0):
            self._evict_entries(1)
            current_memory = sum(e.size_bytes for e in self._cache.values())
        
        entry = CacheEntry(
            value=value,
            expires_at=expires_at,
            size_bytes=size_bytes,
        )
        
        # 如果键已存在，更新
        if key in self._cache:
            self._cache[key] = entry
            self._cache.move_to_end(key)
        else:
            self._cache[key] = entry
    
    def delete(self, key: str) -> bool:
        """删除缓存键
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功删除
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0
    
    def keys(self) -> List[str]:
        """获取所有有效键"""
        now = time.time()
        return [
            k for k, e in self._cache.items()
            if now <= e.expires_at
        ]
    
    def get_stats(self) -> CacheStats:
        """获取缓存统计
        
        Returns:
            缓存统计信息
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        
        total_memory = sum(e.size_bytes for e in self._cache.values())
        avg_size = total_memory / len(self._cache) if self._cache else 0.0
        
        now = time.time()
        oldest_age = (
            now - min(e.last_access for e in self._cache.values())
            if self._cache else 0.0
        )
        
        return CacheStats(
            size=len(self._cache),
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            expirations=self._expirations,
            total_memory_bytes=total_memory,
            hit_rate=hit_rate,
            avg_entry_size_bytes=avg_size,
            oldest_entry_age_seconds=oldest_age,
        )
    
    def _estimate_size(self, value: Any) -> int:
        """估算值的大小（字节）"""
        import sys
        try:
            return sys.getsizeof(value)
        except Exception:
            # 无法估算时返回默认值
            return 100
    
    def _evict_entries(self, count: int) -> None:
        """淘汰指定数量的条目"""
        if not self._cache:
            return
        
        for _ in range(min(count, len(self._cache))):
            if self.eviction_policy == "lru":
                # 淘汰最久未使用的
                key = next(iter(self._cache))
            elif self.eviction_policy == "lfu":
                # 淘汰使用次数最少的
                key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].access_count
                )
            else:  # fifo
                # 淘汰最早加入的
                key = next(iter(self._cache))
            
            del self._cache[key]
            self._evictions += 1
    
    def _on_memory_alert(self, level: str, ratio: float) -> None:
        """内存告警回调"""
        logger.warning(f"缓存收到内存告警: {level} ({ratio * 100:.1f}%)")
        
        # 紧急清理
        if level == "critical":
            # 清理50%的条目
            target_size = len(self._cache) // 2
            self._evict_entries(len(self._cache) - target_size)
        elif level == "warning":
            # 清理20%的条目
            target_size = int(len(self._cache) * 0.8)
            self._evict_entries(len(self._cache) - target_size)
    
    async def _cleanup_loop(self) -> None:
        """后台清理循环"""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"缓存清理错误: {e}")
    
    async def _cleanup_expired(self) -> int:
        """清理过期条目
        
        Returns:
            清理的条目数
        """
        now = time.time()
        expired_keys = [
            k for k, e in self._cache.items()
            if now > e.expires_at
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        self._expirations += len(expired_keys)
        
        if expired_keys:
            logger.debug(f"清理了 {len(expired_keys)} 个过期缓存条目")
        
        return len(expired_keys)


class CacheWarmer:
    """缓存预热器
    
    在启动时预加载热点数据到缓存，减少冷启动延迟。
    
    Example:
        >>> warmer = CacheWarmer(cache)
        >>> 
        >>> # 定义预热数据源
        >>> async def load_hot_data():
        ...     return await db.get_recent_torrents(limit=100)
        >>> 
        >>> # 添加预热任务
        >>> warmer.add_source("recent_torrents", load_hot_data, ttl=1800)
        >>> 
        >>> # 执行预热
        >>> stats = await warmer.warmup()
        >>> print(f"预热完成: {stats['loaded']} 条记录")
    """
    
    def __init__(self, cache: TTLCache[Any]):
        """初始化缓存预热器
        
        Args:
            cache: TTL缓存实例
        """
        self.cache = cache
        self._sources: Dict[str, Dict[str, Any]] = {}
    
    def add_source(
        self,
        name: str,
        loader: Callable[[], Any],
        key_prefix: str = "",
        ttl: Optional[float] = None,
    ) -> None:
        """添加预热数据源
        
        Args:
            name: 数据源名称
            loader: 数据加载函数，返回可迭代的数据
            key_prefix: 缓存键前缀
            ttl: 缓存TTL
        """
        self._sources[name] = {
            "loader": loader,
            "key_prefix": key_prefix,
            "ttl": ttl,
        }
    
    def remove_source(self, name: str) -> bool:
        """移除预热数据源
        
        Args:
            name: 数据源名称
            
        Returns:
            是否成功移除
        """
        if name in self._sources:
            del self._sources[name]
            return True
        return False
    
    async def warmup(
        self,
        sources: Optional[List[str]] = None,
        max_concurrent: int = 3,
    ) -> Dict[str, Any]:
        """执行缓存预热
        
        Args:
            sources: 要预热的数据源列表，None表示所有
            max_concurrent: 最大并发数
            
        Returns:
            预热统计字典
        """
        source_names = sources or list(self._sources.keys())
        semaphore = asyncio.Semaphore(max_concurrent)
        
        total_loaded = 0
        source_stats: Dict[str, Dict[str, Any]] = {}
        start_time = time.time()
        
        async def warmup_source(name: str) -> Tuple[str, int, Optional[str]]:
            async with semaphore:
                source = self._sources.get(name)
                if not source:
                    return name, 0, f"数据源 {name} 不存在"
                
                try:
                    loader = source["loader"]
                    
                    # 支持同步和异步loader
                    if asyncio.iscoroutinefunction(loader):
                        data = await loader()
                    else:
                        data = loader()
                    
                    # 加载到缓存
                    loaded = 0
                    if isinstance(data, dict):
                        for key, value in data.items():
                            cache_key = f"{source['key_prefix']}{key}"
                            self.cache.set(
                                cache_key,
                                value,
                                ttl=source.get("ttl")
                            )
                            loaded += 1
                    elif isinstance(data, (list, tuple)):
                        for i, value in enumerate(data):
                            cache_key = f"{source['key_prefix']}{i}"
                            self.cache.set(
                                cache_key,
                                value,
                                ttl=source.get("ttl")
                            )
                            loaded += 1
                    else:
                        # 单个值
                        self.cache.set(
                            source["key_prefix"] or name,
                            data,
                            ttl=source.get("ttl")
                        )
                        loaded = 1
                    
                    return name, loaded, None
                    
                except Exception as e:
                    logger.error(f"预热数据源 {name} 失败: {e}")
                    return name, 0, str(e)
        
        # 并发执行所有预热任务
        tasks = [warmup_source(name) for name in source_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"预热任务异常: {result}")
                continue
            
            name, loaded, error = result
            total_loaded += loaded
            source_stats[name] = {
                "loaded": loaded,
                "error": error,
            }
        
        elapsed = time.time() - start_time
        
        return {
            "total_loaded": total_loaded,
            "sources": source_stats,
            "elapsed_seconds": elapsed,
            "sources_per_second": total_loaded / elapsed if elapsed > 0 else 0,
        }
    
    async def warmup_background(
        self,
        sources: Optional[List[str]] = None,
        delay: float = 0.0,
    ) -> asyncio.Task:
        """后台执行缓存预热
        
        Args:
            sources: 要预热的数据源列表
            delay: 延迟执行时间（秒）
            
        Returns:
            预热任务
        """
        async def _delayed_warmup():
            if delay > 0:
                await asyncio.sleep(delay)
            return await self.warmup(sources)
        
        return asyncio.create_task(_delayed_warmup(), name="cache_warmup")
