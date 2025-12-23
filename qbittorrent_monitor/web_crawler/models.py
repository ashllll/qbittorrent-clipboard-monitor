"""
Web爬虫数据模型模块

定义爬虫相关的数据结构和配置类
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class SiteConfig:
    """
    网站特定配置

    用于配置不同网站的爬取策略和行为
    """
    name: str
    url_pattern: str
    selectors: Dict[str, str]
    rate_limit: float = 2.0  # 每秒请求数
    max_concurrent: int = 5
    pagination: bool = True
    use_js: bool = True
    timeout: int = 30
    retries: int = 3
    user_agents: List[str] = field(default_factory=list)
    custom_headers: Dict[str, str] = field(default_factory=dict)


class MemoryMonitor:
    """
    内存监控器

    监控和管理爬虫内存使用，防止内存溢出
    """

    def __init__(self, memory_limit_mb: int = 100):
        self.memory_limit = memory_limit_mb * 1024 * 1024  # 转换为字节
        self.current_usage = 0
        self.peak_usage = 0
        self.cleanup_threshold = 0.8  # 80% 时开始清理
        self.logger = logging.getLogger('MemoryMonitor')

    async def check_memory(self) -> Dict[str, Any]:
        """
        检查内存使用情况

        Returns:
            Dict包含当前和峰值内存使用情况
        """
        try:
            import psutil
            process = psutil.Process()
            self.current_usage = process.memory_info().rss

            if self.current_usage > self.peak_usage:
                self.peak_usage = self.current_usage

            # 检查是否超过限制
            memory_info = {
                "current_mb": self.current_usage / 1024 / 1024,
                "peak_mb": self.peak_usage / 1024 / 1024,
                "limit_mb": self.memory_limit / 1024 / 1024,
                "usage_percent": (self.current_usage / self.memory_limit) * 100
            }

            if self.current_usage > self.memory_limit:
                self.logger.warning(
                    f"内存使用超限: {memory_info['current_mb']:.1f}MB / "
                    f"{memory_info['limit_mb']:.1f}MB"
                )
                await self._cleanup_cache()
            elif self.current_usage > self.memory_limit * self.cleanup_threshold:
                # 达到阈值时主动清理
                self.logger.debug(
                    f"内存使用达到阈值: {memory_info['usage_percent']:.1f}%"
                )
                await self._cleanup_cache()

            return memory_info

        except ImportError:
            self.logger.warning("psutil 未安装，跳过内存监控")
            return {
                "current_mb": 0,
                "peak_mb": 0,
                "limit_mb": self.memory_limit / 1024 / 1024,
                "usage_percent": 0,
                "error": "psutil not installed"
            }
        except Exception as e:
            self.logger.error(f"内存监控出错: {str(e)}")
            return {
                "current_mb": 0,
                "peak_mb": 0,
                "limit_mb": self.memory_limit / 1024 / 1024,
                "usage_percent": 0,
                "error": str(e)
            }

    async def _cleanup_cache(self) -> None:
        """
        执行内存清理

        子类可以重写此方法来清理特定的缓存
        """
        self.logger.info("执行内存清理...")
        # 这里可以清理内部缓存
        # 暂时只是一个占位符
        await asyncio.sleep(0.1)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取内存统计信息

        Returns:
            Dict包含内存使用统计
        """
        return {
            "current_usage_mb": self.current_usage / 1024 / 1024,
            "peak_usage_mb": self.peak_usage / 1024 / 1024,
            "limit_mb": self.memory_limit / 1024 / 1024,
            "usage_percent": (self.current_usage / self.memory_limit) * 100 if self.memory_limit > 0 else 0,
            "cleanup_threshold": self.cleanup_threshold
        }
