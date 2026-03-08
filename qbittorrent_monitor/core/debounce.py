"""防抖服务 - 蜂群优化版

独立职责：管理磁力链接的防抖处理。
"""

from __future__ import annotations

import time
import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(order=True)
class DebounceEntry:
    """防抖条目"""
    expire_time: float
    magnet_hash: str = field(compare=False)


class DebounceService:
    """防抖服务
    
    使用堆优化过期清理，时间复杂度从 O(n) 降到 O(log n)。
    """
    
    def __init__(
        self,
        debounce_seconds: float = 2.0,
        cleanup_multiplier: float = 2.0,
        max_size: int = 1000
    ):
        self.debounce_seconds = debounce_seconds
        self.cleanup_multiplier = cleanup_multiplier
        self.max_size = max_size
        
        self._entries: Dict[str, float] = {}  # hash -> timestamp
        self._heap: List[DebounceEntry] = []   # 过期时间堆
    
    def should_skip(self, magnet_hash: str) -> bool:
        """检查是否应该跳过（在防抖窗口内）
        
        Args:
            magnet_hash: 磁力链接hash
            
        Returns:
            是否应该跳过
        """
        now = time.time()
        
        # 清理过期条目
        self._cleanup_expired(now)
        
        # 检查是否在防抖窗口内
        if magnet_hash in self._entries:
            last_seen = self._entries[magnet_hash]
            if now - last_seen < self.debounce_seconds:
                return True
        
        # 更新条目
        self._entries[magnet_hash] = now
        expire_time = now + self.debounce_seconds * self.cleanup_multiplier
        heapq.heappush(self._heap, DebounceEntry(expire_time, magnet_hash))
        
        return False
    
    def _cleanup_expired(self, now: float) -> None:
        """清理过期的防抖记录"""
        while self._heap and self._heap[0].expire_time <= now:
            entry = heapq.heappop(self._heap)
            if entry.magnet_hash in self._entries:
                del self._entries[entry.magnet_hash]
    
    def clear(self) -> None:
        """清空所有防抖记录"""
        self._entries.clear()
        self._heap.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """获取防抖统计"""
        return {
            "active_entries": len(self._entries),
            "heap_size": len(self._heap),
        }
