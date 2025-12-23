"""
性能优化器模块

提供异步优化、并发控制、内存管理和CPU优化功能。

主要组件:
- OptimizedAsyncWebCrawler: 优化的异步Web爬虫
- SmartConcurrencyController: 智能并发控制器
- PerformanceOptimizer: 性能优化器
"""

import asyncio
import time
import weakref
from typing import Dict, List, Optional, Any, Callable, Set, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from .models import SiteConfig, MemoryMonitor


logger = logging.getLogger(__name__)


class OptimizationLevel(Enum):
    """优化级别"""
    NONE = 0          # 无优化
    BASIC = 1         # 基础优化
    MODERATE = 2      # 中等优化
    AGGRESSIVE = 3    # 激进优化


class LoadState(Enum):
    """系统负载状态"""
    LOW = "low"       # 低负载
    MEDIUM = "medium" # 中等负载
    HIGH = "high"     # 高负载


@dataclass
class PerformanceMetrics:
    """性能指标"""
    # 吞吐量指标
    requests_per_second: float = 0.0
    pages_per_second: float = 0.0
    bytes_per_second: float = 0.0

    # 延迟指标
    average_response_time: float = 0.0
    median_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0

    # 资源使用
    cpu_usage: float = 0.0
    memory_usage_mb: float = 0.0
    active_connections: int = 0

    # 错误统计
    error_rate: float = 0.0
    timeout_rate: float = 0.0
    retry_rate: float = 0.0

    # 时间窗口
    window_size: int = 100  # 保留最近100个请求的统计


class SmartConcurrencyController:
    """智能并发控制器

    动态调整并发级别以优化性能
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        optimization_level: OptimizationLevel = OptimizationLevel.MODERATE
    ):
        """
        初始化控制器

        Args:
            max_concurrent: 最大并发数
            optimization_level: 优化级别
        """
        self.max_concurrent = max_concurrent
        self.optimization_level = optimization_level

        # 当前并发数
        self.current_concurrent = 1

        # 性能统计
        self.metrics = PerformanceMetrics()
        self.response_times = deque(maxlen=self.metrics.window_size)
        self.error_counts = {'total': 0, 'timeouts': 0, 'retries': 0}

        # 负载状态
        self.load_state = LoadState.MEDIUM

        # 自动调整参数
        self.adjustment_interval = 10.0  # 每10秒调整一次
        self.last_adjustment = time.time()

        # 控制标志
        self._adjustment_lock = threading.Lock()
        self._stop_event = threading.Event()

        # 监控任务
        self._monitor_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动监控"""
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """停止监控"""
        self._stop_event.set()
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.adjustment_interval)
                await self._adjust_concurrency()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Concurrency adjustment error: {e}")

    async def _adjust_concurrency(self):
        """调整并发级别"""
        now = time.time()
        if now - self.last_adjustment < self.adjustment_interval:
            return

        with self._adjustment_lock:
            try:
                # 计算当前性能指标
                self._calculate_metrics()

                # 根据性能调整并发
                new_concurrent = self._calculate_optimal_concurrent()

                if new_concurrent != self.current_concurrent:
                    logger.info(
                        f"Adjusting concurrency: {self.current_concurrent} -> "
                        f"{new_concurrent} (RPS: {self.metrics.requests_per_second:.2f}, "
                        f"Error rate: {self.metrics.error_rate:.2%})"
                    )
                    self.current_concurrent = new_concurrent

                self.last_adjustment = now

            except Exception as e:
                logger.error(f"Concurrency calculation error: {e}")

    def _calculate_metrics(self):
        """计算性能指标"""
        # 计算响应时间统计
        if self.response_times:
            times = list(self.response_times)
            times.sort()

            self.metrics.average_response_time = sum(times) / len(times)
            self.metrics.median_response_time = times[len(times) // 2]
            self.metrics.p95_response_time = times[int(len(times) * 0.95)]
            self.metrics.p99_response_time = times[int(len(times) * 0.99)]

            # 计算吞吐量 (简化计算)
            if self.metrics.window_size > 0:
                self.metrics.requests_per_second = len(times) / self.adjustment_interval

        # 计算错误率
        total_requests = len(self.response_times)
        if total_requests > 0:
            self.metrics.error_rate = self.error_counts['total'] / total_requests
            self.metrics.timeout_rate = self.error_counts['timeouts'] / total_requests
            self.metrics.retry_rate = self.error_counts['retries'] / total_requests

    def _calculate_optimal_concurrent(self) -> int:
        """计算最优并发数"""
        # 根据优化级别设置调整策略
        if self.optimization_level == OptimizationLevel.NONE:
            return self.current_concurrent

        if self.optimization_level == OptimizationLevel.BASIC:
            # 基础优化：简单的线性调整
            if self.metrics.error_rate > 0.1:  # 错误率 > 10%
                return max(1, self.current_concurrent - 1)
            elif self.metrics.average_response_time < 1.0 and self.metrics.error_rate < 0.05:
                return min(self.max_concurrent, self.current_concurrent + 1)
            return self.current_concurrent

        # 中等和激进优化：基于多指标决策
        score = 0

        # 响应时间评分 (响应越快得分越高)
        if self.metrics.average_response_time < 0.5:
            score += 2
        elif self.metrics.average_response_time < 1.0:
            score += 1
        elif self.metrics.average_response_time > 3.0:
            score -= 2
        elif self.metrics.average_response_time > 2.0:
            score -= 1

        # 错误率评分 (错误率越低得分越高)
        if self.metrics.error_rate < 0.01:
            score += 2
        elif self.metrics.error_rate < 0.05:
            score += 1
        elif self.metrics.error_rate > 0.1:
            score -= 3
        elif self.metrics.error_rate > 0.05:
            score -= 1

        # 吞吐量评分 (吞吐量越高得分越高)
        if self.metrics.requests_per_second > 5:
            score += 1
        elif self.metrics.requests_per_second < 1:
            score -= 1

        # 内存使用评分 (内存使用越高得分越低)
        if self.metrics.memory_usage_mb > 500:
            score -= 2
        elif self.metrics.memory_usage_mb > 300:
            score -= 1

        # 根据得分调整并发
        new_concurrent = self.current_concurrent

        if score >= 2:
            new_concurrent = min(self.max_concurrent, self.current_concurrent + 2)
        elif score == 1:
            new_concurrent = min(self.max_concurrent, self.current_concurrent + 1)
        elif score == -1:
            new_concurrent = max(1, self.current_concurrent - 1)
        elif score <= -2:
            new_concurrent = max(1, self.current_concurrent - 2)

        # 激进优化时更激进的调整
        if self.optimization_level == OptimizationLevel.AGGRESSIVE:
            new_concurrent = max(1, min(self.max_concurrent, self.current_concurrent + score))

        return new_concurrent

    def record_request(self, response_time: float, is_error: bool = False, is_timeout: bool = False):
        """
        记录请求

        Args:
            response_time: 响应时间
            is_error: 是否错误
            is_timeout: 是否超时
        """
        self.response_times.append(response_time)

        if is_error:
            self.error_counts['total'] += 1

        if is_timeout:
            self.error_counts['timeouts'] += 1

    def can_start_request(self) -> bool:
        """
        检查是否可以开始新请求

        Returns:
            bool: 是否可以开始
        """
        return len(self.response_times) < self.current_concurrent

    def acquire_slot(self, timeout: float = 0.1) -> bool:
        """
        获取并发槽位

        Args:
            timeout: 超时时间

        Returns:
            bool: 是否获取成功
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.can_start_request():
                return True
            time.sleep(0.01)
        return False

    def release_slot(self):
        """释放并发槽位"""
        # 这里简化处理，实际可以维护一个活跃请求的计数器
        pass


class OptimizedAsyncWebCrawler:
    """优化的异步Web爬虫

    提供高性能的异步网页抓取能力
    """

    def __init__(
        self,
        config: SiteConfig,
        memory_monitor: MemoryMonitor,
        optimization_level: OptimizationLevel = OptimizationLevel.MODERATE
    ):
        """
        初始化爬虫

        Args:
            config: 网站配置
            memory_monitor: 内存监控器
            optimization_level: 优化级别
        """
        self.config = config
        self.memory_monitor = memory_monitor

        # 并发控制
        self.concurrency_controller = SmartConcurrencyController(
            max_concurrent=config.max_concurrent,
            optimization_level=optimization_level
        )

        # 线程池 (用于CPU密集型任务)
        self.thread_pool = ThreadPoolExecutor(
            max_workers=config.max_concurrent,
            thread_name_prefix="webcrawler"
        )

        # 性能统计
        self.metrics = PerformanceMetrics()

        # 状态
        self._running = False
        self._active_tasks: Set[asyncio.Task] = set()

        # 回调函数
        self.on_success: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

    async def start(self):
        """启动爬虫"""
        self._running = True
        await self.concurrency_controller.start()

    async def stop(self):
        """停止爬虫"""
        self._running = False
        await self.concurrency_controller.stop()

        # 取消所有活跃任务
        for task in self._active_tasks:
            if not task.done():
                task.cancel()

        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

        # 关闭线程池
        self.thread_pool.shutdown(wait=True)

    async def crawl(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        批量爬取

        Args:
            urls: URL列表

        Returns:
            List[Dict[str, Any]]: 爬取结果
        """
        results = []
        semaphore = asyncio.Semaphore(self.concurrency_controller.current_concurrent)

        # 创建任务
        tasks = [
            self._crawl_single(url, semaphore)
            for url in urls
        ]

        # 并发执行
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                results.append(result)
            except Exception as e:
                logger.error(f"Crawl error: {e}")
                results.append({'url': '', 'error': str(e)})

        return results

    async def _crawl_single(self, url: str, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
        """
        爬取单个URL

        Args:
            url: 目标URL
            semaphore: 信号量

        Returns:
            Dict[str, Any]: 爬取结果
        """
        start_time = time.time()

        async with semaphore:
            try:
                # 内存检查
                if self.memory_monitor.should_trigger_cleanup():
                    await self.memory_monitor.cleanup()

                # 获取并发槽位
                if not self.concurrency_controller.acquire_slot():
                    raise TimeoutError("Failed to acquire concurrency slot")

                # 执行爬取 (简化实现)
                await asyncio.sleep(0.1)  # 模拟网络请求

                response_time = time.time() - start_time

                # 记录性能指标
                self.concurrency_controller.record_request(response_time, is_error=False)

                result = {
                    'url': url,
                    'status': 'success',
                    'response_time': response_time,
                    'content': f"Content from {url}",
                }

                # 调用成功回调
                if self.on_success:
                    await self._safe_callback(self.on_success, result)

                return result

            except Exception as e:
                response_time = time.time() - start_time
                is_timeout = isinstance(e, TimeoutError)

                self.concurrency_controller.record_request(
                    response_time,
                    is_error=True,
                    is_timeout=is_timeout
                )

                result = {
                    'url': url,
                    'status': 'error',
                    'error': str(e),
                    'response_time': response_time,
                }

                # 调用错误回调
                if self.on_error:
                    await self._safe_callback(self.on_error, result)

                return result

            finally:
                self.concurrency_controller.release_slot()

    async def _safe_callback(self, callback: Callable, result: Dict[str, Any]):
        """
        安全执行回调

        Args:
            callback: 回调函数
            result: 结果数据
        """
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(result)
            else:
                callback(result)
        except Exception as e:
            logger.error(f"Callback error: {e}")

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计

        Returns:
            Dict[str, Any]: 性能统计
        """
        self.concurrency_controller._calculate_metrics()

        return {
            'concurrency': {
                'current': self.concurrency_controller.current_concurrent,
                'max': self.concurrency_controller.max_concurrent,
                'optimization_level': self.concurrency_controller.optimization_level.name,
            },
            'metrics': {
                'requests_per_second': self.concurrency_controller.metrics.requests_per_second,
                'average_response_time': self.concurrency_controller.metrics.average_response_time,
                'median_response_time': self.concurrency_controller.metrics.median_response_time,
                'p95_response_time': self.concurrency_controller.metrics.p95_response_time,
                'error_rate': self.concurrency_controller.metrics.error_rate,
                'timeout_rate': self.concurrency_controller.metrics.timeout_rate,
            },
            'memory': self.memory_monitor.get_stats(),
        }


class PerformanceOptimizer:
    """性能优化器

    全局性能优化管理器
    """

    def __init__(self):
        """初始化优化器"""
        self.optimizers: Dict[str, OptimizedAsyncWebCrawler] = {}
        self.global_settings = {
            'max_total_concurrent': 50,
            'target_response_time': 1.0,
            'max_error_rate': 0.1,
        }

    def register_optimizer(self, name: str, optimizer: OptimizedAsyncWebCrawler):
        """
        注册优化器

        Args:
            name: 优化器名称
            optimizer: 优化器实例
        """
        self.optimizers[name] = optimizer

    def unregister_optimizer(self, name: str):
        """
        注销优化器

        Args:
            name: 优化器名称
        """
        if name in self.optimizers:
            del self.optimizers[name]

    def get_global_stats(self) -> Dict[str, Any]:
        """
        获取全局统计

        Returns:
            Dict[str, Any]: 全局统计
        """
        total_concurrent = sum(
            opt.concurrency_controller.current_concurrent
            for opt in self.optimizers.values()
        )

        avg_response_time = sum(
            opt.concurrency_controller.metrics.average_response_time
            for opt in self.optimizers.values()
        ) / len(self.optimizers) if self.optimizers else 0

        avg_error_rate = sum(
            opt.concurrency_controller.metrics.error_rate
            for opt in self.optimizers.values()
        ) / len(self.optimizers) if self.optimizers else 0

        return {
            'total_optimizers': len(self.optimizers),
            'total_concurrent': total_concurrent,
            'avg_response_time': avg_response_time,
            'avg_error_rate': avg_error_rate,
            'global_settings': self.global_settings,
            'optimizer_stats': {
                name: opt.get_performance_stats()
                for name, opt in self.optimizers.items()
            },
        }

    def optimize_all(self):
        """优化所有注册的爬虫"""
        stats = self.get_global_stats()

        # 根据全局统计调整设置
        if stats['avg_error_rate'] > self.global_settings['max_error_rate']:
            logger.warning(
                f"High global error rate: {stats['avg_error_rate']:.2%}. "
                "Consider reducing concurrency."
            )

        if stats['avg_response_time'] > self.global_settings['target_response_time']:
            logger.info(
                f"High average response time: {stats['avg_response_time']:.2f}s. "
                "Optimization may be needed."
            )


# 导出
__all__ = [
    'OptimizationLevel',
    'LoadState',
    'PerformanceMetrics',
    'SmartConcurrencyController',
    'OptimizedAsyncWebCrawler',
    'PerformanceOptimizer',
]
