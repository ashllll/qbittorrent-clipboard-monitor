"""
并发控制模块

提供高级并发控制功能，包括信号量、限流器、工作池等
"""

import asyncio
import time
import logging
from typing import Any, Dict, List, Optional, Callable, Awaitable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@dataclass
class ConcurrencyStats:
    """并发统计信息"""
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_wait_time: float = 0.0
    max_concurrent: int = 0
    queue_size: int = 0
    throughput: float = 0.0  # 任务/秒


class AsyncRateLimiter:
    """
    异步速率限制器

    基于令牌桶算法的速率限制器
    """

    def __init__(
        self,
        rate: float,  # 每秒令牌数
        capacity: Optional[float] = None,  # 令牌桶容量
        token_cost: float = 1.0  # 每次操作消耗的令牌数
    ):
        self.rate = rate
        self.capacity = capacity or rate * 10  # 默认容量为速率的10倍
        self.token_cost = token_cost

        self._tokens = self.capacity
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()
        self._waiters: deque = deque()

    async def acquire(self, tokens: float = 1.0) -> None:
        """获取令牌"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_update

            # 根据时间补充令牌
            self._tokens = min(
                self.capacity,
                self._tokens + elapsed * self.rate
            )
            self._last_update = now

            # 检查是否有足够的令牌
            needed = tokens * self.token_cost
            if self._tokens >= needed:
                self._tokens -= needed
                return

            # 等待令牌补充
            wait_time = (needed - self._tokens) / self.rate
            self._waiters.append(wait_time)

        # 等待指定时间
        await asyncio.sleep(wait_time)

    def available_tokens(self) -> float:
        """获取当前可用令牌数"""
        now = time.monotonic()
        elapsed = now - self._last_update
        return min(
            self.capacity,
            self._tokens + elapsed * self.rate
        )


class AsyncThrottler:
    """
    异步节流器

    限制特定操作的并发数
    """

    def __init__(
        self,
        max_concurrent: int,
        max_waiting: int = 1000
    ):
        self.max_concurrent = max_concurrent
        self.max_waiting = max_waiting

        self._active_count = 0
        self._waiting_count = 0
        self._lock = asyncio.Lock()
        self._queue: deque = deque()
        self._stats = ConcurrencyStats()

    async def acquire(self) -> None:
        """获取执行许可"""
        async with self._lock:
            # 检查是否超过最大等待数
            if self._waiting_count >= self.max_waiting:
                raise RuntimeError(f"等待队列已满 ({self.max_waiting})")

            # 如果当前活跃任务数少于限制，直接执行
            if self._active_count < self.max_concurrent:
                self._active_count += 1
                self._stats.active_tasks += 1
                self._stats.max_concurrent = max(
                    self._stats.max_concurrent,
                    self._active_count
                )
                return

            # 否则加入等待队列
            self._waiting_count += 1
            self._stats.queue_size = self._waiting_count

        # 等待许可
        future = asyncio.Future()
        self._queue.append(future)

        try:
            await future
        finally:
            async with self._lock:
                self._waiting_count -= 1
                self._stats.queue_size = self._waiting_count

    def release(self) -> None:
        """释放执行许可"""
        # 同步锁的释放
        self._active_count = max(0, self._active_count - 1)
        self._stats.active_tasks -= 1

        # 唤醒等待队列中的下一个任务
        if self._queue:
                future = self._queue.popleft()
                self._active_count += 1
                self._stats.active_tasks += 1
                future.set_result(None)

    def get_stats(self) -> ConcurrencyStats:
        """获取统计信息"""
        return self._stats


class AsyncWorkPool:
    """
    异步工作池

    管理一组工作线程，限制并发数
    """

    def __init__(
        self,
        max_workers: int = 10,
        work_queue_size: int = 1000,
        max_waiting: int = 1000
    ):
        self.max_workers = max_workers
        self.work_queue_size = work_queue_size
        self.max_waiting = max_waiting

        self._work_queue = asyncio.Queue(maxsize=work_queue_size)
        self._workers: List[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
        self._throttler = AsyncThrottler(max_workers, max_waiting)
        self._stats = ConcurrencyStats()
        self._start_time = time.time()
        self._completed_tasks = 0
        self._failed_tasks = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """启动工作池"""
        # 创建工作线程
        for i in range(self.max_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)

        logger.info(f"工作池已启动 (工作线程数: {self.max_workers})")

    async def stop(self) -> None:
        """停止工作池"""
        # 设置关闭事件
        self._shutdown_event.set()

        # 等待所有工作线程结束
        await asyncio.gather(*self._workers, return_exceptions=True)

        # 清空队列
        while not self._work_queue.empty():
            try:
                self._work_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        logger.info("工作池已停止")

    async def submit(
        self,
        func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs
    ) -> Any:
        """提交任务"""
        future = asyncio.Future()

        # 创建任务
        task = {
            "func": func,
            "args": args,
            "kwargs": kwargs,
            "future": future
        }

        try:
            # 加入工作队列
            await self._work_queue.put(task)
        except asyncio.QueueFull:
            raise RuntimeError(f"工作队列已满 ({self.work_queue_size})")

        return await future

    async def _worker(self, worker_id: int) -> None:
        """工作线程"""
        logger.debug(f"工作线程 {worker_id} 已启动")

        while not self._shutdown_event.is_set():
            try:
                # 从队列获取任务
                task = await asyncio.wait_for(
                    self._work_queue.get(),
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            # 获取执行许可
            wait_start = time.time()
            await self._throttler.acquire()
            wait_time = time.monotonic() - wait_start

            async with self._lock:
                self._stats.total_wait_time += wait_time

            try:
                # 执行任务
                start_time = time.time()
                result = await task["func"](*task["args"], **task["kwargs"])
                execution_time = time.monotonic() - start_time

                # 设置结果
                task["future"].set_result(result)

                # 更新统计
                async with self._lock:
                    self._stats.completed_tasks += 1
                    self._completed_tasks += 1

                    # 更新吞吐量
                    elapsed = time.time() - self._start_time
                    self._stats.throughput = self._completed_tasks / elapsed

            except Exception as e:
                # 设置异常
                task["future"].set_exception(e)

                # 更新统计
                async with self._lock:
                    self._stats.failed_tasks += 1
                    self._failed_tasks += 1

                logger.error(f"工作线程 {worker_id} 执行任务失败: {str(e)}")

            finally:
                # 释放执行许可
                self._throttler.release()

                # 标记任务完成
                self._work_queue.task_done()

        logger.debug(f"工作线程 {worker_id} 已退出")

    def get_stats(self) -> ConcurrencyStats:
        """获取统计信息"""
        with self._lock:
            stats = self._stats
            stats.queue_size = self._work_queue.qsize()

            # 计算平均等待时间
            total_tasks = self._stats.completed_tasks + self._stats.failed_tasks
            if total_tasks > 0:
                avg_wait = self._stats.total_wait_time / total_tasks
            else:
                avg_wait = 0.0

            return stats


class AsyncBatchProcessor:
    """
    异步批处理器

    批量处理任务，提高吞吐量
    """

    def __init__(
        self,
        batch_size: int = 10,
        max_wait_time: float = 1.0,
        max_workers: int = 5
    ):
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.max_workers = max_workers

        self._queue: deque = deque()
        self._futures: Dict[int, asyncio.Future] = {}
        self._batch_id = 0
        self._lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()
        self._batch_task: Optional[asyncio.Task] = None
        self._work_pool: Optional[AsyncWorkPool] = None

    async def start(self) -> None:
        """启动批处理器"""
        self._work_pool = AsyncWorkPool(self.max_workers)
        await self._work_pool.start()

        self._batch_task = asyncio.create_task(self._batch_loop())

    async def stop(self) -> None:
        """停止批处理器"""
        self._shutdown_event.set()

        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

        if self._work_pool:
            await self._work_pool.stop()

    async def process(
        self,
        func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs
    ) -> Any:
        """提交单个处理任务"""
        future = asyncio.Future()

        async with self._lock:
            task_id = self._batch_id
            self._batch_id += 1
            self._queue.append({
                "id": task_id,
                "func": func,
                "args": args,
                "kwargs": kwargs,
                "future": future
            })
            self._futures[task_id] = future

        return await future

    async def _batch_loop(self) -> None:
        """批处理循环"""
        while not self._shutdown_event.is_set():
            try:
                # 等待收集批次
                await asyncio.sleep(self.max_wait_time)

                # 收集批次任务
                batch = []
                async with self._lock:
                    while self._queue and len(batch) < self.batch_size:
                        batch.append(self._queue.popleft())

                if not batch:
                    continue

                # 提交批次任务
                await self._submit_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"批处理循环错误: {str(e)}")

    async def _submit_batch(self, batch: List[Dict[str, Any]]) -> None:
        """提交批次任务"""
        if not self._work_pool:
            return

        # 提交所有任务
        tasks = []
        for task in batch:
            future = task["future"]
            tasks.append(
                self._work_pool.submit(
                    task["func"],
                    *task["args"],
                    **task["kwargs"]
                )
            )

        # 等待所有任务完成
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 设置结果
            for task, result in zip(batch, results):
                task["future"].set_result(result)

        except Exception as e:
            logger.error(f"批次任务执行失败: {str(e)}")
            for task in batch:
                task["future"].set_exception(e)


class AsyncSemaphoreGroup:
    """
    异步信号量组

    管理多个不同类型的信号量
    """

    def __init__(self):
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._stats: Dict[str, ConcurrencyStats] = defaultdict(ConcurrencyStats)
        self._lock = asyncio.Lock()

    def create_semaphore(
        self,
        name: str,
        max_size: int,
        stats: ConcurrencyStats
    ) -> asyncio.Semaphore:
        """创建信号量"""
        self._semaphores[name] = asyncio.Semaphore(max_size)
        self._stats[name] = stats
        return self._semaphores[name]

    def get_semaphore(self, name: str) -> Optional[asyncio.Semaphore]:
        """获取信号量"""
        return self._semaphores.get(name)

    async def acquire(self, name: str) -> None:
        """获取信号量"""
        semaphore = self._semaphores.get(name)
        if not semaphore:
            raise ValueError(f"信号量 '{name}' 不存在")

        await semaphore.acquire()
        self._stats[name].active_tasks += 1
        self._stats[name].max_concurrent = max(
            self._stats[name].max_concurrent,
            self._stats[name].active_tasks
        )

    def release(self, name: str) -> None:
        """释放信号量"""
        semaphore = self._semaphores.get(name)
        if not semaphore:
            return

        semaphore.release()
        if self._stats[name].active_tasks > 0:
            self._stats[name].active_tasks -= 1

    def get_all_stats(self) -> Dict[str, ConcurrencyStats]:
        """获取所有统计"""
        return self._stats.copy()


# 预定义的并发配置
CONCURRENCY_CONFIGS = {
    "low": {
        "max_workers": 2,
        "max_concurrent": 5,
        "rate": 1.0
    },
    "medium": {
        "max_workers": 5,
        "max_concurrent": 10,
        "rate": 5.0
    },
    "high": {
        "max_workers": 10,
        "max_concurrent": 20,
        "rate": 10.0
    },
    "aggressive": {
        "max_workers": 20,
        "max_concurrent": 50,
        "rate": 20.0
    }
}


def get_concurrency_config(name: str) -> Dict[str, Any]:
    """获取预定义的并发配置"""
    return CONCURRENCY_CONFIGS.get(name, CONCURRENCY_CONFIGS["medium"])


@asynccontextmanager
async def async_throttle(
    throttler: AsyncThrottler,
    name: str = "default"
):
    """异步节流上下文管理器"""
    await throttler.acquire()
    try:
        yield
    finally:
        throttler.release()
