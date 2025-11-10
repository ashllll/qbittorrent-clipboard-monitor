"""
爬虫资源池模块
"""

import asyncio
import logging
from typing import List

from ..config import AppConfig


# 可选导入 crawl4ai
try:
    from crawl4ai import AsyncWebCrawler
    HAS_CRAWL4AI = True
except ImportError:
    HAS_CRAWL4AI = False


class CrawlerResourcePool:
    """爬虫资源池 - 管理爬虫实例的获取和释放"""

    def __init__(self, max_size: int, config: AppConfig, logger: logging.Logger):
        if not HAS_CRAWL4AI:
            raise ImportError("crawl4ai module is not installed")

        self.max_size = max_size
        self.config = config
        self.logger = logger
        self._pool: List = []  # 使用List替代具体类型
        self._semaphore = asyncio.Semaphore(max_size)

    async def acquire(self):
        """获取爬虫实例"""
        async with self._semaphore:
            if self._pool:
                return self._pool.pop()
            crawler = AsyncWebCrawler(
                headless=True,
                browser_type="chromium",
                verbose=False,
                delay_before_return_html=2.0,
                js_code=[
                    "window.scrollTo(0, document.body.scrollHeight);",
                    "await new Promise(resolve => setTimeout(resolve, 1000));"
                ]
            )
            await crawler.start()
            return crawler

    async def release(self, crawler):
        """释放爬虫实例"""
        if len(self._pool) < self.max_size:
            self._pool.append(crawler)
        else:
            await crawler.close()

    async def close_all(self):
        """关闭所有资源"""
        while self._pool:
            crawler = self._pool.pop()
            try:
                await crawler.close()
            except Exception as exc:
                self.logger.warning(f"关闭爬虫实例时出错: {exc}")


# 修复循环导入 - 延迟导入
def __getattr__(name):
    if name == "TorrentInfo":
        from .torrent_info import TorrentInfo
        return TorrentInfo
    elif name == "CrawlerStats":
        from .crawler_stats import CrawlerStats
        return CrawlerStats
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
