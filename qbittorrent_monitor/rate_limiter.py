"""
速率限制模块 - DoS防护

提供多种速率限制策略，防止滥用和DoS攻击。
遵循滑动窗口计数器算法和令牌桶算法。
"""

import time
import asyncio
from typing import Dict, Optional, List, Tuple, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from functools import wraps

from .exceptions import QBMonitorError


class RateLimitError(QBMonitorError):
    """速率限制错误"""
    pass


class RateLimitStrategy(Enum):
    """速率限制策略"""
    SLIDING_WINDOW = "sliding_window"  # 滑动窗口
    TOKEN_BUCKET = "token_bucket"      # 令牌桶
    FIXED_WINDOW = "fixed_window"      # 固定窗口


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    max_requests: int = 100           # 窗口内最大请求数
    window_seconds: float = 60.0      # 窗口大小（秒）
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    burst_size: int = 10              # 突发请求容量（令牌桶用）
    refill_rate: float = 1.0          # 令牌 refill 速率（每秒）


@dataclass
class RateLimitStatus:
    """速率限制状态"""
    is_limited: bool = False
    remaining: int = 0
    reset_time: float = 0.0
    retry_after: float = 0.0
    current_count: int = 0


class SlidingWindowCounter:
    """
    滑动窗口计数器
    
    在滑动时间窗口内统计请求数量，实现平滑的速率限制。
    """
    
    def __init__(self, window_size: float = 60.0, max_requests: int = 100):
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()
    
    async def check_and_record(self) -> Tuple[bool, RateLimitStatus]:
        """
        检查并记录请求
        
        Returns:
            Tuple[bool, RateLimitStatus]: (是否允许, 状态信息)
        """
        async with self._lock:
            now = time.time()
            window_start = now - self.window_size
            
            # 移除窗口外的请求记录
            while self.requests and self.requests[0] < window_start:
                self.requests.popleft()
            
            current_count = len(self.requests)
            remaining = max(0, self.max_requests - current_count)
            
            if current_count >= self.max_requests:
                # 计算重试时间
                oldest_request = self.requests[0]
                retry_after = oldest_request + self.window_size - now
                
                status = RateLimitStatus(
                    is_limited=True,
                    remaining=0,
                    reset_time=oldest_request + self.window_size,
                    retry_after=max(0, retry_after),
                    current_count=current_count
                )
                return False, status
            
            # 记录当前请求
            self.requests.append(now)
            
            # 计算reset时间
            if self.requests:
                reset_time = self.requests[0] + self.window_size
            else:
                reset_time = now + self.window_size
            
            status = RateLimitStatus(
                is_limited=False,
                remaining=remaining - 1,
                reset_time=reset_time,
                retry_after=0.0,
                current_count=current_count + 1
            )
            return True, status
    
    async def get_status(self) -> RateLimitStatus:
        """获取当前状态"""
        async with self._lock:
            now = time.time()
            window_start = now - self.window_size
            
            # 清理过期记录
            while self.requests and self.requests[0] < window_start:
                self.requests.popleft()
            
            current_count = len(self.requests)
            remaining = max(0, self.max_requests - current_count)
            
            reset_time = self.requests[0] + self.window_size if self.requests else now + self.window_size
            
            return RateLimitStatus(
                is_limited=current_count >= self.max_requests,
                remaining=remaining,
                reset_time=reset_time,
                retry_after=0.0 if current_count < self.max_requests else reset_time - now,
                current_count=current_count
            )
    
    def reset(self) -> None:
        """重置计数器"""
        self.requests.clear()


class TokenBucket:
    """
    令牌桶算法
    
    支持突发流量，同时保持平均速率限制。
    """
    
    def __init__(self, capacity: int = 10, refill_rate: float = 1.0):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_rate = refill_rate
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def _refill(self) -> None:
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
    
    async def acquire(self, tokens: int = 1, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """
        获取令牌
        
        Args:
            tokens: 需要的令牌数
            blocking: 是否阻塞等待
            timeout: 超时时间（秒）
            
        Returns:
            是否成功获取
        """
        async with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            if not blocking:
                return False
            
            # 计算需要等待的时间
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.refill_rate
            
            if timeout is not None and wait_time > timeout:
                return False
        
        # 等待后重试
        if timeout is not None:
            await asyncio.sleep(min(wait_time, timeout))
        else:
            await asyncio.sleep(wait_time)
        
        return await self.acquire(tokens, blocking=False)
    
    async def check(self, tokens: int = 1) -> Tuple[bool, RateLimitStatus]:
        """
        检查是否可用（不消耗令牌）
        
        Args:
            tokens: 需要的令牌数
            
        Returns:
            Tuple[bool, RateLimitStatus]: (是否可用, 状态)
        """
        async with self._lock:
            await self._refill()
            
            available = self.tokens >= tokens
            
            if available:
                retry_after = 0.0
            else:
                tokens_needed = tokens - self.tokens
                retry_after = tokens_needed / self.refill_rate
            
            status = RateLimitStatus(
                is_limited=not available,
                remaining=int(self.tokens),
                reset_time=time.time() + (self.capacity - self.tokens) / self.refill_rate,
                retry_after=retry_after,
                current_count=int(self.capacity - self.tokens)
            )
            
            return available, status
    
    async def consume(self, tokens: int = 1) -> Tuple[bool, RateLimitStatus]:
        """
        消费令牌
        
        Returns:
            Tuple[bool, RateLimitStatus]: (是否成功, 状态)
        """
        async with self._lock:
            await self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                status = RateLimitStatus(
                    is_limited=False,
                    remaining=int(self.tokens),
                    reset_time=time.time() + (self.capacity - self.tokens) / self.refill_rate,
                    retry_after=0.0,
                    current_count=int(self.capacity - self.tokens)
                )
                return True, status
            else:
                tokens_needed = tokens - self.tokens
                retry_after = tokens_needed / self.refill_rate
                status = RateLimitStatus(
                    is_limited=True,
                    remaining=0,
                    reset_time=time.time() + retry_after,
                    retry_after=retry_after,
                    current_count=int(self.capacity - self.tokens)
                )
                return False, status
    
    async def get_status(self) -> RateLimitStatus:
        """获取当前状态"""
        async with self._lock:
            await self._refill()
            
            return RateLimitStatus(
                is_limited=self.tokens <= 0,
                remaining=int(self.tokens),
                reset_time=time.time() + (self.capacity - self.tokens) / self.refill_rate,
                retry_after=0.0 if self.tokens > 0 else 1.0 / self.refill_rate,
                current_count=int(self.capacity - self.tokens)
            )
    
    def reset(self) -> None:
        """重置令牌桶"""
        self.tokens = float(self.capacity)
        self.last_refill = time.time()


class FixedWindowCounter:
    """
    固定窗口计数器
    
    在固定时间窗口内统计请求数量，实现简单但可能在窗口边界出现突发。
    """
    
    def __init__(self, window_size: float = 60.0, max_requests: int = 100):
        self.window_size = window_size
        self.max_requests = max_requests
        self.current_window = int(time.time() / window_size)
        self.count = 0
        self._lock = asyncio.Lock()
    
    async def check_and_record(self) -> Tuple[bool, RateLimitStatus]:
        """
        检查并记录请求
        
        Returns:
            Tuple[bool, RateLimitStatus]: (是否允许, 状态信息)
        """
        async with self._lock:
            now = time.time()
            window = int(now / self.window_size)
            
            # 检查是否进入新窗口
            if window > self.current_window:
                self.current_window = window
                self.count = 0
            
            if self.count >= self.max_requests:
                # 计算下一个窗口的开始时间
                next_window_start = (window + 1) * self.window_size
                retry_after = next_window_start - now
                
                status = RateLimitStatus(
                    is_limited=True,
                    remaining=0,
                    reset_time=next_window_start,
                    retry_after=retry_after,
                    current_count=self.count
                )
                return False, status
            
            self.count += 1
            next_window_start = (window + 1) * self.window_size
            
            status = RateLimitStatus(
                is_limited=False,
                remaining=self.max_requests - self.count,
                reset_time=next_window_start,
                retry_after=0.0,
                current_count=self.count
            )
            return True, status
    
    async def get_status(self) -> RateLimitStatus:
        """获取当前状态"""
        async with self._lock:
            now = time.time()
            window = int(now / self.window_size)
            
            if window > self.current_window:
                return RateLimitStatus(
                    is_limited=False,
                    remaining=self.max_requests,
                    reset_time=(window + 1) * self.window_size,
                    retry_after=0.0,
                    current_count=0
                )
            
            next_window_start = (window + 1) * self.window_size
            
            return RateLimitStatus(
                is_limited=self.count >= self.max_requests,
                remaining=max(0, self.max_requests - self.count),
                reset_time=next_window_start,
                retry_after=next_window_start - now if self.count >= self.max_requests else 0.0,
                current_count=self.count
            )
    
    def reset(self) -> None:
        """重置计数器"""
        self.current_window = int(time.time() / self.window_size)
        self.count = 0


class RateLimiter:
    """
    速率限制器 - 支持多维度限制
    
    支持按不同维度（IP、用户、API端点等）进行速率限制。
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self.counters: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
    
    def _create_counter(self) -> Any:
        """根据策略创建计数器"""
        if self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return SlidingWindowCounter(
                window_size=self.config.window_seconds,
                max_requests=self.config.max_requests
            )
        elif self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return TokenBucket(
                capacity=self.config.burst_size,
                refill_rate=self.config.refill_rate
            )
        elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
            return FixedWindowCounter(
                window_size=self.config.window_seconds,
                max_requests=self.config.max_requests
            )
        else:
            raise ValueError(f"未知的策略: {self.config.strategy}")
    
    async def _get_counter(self, key: str) -> Any:
        """获取或创建计数器"""
        async with self._lock:
            if key not in self.counters:
                self.counters[key] = self._create_counter()
            return self.counters[key]
    
    async def acquire(self, key: str = "default", tokens: int = 1) -> Tuple[bool, RateLimitStatus]:
        """
        获取许可
        
        Args:
            key: 限制维度标识
            tokens: 需要的令牌数（令牌桶策略）
            
        Returns:
            Tuple[bool, RateLimitStatus]: (是否成功, 状态)
        """
        counter = await self._get_counter(key)
        
        if isinstance(counter, TokenBucket):
            return await counter.consume(tokens)
        else:
            return await counter.check_and_record()
    
    async def check(self, key: str = "default", tokens: int = 1) -> Tuple[bool, RateLimitStatus]:
        """
        检查是否可用（不消耗额度）
        
        Args:
            key: 限制维度标识
            tokens: 需要的令牌数
            
        Returns:
            Tuple[bool, RateLimitStatus]: (是否可用, 状态)
        """
        counter = await self._get_counter(key)
        
        if isinstance(counter, TokenBucket):
            return await counter.check(tokens)
        else:
            status = await counter.get_status()
            return not status.is_limited, status
    
    async def get_status(self, key: str = "default") -> RateLimitStatus:
        """获取指定维度的状态"""
        counter = await self._get_counter(key)
        return await counter.get_status()
    
    async def reset(self, key: Optional[str] = None) -> None:
        """
        重置计数器
        
        Args:
            key: 要重置的维度，None表示重置所有
        """
        async with self._lock:
            if key is None:
                self.counters.clear()
            elif key in self.counters:
                self.counters[key].reset()
    
    async def cleanup_inactive(self, inactive_seconds: float = 300.0) -> int:
        """
        清理不活跃的计数器
        
        Args:
            inactive_seconds: 不活跃时间阈值
            
        Returns:
            清理的计数器数量
        """
        # 注意：当前实现不追踪最后访问时间
        # 实际应用中可能需要添加此功能
        return 0


# ============ 装饰器 ============

def rate_limited(
    limiter: Optional[RateLimiter] = None,
    key_func: Optional[Callable[..., str]] = None,
    error_message: str = "请求过于频繁，请稍后再试"
):
    """
    速率限制装饰器
    
    Args:
        limiter: 速率限制器实例
        key_func: 生成限制键的函数
        error_message: 限制时的错误信息
        
    Example:
        limiter = RateLimiter(RateLimitConfig(max_requests=10, window_seconds=60))
        
        @rate_limited(limiter, key_func=lambda user_id, **kwargs: f"user:{user_id}")
        async def api_call(user_id: str):
            return await fetch_data(user_id)
    """
    def decorator(func: Callable) -> Callable:
        nonlocal limiter
        if limiter is None:
            limiter = RateLimiter()
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成限制键
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = func.__name__
            
            # 检查速率限制
            allowed, status = await limiter.acquire(key)
            
            if not allowed:
                raise RateLimitError(
                    f"{error_message}（请在 {status.retry_after:.1f} 秒后重试）"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============ 专用速率限制器 ============

class ClipboardRateLimiter:
    """
    剪贴板监控专用速率限制器
    
    针对剪贴板监控场景的速率限制。
    """
    
    def __init__(self):
        # 磁力链接处理速率限制（每分钟最多100个）
        self.magnet_limiter = RateLimiter(
            RateLimitConfig(
                max_requests=100,
                window_seconds=60.0,
                strategy=RateLimitStrategy.SLIDING_WINDOW
            )
        )
        
        # API调用速率限制（每秒最多10次）
        self.api_limiter = RateLimiter(
            RateLimitConfig(
                burst_size=10,
                refill_rate=10.0,
                strategy=RateLimitStrategy.TOKEN_BUCKET
            )
        )
        
        # 分类请求速率限制（每分钟最多30次AI分类）
        self.classification_limiter = RateLimiter(
            RateLimitConfig(
                max_requests=30,
                window_seconds=60.0,
                strategy=RateLimitStrategy.SLIDING_WINDOW
            )
        )
    
    async def check_magnet(self, magnet_hash: str) -> Tuple[bool, RateLimitStatus]:
        """检查磁力链接处理速率"""
        return await self.magnet_limiter.acquire(f"magnet:{magnet_hash[:8]}")
    
    async def check_api_call(self, endpoint: str) -> Tuple[bool, RateLimitStatus]:
        """检查API调用速率"""
        return await self.api_limiter.acquire(f"api:{endpoint}")
    
    async def check_classification(self, method: str = "default") -> Tuple[bool, RateLimitStatus]:
        """检查分类请求速率"""
        return await self.classification_limiter.acquire(f"classify:{method}")
    
    async def get_all_status(self) -> Dict[str, RateLimitStatus]:
        """获取所有限制器状态"""
        return {
            "magnet": await self.magnet_limiter.get_status("magnet:default"),
            "api": await self.api_limiter.get_status("api:default"),
            "classification": await self.classification_limiter.get_status("classify:default"),
        }


# ============ 全局实例 ============

# 默认速率限制器
default_rate_limiter = RateLimiter()

# 剪贴板专用速率限制器
clipboard_rate_limiter = ClipboardRateLimiter()
