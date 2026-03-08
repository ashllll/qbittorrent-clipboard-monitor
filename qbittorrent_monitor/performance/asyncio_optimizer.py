"""Asyncio性能优化模块

提供阻塞调用识别与优化、任务取消处理和并发限制功能。

主要优化:
    1. 阻塞调用检测和线程池执行
    2. 任务取消安全处理
    3. 并发限制和流量控制
    4. 协程性能分析
"""

import asyncio
import functools
import inspect
import logging
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import (
    Any, Callable, Coroutine, Dict, Generic, List, Optional, 
    Set, TypeVar, Union, overload
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class TaskStats:
    """任务统计"""
    created: int = 0
    completed: int = 0
    cancelled: int = 0
    failed: int = 0
    avg_duration_ms: float = 0.0
    _durations: deque = field(default_factory=lambda: deque(maxlen=1000))


@dataclass
class CoroutineMetrics:
    """协程性能指标"""
    name: str
    call_count: int = 0
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    max_time_ms: float = 0.0
    min_time_ms: float = float('inf')


class TaskManager:
    """任务管理器
    
    管理异步任务的生命周期，提供：
    - 任务追踪和监控
    - 优雅取消
    - 超时处理
    - 错误恢复
    
    Example:
        >>> manager = TaskManager()
        >>> 
        >>> # 创建任务
        >>> task = manager.create_task(
        ...     some_coroutine(),
        ...     name="my_task",
        ...     on_complete=lambda t: print(f"完成: {t.result()}")
        ... )
        >>> 
        >>> # 等待所有任务完成
        >>> await manager.wait_all(timeout=10.0)
        >>> 
        >>> # 取消所有任务
        >>> await manager.cancel_all()
    """
    
    def __init__(self):
        """初始化任务管理器"""
        self._tasks: Set[asyncio.Task] = set()
        self._stats = TaskStats()
        self._callbacks: Dict[str, List[Callable]] = {
            "on_complete": [],
            "on_cancel": [],
            "on_error": [],
        }
    
    def create_task(
        self,
        coro: Coroutine[Any, Any, T],
        name: Optional[str] = None,
        on_complete: Optional[Callable[[asyncio.Task[T]], None]] = None,
        on_cancel: Optional[Callable[[asyncio.Task[T]], None]] = None,
        on_error: Optional[Callable[[asyncio.Task[T], Exception], None]] = None,
    ) -> asyncio.Task[T]:
        """创建并追踪任务
        
        Args:
            coro: 协程对象
            name: 任务名称
            on_complete: 完成回调
            on_cancel: 取消回调
            on_error: 错误回调
            
        Returns:
            创建的Task对象
        """
        task = asyncio.create_task(
            self._wrap_coro(coro, on_complete, on_cancel, on_error),
            name=name,
        )
        
        self._tasks.add(task)
        self._stats.created += 1
        
        # 任务完成时自动移除
        task.add_done_callback(self._on_task_done)
        
        return task
    
    async def wait_all(
        self,
        timeout: Optional[float] = None,
        return_exceptions: bool = True,
    ) -> List[Any]:
        """等待所有任务完成
        
        Args:
            timeout: 超时时间
            return_exceptions: 是否返回异常而不是抛出
            
        Returns:
            任务结果列表
        """
        if not self._tasks:
            return []
        
        tasks_list = list(self._tasks)
        
        if timeout:
            done, pending = await asyncio.wait(
                tasks_list,
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED,
            )
            
            # 取消超时未完成的任务
            for task in pending:
                task.cancel()
            
            results = []
            for task in done:
                try:
                    results.append(task.result())
                except Exception as e:
                    if return_exceptions:
                        results.append(e)
                    else:
                        raise
            
            return results
        else:
            return await asyncio.gather(
                *tasks_list,
                return_exceptions=return_exceptions,
            )
    
    async def cancel_all(self, wait: bool = True, timeout: float = 5.0) -> int:
        """取消所有任务
        
        Args:
            wait: 是否等待任务完成取消
            timeout: 等待超时时间
            
        Returns:
            取消的任务数
        """
        cancelled_count = 0
        
        for task in list(self._tasks):
            if not task.done():
                task.cancel()
                cancelled_count += 1
        
        if wait and cancelled_count > 0:
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        *self._tasks,
                        return_exceptions=True,
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"等待任务取消超时，{len(self._tasks)} 个任务可能仍在运行")
        
        return cancelled_count
    
    def get_active_tasks(self) -> List[asyncio.Task]:
        """获取当前活跃任务"""
        return [t for t in self._tasks if not t.done()]
    
    def get_stats(self) -> TaskStats:
        """获取任务统计"""
        return TaskStats(
            created=self._stats.created,
            completed=self._stats.completed,
            cancelled=self._stats.cancelled,
            failed=self._stats.failed,
            avg_duration_ms=sum(self._stats._durations) / len(self._stats._durations)
            if self._stats._durations else 0.0,
        )
    
    async def _wrap_coro(
        self,
        coro: Coroutine[Any, Any, T],
        on_complete: Optional[Callable] = None,
        on_cancel: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> T:
        """包装协程以处理回调"""
        start_time = time.time()
        
        try:
            result = await coro
            self._stats.completed += 1
            
            if on_complete:
                try:
                    on_complete(result)
                except Exception as e:
                    logger.error(f"完成回调错误: {e}")
            
            return result
            
        except asyncio.CancelledError:
            self._stats.cancelled += 1
            
            if on_cancel:
                try:
                    on_cancel()
                except Exception as e:
                    logger.error(f"取消回调错误: {e}")
            
            raise
            
        except Exception as e:
            self._stats.failed += 1
            
            if on_error:
                try:
                    on_error(e)
                except Exception as callback_error:
                    logger.error(f"错误回调错误: {callback_error}")
            
            raise
            
        finally:
            duration = (time.time() - start_time) * 1000
            self._stats._durations.append(duration)
    
    def _on_task_done(self, task: asyncio.Task) -> None:
        """任务完成回调"""
        self._tasks.discard(task)


class ConcurrencyLimiter:
    """并发限制器
    
    限制并发任务数量，防止资源耗尽。
    
    Example:
        >>> limiter = ConcurrencyLimiter(max_concurrent=10)
        >>> 
        >>> async with limiter:
        ...     # 最多10个任务同时执行此处
        ...     await process_item(item)
        >>> 
        >>> # 批量处理
        >>> async def process_all(items):
        ...     tasks = [limiter.run(process_item, item) for item in items]
        ...     return await asyncio.gather(*tasks)
    """
    
    def __init__(
        self,
        max_concurrent: int = 10,
        max_queue_size: int = 1000,
        priority: bool = False,
    ):
        """初始化并发限制器
        
        Args:
            max_concurrent: 最大并发数
            max_queue_size: 队列最大长度
            priority: 是否使用优先级队列
        """
        self.max_concurrent = max_concurrent
        
        if priority:
            self._semaphore = asyncio.PriorityQueue(maxsize=max_queue_size)
            # 初始化信号量计数
            for _ in range(max_concurrent):
                self._semaphore.put_nowait(0)
        else:
            self._semaphore = asyncio.Semaphore(max_concurrent)
        
        self._stats = {
            "acquired": 0,
            "released": 0,
            "queued": 0,
            "rejected": 0,
        }
    
    @asynccontextmanager
    async def acquire(self, timeout: Optional[float] = None):
        """获取并发许可（上下文管理器）
        
        Args:
            timeout: 获取超时时间
            
        Yields:
            None
        """
        acquired = False
        try:
            if timeout:
                await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout)
            else:
                await self._semaphore.acquire()
            
            acquired = True
            self._stats["acquired"] += 1
            yield
            
        finally:
            if acquired:
                self._semaphore.release()
                self._stats["released"] += 1
    
    async def run(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args,
        **kwargs,
    ) -> T:
        """在并发限制下运行函数
        
        Args:
            func: 异步函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数返回值
        """
        async with self.acquire():
            return await func(*args, **kwargs)
    
    def run_sync(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> Coroutine[Any, Any, T]:
        """在并发限制下运行同步函数（自动使用线程池）
        
        Args:
            func: 同步函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            协程对象
        """
        async def _wrapper():
            async with self.acquire():
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, functools.partial(func, *args, **kwargs)
                )
        
        return _wrapper()
    
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return dict(self._stats)


class AsyncIOOptimizer:
    """AsyncIO优化器
    
    提供全面的asyncio性能优化功能：
    - 阻塞调用自动检测和优化
    - 协程性能分析
    - 事件循环优化
    - 线程池管理
    
    Example:
        >>> optimizer = AsyncIOOptimizer()
        >>> optimizer.enable_monitoring()
        >>> 
        >>> # 优化阻塞调用
        >>> result = await optimizer.run_in_thread(blocking_function, arg1, arg2)
        >>> 
        >>> # 性能分析装饰器
        >>> @optimizer.profile
        ... async def my_coroutine():
        ...     await asyncio.sleep(1)
        >>> 
        >>> # 获取性能报告
        >>> report = optimizer.get_performance_report()
    """
    
    def __init__(
        self,
        max_workers: int = 10,
        enable_profiling: bool = False,
    ):
        """初始化优化器
        
        Args:
            max_workers: 线程池最大工作线程数
            enable_profiling: 是否启用性能分析
        """
        self.max_workers = max_workers
        self.enable_profiling = enable_profiling
        
        # 线程池
        self._executor: Optional[ThreadPoolExecutor] = None
        
        # 性能分析数据
        self._metrics: Dict[str, CoroutineMetrics] = {}
        self._blocking_calls: deque = deque(maxlen=100)
        
        # 事件循环
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def initialize(self) -> None:
        """初始化优化器"""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="asyncio_optimizer",
            )
        
        self._loop = asyncio.get_event_loop()
        logger.debug(f"AsyncIO优化器已初始化 (max_workers={self.max_workers})")
    
    def shutdown(self, wait: bool = True) -> None:
        """关闭优化器"""
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None
    
    async def run_in_thread(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """在线程池中运行同步函数
        
        Args:
            func: 同步函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数返回值
        """
        if self._executor is None:
            self.initialize()
        
        loop = self._loop or asyncio.get_event_loop()
        
        # 记录阻塞调用
        self._blocking_calls.append({
            "func": func.__name__,
            "timestamp": time.time(),
        })
        
        # 在线程池中执行
        return await loop.run_in_executor(
            self._executor,
            functools.partial(func, *args, **kwargs),
        )
    
    def profile(self, func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        """性能分析装饰器
        
        Args:
            func: 要分析的协程函数
            
        Returns:
            包装后的函数
        """
        if not self.enable_profiling:
            return func
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            name = func.__name__
            start_time = time.time()
            
            if name not in self._metrics:
                self._metrics[name] = CoroutineMetrics(name=name)
            
            metrics = self._metrics[name]
            metrics.call_count += 1
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed_ms = (time.time() - start_time) * 1000
                metrics.total_time_ms += elapsed_ms
                metrics.avg_time_ms = metrics.total_time_ms / metrics.call_count
                metrics.max_time_ms = max(metrics.max_time_ms, elapsed_ms)
                metrics.min_time_ms = min(metrics.min_time_ms, elapsed_ms)
        
        return wrapper
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告
        
        Returns:
            性能报告字典
        """
        return {
            "coroutines": {
                name: {
                    "call_count": m.call_count,
                    "total_time_ms": round(m.total_time_ms, 2),
                    "avg_time_ms": round(m.avg_time_ms, 2),
                    "max_time_ms": round(m.max_time_ms, 2),
                    "min_time_ms": round(m.min_time_ms, 2) if m.min_time_ms != float('inf') else 0,
                }
                for name, m in self._metrics.items()
            },
            "blocking_calls": list(self._blocking_calls),
            "thread_pool": {
                "max_workers": self.max_workers,
            },
        }
    
    def optimize_event_loop(self) -> None:
        """优化事件循环配置"""
        loop = asyncio.get_event_loop()
        
        # 设置更快的异常处理程序
        def fast_exception_handler(loop, context):
            exception = context.get("exception")
            if exception:
                logger.error(f"事件循环异常: {exception}")
        
        loop.set_exception_handler(fast_exception_handler)
        
        # 对于Python 3.9+，启用更快的任务工厂
        if hasattr(loop, "set_task_factory"):
            original_factory = loop.get_task_factory()
            
            def optimized_task_factory(loop, coro, **kwargs):
                # 使用优化的任务创建
                task = asyncio.Task(coro, loop=loop, **kwargs)
                return task
            
            loop.set_task_factory(optimized_task_factory)
        
        logger.debug("事件循环已优化")
    
    @staticmethod
    def detect_blocking_calls(
        threshold_ms: float = 100.0,
    ) -> Callable:
        """阻塞调用检测装饰器
        
        Args:
            threshold_ms: 阻塞阈值（毫秒）
            
        Returns:
            装饰器函数
        """
        def decorator(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
            if asyncio.iscoroutinefunction(func):
                # 已经是协程函数，直接返回
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    start = time.time()
                    result = await func(*args, **kwargs)
                    elapsed_ms = (time.time() - start) * 1000
                    
                    if elapsed_ms > threshold_ms:
                        logger.warning(
                            f"潜在的慢协程: {func.__name__} 耗时 {elapsed_ms:.2f}ms"
                        )
                    
                    return result
                
                return async_wrapper
            else:
                # 同步函数，建议在线程池中运行
                @functools.wraps(func)
                async def sync_wrapper(*args, **kwargs):
                    logger.warning(
                        f"检测到同步函数 {func.__name__} 在异步上下文中调用，"
                        f"建议使用 run_in_thread"
                    )
                    
                    start = time.time()
                    result = func(*args, **kwargs)
                    elapsed_ms = (time.time() - start) * 1000
                    
                    if elapsed_ms > threshold_ms:
                        logger.warning(
                            f"检测到阻塞调用: {func.__name__} 耗时 {elapsed_ms:.2f}ms，"
                            f"强烈建议使用线程池"
                        )
                    
                    return result
                
                return sync_wrapper
        
        return decorator


# 便捷函数

async def run_in_executor(
    func: Callable[..., T],
    *args,
    executor: Optional[ThreadPoolExecutor] = None,
    **kwargs,
) -> T:
    """在线程池中运行同步函数
    
    Args:
        func: 同步函数
        *args: 位置参数
        executor: 可选的线程池
        **kwargs: 关键字参数
        
    Returns:
        函数返回值
    """
    loop = asyncio.get_event_loop()
    
    if kwargs:
        func = functools.partial(func, **kwargs)
    
    return await loop.run_in_executor(executor, func, *args)


def create_limited_task(
    coro: Coroutine[Any, Any, T],
    semaphore: asyncio.Semaphore,
    name: Optional[str] = None,
) -> asyncio.Task[T]:
    """创建受信号量限制的任务
    
    Args:
        coro: 协程对象
        semaphore: 并发限制信号量
        name: 任务名称
        
    Returns:
        创建的Task对象
    """
    async def _limited_coro():
        async with semaphore:
            return await coro
    
    return asyncio.create_task(_limited_coro(), name=name)


async def gather_with_concurrency(
    coros: List[Coroutine[Any, Any, T]],
    limit: int = 10,
    return_exceptions: bool = True,
) -> List[Any]:
    """带并发限制的gather
    
    Args:
        coros: 协程列表
        limit: 并发限制
        return_exceptions: 是否返回异常
        
    Returns:
        结果列表
    """
    semaphore = asyncio.Semaphore(limit)
    
    async def _limited_coro(coro):
        async with semaphore:
            return await coro
    
    limited_coros = [_limited_coro(c) for c in coros]
    return await asyncio.gather(*limited_coros, return_exceptions=return_exceptions)


async def timeout(
    coro: Coroutine[Any, Any, T],
    timeout_seconds: float,
    default: Optional[T] = None,
) -> Optional[T]:
    """带超时的协程执行
    
    Args:
        coro: 协程对象
        timeout_seconds: 超时时间（秒）
        default: 超时时的默认值
        
    Returns:
        协程结果或默认值
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return default
