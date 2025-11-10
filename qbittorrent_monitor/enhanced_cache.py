"""
增强的缓存和内存管理模块

提供多级缓存、内存监控、自动清理等功能
"""

import asyncio
import time
import logging
import weakref
import sys
import gc
from typing import Any, Dict, List, Optional, Callable, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict, defaultdict
from pathlib import Path
import psutil

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: datetime
    last_access: datetime
    access_count: int = 0
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def age(self) -> float:
        """计算年龄（秒）"""
        return (datetime.now() - self.created_at).total_seconds()

    def idle_time(self) -> float:
        """计算空闲时间（秒）"""
        return (datetime.now() - self.last_access).total_seconds()

    def is_expired(self, ttl_seconds: float) -> bool:
        """检查是否过期"""
        return self.age() > ttl_seconds

    def is_idle(self, idle_threshold: float) -> bool:
        """检查是否空闲"""
        return self.idle_time() > idle_threshold


class EnhancedLRUCache:
    """
    增强的LRU缓存

    支持TTL、最大大小、内存限制、自动清理等功能
    """

    def __init__(
        self,
        max_size: int = 1000,
        max_memory_mb: int = 100,
        ttl_seconds: float = 3600,
        idle_timeout: float = 1800,
        cleanup_interval: float = 60.0,
        enable_stats: bool = True
    ):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.ttl_seconds = ttl_seconds
        self.idle_timeout = idle_timeout
        self.cleanup_interval = cleanup_interval
        self.enable_stats = enable_stats

        # 存储结构：OrderedDict保持访问顺序
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_closed = False

        # 统计信息
        if enable_stats:
            self._stats = {
                "hits": 0,
                "misses": 0,
                "evictions": 0,
                "expirations": 0,
                "cleanups": 0,
                "total_gets": 0,
                "total_sets": 0,
                "total_deletes": 0,
                "memory_usage_bytes": 0,
                "avg_access_count": 0.0
            }

    async def start(self) -> None:
        """启动缓存"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """停止缓存"""
        self._is_closed = True
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        self._cache.clear()

    def _estimate_size(self, value: Any) -> int:
        """估算值的大小"""
        try:
            # 对于简单类型
            if isinstance(value, (str, bytes)):
                return len(value)
            elif isinstance(value, (int, float, bool, type(None))):
                return 64  # 估算值
            elif isinstance(value, (list, tuple)):
                return sum(self._estimate_size(item) for item in value)
            elif isinstance(value, dict):
                return sum(
                    len(k) + self._estimate_size(v)
                    for k, v in value.items()
                )
            else:
                # 对于复杂对象，使用估算
                return 1024
        except:
            return 256  # 默认估算值

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            if key not in self._cache:
                if self.enable_stats:
                    self._stats["misses"] += 1
                    self._stats["total_gets"] += 1
                return None

            entry = self._cache[key]

            # 检查是否过期
            if entry.is_expired(self.ttl_seconds):
                del self._cache[key]
                if self.enable_stats:
                    self._stats["expirations"] += 1
                    self._stats["total_gets"] += 1
                return None

            # 更新访问信息
            entry.last_access = datetime.now()
            entry.access_count += 1

            # 移动到末尾（LRU）
            self._cache.move_to_end(key)

            if self.enable_stats:
                self._stats["hits"] += 1
                self._stats["total_gets"] += 1

            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """设置缓存值"""
        async with self._lock:
            # 估算大小
            size_bytes = self._estimate_size(value)

            # 如果键已存在，更新
            if key in self._cache:
                old_entry = self._cache[key]
                if self.enable_stats:
                    self._stats["memory_usage_bytes"] -= old_entry.size_bytes

                entry = CacheEntry(
                    key=key,
                    value=value,
                    created_at=datetime.now(),
                    last_access=datetime.now(),
                    size_bytes=size_bytes,
                    metadata=metadata or {}
                )
                self._cache[key] = entry
                self._cache.move_to_end(key)
            else:
                # 创建新条目
                entry = CacheEntry(
                    key=key,
                    value=value,
                    created_at=datetime.now(),
                    last_access=datetime.now(),
                    size_bytes=size_bytes,
                    metadata=metadata or {}
                )
                self._cache[key] = entry

            if self.enable_stats:
                self._stats["memory_usage_bytes"] += size_bytes
                self._stats["total_sets"] += 1

            # 清理过期或多余的条目
            await self._cleanup_internal()

    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        async with self._lock:
            if key not in self._cache:
                return False

            entry = self._cache[key]
            if self.enable_stats:
                self._stats["memory_usage_bytes"] -= entry.size_bytes

            del self._cache[key]
            if self.enable_stats:
                self._stats["total_deletes"] += 1

            return True

    async def clear(self) -> None:
        """清空缓存"""
        async with self._lock:
            if self.enable_stats:
                self._stats["memory_usage_bytes"] = 0

            self._cache.clear()

    async def _cleanup_internal(self) -> None:
        """内部清理逻辑"""
        cleaned = 0

        # 1. 清理过期的条目
        expired_keys = []
        for key, entry in self._cache.items():
            if entry.is_expired(self.ttl_seconds):
                expired_keys.append(key)

        for key in expired_keys:
            if self.enable_stats:
                self._stats["memory_usage_bytes"] -= self._cache[key].size_bytes
            del self._cache[key]
            cleaned += 1

        # 2. 清理空闲时间过长的条目
        if cleaned == 0 and self.idle_timeout > 0:
            idle_keys = []
            for key, entry in self._cache.items():
                if entry.is_idle(self.idle_timeout):
                    idle_keys.append(key)

            for key in idle_keys:
                if self.enable_stats:
                    self._stats["memory_usage_bytes"] -= self._cache[key].size_bytes
                del self._cache[key]
                cleaned += 1

        # 3. 如果仍然超过限制，清理最少使用的条目
        while len(self._cache) > self.max_size:
            # 删除最久未使用的条目
            oldest_key = next(iter(self._cache))
            if self.enable_stats:
                self._stats["memory_usage_bytes"] -= self._cache[oldest_key].size_bytes
                self._stats["evictions"] += 1
            del self._cache[oldest_key]
            cleaned += 1

        # 4. 如果仍然超过内存限制，清理最大的条目
        while (self.enable_stats and
               self._stats["memory_usage_bytes"] > self.max_memory_bytes and
               self._cache):
            # 找到最大的条目
            largest_key = max(
                self._cache.keys(),
                key=lambda k: self._cache[k].size_bytes
            )
            if self.enable_stats:
                self._stats["memory_usage_bytes"] -= self._cache[largest_key].size_bytes
                self._stats["evictions"] += 1
            del self._cache[largest_key]
            cleaned += 1

        if cleaned > 0 and self.enable_stats:
            self._stats["cleanups"] += cleaned

    async def _cleanup_loop(self) -> None:
        """清理循环"""
        while not self._is_closed:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_internal()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"缓存清理循环错误: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.enable_stats:
            return {}

        total_requests = self._stats["total_gets"]
        hit_rate = (
            self._stats["hits"] / total_requests
            if total_requests > 0 else 0.0
        )

        avg_access = (
            sum(entry.access_count for entry in self._cache.values()) / len(self._cache)
            if self._cache else 0.0
        )

        return {
            "hit_rate": hit_rate,
            "hit_count": self._stats["hits"],
            "miss_count": self._stats["misses"],
            "eviction_count": self._stats["evictions"],
            "expiration_count": self._stats["expirations"],
            "cleanup_count": self._stats["cleanups"],
            "total_requests": total_requests,
            "total_sets": self._stats["total_sets"],
            "total_deletes": self._stats["total_deletes"],
            "current_size": len(self._cache),
            "max_size": self.max_size,
            "memory_usage_mb": self._stats["memory_usage_bytes"] / 1024 / 1024,
            "max_memory_mb": self.max_memory_bytes / 1024 / 1024,
            "avg_access_count": avg_access,
            "oldest_entry_age": min((e.age() for e in self._cache.values()), default=0),
            "newest_entry_age": max((e.age() for e in self._cache.values()), default=0)
        }


class MemoryMonitor:
    """
    内存监控器

    监控内存使用情况，提供预警和自动清理
    """

    def __init__(
        self,
        warning_threshold: float = 0.8,  # 警告阈值（80%）
        critical_threshold: float = 0.9,  # 严重阈值（90%）
        check_interval: float = 10.0,  # 检查间隔（秒）
        auto_cleanup: bool = True
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.check_interval = check_interval
        self.auto_cleanup = auto_cleanup

        self._monitor_task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable] = []
        self._is_running = False
        self._stats = {
            "check_count": 0,
            "warning_count": 0,
            "critical_count": 0,
            "cleanup_count": 0,
            "peak_memory_mb": 0.0
        }

    def add_callback(self, callback: Callable) -> None:
        """添加内存警告回调"""
        self._callbacks.append(callback)

    async def start(self) -> None:
        """启动内存监控"""
        if self._is_running:
            return

        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        """停止内存监控"""
        self._is_running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def get_memory_info(self) -> Dict[str, Any]:
        """获取内存信息"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # 获取系统内存信息
            system_memory = psutil.virtual_memory()

            return {
                "process_rss_mb": memory_info.rss / 1024 / 1024,
                "process_vms_mb": memory_info.vms / 1024 / 1024,
                "process_percent": memory_percent,
                "system_total_mb": system_memory.total / 1024 / 1024,
                "system_available_mb": system_memory.available / 1024 / 1024,
                "system_percent": system_memory.percent,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取内存信息失败: {str(e)}")
            return {}

    async def check_memory(self) -> Dict[str, Any]:
        """检查内存使用情况"""
        memory_info = await self.get_memory_info()
        if not memory_info:
            return {}

        process_percent = memory_info.get("process_percent", 0)
        self._stats["check_count"] += 1

        # 更新峰值
        if memory_info.get("process_rss_mb", 0) > self._stats["peak_memory_mb"]:
            self._stats["peak_memory_mb"] = memory_info["process_rss_mb"]

        # 检查阈值
        status = "normal"
        if process_percent >= self.critical_threshold * 100:
            status = "critical"
            self._stats["critical_count"] += 1
        elif process_percent >= self.warning_threshold * 100:
            status = "warning"
            self._stats["warning_count"] += 1

        result = {
            "status": status,
            "usage_percent": process_percent,
            "info": memory_info
        }

        # 触发回调
        if status != "normal":
            for callback in self._callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(status, memory_info)
                    else:
                        callback(status, memory_info)
                except Exception as e:
                    logger.error(f"内存警告回调执行失败: {str(e)}")

        return result

    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._is_running:
            try:
                result = await self.check_memory()

                if result.get("status") == "critical" and self.auto_cleanup:
                    # 执行内存清理
                    self._stats["cleanup_count"] += 1
                    await self._trigger_cleanup()

                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"内存监控循环错误: {str(e)}")
                await asyncio.sleep(self.check_interval)

    async def _trigger_cleanup(self) -> None:
        """触发内存清理"""
        logger.warning("执行内存清理...")

        try:
            # 强制垃圾回收
            collected = gc.collect()
            logger.info(f"垃圾回收完成，回收对象: {collected}")
        except Exception as e:
            logger.error(f"垃圾回收失败: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        """获取监控统计"""
        return self._stats.copy()


class MultiLevelCache:
    """
    多级缓存

    L1: 内存缓存（快速）
    L2: 文件缓存（持久）
    """

    def __init__(
        self,
        l1_size: int = 1000,
        l1_ttl: float = 3600,
        l2_path: Optional[str] = None,
        l2_ttl: float = 86400  # 24小时
    ):
        self.l1_cache = EnhancedLRUCache(l1_size, ttl_seconds=l1_ttl)
        self.l2_path = Path(l2_path) if l2_path else None
        self.l2_ttl = l2_ttl

        if self.l2_path:
            self.l2_path.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        """启动缓存"""
        await self.l1_cache.start()

    async def stop(self) -> None:
        """停止缓存"""
        await self.l1_cache.stop()

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        # 优先从L1获取
        value = await self.l1_cache.get(key)
        if value is not None:
            return value

        # 从L2获取
        if self.l2_path:
            try:
                # 读取文件
                file_path = self.l2_path / f"{hash(key)}.cache"
                if file_path.exists():
                    # 检查是否过期
                    file_age = time.time() - file_path.stat().st_mtime
                    if file_age <= self.l2_ttl:
                        import pickle
                        with open(file_path, 'rb') as f:
                            value = pickle.load(f)

                        # 放入L1缓存
                        await self.l1_cache.set(key, value)
                        return value
                    else:
                        # 删除过期文件
                        file_path.unlink()
            except Exception as e:
                logger.error(f"读取L2缓存失败: {str(e)}")

        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None
    ) -> None:
        """设置缓存值"""
        # 设置到L1
        await self.l1_cache.set(key, value, ttl)

        # 设置到L2
        if self.l2_path:
            try:
                import pickle
                file_path = self.l2_path / f"{hash(key)}.cache"
                with open(file_path, 'wb') as f:
                    pickle.dump(value, f)
            except Exception as e:
                logger.error(f"写入L2缓存失败: {str(e)}")

    async def delete(self, key: str) -> None:
        """删除缓存值"""
        await self.l1_cache.delete(key)

        if self.l2_path:
            try:
                file_path = self.l2_path / f"{hash(key)}.cache"
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.error(f"删除L2缓存失败: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "l1": self.l1_cache.get_stats(),
            "l2_enabled": self.l2_path is not None
        }

        if self.l2_path:
            try:
                l2_files = list(self.l2_path.glob("*.cache"))
                stats["l2"] = {
                    "file_count": len(l2_files),
                    "total_size_mb": sum(f.stat().st_size for f in l2_files) / 1024 / 1024
                }
            except Exception as e:
                logger.error(f"获取L2统计失败: {str(e)}")
                stats["l2"] = {"error": str(e)}

        return stats


# 全局缓存实例
_global_cache: Optional[EnhancedLRUCache] = None
_global_memory_monitor: Optional[MemoryMonitor] = None


def get_global_cache() -> EnhancedLRUCache:
    """获取全局缓存"""
    global _global_cache
    if _global_cache is None:
        _global_cache = EnhancedLRUCache(
            max_size=1000,
            max_memory_mb=50,
            ttl_seconds=3600
        )
    return _global_cache


def get_global_memory_monitor() -> MemoryMonitor:
    """获取全局内存监控器"""
    global _global_memory_monitor
    if _global_memory_monitor is None:
        _global_memory_monitor = MemoryMonitor(
            warning_threshold=0.8,
            critical_threshold=0.9,
            check_interval=10.0
        )
    return _global_memory_monitor
