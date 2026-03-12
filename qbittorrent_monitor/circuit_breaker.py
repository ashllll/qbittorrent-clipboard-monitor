"""
熔断器模块 - 故障保护

实现熔断器模式，防止级联故障和系统过载。
遵循"快速失败"原则，提高系统稳定性。
"""

import time
import asyncio
import logging
from typing import Optional, Callable, Any, Type, Dict, List
from enum import Enum
from dataclasses import dataclass, field
from functools import wraps

from .exceptions_unified import QBittorrentMonitorError


logger = logging.getLogger(__name__)


class CircuitBreakerError(QBittorrentMonitorError):
    """熔断器错误"""
    pass


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"       # 正常状态（熔断器关闭）
    OPEN = "open"           # 熔断状态（熔断器打开）
    HALF_OPEN = "half_open" # 半开状态（测试恢复）


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5          # 触发熔断的失败次数
    success_threshold: int = 3          # 半开状态恢复所需成功次数
    timeout_seconds: float = 60.0       # 熔断后尝试恢复的时间
    half_open_max_calls: int = 3        # 半开状态最大测试调用数
    exception_types: Tuple[Type[Exception], ...] = field(
        default_factory=lambda: (Exception,)
    )                                   # 触发熔断的异常类型
    
    def __post_init__(self):
        # 确保exception_types是元组
        if isinstance(self.exception_types, list):
            self.exception_types = tuple(self.exception_types)


@dataclass
class CircuitBreakerStats:
    """熔断器统计信息"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    open_count: int = 0                 # 熔断次数统计


class CircuitBreaker:
    """
    熔断器
    
    实现熔断器模式，当失败率达到阈值时自动熔断，
    防止级联故障和系统资源耗尽。
    
    状态转换：
    - CLOSED -> OPEN: 连续失败次数达到阈值
    - OPEN -> HALF_OPEN: 熔断时间过后
    - HALF_OPEN -> CLOSED: 连续成功次数达到阈值
    - HALF_OPEN -> OPEN: 测试调用失败
    
    Example:
        breaker = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=5, timeout_seconds=60)
        )
        
        @breaker
        async def unstable_api():
            # 可能失败的API调用
            pass
        
        try:
            result = await unstable_api()
        except CircuitBreakerError:
            # 熔断器打开，快速失败
            pass
    """
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None, name: str = "default"):
        self.config = config or CircuitBreakerConfig()
        self.name = name
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        self._half_open_calls = 0  # 半开状态的测试调用计数
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        执行受保护的函数调用
        
        Args:
            func: 要调用的函数
            *args, **kwargs: 函数参数
            
        Returns:
            函数返回值
            
        Raises:
            CircuitBreakerError: 熔断器打开时
            Exception: 函数执行异常
        """
        async with self._lock:
            # 检查是否可以从熔断状态恢复
            await self._try_transition_from_open()
            
            # 检查熔断器状态
            if self.state == CircuitState.OPEN:
                logger.warning(f"熔断器 '{self.name}' 已打开，快速失败")
                raise CircuitBreakerError(
                    f"服务暂时不可用（熔断器已打开），请 {self.config.timeout_seconds} 秒后重试"
                )
            
            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    logger.warning(f"熔断器 '{self.name}' 半开状态测试调用数已达上限")
                    raise CircuitBreakerError(
                        f"服务正在恢复中，请稍后再试"
                    )
                self._half_open_calls += 1
        
        # 执行函数（在锁外执行以避免阻塞）
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await self._on_success()
            return result
            
        except Exception as e:
            # 检查是否应该触发熔断
            if isinstance(e, self.config.exception_types):
                await self._on_failure()
            raise
    
    async def _on_success(self) -> None:
        """处理成功调用"""
        async with self._lock:
            self.stats.total_calls += 1
            self.stats.total_successes += 1
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            self.stats.last_success_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # 半开状态累计成功
                self.stats.success_count += 1
                
                if self.stats.success_count >= self.config.success_threshold:
                    # 恢复成功，关闭熔断器
                    logger.info(f"熔断器 '{self.name}' 恢复成功，切换到关闭状态")
                    self._transition_to_closed()
    
    async def _on_failure(self) -> None:
        """处理失败调用"""
        async with self._lock:
            self.stats.total_calls += 1
            self.stats.total_failures += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = time.time()
            
            if self.state == CircuitState.CLOSED:
                self.stats.failure_count += 1
                
                if self.stats.failure_count >= self.config.failure_threshold:
                    # 触发熔断
                    logger.error(
                        f"熔断器 '{self.name}' 触发熔断："
                        f"连续失败 {self.stats.failure_count} 次"
                    )
                    self._transition_to_open()
                    
            elif self.state == CircuitState.HALF_OPEN:
                # 半开状态测试失败，重新打开
                logger.warning(f"熔断器 '{self.name}' 半开状态测试失败，重新打开")
                self._transition_to_open()
    
    async def _try_transition_from_open(self) -> None:
        """尝试从打开状态转换到半开状态"""
        if self.state != CircuitState.OPEN:
            return
        
        if self.stats.last_failure_time is None:
            return
        
        elapsed = time.time() - self.stats.last_failure_time
        if elapsed >= self.config.timeout_seconds:
            logger.info(f"熔断器 '{self.name}' 超时时间已过，切换到半开状态")
            self._transition_to_half_open()
    
    def _transition_to_open(self) -> None:
        """转换到打开状态"""
        self.state = CircuitState.OPEN
        self.stats.state = CircuitState.OPEN
        self.stats.failure_count = 0
        self.stats.success_count = 0
        self.stats.open_count += 1
        self._half_open_calls = 0
    
    def _transition_to_half_open(self) -> None:
        """转换到半开状态"""
        self.state = CircuitState.HALF_OPEN
        self.stats.state = CircuitState.HALF_OPEN
        self.stats.failure_count = 0
        self.stats.success_count = 0
        self._half_open_calls = 0
    
    def _transition_to_closed(self) -> None:
        """转换到关闭状态"""
        self.state = CircuitState.CLOSED
        self.stats.state = CircuitState.CLOSED
        self.stats.failure_count = 0
        self.stats.success_count = 0
        self._half_open_calls = 0
    
    def __call__(self, func: Callable) -> Callable:
        """装饰器支持"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)
        
        # 附加熔断器引用
        wrapper._circuit_breaker = self
        return wrapper
    
    async def get_stats(self) -> CircuitBreakerStats:
        """获取熔断器统计信息"""
        async with self._lock:
            # 返回副本
            return CircuitBreakerStats(
                state=self.stats.state,
                failure_count=self.stats.failure_count,
                success_count=self.stats.success_count,
                last_failure_time=self.stats.last_failure_time,
                last_success_time=self.stats.last_success_time,
                total_calls=self.stats.total_calls,
                total_failures=self.stats.total_failures,
                total_successes=self.stats.total_successes,
                consecutive_failures=self.stats.consecutive_failures,
                consecutive_successes=self.stats.consecutive_successes,
                open_count=self.stats.open_count,
            )
    
    async def reset(self) -> None:
        """手动重置熔断器"""
        async with self._lock:
            logger.info(f"熔断器 '{self.name}' 手动重置")
            self.state = CircuitState.CLOSED
            self.stats = CircuitBreakerStats()
            self._half_open_calls = 0
    
    async def force_open(self) -> None:
        """强制打开熔断器"""
        async with self._lock:
            logger.warning(f"熔断器 '{self.name}' 被强制打开")
            self._transition_to_open()
    
    async def force_close(self) -> None:
        """强制关闭熔断器"""
        async with self._lock:
            logger.info(f"熔断器 '{self.name}' 被强制关闭")
            self._transition_to_closed()


class CircuitBreakerRegistry:
    """
    熔断器注册表
    
    管理多个熔断器实例，支持按名称获取。
    """
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        获取或创建熔断器
        
        Args:
            name: 熔断器名称
            config: 熔断器配置
            
        Returns:
            熔断器实例
        """
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(config, name)
            return self._breakers[name]
    
    async def get(self, name: str) -> Optional[CircuitBreaker]:
        """获取熔断器"""
        async with self._lock:
            return self._breakers.get(name)
    
    async def remove(self, name: str) -> bool:
        """移除熔断器"""
        async with self._lock:
            if name in self._breakers:
                del self._breakers[name]
                return True
            return False
    
    async def get_all_stats(self) -> Dict[str, CircuitBreakerStats]:
        """获取所有熔断器统计信息"""
        async with self._lock:
            stats = {}
            for name, breaker in self._breakers.items():
                stats[name] = await breaker.get_stats()
            return stats
    
    async def reset_all(self) -> None:
        """重置所有熔断器"""
        async with self._lock:
            for breaker in self._breakers.values():
                await breaker.reset()


# ============ 专用熔断器配置 ============

# qBittorrent API 熔断器配置
QB_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    success_threshold=3,
    timeout_seconds=60.0,
    half_open_max_calls=3,
    exception_types=(Exception,)  # 捕获所有异常
)

# AI 分类熔断器配置
AI_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    success_threshold=2,
    timeout_seconds=120.0,  # AI服务恢复可能需要更长时间
    half_open_max_calls=2,
    exception_types=(Exception,)
)

# 数据库熔断器配置
DB_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=10,
    success_threshold=5,
    timeout_seconds=30.0,
    half_open_max_calls=5,
    exception_types=(Exception,)
)

# 剪贴板读取熔断器配置
CLIPBOARD_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=20,    # 剪贴板读取失败容忍度更高
    success_threshold=5,
    timeout_seconds=10.0,
    half_open_max_calls=5,
    exception_types=(Exception,)
)


# ============ 全局注册表 ============

circuit_breaker_registry = CircuitBreakerRegistry()


async def get_qb_circuit_breaker() -> CircuitBreaker:
    """获取qBittorrent熔断器"""
    return await circuit_breaker_registry.get_or_create("qbittorrent", QB_CIRCUIT_CONFIG)


async def get_ai_circuit_breaker() -> CircuitBreaker:
    """获取AI分类熔断器"""
    return await circuit_breaker_registry.get_or_create("ai_classifier", AI_CIRCUIT_CONFIG)


async def get_db_circuit_breaker() -> CircuitBreaker:
    """获取数据库熔断器"""
    return await circuit_breaker_registry.get_or_create("database", DB_CIRCUIT_CONFIG)


async def get_clipboard_circuit_breaker() -> CircuitBreaker:
    """获取剪贴板熔断器"""
    return await circuit_breaker_registry.get_or_create("clipboard", CLIPBOARD_CIRCUIT_CONFIG)


# ============ 实用装饰器 ============

def with_circuit_breaker(
    breaker_name: str,
    config: Optional[CircuitBreakerConfig] = None,
    fallback: Optional[Callable] = None
):
    """
    熔断器装饰器
    
    Args:
        breaker_name: 熔断器名称
        config: 熔断器配置
        fallback: 熔断时的回退函数
        
    Example:
        @with_circuit_breaker("api_service", QB_CIRCUIT_CONFIG)
        async def call_api():
            return await fetch_data()
        
        @with_circuit_breaker("api_service", fallback=default_value)
        async def call_api_with_fallback():
            return await fetch_data()
    """
    def decorator(func: Callable) -> Callable:
        breaker: Optional[CircuitBreaker] = None
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal breaker
            if breaker is None:
                breaker = await circuit_breaker_registry.get_or_create(
                    breaker_name, config
                )
            
            try:
                return await breaker.call(func, *args, **kwargs)
            except CircuitBreakerError:
                if fallback is not None:
                    if asyncio.iscoroutinefunction(fallback):
                        return await fallback(*args, **kwargs)
                    else:
                        return fallback(*args, **kwargs)
                raise
        
        return wrapper
    return decorator


# ============ 熔断器组 ============

class CircuitBreakerGroup:
    """
    熔断器组
    
    管理多个相关熔断器，实现更复杂的熔断策略。
    """
    
    def __init__(self, breakers: Dict[str, CircuitBreaker]):
        self.breakers = breakers
    
    async def are_all_closed(self) -> bool:
        """检查所有熔断器是否都关闭"""
        for breaker in self.breakers.values():
            stats = await breaker.get_stats()
            if stats.state != CircuitState.CLOSED:
                return False
        return True
    
    async def is_any_open(self) -> bool:
        """检查是否有熔断器打开"""
        for breaker in self.breakers.values():
            stats = await breaker.get_stats()
            if stats.state == CircuitState.OPEN:
                return True
        return False
    
    async def get_open_count(self) -> int:
        """获取打开的熔断器数量"""
        count = 0
        for breaker in self.breakers.values():
            stats = await breaker.get_stats()
            if stats.state == CircuitState.OPEN:
                count += 1
        return count
    
    async def reset_all(self) -> None:
        """重置所有熔断器"""
        for breaker in self.breakers.values():
            await breaker.reset()


# 创建系统熔断器组
async def get_system_circuit_breaker_group() -> CircuitBreakerGroup:
    """获取系统熔断器组"""
    breakers = {
        "qbittorrent": await get_qb_circuit_breaker(),
        "ai_classifier": await get_ai_circuit_breaker(),
        "database": await get_db_circuit_breaker(),
        "clipboard": await get_clipboard_circuit_breaker(),
    }
    return CircuitBreakerGroup(breakers)
