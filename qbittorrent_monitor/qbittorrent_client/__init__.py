"""qBittorrent客户端模块 - 向后兼容导出

此模块提供qBittorrent客户端功能，包括：
- QBittorrentClient: 核心客户端类
- OptimizedQBittorrentClient: 优化版客户端
- ConnectionPool: 连接池管理
- CacheManager: 缓存管理
- BatchOperations: 批量操作

示例:
    >>> from qbittorrent_monitor.qbittorrent_client import QBittorrentClient
    >>> client = QBittorrentClient(config)
    >>> await client.login()
"""

# 基类和协议
from .base import (
    QBittorrentClientProtocol,
    ConnectionPoolProtocol,
    CacheManagerProtocol,
)

# 核心组件
from .connection_pool import ConnectionPool, MultiTierConnectionPool
from .cache_manager import CacheManager, CacheStats
from .core import QBittorrentClient, APIErrorType, QBAPIError, with_retry
from .batch_operations import BatchOperations
from .optimized import OptimizedQBittorrentClient

__all__ = [
    # 协议
    'QBittorrentClientProtocol',
    'ConnectionPoolProtocol',
    'CacheManagerProtocol',
    # 连接池
    'ConnectionPool',
    'MultiTierConnectionPool',
    # 缓存
    'CacheManager',
    'CacheStats',
    # 核心客户端
    'QBittorrentClient',
    'APIErrorType',
    'QBAPIError',
    'with_retry',
    # 批量操作
    'BatchOperations',
    # 优化版
    'OptimizedQBittorrentClient',
]
