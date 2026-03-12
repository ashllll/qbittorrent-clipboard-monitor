"""
资源监控模块 - 系统资源使用监控

提供内存、CPU等资源使用监控，防止资源耗尽攻击。
"""

import os
import sys
import time
import asyncio
import logging
import threading
from typing import Optional, Dict, Any, Callable, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

from .exceptions_unified import QBittorrentMonitorError


logger = logging.getLogger(__name__)


class ResourceLimitError(QBittorrentMonitorError):
    """资源限制错误"""
    pass


class ResourceType(Enum):
    """资源类型"""
    MEMORY = "memory"
    CPU = "cpu"
    DISK = "disk"
    THREADS = "threads"
    HANDLES = "handles"


@dataclass
class ResourceThresholds:
    """资源阈值配置"""
    # 内存限制（MB）
    max_memory_mb: float = 512.0
    memory_warning_mb: float = 400.0
    
    # CPU限制（百分比）
    max_cpu_percent: float = 80.0
    cpu_warning_percent: float = 60.0
    
    # 磁盘限制（MB）
    max_disk_mb: float = 1024.0
    disk_warning_mb: float = 800.0
    
    # 线程限制
    max_threads: int = 100
    thread_warning: int = 80
    
    # 检查间隔（秒）
    check_interval: float = 5.0


@dataclass
class ResourceSnapshot:
    """资源使用快照"""
    timestamp: float
    memory_mb: float
    cpu_percent: float
    disk_mb: float
    thread_count: int
    handle_count: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'memory_mb': round(self.memory_mb, 2),
            'cpu_percent': round(self.cpu_percent, 2),
            'disk_mb': round(self.disk_mb, 2),
            'thread_count': self.thread_count,
            'handle_count': self.handle_count,
        }


@dataclass
class ResourceStats:
    """资源使用统计"""
    snapshots: deque = field(default_factory=lambda: deque(maxlen=100))
    peak_memory_mb: float = 0.0
    peak_cpu_percent: float = 0.0
    average_memory_mb: float = 0.0
    average_cpu_percent: float = 0.0
    violation_count: int = 0
    warning_count: int = 0
    
    def add_snapshot(self, snapshot: ResourceSnapshot) -> None:
        """添加快照"""
        self.snapshots.append(snapshot)
        
        # 更新峰值
        self.peak_memory_mb = max(self.peak_memory_mb, snapshot.memory_mb)
        self.peak_cpu_percent = max(self.peak_cpu_percent, snapshot.cpu_percent)
        
        # 计算平均值
        if self.snapshots:
            self.average_memory_mb = sum(s.memory_mb for s in self.snapshots) / len(self.snapshots)
            self.average_cpu_percent = sum(s.cpu_percent for s in self.snapshots) / len(self.snapshots)
    
    def record_violation(self) -> None:
        """记录违规"""
        self.violation_count += 1
    
    def record_warning(self) -> None:
        """记录警告"""
        self.warning_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'peak_memory_mb': round(self.peak_memory_mb, 2),
            'peak_cpu_percent': round(self.peak_cpu_percent, 2),
            'average_memory_mb': round(self.average_memory_mb, 2),
            'average_cpu_percent': round(self.average_cpu_percent, 2),
            'violation_count': self.violation_count,
            'warning_count': self.warning_count,
            'snapshot_count': len(self.snapshots),
        }


class ResourceMonitor:
    """
    资源监控器
    
    监控系统资源使用情况，防止资源耗尽。
    """
    
    def __init__(self, thresholds: Optional[ResourceThresholds] = None):
        self.thresholds = thresholds or ResourceThresholds()
        self.stats = ResourceStats()
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[ResourceType, float, str], None]] = []
        self._lock = asyncio.Lock()
        self._process_id = os.getpid()
        self._last_cpu_times: Optional[Tuple[float, float]] = None
        self._last_cpu_check: float = 0.0
        
        # 尝试导入psutil
        self._psutil_available = False
        try:
            import psutil
            self._psutil = psutil
            self._psutil_available = True
            self._process = psutil.Process(self._process_id)
        except ImportError:
            self._psutil = None
            self._process = None
            logger.warning("psutil未安装，资源监控功能受限")
    
    def _get_memory_usage(self) -> float:
        """获取内存使用（MB）"""
        if self._psutil_available and self._process:
            try:
                return self._process.memory_info().rss / (1024 * 1024)
            except Exception:
                pass
        
        # 回退方案
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            return usage.ru_maxrss / 1024  # KB to MB
        except Exception:
            return 0.0
    
    def _get_cpu_percent(self) -> float:
        """获取CPU使用率"""
        if self._psutil_available and self._process:
            try:
                return self._process.cpu_percent(interval=0.1)
            except Exception:
                pass
        
        # 回退方案（粗略估计）
        try:
            import resource
            import time
            
            usage = resource.getrusage(resource.RUSAGE_SELF)
            current_time = time.time()
            
            if self._last_cpu_times is not None:
                last_utime, last_stime = self._last_cpu_times
                time_delta = current_time - self._last_cpu_check
                
                if time_delta > 0:
                    # 计算CPU时间差（秒）
                    user_time = usage.ru_utime - last_utime
                    system_time = usage.ru_stime - last_stime
                    total_time = user_time + system_time
                    
                    # 计算百分比（假设单核）
                    cpu_percent = (total_time / time_delta) * 100
                    return min(100.0, max(0.0, cpu_percent))
            
            self._last_cpu_times = (usage.ru_utime, usage.ru_stime)
            self._last_cpu_check = current_time
            return 0.0
        except Exception:
            return 0.0
    
    def _get_disk_usage(self) -> float:
        """获取磁盘使用（MB）"""
        # 简化的磁盘使用估算
        # 实际应用中可以监控特定目录的大小
        return 0.0
    
    def _get_thread_count(self) -> int:
        """获取线程数"""
        if self._psutil_available and self._process:
            try:
                return self._process.num_threads()
            except Exception:
                pass
        
        return threading.active_count()
    
    async def _check_resources(self) -> None:
        """检查资源使用情况"""
        try:
            # 获取资源使用
            memory_mb = self._get_memory_usage()
            cpu_percent = self._get_cpu_percent()
            disk_mb = self._get_disk_usage()
            thread_count = self._get_thread_count()
            
            snapshot = ResourceSnapshot(
                timestamp=time.time(),
                memory_mb=memory_mb,
                cpu_percent=cpu_percent,
                disk_mb=disk_mb,
                thread_count=thread_count
            )
            
            async with self._lock:
                self.stats.add_snapshot(snapshot)
            
            # 检查阈值
            await self._check_thresholds(snapshot)
            
        except Exception as e:
            logger.warning(f"资源检查失败: {e}")
    
    async def _check_thresholds(self, snapshot: ResourceSnapshot) -> None:
        """检查是否超过阈值"""
        # 内存检查
        if snapshot.memory_mb > self.thresholds.max_memory_mb:
            self.stats.record_violation()
            await self._on_violation(ResourceType.MEMORY, snapshot.memory_mb, 
                                     f"内存使用超过限制 ({snapshot.memory_mb:.1f}MB > {self.thresholds.max_memory_mb:.1f}MB)")
        elif snapshot.memory_mb > self.thresholds.memory_warning_mb:
            self.stats.record_warning()
            await self._on_warning(ResourceType.MEMORY, snapshot.memory_mb,
                                   f"内存使用接近限制 ({snapshot.memory_mb:.1f}MB > {self.thresholds.memory_warning_mb:.1f}MB)")
        
        # CPU检查
        if snapshot.cpu_percent > self.thresholds.max_cpu_percent:
            self.stats.record_violation()
            await self._on_violation(ResourceType.CPU, snapshot.cpu_percent,
                                     f"CPU使用超过限制 ({snapshot.cpu_percent:.1f}% > {self.thresholds.max_cpu_percent:.1f}%)")
        elif snapshot.cpu_percent > self.thresholds.cpu_warning_percent:
            self.stats.record_warning()
            await self._on_warning(ResourceType.CPU, snapshot.cpu_percent,
                                   f"CPU使用接近限制 ({snapshot.cpu_percent:.1f}% > {self.thresholds.cpu_warning_percent:.1f}%)")
        
        # 线程检查
        if snapshot.thread_count > self.thresholds.max_threads:
            self.stats.record_violation()
            await self._on_violation(ResourceType.THREADS, snapshot.thread_count,
                                     f"线程数超过限制 ({snapshot.thread_count} > {self.thresholds.max_threads})")
        elif snapshot.thread_count > self.thresholds.thread_warning:
            self.stats.record_warning()
            await self._on_warning(ResourceType.THREADS, snapshot.thread_count,
                                   f"线程数接近限制 ({snapshot.thread_count} > {self.thresholds.thread_warning})")
    
    async def _on_violation(self, resource_type: ResourceType, value: float, message: str) -> None:
        """资源违规处理"""
        logger.error(f"[RESOURCE VIOLATION] {message}")
        
        # 调用回调
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(resource_type, value, message)
                else:
                    callback(resource_type, value, message)
            except Exception as e:
                logger.error(f"资源违规回调失败: {e}")
    
    async def _on_warning(self, resource_type: ResourceType, value: float, message: str) -> None:
        """资源警告处理"""
        logger.warning(f"[RESOURCE WARNING] {message}")
    
    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                await self._check_resources()
                await asyncio.sleep(self.thresholds.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(1.0)
    
    def start(self) -> None:
        """启动资源监控"""
        if self._running:
            return
        
        self._running = True
        try:
            loop = asyncio.get_event_loop()
            self._monitor_task = loop.create_task(self._monitor_loop())
        except RuntimeError:
            # 没有运行的事件循环
            pass
        
        logger.info("资源监控已启动")
    
    async def start_async(self) -> None:
        """异步启动资源监控"""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("资源监控已启动")
    
    def stop(self) -> None:
        """停止资源监控"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        logger.info("资源监控已停止")
    
    async def stop_async(self) -> None:
        """异步停止资源监控"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("资源监控已停止")
    
    def add_violation_callback(self, callback: Callable[[ResourceType, float, str], None]) -> None:
        """添加违规回调"""
        self._callbacks.append(callback)
    
    def remove_violation_callback(self, callback: Callable[[ResourceType, float, str], None]) -> bool:
        """移除违规回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            return True
        return False
    
    async def get_current_usage(self) -> ResourceSnapshot:
        """获取当前资源使用"""
        memory_mb = self._get_memory_usage()
        cpu_percent = self._get_cpu_percent()
        disk_mb = self._get_disk_usage()
        thread_count = self._get_thread_count()
        
        return ResourceSnapshot(
            timestamp=time.time(),
            memory_mb=memory_mb,
            cpu_percent=cpu_percent,
            disk_mb=disk_mb,
            thread_count=thread_count
        )
    
    async def get_stats(self) -> ResourceStats:
        """获取统计信息"""
        async with self._lock:
            # 返回副本
            return ResourceStats(
                snapshots=deque(self.stats.snapshots),
                peak_memory_mb=self.stats.peak_memory_mb,
                peak_cpu_percent=self.stats.peak_cpu_percent,
                average_memory_mb=self.stats.average_memory_mb,
                average_cpu_percent=self.stats.average_cpu_percent,
                violation_count=self.stats.violation_count,
                warning_count=self.stats.warning_count,
            )
    
    async def check_limits(self) -> Tuple[bool, Optional[str]]:
        """
        检查是否超出限制
        
        Returns:
            Tuple[bool, Optional[str]]: (是否超出, 错误信息)
        """
        snapshot = await self.get_current_usage()
        
        if snapshot.memory_mb > self.thresholds.max_memory_mb:
            return False, f"内存使用超过限制 ({snapshot.memory_mb:.1f}MB)"
        
        if snapshot.cpu_percent > self.thresholds.max_cpu_percent:
            return False, f"CPU使用超过限制 ({snapshot.cpu_percent:.1f}%)"
        
        if snapshot.thread_count > self.thresholds.max_threads:
            return False, f"线程数超过限制 ({snapshot.thread_count})"
        
        return True, None
    
    async def require_resources(
        self,
        memory_mb: Optional[float] = None,
        cpu_percent: Optional[float] = None
    ) -> bool:
        """
        检查是否有足够的资源
        
        Args:
            memory_mb: 需要的内存（MB）
            cpu_percent: 需要的CPU百分比
            
        Returns:
            是否有足够资源
        """
        snapshot = await self.get_current_usage()
        
        if memory_mb is not None:
            projected = snapshot.memory_mb + memory_mb
            if projected > self.thresholds.max_memory_mb:
                return False
        
        if cpu_percent is not None:
            projected = snapshot.cpu_percent + cpu_percent
            if projected > self.thresholds.max_cpu_percent:
                return False
        
        return True


# ============ 内存使用限制器 ============

class MemoryLimiter:
    """
    内存使用限制器
    
    限制内存使用，防止内存泄漏和耗尽。
    """
    
    def __init__(self, max_memory_mb: float = 512.0, check_interval: float = 1.0):
        self.max_memory_mb = max_memory_mb
        self.check_interval = check_interval
        self._current_memory = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self, memory_mb: float, timeout: Optional[float] = None) -> bool:
        """
        申请内存
        
        Args:
            memory_mb: 申请的内存（MB）
            timeout: 超时时间
            
        Returns:
            是否成功
        """
        start_time = time.time()
        
        while True:
            async with self._lock:
                if self._current_memory + memory_mb <= self.max_memory_mb:
                    self._current_memory += memory_mb
                    return True
            
            if timeout is not None and time.time() - start_time > timeout:
                return False
            
            await asyncio.sleep(self.check_interval)
    
    async def release(self, memory_mb: float) -> None:
        """释放内存"""
        async with self._lock:
            self._current_memory = max(0.0, self._current_memory - memory_mb)
    
    async def get_usage(self) -> float:
        """获取当前内存使用"""
        async with self._lock:
            return self._current_memory


# ============ 全局监控器 ============

# 全局资源监控器实例
_global_monitor: Optional[ResourceMonitor] = None


def get_resource_monitor(thresholds: Optional[ResourceThresholds] = None) -> ResourceMonitor:
    """获取全局资源监控器"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ResourceMonitor(thresholds)
    return _global_monitor


def start_global_monitor() -> None:
    """启动全局资源监控"""
    monitor = get_resource_monitor()
    monitor.start()


async def start_global_monitor_async() -> None:
    """异步启动全局资源监控"""
    monitor = get_resource_monitor()
    await monitor.start_async()


def stop_global_monitor() -> None:
    """停止全局资源监控"""
    global _global_monitor
    if _global_monitor:
        _global_monitor.stop()
        _global_monitor = None


async def stop_global_monitor_async() -> None:
    """异步停止全局资源监控"""
    global _global_monitor
    if _global_monitor:
        await _global_monitor.stop_async()
        _global_monitor = None


# ============ 实用装饰器 ============

def with_resource_check(
    memory_mb: Optional[float] = None,
    cpu_percent: Optional[float] = None
):
    """
    资源检查装饰器
    
    Args:
        memory_mb: 需要的内存（MB）
        cpu_percent: 需要的CPU百分比
        
    Example:
        @with_resource_check(memory_mb=100)
        async def process_large_file(data):
            # 处理大文件
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            monitor = get_resource_monitor()
            
            has_resources = await monitor.require_resources(memory_mb, cpu_percent)
            if not has_resources:
                raise ResourceLimitError("系统资源不足，无法执行操作")
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
