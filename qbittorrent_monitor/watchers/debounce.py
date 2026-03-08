"""防抖过滤器模块

提供时间窗口内的重复内容过滤功能。
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)


class DebounceFilter:
    """防抖过滤器
    
    防止在指定时间窗口内重复处理相同的磁力链接。
    使用滑动窗口机制，自动清理过期的记录。
    
    Attributes:
        debounce_seconds: 防抖时间窗口（秒）
        cleanup_multiplier: 清理乘数（超过此倍数时清理）
    
    Example:
        >>> filter = DebounceFilter(debounce_seconds=2.0)
        >>> if not filter.is_debounced("hash123"):
        ...     process_magnet(magnet)
        >>> # 2秒内再次检查同一 hash 会被防抖
        >>> filter.is_debounced("hash123")  # True
    """

    def __init__(
        self,
        debounce_seconds: float = 2.0,
        cleanup_multiplier: float = 2.0
    ):
        """初始化防抖过滤器
        
        Args:
            debounce_seconds: 防抖时间窗口（秒）
            cleanup_multiplier: 清理乘数，超过防抖窗口的此倍数时清理
        """
        self.debounce_seconds = debounce_seconds
        self.cleanup_multiplier = cleanup_multiplier
        self._pending: Dict[str, float] = {}  # hash -> timestamp
        self._stats = {
            "debounced": 0,
            "passed": 0,
            "cleaned": 0,
        }

    def is_debounced(self, content_hash: str) -> bool:
        """检查内容是否在防抖窗口内
        
        Args:
            content_hash: 内容哈希
            
        Returns:
            True 如果在防抖窗口内（应跳过），False 如果可以通过
        """
        now = time.time()
        
        if content_hash in self._pending:
            last_seen = self._pending[content_hash]
            if now - last_seen < self.debounce_seconds:
                self._stats["debounced"] += 1
                logger.debug(f"内容在防抖窗口内，跳过: {content_hash[:16]}...")
                return True
        
        # 更新时间戳
        self._pending[content_hash] = now
        self._stats["passed"] += 1
        
        # 定期清理
        if self._should_cleanup():
            self.cleanup()
        
        return False

    def touch(self, content_hash: str) -> None:
        """更新时间戳（不检查是否防抖）
        
        Args:
            content_hash: 内容哈希
        """
        self._pending[content_hash] = time.time()

    def cleanup(self) -> int:
        """清理过期的防抖记录
        
        Returns:
            清理的记录数量
        """
        now = time.time()
        threshold = self.debounce_seconds * self.cleanup_multiplier
        
        expired = [
            h for h, ts in self._pending.items()
            if now - ts > threshold
        ]
        
        for h in expired:
            del self._pending[h]
        
        self._stats["cleaned"] += len(expired)
        
        if expired:
            logger.debug(f"清理 {len(expired)} 条过期防抖记录")
        
        return len(expired)

    def clear(self) -> None:
        """清空所有防抖记录"""
        self._pending.clear()
        logger.debug("防抖过滤器已清空")

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息
        
        Returns:
            统计字典
        """
        return {
            **self._stats,
            "pending_count": len(self._pending),
        }

    def _should_cleanup(self) -> bool:
        """检查是否应该执行清理"""
        # 每100次检查清理一次
        total_checks = self._stats["debounced"] + self._stats["passed"]
        return total_checks > 0 and total_checks % 100 == 0

    def set_debounce_seconds(self, seconds: float) -> None:
        """动态设置防抖时间
        
        Args:
            seconds: 新的防抖时间（秒）
        """
        if seconds <= 0:
            raise ValueError("防抖时间必须大于0")
        self.debounce_seconds = seconds
