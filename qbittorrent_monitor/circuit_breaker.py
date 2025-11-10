"""
统一熔断器和限流机制模块

提供集中的熔断器、限流器和流量控制功能
"""

import asyncio
import time
import logging
from typing import Any, Dict, Optional, Callable, List, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict

from .exceptions_enhanced import CircuitBreakerOpenError
from .monitoring import get_metrics_collector, get_health_checker, HealthStatus

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"  # 正常状态
    OPEN = "open"  # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态


class RateLimitStrategy(Enum):
    """限流策略"""
    FIXED_WINDOW = "fixed_window"  # 固定窗口
    SLIDING_WINDOW = "sliding_window"  # 滑动窗口
    TOKEN_BUCKET = "token_bucket"  # 令牌桶
    LEAKY_BUCKET = "leaky_bucket"  # 漏桶


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5  # 失败阈值
    success_threshold: int = 3  # 成功阈值（半开状态下）
    timeout: float = 60.0  # 超时时间（秒）
    monitor_window: float = 60.0  # 监控窗口（秒）
    expected_exception: type = Exception  # 预期的异常类型
    recovery_timeout: float = 30.0  # 恢复超时（秒）
    name: str = ""  # 名称


@dataclass
class RateLimitConfig:
    """限流器配置"""
    rate: float  # 速率（请求/秒）
    capacity: Optional[float] = None  # 容量
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET  # 策略
    burst_factor: float = 2.0  # 突发因子
    name: str = ""  # 名称


class UnifiedCircuitBreaker:
    """
    统一熔断器

    提供智能熔断、重试和恢复机制
    """

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.last_state_change = time.time()
        self._lock = asyncio.Lock()

        # 统计信息
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "rejected_calls": 0,
            "state_changes": 0,
            "avg_response_time": 0.0,
            "error_rate": 0.0
        }

        # 调用历史（用于监控窗口计算）
        self.call_history: deque = deque(maxlen=1000)

    async def allow_request(self) -> bool:
        """检查是否允许请求"""
        async with self._lock:
            now = time.time()

            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                # 检查是否超时，可以进入半开状态
                if now - self.last_state_change >= self.config.timeout:
                    await self._change_state(CircuitState.HALF_OPEN)
                    logger.info(f"熔断器进入半开状态: {self.config.name}")
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                return True

        return False

    async def record_success(self, response_time: float = 0.0):
        """记录成功"""
        async with self._lock:
            self.success_count += 1
            self.stats["successful_calls"] += 1

            # 更新平均响应时间
            self._update_response_time(response_time)

            if self.state == CircuitState.HALF_OPEN:
                if self.success_count >= self.config.success_threshold:
                    await self._change_state(CircuitState.CLOSED)
                    logger.info(f"熔断器恢复正常: {self.config.name}")
            elif self.state == CircuitState.CLOSED:
                # 减少失败计数（滑动窗口）
                self._prune_old_failures()

    async def record_failure(self, response_time: float = 0.0):
        """记录失败"""
        async with self._lock:
            self.failure_count += 1
            self.stats["failed_calls"] += 1
            self.last_failure_time = time.time()

            # 更新平均响应时间
            self._update_response_time(response_time)

            # 记录调用历史
            self.call_history.append({
                "time": time.time(),
                "success": False
            })

            if self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    await self._change_state(CircuitState.OPEN)
                    logger.warning(
                        f"熔断器打开 (失败次数: {self.failure_count}): {self.config.name}"
                    )
            elif self.state == CircuitState.HALF_OPEN:
                await self._change_state(CircuitState.OPEN)
                logger.warning(
                    f"半开状态下失败，熔断器重新打开: {self.config.name}"
                )

    async def _change_state(self, new_state: CircuitState):
        """改变状态"""
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.time()
        self.stats["state_changes"] += 1

        # 重置计数器
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.success_count = 0

        logger.info(
            f"熔断器状态变化: {old_state.value} -> {new_state.value}: {self.config.name}"
        )

    def _update_response_time(self, response_time: float):
        """更新平均响应时间"""
        if self.stats["total_calls"] == 0:
            self.stats["avg_response_time"] = response_time
        else:
            alpha = 0.1  # 指数移动平均
            self.stats["avg_response_time"] = (
                alpha * response_time +
                (1 - alpha) * self.stats["avg_response_time"]
            )

    def _prune_old_failures(self):
        """清理旧的失败记录"""
        now = time.time()
        # 这里可以添加清理逻辑，但为了简化，暂时使用计数器衰减

    async def call(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        通过熔断器调用函数

        Args:
            func: 要调用的函数
            *args: 位置参数
            fallback: 降级函数
            **kwargs: 关键字参数

        Returns:
            函数结果或降级结果

        Raises:
            CircuitBreakerOpenError: 熔断器开启时
        """
        # 检查是否允许请求
        if not await self.allow_request():
            self.stats["rejected_calls"] += 1
            logger.warning(
                f"熔断器拒绝请求: {self.config.name}"
            )
            if fallback:
                logger.info(f"执行降级函数: {self.config.name}")
                return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
            raise CircuitBreakerOpenError(f"熔断器开启: {self.config.name}")

        start_time = time.time()
        self.stats["total_calls"] += 1

        try:
            # 调用函数
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # 记录成功
            response_time = (time.time() - start_time) * 1000
            await self.record_success(response_time)

            return result

        except self.config.expected_exception as e:
            # 记录失败
            response_time = (time.time() - start_time) * 1000
            await self.record_failure(response_time)

            # 尝试降级
            if fallback:
                logger.info(f"执行降级函数: {self.config.name}")
                try:
                    if asyncio.iscoroutinefunction(fallback):
                        return await fallback(*args, **kwargs)
                    else:
                        return fallback(*args, **kwargs)
                except Exception as fallback_error:
                    logger.error(f"降级函数执行失败: {str(fallback_error)}")
                    raise e

            raise

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        async def _get_stats():
            return {
                "name": self.config.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "last_failure_time": self.last_failure_time,
                "last_state_change": self.last_state_change,
                "stats": self.stats.copy()
            }
        return asyncio.create_task(_get_stats())

    def reset(self):
        """重置熔断器"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.last_state_change = time.time()
        self.call_history.clear()
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "rejected_calls": 0,
            "state_changes": 0,
            "avg_response_time": 0.0,
            "error_rate": 0.0
        }
        logger.info(f"熔断器已重置: {self.config.name}")


class FixedWindowRateLimiter:
    """固定窗口限流器"""

    def __init__(self, rate: float, window_size: float = 1.0):
        self.rate = rate
        self.window_size = window_size
        self.tokens = rate
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> bool:
        """获取令牌"""
        async with self._lock:
            now = time.time()
            # 补充令牌
            time_passed = now - self.last_refill
            self.tokens = min(self.rate, self.tokens + time_passed * self.rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def time_until_available(self, tokens: float = 1.0) -> float:
        """计算等待时间"""
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.rate


class SlidingWindowRateLimiter:
    """滑动窗口限流器"""

    def __init__(self, rate: float, window_size: float = 60.0):
        self.rate = rate
        self.window_size = window_size
        self.requests: deque = deque()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> bool:
        """获取令牌"""
        async with self._lock:
            now = time.time()
            # 清理过期请求
            while self.requests and now - self.requests[0] > self.window_size:
                self.requests.popleft()

            # 检查是否超过限制
            if len(self.requests) + tokens <= self.rate:
                # 记录请求
                for _ in range(int(tokens)):
                    self.requests.append(now)
                return True
            return False

    def get_request_count(self, window: Optional[float] = None) -> int:
        """获取窗口内的请求数"""
        if window is None:
            window = self.window_size

        now = time.time()
        count = 0
        for req_time in self.requests:
            if now - req_time <= window:
                count += 1
        return count


class TokenBucketRateLimiter:
    """令牌桶限流器"""

    def __init__(self, rate: float, capacity: Optional[float] = None):
        self.rate = rate
        self.capacity = capacity or rate * 2
        self.tokens = self.capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> bool:
        """获取令牌"""
        async with self._lock:
            now = time.time()
            # 补充令牌
            time_passed = now - self.last_refill
            self.tokens = min(
                self.capacity,
                self.tokens + time_passed * self.rate
            )
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def available_tokens(self) -> float:
        """获取可用令牌数"""
        now = time.time()
        time_passed = now - self.last_refill
        return min(
            self.capacity,
            self.tokens + time_passed * self.rate
        )


class LeakyBucketRateLimiter:
    """漏桶限流器"""

    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self.water_level = 0.0
        self.last_leak = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> bool:
        """获取令牌"""
        async with self._lock:
            now = time.time()
            # 漏水
            time_passed = now - self.last_leak
            self.water_level = max(0, self.water_level - time_passed * self.rate)
            self.last_leak = now

            # 检查是否有足够空间
            if self.water_level + tokens <= self.capacity:
                self.water_level += tokens
                return True
            return False


class UnifiedRateLimiter:
    """
    统一限流器

    支持多种限流策略的统一接口
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.stats = {
            "total_requests": 0,
            "allowed_requests": 0,
            "rejected_requests": 0,
            "avg_wait_time": 0.0
        }
        self._lock = asyncio.Lock()

        # 根据策略选择实现
        if config.strategy == RateLimitStrategy.FIXED_WINDOW:
            self._limiter = FixedWindowRateLimiter(config.rate)
        elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            self._limiter = SlidingWindowRateLimiter(config.rate)
        elif config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            capacity = config.capacity or config.rate * config.burst_factor
            self._limiter = TokenBucketRateLimiter(config.rate, capacity)
        elif config.strategy == RateLimitStrategy.LEAKY_BUCKET:
            if not config.capacity:
                raise ValueError("漏桶策略需要指定容量")
            self._limiter = LeakyBucketRateLimiter(config.rate, config.capacity)
        else:
            raise ValueError(f"不支持的限流策略: {config.strategy}")

    async def acquire(self, tokens: float = 1.0, block: bool = True) -> bool:
        """
        获取令牌

        Args:
            tokens: 请求的令牌数
            block: 是否阻塞等待

        Returns:
            是否获取成功
        """
        async with self._lock:
            self.stats["total_requests"] += 1

        if block:
            # 阻塞模式
            while True:
                if await self._limiter.acquire(tokens):
                    async with self._lock:
                        self.stats["allowed_requests"] += 1
                    return True
                # 计算等待时间
                if hasattr(self._limiter, 'time_until_available'):
                    wait_time = self._limiter.time_until_available(tokens)
                else:
                    wait_time = 1.0 / self.config.rate

                await asyncio.sleep(min(wait_time, 1.0))
        else:
            # 非阻塞模式
            if await self._limiter.acquire(tokens):
                async with self._lock:
                    self.stats["allowed_requests"] += 1
                return True
            else:
                async with self._lock:
                    self.stats["rejected_requests"] += 1
                return False

    async def rate_limit(
        self,
        func: Callable,
        *args,
        tokens: float = 1.0,
        block: bool = True,
        **kwargs
    ) -> Any:
        """
        限流调用

        Args:
            func: 要调用的函数
            *args: 位置参数
            tokens: 消耗的令牌数
            block: 是否阻塞
            **kwargs: 关键字参数

        Returns:
            函数结果
        """
        # 获取令牌
        acquired = await self.acquire(tokens, block=block)
        if not acquired:
            logger.warning(f"请求被限流器拒绝: {self.config.name}")
            raise RuntimeError(f"Rate limit exceeded: {self.config.name}")

        # 调用函数
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "name": self.config.name,
            "strategy": self.config.strategy.value,
            "rate": self.config.rate,
            "capacity": getattr(self._limiter, 'capacity', None),
            "stats": self.stats.copy()
        }


class TrafficController:
    """
    流量控制器

    结合熔断器和限流器，提供完整的流量控制
    """

    def __init__(self):
        self.circuit_breakers: Dict[str, UnifiedCircuitBreaker] = {}
        self.rate_limiters: Dict[str, UnifiedRateLimiter] = {}
        self._lock = asyncio.Lock()

    def add_circuit_breaker(
        self,
        name: str,
        config: CircuitBreakerConfig
    ) -> UnifiedCircuitBreaker:
        """添加熔断器"""
        cb = UnifiedCircuitBreaker(config)
        self.circuit_breakers[name] = cb
        logger.info(f"添加熔断器: {name}")
        return cb

    def get_circuit_breaker(self, name: str) -> Optional[UnifiedCircuitBreaker]:
        """获取熔断器"""
        return self.circuit_breakers.get(name)

    def add_rate_limiter(
        self,
        name: str,
        config: RateLimitConfig
    ) -> UnifiedRateLimiter:
        """添加限流器"""
        rl = UnifiedRateLimiter(config)
        self.rate_limiters[name] = rl
        logger.info(f"添加限流器: {name}")
        return rl

    def get_rate_limiter(self, name: str) -> Optional[UnifiedRateLimiter]:
        """获取限流器"""
        return self.rate_limiters.get(name)

    async def call(
        self,
        func: Callable,
        circuit_breaker_name: Optional[str] = None,
        rate_limiter_name: Optional[str] = None,
        rate_limiter_tokens: float = 1.0,
        fallback: Optional[Callable] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        通过流量控制器调用函数

        Args:
            func: 要调用的函数
            circuit_breaker_name: 熔断器名称
            rate_limiter_name: 限流器名称
            rate_limiter_tokens: 限流器令牌数
            fallback: 降级函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数结果
        """
        # 限流
        if rate_limiter_name:
            limiter = self.get_rate_limiter(rate_limiter_name)
            if limiter:
                acquired = await limiter.acquire(rate_limiter_tokens)
                if not acquired:
                    if fallback:
                        logger.info(f"限流降级: {rate_limiter_name}")
                        return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
                    raise RuntimeError(f"Rate limit exceeded: {rate_limiter_name}")

        # 熔断
        if circuit_breaker_name:
            breaker = self.get_circuit_breaker(circuit_breaker_name)
            if breaker:
                return await breaker.call(func, *args, fallback=fallback, **kwargs)

        # 直接调用
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有统计信息"""
        stats = {
            "circuit_breakers": {},
            "rate_limiters": {},
            "total_circuit_breakers": len(self.circuit_breakers),
            "total_rate_limiters": len(self.rate_limiters)
        }

        # 熔断器统计
        for name, cb in self.circuit_breakers.items():
            stats["circuit_breakers"][name] = {
                "state": cb.state.value,
                "failure_count": cb.failure_count,
                "success_count": cb.success_count,
                "stats": cb.stats.copy()
            }

        # 限流器统计
        for name, rl in self.rate_limiters.items():
            stats["rate_limiters"][name] = rl.get_stats()

        return stats


# 全局流量控制器实例
_global_traffic_controller: Optional[TrafficController] = None


def get_global_traffic_controller() -> TrafficController:
    """获取全局流量控制器"""
    global _global_traffic_controller
    if _global_traffic_controller is None:
        _global_traffic_controller = TrafficController()
    return _global_traffic_controller


# 预定义的配置模板
CIRCUIT_BREAKER_CONFIGS = {
    "default": CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=3,
        timeout=60.0,
        name="default"
    ),
    "strict": CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout=30.0,
        name="strict"
    ),
    "relaxed": CircuitBreakerConfig(
        failure_threshold=10,
        success_threshold=5,
        timeout=120.0,
        name="relaxed"
    )
}

RATE_LIMITER_CONFIGS = {
    "slow": RateLimitConfig(
        rate=1.0,
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        name="slow"
    ),
    "normal": RateLimitConfig(
        rate=10.0,
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        name="normal"
    ),
    "fast": RateLimitConfig(
        rate=100.0,
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        name="fast"
    )
}


def get_circuit_breaker_config(name: str) -> CircuitBreakerConfig:
    """获取预定义的熔断器配置"""
    return CIRCUIT_BREAKER_CONFIGS.get(name, CIRCUIT_BREAKER_CONFIGS["default"])


def get_rate_limiter_config(name: str) -> RateLimitConfig:
    """获取预定义的限流器配置"""
    return RATE_LIMITER_CONFIGS.get(name, RATE_LIMITER_CONFIGS["normal"])
