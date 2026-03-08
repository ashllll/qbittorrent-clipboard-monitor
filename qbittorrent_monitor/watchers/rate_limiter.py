"""速率限制器模块

提供处理频率限制功能，防止系统过载。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    max_per_second: float = 10.0  # 每秒最大处理数
    max_per_minute: float = 100.0  # 每分钟最大处理数
    burst_size: int = 5  # 突发处理容量


class RateLimiter:
    """速率限制器
    
    使用令牌桶算法限制处理频率，防止系统过载。
    
    Attributes:
        config: 速率限制配置
    
    Example:
        >>> limiter = RateLimiter(max_per_second=5.0, burst_size=3)
        >>> if limiter.try_acquire():
        ...     process_item()
        >>> # 或者等待直到可以处理
        >>> await limiter.acquire()
        >>> process_item()
    """

    def __init__(
        self,
        max_per_second: float = 10.0,
        max_per_minute: float = 100.0,
        burst_size: int = 5
    ):
        """初始化速率限制器
        
        Args:
            max_per_second: 每秒最大处理数
            max_per_minute: 每分钟最大处理数
            burst_size: 突发处理容量
        """
        self.config = RateLimitConfig(
            max_per_second=max_per_second,
            max_per_minute=max_per_minute,
            burst_size=burst_size
        )
        
        # 令牌桶
        self._tokens = float(burst_size)
        self._last_update = time.time()
        
        # 每分钟统计
        self._minute_timestamps: List[float] = []
        
        # 统计
        self._stats = {
            "allowed": 0,
            "denied": 0,
            "waited": 0.0,
        }

    def try_acquire(self) -> bool:
        """尝试获取处理许可
        
        Returns:
            True 如果允许处理，False 如果应拒绝
        """
        self._update_tokens()
        self._cleanup_minute_history()
        
        # 检查每分钟限制
        if len(self._minute_timestamps) >= self.config.max_per_minute:
            self._stats["denied"] += 1
            return False
        
        # 检查令牌桶
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            self._minute_timestamps.append(time.time())
            self._stats["allowed"] += 1
            return True
        
        self._stats["denied"] += 1
        return False

    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """获取处理许可（阻塞直到获得或超时）
        
        Args:
            timeout: 超时时间（秒），None 表示无限等待
            
        Returns:
            True 如果获得许可，False 如果超时
        """
        import asyncio
        
        start_time = time.time()
        
        while True:
            if self.try_acquire():
                return True
            
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
                wait_time = min(0.1, timeout - elapsed)
            else:
                wait_time = 0.1
            
            self._stats["waited"] += wait_time
            await asyncio.sleep(wait_time)

    def get_wait_time(self) -> float:
        """获取预计等待时间
        
        Returns:
            预计需要等待的秒数
        """
        self._update_tokens()
        
        if self._tokens >= 1.0:
            return 0.0
        
        # 计算需要多少时间才能积累足够的令牌
        tokens_needed = 1.0 - self._tokens
        time_needed = tokens_needed / self.config.max_per_second
        
        return time_needed

    def get_stats(self) -> Dict[str, float]:
        """获取统计信息
        
        Returns:
            统计字典
        """
        return {
            **self._stats,
            "current_tokens": self._tokens,
            "current_rpm": len(self._minute_timestamps),
        }

    def _update_tokens(self) -> None:
        """更新令牌桶"""
        now = time.time()
        elapsed = now - self._last_update
        
        # 根据时间添加令牌
        tokens_to_add = elapsed * self.config.max_per_second
        self._tokens = min(
            self.config.burst_size,
            self._tokens + tokens_to_add
        )
        
        self._last_update = now

    def _cleanup_minute_history(self) -> None:
        """清理超过一分钟的历史记录"""
        now = time.time()
        cutoff = now - 60.0
        
        self._minute_timestamps = [
            ts for ts in self._minute_timestamps
            if ts > cutoff
        ]

    def reset(self) -> None:
        """重置速率限制器状态"""
        self._tokens = float(self.config.burst_size)
        self._last_update = time.time()
        self._minute_timestamps.clear()
        self._stats = {"allowed": 0, "denied": 0, "waited": 0.0}
        logger.debug("速率限制器已重置")


class BatchRateLimiter:
    """批量速率限制器
    
    用于限制批量处理的速率。
    
    Attributes:
        max_batch_size: 每批最大数量
        min_interval: 批次间最小间隔（秒）
    """

    def __init__(
        self,
        max_batch_size: int = 100,
        min_interval: float = 1.0
    ):
        """初始化批量速率限制器
        
        Args:
            max_batch_size: 每批最大数量
            min_interval: 批次间最小间隔（秒）
        """
        self.max_batch_size = max_batch_size
        self.min_interval = min_interval
        self._last_batch_time = 0.0
        self._stats = {
            "batches_processed": 0,
            "items_processed": 0,
            "batches_throttled": 0,
        }

    def limit_batch(self, items: List) -> List:
        """限制批量大小
        
        Args:
            items: 待处理的项目列表
            
        Returns:
            本批应处理的项目子集
        """
        now = time.time()
        
        # 检查是否需要节流
        if now - self._last_batch_time < self.min_interval:
            self._stats["batches_throttled"] += 1
            return []
        
        # 限制批次大小
        batch = items[:self.max_batch_size]
        
        self._last_batch_time = now
        self._stats["batches_processed"] += 1
        self._stats["items_processed"] += len(batch)
        
        return batch

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self._stats.copy()
