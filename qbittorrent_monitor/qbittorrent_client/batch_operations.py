"""批量操作模块 - 种子批量添加和查询

此模块提供 BatchOperations 类，用于批量处理种子操作。
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

if TYPE_CHECKING:
    from .core import QBittorrentClient


logger = logging.getLogger(__name__)


class BatchOperations:
    """批量操作助手类
    
    提供种子批量添加和查询功能。
    
    Attributes:
        client: QBittorrentClient 实例
        stats: 批量操作统计
    
    Example:
        >>> batch_ops = BatchOperations(client)
        >>> results = await batch_ops.add_torrents_batch(torrents)
    """
    
    def __init__(self, client: QBittorrentClient):
        """初始化批量操作助手
        
        Args:
            client: QBittorrentClient 实例
        """
        self.client = client
        self._stats = {
            'total_batches': 0,
            'successful_batches': 0,
            'failed_batches': 0,
            'total_items': 0,
            'avg_batch_size': 0.0
        }
    
    async def add_torrents_batch(
        self,
        torrents: List[Tuple[str, str]],
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """批量添加种子
        
        Args:
            torrents: [(magnet_link, category), ...]
            batch_size: 每批处理数量
        
        Returns:
            包含操作结果的字典
        """
        logger.info(f"开始批量添加 {len(torrents)} 个种子")
        self._stats['total_batches'] += 1
        self._stats['total_items'] += len(torrents)
        
        results = {
            'success_count': 0,
            'failed_count': 0,
            'skipped_count': 0,
            'results': []
        }
        
        # 分批处理
        for i in range(0, len(torrents), batch_size):
            batch = torrents[i:i + batch_size]
            batch_results = await self._process_batch(batch, i // batch_size + 1)
            
            for result in batch_results:
                if result['status'] == 'success':
                    results['success_count'] += 1
                elif result['status'] == 'skipped':
                    results['skipped_count'] += 1
                else:
                    results['failed_count'] += 1
                results['results'].append(result)
        
        # 更新统计
        if results['failed_count'] == 0:
            self._stats['successful_batches'] += 1
        else:
            self._stats['failed_batches'] += 1
        
        self._stats['avg_batch_size'] = (
            self._stats['total_items'] / max(self._stats['total_batches'], 1)
        )
        
        return results
    
    async def _process_batch(
        self,
        batch: List[Tuple[str, str]],
        batch_num: int
    ) -> List[Dict[str, Any]]:
        """处理单个批次
        
        Args:
            batch: 批次中的项目列表
            batch_num: 批次编号
        
        Returns:
            处理结果列表
        """
        tasks = []
        for magnet_link, category in batch:
            task = self._add_torrent_safe(magnet_link, category)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        batch_results = []
        for (magnet_link, category), result in zip(batch, results):
            if isinstance(result, Exception):
                batch_results.append({
                    'magnet': magnet_link[:50] + "...",
                    'category': category,
                    'status': 'failed',
                    'error': str(result)
                })
            elif result is True:
                batch_results.append({
                    'magnet': magnet_link[:50] + "...",
                    'category': category,
                    'status': 'success'
                })
            else:
                batch_results.append({
                    'magnet': magnet_link[:50] + "...",
                    'category': category,
                    'status': 'skipped',
                    'reason': 'duplicate'
                })
        
        return batch_results
    
    async def _add_torrent_safe(self, magnet_link: str, category: str) -> bool:
        """安全添加单个种子
        
        Args:
            magnet_link: 磁力链接
            category: 分类名称
        
        Returns:
            是否添加成功
        """
        try:
            return await self.client.add_torrent(magnet_link, category)
        except Exception as e:
            logger.error(f"添加失败: {magnet_link[:30]}... - {e}")
            raise
    
    async def get_torrents_batch(
        self,
        hashes: List[str],
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """批量获取种子信息
        
        Args:
            hashes: 种子哈希列表
            batch_size: 每批处理数量
        
        Returns:
            包含种子信息的字典
        """
        results = {
            'total': len(hashes),
            'found': 0,
            'not_found': 0,
            'torrents': {}
        }
        
        # 这里可以实现批量查询逻辑
        # 目前qBittorrent API支持通过hashes参数查询多个种子
        # 但为了简化，这里先返回空结果
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取批量操作统计
        
        Returns:
            包含统计信息的字典
        """
        stats = self._stats.copy()
        if stats['total_batches'] > 0:
            stats['success_rate'] = (
                stats['successful_batches'] / stats['total_batches'] * 100
            )
        return stats
    
    def reset_stats(self) -> None:
        """重置统计"""
        self._stats = {
            'total_batches': 0,
            'successful_batches': 0,
            'failed_batches': 0,
            'total_items': 0,
            'avg_batch_size': 0.0
        }
