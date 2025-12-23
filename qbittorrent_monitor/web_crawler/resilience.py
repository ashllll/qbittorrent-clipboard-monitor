"""
Web爬虫弹性设计模块

提供断路器、限流、重试等弹性功能
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta


class ResilienceManager:
    """
    弹性管理器

    负责管理断路器、速率限制、重试等弹性功能
    """

    def __init__(self, rate_limit: float = 5.0, max_retries: int = 3):
        """
        初始化弹性管理器

        Args:
            rate_limit: 每秒最大请求数
            max_retries: 最大重试次数
        """
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.logger = logging.getLogger('ResilienceManager')
        self._request_times = []

    def check_rate_limit(self) -> bool:
        """
        检查是否超过速率限制

        Returns:
            True if allowed, False if rate limited
        """
        try:
            now = datetime.now()

            # 清理1秒前的请求记录
            self._request_times = [
                t for t in self._request_times
                if now - t < timedelta(seconds=1)
            ]

            # 检查当前速率
            if len(self._request_times) >= self.rate_limit:
                return False

            # 记录本次请求
            self._request_times.append(now)
            return True

        except Exception as e:
            self.logger.error(f"速率限制检查异常: {e}")
            return True  # 发生错误时允许请求

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """
        判断是否应该重试

        Args:
            attempt: 当前尝试次数（从0开始）
            exception: 异常对象

        Returns:
            True if should retry, False otherwise
        """
        # 超过最大重试次数
        if attempt >= self.max_retries:
            return False

        # 对于网络错误，建议重试
        if isinstance(exception, (ConnectionError, TimeoutError)):
            return True

        # 对于其他错误，不重试
        return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取弹性管理器统计信息

        Returns:
            Dict包含统计信息
        """
        now = datetime.now()
        recent_requests = [
            t for t in self._request_times
            if now - t < timedelta(seconds=1)
        ]

        return {
            "rate_limit": self.rate_limit,
            "max_retries": self.max_retries,
            "current_rate": len(recent_requests),
            "requests_last_second": len(recent_requests)
        }
