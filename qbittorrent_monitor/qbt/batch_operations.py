"""
批量操作模块

处理批量种子操作，包括：
- 批量添加种子
- 批量获取种子信息
- 智能重试机制
- 并发控制
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class BatchOperations:
    """批量操作处理器"""

    def __init__(self, api_client, torrent_manager, max_workers: int = 4):
        self.api_client = api_client
        self.torrent_manager = torrent_manager
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logging.getLogger('BatchOperations')

    async def add_torrents_batch(
        self,
        magnet_links: List[str],
        category: str,
        **kwargs
    ) -> Dict[str, bool]:
        """批量添加种子"""
        results = {}

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(self.max_workers)

        async def add_single_torrent(magnet: str) -> tuple:
            async with semaphore:
                try:
                    success = await self.torrent_manager.add_torrent(magnet, category, **kwargs)
                    return magnet, success
                except Exception as e:
                    self.logger.error(f"添加种子失败: {magnet[:50]}... - {e}")
                    return magnet, False

        # 并发执行添加任务
        tasks = [add_single_torrent(magnet) for magnet in magnet_links]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for result in results_list:
            if isinstance(result, tuple):
                magnet, success = result
                results[magnet] = success

        return results

    async def get_torrents_batch(
        self,
        categories: Optional[List[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """批量获取种子信息"""
        results = {}

        if categories is None:
            # 获取所有分类的种子
            status, all_torrents = await self.api_client.get('torrents/info')
            if status == 200 and all_torrents:
                # 按分类分组
                for torrent in all_torrents:
                    cat = torrent.get('category', 'uncategorized')
                    if cat not in results:
                        results[cat] = []
                    results[cat].append(torrent)
            return results

        # 获取指定分类的种子
        semaphore = asyncio.Semaphore(self.max_workers)

        async def get_category_torrents(cat: str) -> tuple:
            async with semaphore:
                try:
                    torrents = await self.torrent_manager.get_torrents(cat)
                    return cat, torrents
                except Exception as e:
                    self.logger.error(f"获取分类 {cat} 种子失败: {e}")
                    return cat, []

        # 并发获取各分类种子
        tasks = [get_category_torrents(cat) for cat in categories]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for result in results_list:
            if isinstance(result, tuple):
                cat, torrents = result
                results[cat] = torrents

        return results

    async def get_torrents_by_category_batch(
        self,
        category_torrents: Dict[str, List[str]]
    ) -> Dict[str, Dict[str, Any]]:
        """批量按分类获取种子详情"""
        results = {}

        semaphore = asyncio.Semaphore(self.max_workers)

        async def get_torrent_details(category: str, torrents: List[str]) -> tuple:
            async with semaphore:
                try:
                    details = {}
                    for torrent in torrents:
                        props = await self.torrent_manager.get_torrent_properties(torrent)
                        details[torrent] = props
                    return category, details
                except Exception as e:
                    self.logger.error(f"获取分类 {category} 种子详情失败: {e}")
                    return category, {}

        # 并发获取各分类的种子详情
        tasks = [
            get_torrent_details(cat, torrents)
            for cat, torrents in category_torrents.items()
        ]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for result in results_list:
            if isinstance(result, tuple):
                cat, details = result
                results[cat] = details

        return results

    def get_batch_stats(self) -> Dict[str, Any]:
        """获取批量操作统计"""
        return {
            "max_workers": self.max_workers,
            "active_threads": self.executor._threads
        }

    async def _smart_retry_with_different_params(self, error: Exception) -> Any:
        """智能重试（使用不同参数）"""
        # 这里可以实现更智能的重试逻辑
        # 例如降低并发数、添加延迟等
        pass

    async def _retry_with_reduced_concurrency(self) -> Any:
        """重试（降低并发数）"""
        # 降低并发数后重试
        pass

    async def _retry_with_backoff(self) -> Any:
        """重试（退避策略）"""
        # 实现指数退避重试
        pass

    async def cleanup(self) -> None:
        """清理资源"""
        try:
            self.executor.shutdown(wait=True)
            logger.info("批量操作资源已清理")
        except Exception as e:
            logger.error(f"清理批量操作资源失败: {e}")
