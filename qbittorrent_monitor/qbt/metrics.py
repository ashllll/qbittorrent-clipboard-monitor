"""
性能监控器

收集和统计API请求性能数据，包括：
- 请求计数
- 错误计数
- 响应时间统计
- 缓存命中统计
- 性能报告生成
"""

import time
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class MetricsCollector:
    """性能指标收集器"""

    def __init__(self):
        self._counters: Dict[str, int] = {}
        self._response_times: List[float] = []
        self._lock = None  # 在使用时初始化
        self._last_request_time = None

    async def init(self):
        """初始化锁"""
        import asyncio
        if self._lock is None:
            self._lock = asyncio.Lock()

    def inc(self, name: str, value: int = 1) -> None:
        """增加计数器"""
        self._counters[name] = self._counters.get(name, 0) + value

    def record_response_time(self, response_time: float) -> None:
        """记录响应时间"""
        self._response_times.append(response_time)
        self._last_request_time = datetime.now()

        # 保持最近1000次记录
        if len(self._response_times) > 1000:
            self._response_times.pop(0)

    def get_counter(self, name: str) -> int:
        """获取计数器值"""
        return self._counters.get(name, 0)

    def snapshot(self) -> Dict[str, Any]:
        """获取性能快照"""
        if not self._response_times:
            return {
                "requests": self.get_counter("requests"),
                "errors": self.get_counter("errors"),
                "cache_hits": self.get_counter("cache_hits"),
                "cache_misses": self.get_counter("cache_misses"),
                "avg_response_time": 0,
                "max_response_time": 0,
                "min_response_time": 0,
                "last_request_time": self._last_request_time
            }

        return {
            "requests": self.get_counter("requests"),
            "errors": self.get_counter("errors"),
            "cache_hits": self.get_counter("cache_hits"),
            "cache_misses": self.get_counter("cache_misses"),
            "avg_response_time": sum(self._response_times) / len(self._response_times),
            "max_response_time": max(self._response_times),
            "min_response_time": min(self._response_times),
            "last_request_time": self._last_request_time
        }

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取详细性能统计"""
        snapshot = self.snapshot()
        cache_total = max(1, snapshot['cache_hits'] + snapshot['cache_misses'])
        total_requests = max(1, snapshot['requests'])
        
        return {
            'total_requests': snapshot['requests'],
            'cache_hit_rate': (snapshot['cache_hits'] / cache_total) * 100,
            'error_rate': (snapshot['errors'] / total_requests) * 100,
            'avg_response_time': round(snapshot['avg_response_time'], 2),
            'max_response_time': round(snapshot['max_response_time'], 2),
            'min_response_time': round(snapshot['min_response_time'], 2),
            'last_request_time': snapshot['last_request_time']
        }

    def reset(self) -> None:
        """重置所有统计"""
        self._counters.clear()
        self._response_times.clear()
        self._last_request_time = None
