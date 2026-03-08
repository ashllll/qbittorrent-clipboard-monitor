"""性能优化集成模块

将性能优化功能集成到现有的 qBittorrent 客户端和监控器中。

主要集成点:
    1. QBClient - 使用优化的连接池
    2. ClipboardMonitor - 使用批量数据库写入和TTL缓存
    3. ContentClassifier - 使用TTL缓存替换LRU缓存
"""

import asyncio
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from ..config import Config
    from ..database import DatabaseManager
    from ..qb_client import QBClient
    from ..classifier import ContentClassifier
    from ..monitor import ClipboardMonitor

logger = logging.getLogger(__name__)


class PerformanceOptimizer:
    """性能优化器集成类
    
    统一管理所有性能优化组件的初始化和配置。
    
    Example:
        >>> from qbittorrent_monitor.performance.integrations import PerformanceOptimizer
        >>> 
        >>> optimizer = PerformanceOptimizer(config)
        >>> await optimizer.initialize()
        >>> 
        >>> # 应用到现有组件
        >>> optimizer.optimize_qb_client(qb_client)
        >>> optimizer.optimize_monitor(monitor)
        >>> optimizer.optimize_classifier(classifier)
        >>> 
        >>> # 获取性能报告
        >>> report = optimizer.get_performance_report()
        >>> 
        >>> await optimizer.shutdown()
    """
    
    def __init__(self, config: "Config"):
        """初始化性能优化器
        
        Args:
            config: 应用配置
        """
        self.config = config
        
        # 优化组件
        self._connection_pool: Optional["OptimizedConnectionPool"] = None
        self._batch_writer: Optional["BatchDatabaseWriter"] = None
        self._cache: Optional["TTLCache"] = None
        self._limiter: Optional["ConcurrencyLimiter"] = None
        self._async_optimizer: Optional["AsyncIOOptimizer"] = None
        
        # 状态
        self._initialized = False
    
    async def initialize(self) -> None:
        """初始化所有优化组件"""
        if self._initialized:
            return
        
        # 导入优化模块
        from .connection_pool import OptimizedConnectionPool
        from .ttl_cache import TTLCache
        from .asyncio_optimizer import AsyncIOOptimizer, ConcurrencyLimiter
        
        # 初始化连接池
        self._connection_pool = OptimizedConnectionPool(
            self.config,
            enable_http2=True,
            dns_cache_ttl=300,
        )
        await self._connection_pool.initialize()
        
        # 初始化缓存
        self._cache = TTLCache[Any](
            max_size=10000,
            default_ttl=3600,
            max_memory_mb=50,
        )
        self._cache.start()
        
        # 初始化并发限制器
        self._limiter = ConcurrencyLimiter(
            max_concurrent=20,
            max_queue_size=1000,
        )
        
        # 初始化AsyncIO优化器
        self._async_optimizer = AsyncIOOptimizer(
            max_workers=10,
            enable_profiling=False,
        )
        self._async_optimizer.initialize()
        
        self._initialized = True
        logger.info("性能优化器已初始化")
    
    async def shutdown(self) -> None:
        """关闭所有优化组件"""
        if not self._initialized:
            return
        
        # 关闭批量写入器
        if self._batch_writer:
            await self._batch_writer.stop()
            self._batch_writer = None
        
        # 关闭连接池
        if self._connection_pool:
            await self._connection_pool.close()
            self._connection_pool = None
        
        # 关闭缓存
        if self._cache:
            self._cache.stop()
            self._cache = None
        
        # 关闭AsyncIO优化器
        if self._async_optimizer:
            self._async_optimizer.shutdown()
            self._async_optimizer = None
        
        self._limiter = None
        self._initialized = False
        
        logger.info("性能优化器已关闭")
    
    def optimize_qb_client(self, qb_client: "QBClient") -> "QBClient":
        """优化qBittorrent客户端
        
        替换客户端的session为优化的连接池session。
        
        Args:
            qb_client: QBClient实例
            
        Returns:
            优化后的QBClient
        """
        if not self._initialized or not self._connection_pool:
            logger.warning("连接池未初始化，跳过QBClient优化")
            return qb_client
        
        # 替换session
        qb_client.session = self._connection_pool.get_session()
        
        logger.debug("QBClient已应用连接池优化")
        return qb_client
    
    def optimize_monitor(
        self,
        monitor: "ClipboardMonitor",
        enable_batch_writer: bool = True,
        enable_cache: bool = True,
    ) -> "ClipboardMonitor":
        """优化监控器
        
        Args:
            monitor: ClipboardMonitor实例
            enable_batch_writer: 启用批量数据库写入
            enable_cache: 启用TTL缓存
            
        Returns:
            优化后的ClipboardMonitor
        """
        from .batch_writer import BatchDatabaseWriter
        
        # 启用批量数据库写入
        if enable_batch_writer and monitor._db_enabled:
            db = monitor._db or monitor._external_db
            if db:
                self._batch_writer = BatchDatabaseWriter(
                    db,
                    batch_size=100,
                    flush_interval=0.1,
                )
                # 启动批量写入器
                asyncio.create_task(self._batch_writer.start())
                
                # 替换monitor的数据库写入方法
                monitor._batch_writer = self._batch_writer
                logger.debug("监控器已应用批量写入优化")
        
        # 应用并发限制器到磁力链接处理
        if self._limiter:
            monitor._concurrency_limiter = self._limiter
            logger.debug("监控器已应用并发限制优化")
        
        return monitor
    
    def optimize_classifier(self, classifier: "ContentClassifier") -> "ContentClassifier":
        """优化分类器
        
        使用TTL缓存替换LRU缓存。
        
        Args:
            classifier: ContentClassifier实例
            
        Returns:
            优化后的ContentClassifier
        """
        if not self._initialized or not self._cache:
            logger.warning("缓存未初始化，跳过分类器优化")
            return classifier
        
        # 为分类器创建专用缓存
        from .ttl_cache import TTLCache
        classifier_cache = TTLCache[Any](
            max_size=5000,
            default_ttl=1800,  # 30分钟TTL
            max_memory_mb=20,
        )
        classifier_cache.start()
        
        # 存储原始缓存方法
        classifier._original_cache = classifier.cache
        classifier._ttl_cache = classifier_cache
        
        # 包装分类方法以使用TTL缓存
        original_classify = classifier.classify
        
        async def optimized_classify(name: str, use_cache: bool = True, timeout: Optional[float] = None):
            if not use_cache:
                return await original_classify(name, use_cache=False, timeout=timeout)
            
            cache_key = classifier._get_cache_key(name)
            cached = classifier_cache.get(cache_key)
            
            if cached is not None:
                return cached
            
            result = await original_classify(name, use_cache=False, timeout=timeout)
            classifier_cache.set(cache_key, result, ttl=1800)
            
            return result
        
        classifier.classify = optimized_classify
        
        logger.debug("分类器已应用TTL缓存优化")
        return classifier
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告
        
        Returns:
            包含各组件性能统计的字典
        """
        report = {
            "initialized": self._initialized,
            "components": {},
        }
        
        # 连接池统计
        if self._connection_pool:
            report["components"]["connection_pool"] = self._connection_pool.get_stats()
        
        # 批量写入器统计
        if self._batch_writer:
            report["components"]["batch_writer"] = self._batch_writer.get_stats()
        
        # 缓存统计
        if self._cache:
            report["components"]["cache"] = self._cache.get_stats().__dict__
        
        # 并发限制器统计
        if self._limiter:
            report["components"]["concurrency_limiter"] = self._limiter.get_stats()
        
        # AsyncIO优化器统计
        if self._async_optimizer:
            report["components"]["asyncio_optimizer"] = self._async_optimizer.get_performance_report()
        
        return report
    
    async def warmup_cache(self, database: "DatabaseManager") -> Dict[str, Any]:
        """预热缓存
        
        从数据库加载热点数据到缓存。
        
        Args:
            database: 数据库管理器
            
        Returns:
            预热统计
        """
        from .ttl_cache import CacheWarmer
        
        if not self._cache:
            return {"error": "缓存未初始化"}
        
        warmer = CacheWarmer(self._cache)
        
        # 添加数据源：最近处理的热力图
        async def load_recent_torrents():
            records = await database.get_torrent_records(limit=1000)
            return {r.magnet_hash: r for r in records}
        
        warmer.add_source("recent_torrents", load_recent_torrents, ttl=3600)
        
        # 执行预热
        stats = await warmer.warmup()
        
        logger.info(f"缓存预热完成: {stats['total_loaded']} 条记录")
        return stats


# 便捷函数

async def create_optimized_monitor(
    config: "Config",
    enable_all_optimizations: bool = True,
) -> "ClipboardMonitor":
    """创建完全优化的监控器
    
    创建并配置所有优化功能的监控器。
    
    Args:
        config: 应用配置
        enable_all_optimizations: 启用所有优化
        
    Returns:
        优化后的ClipboardMonitor实例
    """
    from ..qb_client import QBClient
    from ..classifier import ContentClassifier
    from ..monitor import ClipboardMonitor
    
    # 创建优化器
    optimizer = PerformanceOptimizer(config)
    
    if enable_all_optimizations:
        await optimizer.initialize()
    
    # 创建基础组件
    qb_client = QBClient(config)
    classifier = ContentClassifier(config)
    
    # 应用优化
    if enable_all_optimizations:
        optimizer.optimize_qb_client(qb_client)
        optimizer.optimize_classifier(classifier)
    
    # 创建监控器
    monitor = ClipboardMonitor(
        qb_client=qb_client,
        config=config,
        classifier=classifier,
    )
    
    # 应用监控器优化
    if enable_all_optimizations:
        optimizer.optimize_monitor(monitor)
        monitor._optimizer = optimizer  # 存储引用以便后续访问
    
    return monitor
