"""
增强的异常处理和重试机制

提供统一的重试装饰器、异常包装器和健壮性工具
"""

import asyncio
import functools
import logging
import time
from typing import (
    Optional, Callable, Any, Type, Union, List, Dict, TypeVar, Awaitable
)
from datetime import datetime, timedelta
from .exceptions import (
    QBittorrentMonitorError, NetworkError, ConfigError,
    AIApiError, QbtRateLimitError, AIRateLimitError
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class RetryableError(QBittorrentMonitorError):
    """可重试错误的基类"""
    pass


class NonRetryableError(QBittorrentMonitorError):
    """不可重试错误的基类"""
    pass


class ResourceExhaustedError(NonRetryableError):
    """资源耗尽错误（如连接池满）"""
    pass


class TimeoutError(QBittorrentMonitorError):
    """超时错误"""
    pass


class CircuitBreakerOpenError(NonRetryableError):
    """断路器开启错误"""
    pass


# 重试策略配置
class RetryConfig:
    """重试配置"""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_exceptions: Optional[List[Type[Exception]]] = None,
        non_retry_exceptions: Optional[List[Type[Exception]]] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_exceptions = retry_exceptions or [
            NetworkError,
            TimeoutError,
            QbtRateLimitError,
            AIRateLimitError,
            RetryableError
        ]
        self.non_retry_exceptions = non_retry_exceptions or [
            ConfigError,
            ResourceExhaustedError,
            CircuitBreakerOpenError
        ]

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """判断是否应该重试"""
        # 达到最大尝试次数
        if attempt >= self.max_attempts:
            return False

        # 检查是否是不可重试异常
        for exc_type in self.non_retry_exceptions:
            if isinstance(exception, exc_type):
                return False

        # 检查是否需要特定延迟
        if hasattr(exception, 'retry_after'):
            return True

        # 检查是否在可重试异常列表中
        for exc_type in self.retry_exceptions:
            if isinstance(exception, exc_type):
                return True

        # 网络错误和超时默认重试
        if isinstance(exception, (ConnectionError, TimeoutError, OSError)):
            return True

        return False

    def get_delay(self, attempt: int) -> float:
        """获取延迟时间"""
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)

        if self.jitter:
            import random
            # 添加±20%的随机抖动
            jitter_range = delay * 0.2
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)


def retry(
    config: Optional[RetryConfig] = None,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exponential_base: float = 2.0,
    retry_exceptions: Optional[List[Type[Exception]]] = None
) -> Callable:
    """
    重试装饰器

    Args:
        config: 重试配置，如果不提供则使用默认配置
        max_attempts: 最大尝试次数
        base_delay: 基础延迟时间
        exponential_base: 指数退避基数
        retry_exceptions: 需要重试的异常类型列表
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            retry_cfg = config or RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                exponential_base=exponential_base,
                retry_exceptions=retry_exceptions
            )

            last_exception = None
            start_time = time.time()

            for attempt in range(1, retry_cfg.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not retry_cfg.should_retry(e, attempt):
                        logger.error(
                            f"函数 {func.__name__} 不支持重试，异常: {type(e).__name__}: {str(e)}"
                        )
                        raise

                    if attempt < retry_cfg.max_attempts:
                        delay = retry_cfg.get_delay(attempt)
                        logger.warning(
                            f"函数 {func.__name__} 第 {attempt} 次尝试失败: {type(e).__name__}, "
                            f"{delay:.2f}秒后重试 (总共{max_attempts}次)"
                        )

                        # 如果异常有retry_after属性，使用该延迟
                        if hasattr(e, 'retry_after'):
                            delay = e.retry_after

                        await asyncio.sleep(delay)

            # 所有重试都失败了
            elapsed = time.time() - start_time
            logger.error(
                f"函数 {func.__name__} 经过 {retry_cfg.max_attempts} 次尝试后仍失败 "
                f"(用时 {elapsed:.2f}s)，最后异常: {type(last_exception).__name__}: {str(last_exception)}"
            )
            raise last_exception

        return wrapper
    return decorator


class CircuitBreaker:
    """
    增强的断路器实现

    状态转换:
    CLOSED -> OPEN (失败率超过阈值)
    OPEN -> HALF_OPEN (超时后)
    HALF_OPEN -> CLOSED (成功)
    HALF_OPEN -> OPEN (失败)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
        on_state_change: Optional[Callable[[str], None]] = None
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.on_state_change = on_state_change

        self.failure_count = 0
        self.success_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = 0
        self._lock = asyncio.Lock()

    def _change_state(self, new_state: str):
        """改变状态"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            logger.info(f"断路器状态变化: {old_state} -> {new_state}")
            if self.on_state_change:
                self.on_state_change(new_state)

    async def allow(self) -> bool:
        """检查是否允许执行"""
        async with self._lock:
            now = time.time()

            if self.state == "CLOSED":
                return True

            if self.state == "OPEN":
                # 检查是否超时，可以进入HALF_OPEN状态
                if now - self.last_failure_time >= self.timeout:
                    self._change_state("HALF_OPEN")
                    self.success_count = 0
                    return True
                return False

            if self.state == "HALF_OPEN":
                return True

        return False

    async def record_success(self):
        """记录成功"""
        async with self._lock:
            if self.state == "HALF_OPEN":
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self._change_state("CLOSED")
                    self.failure_count = 0
            elif self.state == "CLOSED":
                self.failure_count = max(0, self.failure_count - 1)

    async def record_failure(self):
        """记录失败"""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == "CLOSED":
                if self.failure_count >= self.failure_threshold:
                    self._change_state("OPEN")
            elif self.state == "HALF_OPEN":
                self._change_state("OPEN")

    def get_state(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time
        }


class AsyncSemaphore:
    """异步信号量包装器，带超时和重试"""

    def __init__(
        self,
        max_size: int,
        acquire_timeout: float = 30.0,
        max_waiters: int = 1000
    ):
        self.semaphore = asyncio.Semaphore(max_size)
        self.max_size = max_size
        self.acquire_timeout = acquire_timeout
        self.max_waiters = max_waiters
        self.current_waiters = 0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """获取信号量"""
        async with self._lock:
            if self.current_waiters >= self.max_waiters:
                raise ResourceExhaustedError(
                    f"等待信号量的任务数已达上限 ({self.max_waiters})"
                )
            self.current_waiters += 1

        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=self.acquire_timeout)
        finally:
            async with self._lock:
                self.current_waiters -= 1

    def release(self):
        """释放信号量"""
        self.semaphore.release()

    def available(self) -> int:
        """获取可用信号量数量"""
        return self.max_size - self.semaphore._value


class ConnectionPool:
    """连接池管理"""

    def __init__(
        self,
        create_func: Callable[[], Awaitable[Any]],
        max_size: int = 10,
        min_size: int = 2,
        acquire_timeout: float = 30.0,
        idle_timeout: float = 300.0,
        max_lifetime: float = 3600.0
    ):
        self.create_func = create_func
        self.max_size = max_size
        self.min_size = min_size
        self.acquire_timeout = acquire_timeout
        self.idle_timeout = idle_timeout
        self.max_lifetime = max_lifetime

        self._pool: List[Any] = []
        self._used: set = set()
        self._lock = asyncio.Lock()
        self._created_count = 0

    async def acquire(self) -> Any:
        """获取连接"""
        async with self._lock:
            # 尝试从池中获取可用连接
            while self._pool:
                conn = self._pool.pop()
                if self._is_connection_valid(conn):
                    self._used.add(conn)
                    return conn

            # 池中没有可用连接，创建新连接
            if self._created_count < self.max_size:
                self._created_count += 1
                conn = await self.create_func()
                self._used.add(conn)
                return conn

            # 达到最大连接数，等待释放
            raise ResourceExhaustedError(
                f"连接池已满 ({self.max_size}/{self.max_size})"
            )

    async def release(self, conn: Any):
        """释放连接"""
        async with self._lock:
            if conn in self._used:
                self._used.remove(conn)

                if self._is_connection_valid(conn):
                    if len(self._pool) < self.max_size:
                        self._pool.append(conn)
                else:
                    self._created_count -= 1

    def _is_connection_valid(self, conn: Any) -> bool:
        """检查连接是否有效"""
        try:
            # 检查是否有健康检查方法
            if hasattr(conn, 'ping'):
                return conn.ping()
            if hasattr(conn, 'is_alive'):
                return conn.is_alive()
            if hasattr(conn, '_closed'):
                return not conn._closed
            return True
        except Exception:
            logger.debug("检查连接状态失败")
            return False

    async def close_all(self):
        """关闭所有连接"""
        async with self._lock:
            for conn in self._pool:
                if hasattr(conn, 'close'):
                    try:
                        await conn.close()
                    except Exception as e:
                        logger.debug(f"关闭连接失败: {str(e)}")
            self._pool.clear()
            self._used.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计"""
        return {
            "pool_size": len(self._pool),
            "used_size": len(self._used),
            "created_count": self._created_count,
            "available": self.max_size - len(self._used)
        }


# 预定义的重试配置
RETRY_CONFIGS = {
    "default": RetryConfig(max_attempts=3, base_delay=1.0),
    "network": RetryConfig(
        max_attempts=5,
        base_delay=2.0,
        max_delay=30.0,
        exponential_base=2.0
    ),
    "api": RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        retry_exceptions=[AIApiError, NetworkError, TimeoutError]
    ),
    "qbittorrent": RetryConfig(
        max_attempts=3,
        base_delay=2.0,
        retry_exceptions=[QbtRateLimitError, NetworkError]
    ),
    "aggressive": RetryConfig(
        max_attempts=10,
        base_delay=0.5,
        max_delay=10.0,
        exponential_base=1.5
    )
}


def get_retry_config(name: str) -> RetryConfig:
    """获取预定义的重试配置"""
    return RETRY_CONFIGS.get(name, RETRY_CONFIGS["default"])
