"""优化版qBittorrent客户端

此模块提供 OptimizedQBittorrentClient 类，继承自 QBittorrentClient，
添加多级连接池和批量操作优化。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .core import QBittorrentClient
from .connection_pool import MultiTierConnectionPool
from .batch_operations import BatchOperations

if TYPE_CHECKING:
    from ..config import Config
    from .cache_manager import CacheManager


logger = logging.getLogger(__name__)


class OptimizedQBittorrentClient(QBittorrentClient):
    """优化版qBittorrent客户端
    
    继承自 QBittorrentClient，添加了以下功能：
    - 多级连接池（读写分离）
    - 批量操作优化
    - 智能错误恢复
    
    Attributes:
        connection_pool: 多级连接池
        batch_operations: 批量操作助手
    
    Example:
        >>> from qbittorrent_monitor.qbittorrent_client import OptimizedQBittorrentClient
        >>> client = OptimizedQBittorrentClient(config)
        >>> await client.initialize()
        >>> await client.add_torrents_batch(torrents)
    """
    
    def __init__(
        self,
        config: Config,
        cache: Optional[CacheManager] = None,
        read_pool_size: int = 10,
        write_pool_size: int = 5,
        api_pool_size: int = 20,
    ):
        """初始化优化版客户端
        
        Args:
            config: 应用配置
            cache: 缓存管理器（可选）
            read_pool_size: 读连接池大小
            write_pool_size: 写连接池大小
            api_pool_size: API连接池大小
        """
        super().__init__(config, cache)
        
        # 多级连接池
        self.connection_pool = MultiTierConnectionPool(
            read_pool_size=read_pool_size,
            write_pool_size=write_pool_size,
            api_pool_size=api_pool_size
        )
        
        # 批量操作
        self.batch_operations = BatchOperations(self)
        
        # 性能统计
        self._perf_stats = {
            'read_ops': 0,
            'write_ops': 0,
            'api_ops': 0,
        }
    
    async def initialize(self) -> None:
        """初始化客户端（异步）"""
        await self.connection_pool.initialize()
        logger.info("OptimizedQBittorrentClient 初始化完成")
    
    async def cleanup(self) -> None:
        """清理资源"""
        await self.connection_pool.close_all()
        await super().cleanup()
        logger.debug("OptimizedQBittorrentClient 资源已清理")
    
    async def add_torrent(
        self,
        magnet: str,
        category: Optional[str] = None,
        save_path: Optional[str] = None
    ) -> bool:
        """添加磁力链接（使用写连接池）
        
        Args:
            magnet: 磁力链接
            category: 分类名称（可选）
            save_path: 保存路径（可选）
        
        Returns:
            是否添加成功
        """
        # 使用写连接池
        old_session = self.session
        self.session = self.connection_pool.write_pool
        
        try:
            result = await super().add_torrent(magnet, category, save_path)
            self._perf_stats['write_ops'] += 1
            return result
        finally:
            self.session = old_session
    
    async def get_categories(self) -> Dict[str, Any]:
        """获取所有分类（使用读连接池）
        
        Returns:
            分类字典
        """
        # 使用读连接池
        old_session = self.session
        self.session = self.connection_pool.read_pool
        
        try:
            result = await super().get_categories()
            self._perf_stats['read_ops'] += 1
            return result
        finally:
            self.session = old_session
    
    async def add_torrents_batch(
        self,
        torrents: List[Tuple[str, str]],
        batch_size: int = 10,
        max_concurrent: int = 3
    ) -> Dict[str, Any]:
        """批量添加种子（优化版）
        
        使用多级连接池和并发控制优化批量添加性能。
        
        Args:
            torrents: [(magnet_link, category), ...]
            batch_size: 每批处理数量
            max_concurrent: 最大并发数
        
        Returns:
            包含操作结果的字典
        """
        logger.info(f"开始批量添加 {len(torrents)} 个种子（优化版）")
        
        results = {
            'success_count': 0,
            'failed_count': 0,
            'skipped_count': 0,
            'results': []
        }
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def add_with_limit(magnet: str, category: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    success = await self.add_torrent(magnet, category)
                    return {
                        'magnet': magnet[:50] + "...",
                        'category': category,
                        'status': 'success' if success else 'failed'
                    }
                except Exception as e:
                    return {
                        'magnet': magnet[:50] + "...",
                        'category': category,
                        'status': 'failed',
                        'error': str(e)
                    }
        
        # 创建任务
        tasks = [
            add_with_limit(magnet, category)
            for magnet, category in torrents
        ]
        
        # 分批执行
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch)
            
            for result in batch_results:
                if result['status'] == 'success':
                    results['success_count'] += 1
                elif result['status'] == 'skipped':
                    results['skipped_count'] += 1
                else:
                    results['failed_count'] += 1
                results['results'].append(result)
            
            logger.debug(f"批次完成: {len(batch)} 个种子处理完成")
        
        # 更新批量操作统计
        self.batch_operations._stats['total_batches'] += 1
        self.batch_operations._stats['total_items'] += len(torrents)
        if results['failed_count'] == 0:
            self.batch_operations._stats['successful_batches'] += 1
        else:
            self.batch_operations._stats['failed_batches'] += 1
        
        return results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计
        
        Returns:
            包含性能统计的字典
        """
        return {
            'connection_pool': {
                'read_ops': self._perf_stats['read_ops'],
                'write_ops': self._perf_stats['write_ops'],
                'api_ops': self._perf_stats['api_ops'],
            },
            'batch_operations': self.batch_operations.get_stats(),
            'cache': self.cache.get_stats() if self.cache else None,
        }
    
    def reset_stats(self) -> None:
        """重置所有统计"""
        self._perf_stats = {
            'read_ops': 0,
            'write_ops': 0,
            'api_ops': 0,
        }
        self.batch_operations.reset_stats()
        logger.info("统计信息已重置")
