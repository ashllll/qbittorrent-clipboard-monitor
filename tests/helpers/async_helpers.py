"""异步测试辅助工具"""

import asyncio
from typing import Callable, Any, Optional
from contextlib import asynccontextmanager


class AsyncTestHelper:
    """异步测试辅助类"""

    @staticmethod
    async def run_coroutine(coro):
        """运行协程并返回结果"""
        return await coro

    @staticmethod
    def run_sync(coro):
        """同步运行异步协程（用于非 async 测试）"""
        try:
            loop = asyncio.get_running_loop()
            # 如果已经有事件循环，创建新任务
            return loop.create_task(coro)
        except RuntimeError:
            # 没有事件循环，创建新的
            return asyncio.run(coro)

    @staticmethod
    async def wait_for_condition(
        condition: Callable[[], bool],
        timeout: float = 5.0,
        interval: float = 0.1,
    ) -> bool:
        """等待条件满足
        
        Args:
            condition: 条件函数
            timeout: 超时时间
            interval: 检查间隔
            
        Returns:
            条件是否在超时前满足
        """
        elapsed = 0.0
        while elapsed < timeout:
            if condition():
                return True
            await asyncio.sleep(interval)
            elapsed += interval
        
        return False

    @staticmethod
    @asynccontextmanager
    async def timeout_context(timeout: float = 5.0):
        """超时上下文管理器
        
        Example:
            >>> async with AsyncTestHelper.timeout_context(1.0):
            ...     await long_running_operation()
        """
        try:
            yield
        except asyncio.TimeoutError:
            raise TimeoutError(f"操作超时（{timeout}秒）")

    @staticmethod
    async def gather_with_concurrency(
        coros: list,
        concurrency: int = 5,
    ) -> list:
        """限制并发数执行多个协程
        
        Args:
            coros: 协程列表
            concurrency: 最大并发数
            
        Returns:
            结果列表
        """
        semaphore = asyncio.Semaphore(concurrency)
        
        async def run_with_semaphore(coro):
            async with semaphore:
                return await coro
        
        return await asyncio.gather(
            *[run_with_semaphore(c) for c in coros],
            return_exceptions=True
        )

    @staticmethod
    def create_future(result: Any = None, exception: Optional[Exception] = None):
        """创建一个已完成的 Future
        
        Args:
            result: Future 的结果
            exception: 要设置的异常
            
        Returns:
            已完成的 Future
        """
        future = asyncio.Future()
        if exception:
            future.set_exception(exception)
        else:
            future.set_result(result)
        return future
