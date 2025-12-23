"""
重试机制模块

提供统一的指数退避重试、断路器模式、连接池管理等功能，增强系统可靠性。
"""

import asyncio
import functools
import logging
import random
import time
from typing import (
    Any, Callable, Dict, List, Optional, Type, TypeVar, Union, Awaitable,
    Tuple
)
from datetime import datetime, timedelta

from .exceptions import (
    QBittorrentMonitorError, NetworkError, NetworkTimeoutError, NetworkConnectionError,
    QbtAuthError, QbtRateLimitError, QbtPermissionError, QbtServerError,
    AIError, AIApiError, AICreditError, AIRateLimitError, AIResponseError,
    ResourceError, ResourceTimeoutError, ResourceExhaustedError,
    SecurityError, AuthenticationError, AuthorizationError,
    ConcurrencyError, DeadlockError, TaskTimeoutError
)
from .metrics import MetricsTracker

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Any)

# 重试条件回调
RetryPredicate = Callable[[Exception, int], bool]
# 重试回调
RetryCallback = Callable[[Exception, int, float], None]


class RetryableError(QBittorrentMonitorError):
    """可重试错误基类"""
    pass


class NonRetryableError(QBittorrentMonitorError):
    """不可重试错误基类"""
    pass


class RetryConfig:
    """重试配置类"""

    DEFAULT_MAX_ATTEMPTS = 3
    DEFAULT_BASE_DELAY = 1.0
    DEFAULT_MAX_DELAY = 60.0
    DEFAULT_EXPONENTIAL_BASE = 2.0
    DEFAULT_JITTER = 0.2
    DEFAULT_MAX_TOTAL_DELAY = 300.0  # 最大总延迟5分钟

    def __init__(
        self,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
        exponential_base: float = DEFAULT_EXPONENTIAL_BASE,
        jitter: float = DEFAULT_JITTER,
        max_total_delay: float = DEFAULT_MAX_TOTAL_DELAY,
        retry_exceptions: Optional[List[Type[Exception]]] = None,
        non_retry_exceptions: Optional[List[Type[Exception]]] = None,
        retry_predicate: Optional[RetryPredicate] = None,
        on_retry: Optional[RetryCallback] = None,
        use_exponential_backoff_with_jitter: bool = True,
        fixed_delay: Optional[float] = None,
        respect_retry_after_header: bool = True,
    ):
        """
        重试配置参数
        
        Args:
            max_attempts: 最大重试次数
            base_delay: 初始延迟时间
            max_delay: 最大延迟时间
            exponential_base: 指数退避基数
            jitter: 抖动比例 (0.0-1.0)
            max_total_delay: 最大总延迟时间
            retry_exceptions: 可重试异常类型列表
            non_retry_exceptions: 不可重试异常类型列表
            retry_predicate: 自定义重试条件判断函数
            on_retry: 重试回调函数
            use_exponential_backoff_with_jitter: 是否使用指数退避加抖动
            fixed_delay: 固定延迟时间，如果设置则忽略指数退避
            respect_retry_after_header: 是否遵循Retry-After头部
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.max_total_delay = max_total_delay
        self.retry_exceptions = retry_exceptions or [
            NetworkError,
            NetworkTimeoutError,
            NetworkConnectionError,
            QbtRateLimitError,
            AIRateLimitError,
            AIApiError,
            QbtServerError,
            ResourceTimeoutError,
            TaskTimeoutError,
            RetryableError
        ]
        self.non_retry_exceptions = non_retry_exceptions or [
            ConfigError,
            QbtPermissionError,
            QbtAuthError,
            AICreditError,
            AuthenticationError,
            AuthorizationError,
            NonRetryableError,
            ResourceExhaustedError,
            DeadlockError
        ]
        self.retry_predicate = retry_predicate
        self.on_retry = on_retry
        self.use_exponential_backoff_with_jitter = use_exponential_backoff_with_jitter
        self.fixed_delay = fixed_delay
        self.respect_retry_after_header = respect_retry_after_header

    def should_retry(self, exception: Exception, attempt: int, elapsed_time: float = 0.0) -> bool:
        """
        判断是否应该重试
        
        Args:
            exception: 异常对象
            attempt: 当前尝试次数 (从1开始)
            elapsed_time: 已用时间（秒）
        
        Returns:
            bool: 是否应该重试
        """
        # 达到最大尝试次数
        if attempt >= self.max_attempts:
            return False
        
        # 检查是否超过最大总延迟时间
        if elapsed_time > self.max_total_delay:
            return False
        
        # 检查是否是不可重试异常
        for exc_type in self.non_retry_exceptions:
            if isinstance(exception, exc_type):
                logger.debug(f"不可重试异常: {type(exception).__name__}")
                return False
        
        # 检查是否有自定义重试条件
        if self.retry_predicate and not self.retry_predicate(exception, attempt):
            return False
        
        # 如果有retry_after属性，优先使用
        if hasattr(exception, 'retry_after') and self.respect_retry_after_header:
            return True
        
        # 检查是否在可重试异常列表中
        for exc_type in self.retry_exceptions:
            if isinstance(exception, exc_type):
                logger.debug(f"可重试异常: {type(exception).__name__}")
                return True
        
        # 其他可重试的异常类型
        if isinstance(exception, (ConnectionError, TimeoutError, OSError)):
            logger.debug(f"系统可重试异常: {type(exception).__name__}")
            return True
        
        logger.debug(f"默认不可重试异常: {type(exception).__name__}")
        return False

    def get_delay(self, attempt: int, exception: Optional[Exception] = None) -> float:
        """
        获取延迟时间
        
        Args:
            attempt: 当前尝试次数 (从1开始)
            exception: 异常对象，如果有retry_after属性则优先使用
        
        Returns:
            float: 延迟时间（秒）
        """
        # 如果异常有retry_after属性，优先使用
        if exception and hasattr(exception, 'retry_after') and self.respect_retry_after_header:
            delay = float(exception.retry_after)
            logger.debug(f"使用异常推荐的延迟时间: {delay}秒")
            return delay
        
        # 如果配置了固定延迟，使用固定延迟
        if self.fixed_delay is not None:
            delay = self.fixed_delay
            logger.debug(f"使用固定延迟: {delay}秒")
            return delay
        
        # 使用指数退避
        if self.use_exponential_backoff_with_jitter:
            # 计算基础延迟
            delay = self.base_delay * (self.exponential_base ** (attempt - 1))
            delay = min(delay, self.max_delay)
            
            # 添加抖动
            if self.jitter > 0:
                jitter_range = delay * self.jitter
                delay += random.uniform(-jitter_range, jitter_range)
            
            logger.debug(f"指数退避延迟 (尝试{attempt}): {delay:.2f}秒")
            return max(0, delay)
        
        # 不使用抖动
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)
        logger.debug(f"指数退避延迟 (尝试{attempt}): {delay:.2f}秒")
        return max(0, delay)


class RetryMetrics:
    """重试统计指标"""
    
    def __init__(self):
        self.total_attempts = 0
        self.successful_attempts = 0
        self.failed_attempts = 0
        self.retry_count = 0
        self.last_retry_time = None
        self.total_retry_delay = 0.0
        self.exception_types = {}
        self._lock = asyncio.Lock()
    
    async def record_attempt(self, success: bool, exception: Optional[Exception] = None):
        """记录一次尝试"""
        async with self._lock:
            self.total_attempts += 1
            if success:
                self.successful_attempts += 1
            else:
                self.failed_attempts += 1
                if exception:
                    exc_type = type(exception).__name__
                    self.exception_types[exc_type] = self.exception_types.get(exc_type, 0) + 1
    
    async def record_retry(self, delay: float, exception: Optional[Exception] = None):
        """记录一次重试"""
        async with self._lock:
            self.retry_count += 1
            self.total_retry_delay += delay
            self.last_retry_time = datetime.now()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "failed_attempts": self.failed_attempts,
            "retry_count": self.retry_count,
            "success_rate": (
                self.successful_attempts / self.total_attempts
                if self.total_attempts > 0 else 0
            ),
            "avg_retry_delay": (
                self.total_retry_delay / self.retry_count
                if self.retry_count > 0 else 0
            ),
            "last_retry_time": self.last_retry_time.isoformat() if self.last_retry_time else None,
            "exception_distribution": dict(self.exception_types)
        }


async def retry(
    config: Optional[RetryConfig] = None,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retry_exceptions: Optional[List[Type[Exception]]] = None,
    non_retry_exceptions: Optional[List[Type[Exception]]] = None,
    retry_predicate: Optional[RetryPredicate] = None,
    on_retry: Optional[RetryCallback] = None,
    fixed_delay: Optional[float] = None,
    use_metrics: bool = True,
    metrics_name: Optional[str] = None
) -> Callable:
    """
    异步重试装饰器
    
    Args:
        config: 重试配置对象，如果提供则忽略其他参数
        max_attempts: 最大重试次数
        base_delay: 初始延迟时间
        max_delay: 最大延迟时间
        exponential_base: 指数退避基数
        retry_exceptions: 可重试异常类型列表
        non_retry_exceptions: 不可重试异常类型列表
        retry_predicate: 自定义重试条件判断函数
        on_retry: 重试回调函数
        fixed_delay: 固定延迟时间
        use_metrics: 是否记录重试指标
        metrics_name: 指标名称
    
    Returns:
        Callable: 装饰器函数
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        # 创建配置对象
        retry_config = config or RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            retry_exceptions=retry_exceptions,
            non_retry_exceptions=non_retry_exceptions,
            retry_predicate=retry_predicate,
            on_retry=on_retry,
            fixed_delay=fixed_delay
        )
        
        # 创建重试指标收集器
        metrics = RetryMetrics() if use_metrics else None
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            start_time = time.time()
            attempt = 0
            
            # 记录指标
            if metrics:
                metrics_tracker = MetricsTracker.get_instance(metrics_name or f"retry:{func.__name__}")
            
            while attempt < retry_config.max_attempts:
                attempt += 1
                elapsed_time = time.time() - start_time
                
                try:
                    logger.debug(f"执行函数 {func.__name__}，尝试 {attempt}/{retry_config.max_attempts}")
                    
                    # 执行函数
                    result = await func(*args, **kwargs)
                    
                    # 记录成功
                    if metrics:
                        await metrics.record_attempt(success=True)
                        metrics_tracker.record("retry_success", 1)
                        metrics_tracker.record("retry_attempts", attempt)
                    
                    return result
                
                except Exception as e:
                    last_exception = e
                    logger.debug(f"函数 {func.__name__} 尝试 {attempt} 失败: {type(e).__name__}: {str(e)}")
                    
                    # 记录失败
                    if metrics:
                        await metrics.record_attempt(success=False, exception=e)
                        metrics_tracker.record("retry_failure", 1)
                    
                    # 检查是否应该重试
                    if not retry_config.should_retry(e, attempt, elapsed_time):
                        logger.debug(f"函数 {func.__name__} 不可重试，抛出异常")
                        break
                    
                    # 计算延迟时间
                    delay = retry_config.get_delay(attempt, e)
                    
                    # 记录重试
                    if metrics:
                        await metrics.record_retry(delay, e)
                    
                    # 执行重试回调
                    if retry_config.on_retry:
                        try:
                            retry_config.on_retry(e, attempt, delay)
                        except Exception as callback_error:
                            logger.error(f"重试回调执行失败: {str(callback_error)}")
                    
                    # 记录重试日志
                    logger.warning(
                        f"函数 {func.__name__} 尝试 {attempt} 失败: {type(e).__name__}, "
                        f"{delay:.2f}秒后重试 (总共{max_attempts}次)"
                    )
                    
                    # 如果还有重试机会，等待后继续
                    if attempt < retry_config.max_attempts:
                        await asyncio.sleep(delay)
            
            # 所有重试都失败了，抛出最后一个异常
            elapsed_total = time.time() - start_time
            logger.error(
                f"函数 {func.__name__} 经过 {retry_config.max_attempts} 次尝试后仍失败 "
                f"(用时 {elapsed_total:.2f}s)，最后异常: {type(last_exception).__name__}: {str(last_exception)}"
            )
            
            # 记录最终失败
            if metrics:
                metrics_tracker.record("retry_final_failure", 1)
                metrics_tracker.record("retry_total_time", elapsed_total)
            
            raise last_exception
        
        return wrapper
    return decorator


class CircuitBreaker:
    """
    断路器实现
    
    状态转换:
    CLOSED -> OPEN (失败率超过阈值)
    OPEN -> HALF_OPEN (超时后)
    HALF_OPEN -> CLOSED (成功)
    HALF_OPEN -> OPEN (失败)
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
        on_state_change: Optional[Callable[[str, str], None]] = None,
        metrics_name: Optional[str] = None
    ):
        """
        初始化断路器
        
        Args:
            failure_threshold: 失败阈值，达到此值则开启断路器
            success_threshold: 成功阈值，半开状态下成功此值次则关闭断路器
            timeout: 断路器开启后的超时时间（秒）
            expected_exception: 预期的异常类型
            on_state_change: 状态变化回调函数
            metrics_name: 指标名称
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.on_state_change = on_state_change
        
        self.failure_count = 0
        self.success_count = 0
        self.state = self.CLOSED
        self.last_failure_time = 0
        self._lock = asyncio.Lock()
        
        self._metrics_tracker = MetricsTracker.get_instance(metrics_name or f"circuit_breaker:{id(self)}")

    def _change_state(self, new_state: str):
        """改变状态"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self._metrics_tracker.record("circuit_breaker_state", new_state)
            logger.info(f"断路器状态变化: {old_state} -> {new_state}")
            
            if self.on_state_change:
                try:
                    self.on_state_change(old_state, new_state)
                except Exception as e:
                    logger.error(f"断路器状态变化回调执行失败: {str(e)}")

    async def allow(self) -> bool:
        """检查是否允许执行"""
        async with self._lock:
            now = time.time()

            if self.state == self.CLOSED:
                return True

            if self.state == self.OPEN:
                # 检查是否超时，可以进入HALF_OPEN状态
                if now - self.last_failure_time >= self.timeout:
                    self._change_state(self.HALF_OPEN)
                    self.success_count = 0
                    return True
                return False

            if self.state == self.HALF_OPEN:
                return True

        return False

    async def record_success(self):
        """记录成功"""
        async with self._lock:
            self._metrics_tracker.record("circuit_breaker_success", 1)
            
            if self.state == self.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self._change_state(self.CLOSED)
                    self.failure_count = 0
            elif self.state == self.CLOSED:
                # 逐渐减少失败计数，防止断路器过于敏感
                self.failure_count = max(0, self.failure_count - 1)

    async def record_failure(self):
        """记录失败"""
        async with self._lock:
            self._metrics_tracker.record("circuit_breaker_failure", 1)
            
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == self.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self._change_state(self.OPEN)
            elif self.state == self.HALF_OPEN:
                self._change_state(self.OPEN)

    def get_state(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "time_until_half_open": max(0, self.timeout - (time.time() - self.last_failure_time))
                if self.state == self.OPEN else 0
        }


class RetryWithCircuitBreaker:
    """结合断路器的重试器"""

    def __init__(
        self,
        func: Callable[..., Awaitable[T]],
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        name: Optional[str] = None
    ):
        """
        初始化重试器
        
        Args:
            func: 要重试的函数
            retry_config: 重试配置
            circuit_breaker: 断路器，如果为None则创建默认断路器
            name: 名称，用于日志和监控
        """
        self.func = func
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5,
            timeout=60,
            metrics_name=f"circuit_breaker:{name or func.__name__}"
        )
        self.name = name or func.__name__
        self.metrics = RetryMetrics()
        self._metrics_tracker = MetricsTracker.get_instance(f"retry_with_circuit_breaker:{self.name}")

    async def __call__(*args, **kwargs) -> T:
        """调用函数，使用重试和断路器保护"""
        # 从参数中获取self（如果是绑定方法）
        self = args[0]
        func_args = args[1:] if len(args) > 1 else ()
        func_kwargs = kwargs

        # 检查断路器是否允许执行
        if not await self.circuit_breaker.allow():
            raise CircuitBreakerOpenError(f"断路器开启，无法执行函数 {self.name}")

        # 执行函数，使用重试装饰器保护
        start_time = time.time()
        attempt = 0
        last_exception = None

        while attempt < self.retry_config.max_attempts:
            attempt += 1
            elapsed_time = time.time() - start_time

            try:
                logger.debug(f"执行函数 {self.name}，尝试 {attempt}/{self.retry_config.max_attempts}")
                
                # 执行函数
                result = await self.func(*func_args, **func_kwargs)
                
                # 记录成功
                await self.metrics.record_attempt(success=True)
                await self.circuit_breaker.record_success()
                self._metrics_tracker.record("success", 1)
                self._metrics_tracker.record("attempts", attempt)
                
                return result

            except Exception as e:
                last_exception = e
                logger.debug(f"函数 {self.name} 尝试 {attempt} 失败: {type(e).__name__}: {str(e)}")
                
                # 记录失败
                await self.metrics.record_attempt(success=False, exception=e)
                
                # 检查是否应该重试
                if not self.retry_config.should_retry(e, attempt, elapsed_time):
                    logger.debug(f"函数 {self.name} 不可重试，抛出异常")
                    await self.circuit_breaker.record_failure()
                    break

                # 计算延迟时间
                delay = self.retry_config.get_delay(attempt, e)
                
                # 记录重试
                await self.metrics.record_retry(delay, e)

                # 如果还有重试机会，等待后继续
                if attempt < self.retry_config.max_attempts:
                    await asyncio.sleep(delay)

        # 所有重试都失败了，抛出最后一个异常
        elapsed_total = time.time() - start_time
        logger.error(
            f"函数 {self.name} 经过 {self.retry_config.max_attempts} 次尝试后仍失败 "
            f"(用时 {elapsed_total:.2f}s)，最后异常: {type(last_exception).__name__}: {str(last_exception)}"
        )
        
        # 记录最终失败
        await self.circuit_breaker.record_failure()
        self._metrics_tracker.record("final_failure", 1)
        self._metrics_tracker.record("total_time", elapsed_total)
        
        raise last_exception


class CircuitBreakerOpenError(NonRetryableError):
    """断路器开启错误"""
    
    def __init__(self, message: str):
        super().__init__(message)
        self.error_code = "CIRCUIT_BREAKER_OPEN"


# 预定义的重试配置
PREDEFINED_RETRY_CONFIGS = {
    "default": RetryConfig(),
    "network": RetryConfig(
        max_attempts=5,
        base_delay=2.0,
        max_delay=30.0,
        exponential_base=2.0,
        retry_exceptions=[
            NetworkError,
            NetworkTimeoutError,
            NetworkConnectionError,
            ConnectionError,
            TimeoutError,
            OSError
        ]
    ),
    "api": RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        retry_exceptions=[AIApiError, NetworkError, TimeoutError],
        respect_retry_after_header=True
    ),
    "qbittorrent": RetryConfig(
        max_attempts=3,
        base_delay=2.0,
        retry_exceptions=[QbtRateLimitError, NetworkError],
        respect_retry_after_header=True
    ),
    "aggressive": RetryConfig(
        max_attempts=10,
        base_delay=0.5,
        max_delay=10.0,
        exponential_base=1.5
    ),
    "conservative": RetryConfig(
        max_attempts=2,
        base_delay=5.0,
        max_delay=60.0,
        exponential_base=1.5
    )
}


def get_retry_config(name: str) -> RetryConfig:
    """获取预定义的重试配置"""
    return PREDEFINED_RETRY_CONFIGS.get(name, PREDEFINED_RETRY_CONFIGS["default"])


def create_retry_with_circuit_breaker(
    func: Callable[..., Awaitable[T]],
    config_name: str = "default",
    circuit_breaker_config: Optional[Dict[str, Any]] = None,
    name: Optional[str] = None
) -> RetryWithCircuitBreaker:
    """
    创建带有断路器的重试器
    
    Args:
        func: 要保护的函数
        config_name: 重试配置名称
        circuit_breaker_config: 断路器配置字典
        name: 名称
    
    Returns:
        RetryWithCircuitBreaker: 重试器实例
    """
    retry_config = get_retry_config(config_name)
    circuit_breaker = None
    
    if circuit_breaker_config:
        circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_config.get("failure_threshold", 5),
            success_threshold=circuit_breaker_config.get("success_threshold", 3),
            timeout=circuit_breaker_config.get("timeout", 60.0),
            metrics_name=f"circuit_breaker:{name or func.__name__}"
        )
    
    return RetryWithCircuitBreaker(
        func=func,
        retry_config=retry_config,
        circuit_breaker=circuit_breaker,
        name=name
    )

