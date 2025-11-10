"""
爬虫性能统计模块
"""

from dataclasses import dataclass, field
from collections import deque
from typing import Dict, Any


@dataclass
class CrawlerStats:
    """爬虫性能统计"""
    requests_made: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    circuit_breaker_trips: int = 0
    rate_limit_hits: int = 0

    def get_avg_response_time(self) -> float:
        """获取平均响应时间"""
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0

    def get_cache_hit_rate(self) -> float:
        """获取缓存命中率"""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
