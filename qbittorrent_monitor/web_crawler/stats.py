"""
Web爬虫统计模块

负责收集和报告爬虫的性能和状态指标
"""

import logging
from typing import Dict, Any
from datetime import datetime


class StatsCollector:
    """
    统计信息收集器

    负责收集爬虫的各种性能指标和状态信息
    """

    def __init__(self):
        """初始化统计收集器"""
        self.reset()
        self.logger = logging.getLogger('StatsCollector')

    def reset(self) -> None:
        """重置所有统计信息"""
        self.reset_time = datetime.now()
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_response_time = 0.0
        self.average_response_time = 0.0

    def record_request(self, success: bool, response_time: float, from_cache: bool = False) -> None:
        """
        记录一次请求

        Args:
            success: 请求是否成功
            response_time: 响应时间（秒）
            from_cache: 是否来自缓存
        """
        self.total_requests += 1

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        if from_cache:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

        # 更新响应时间统计
        self.total_response_time += response_time
        self.average_response_time = self.total_response_time / self.total_requests

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计信息

        Returns:
            Dict包含性能指标
        """
        uptime = datetime.now() - self.reset_time
        uptime_seconds = uptime.total_seconds()

        return {
            "uptime_seconds": uptime_seconds,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": (self.cache_hits / (self.cache_hits + self.cache_misses) * 100) if (self.cache_hits + self.cache_misses) > 0 else 0,
            "average_response_time": self.average_response_time,
            "requests_per_second": self.total_requests / uptime_seconds if uptime_seconds > 0 else 0,
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        获取所有统计信息（别名方法）

        Returns:
            Dict包含所有统计指标
        """
        return self.get_performance_stats()
