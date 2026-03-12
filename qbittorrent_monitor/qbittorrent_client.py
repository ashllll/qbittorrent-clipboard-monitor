"""qBittorrent客户端模块 (向后兼容)

警告: 此文件为兼容代理，请从 qbittorrent_client 子模块导入。

推荐的新导入方式:
    >>> from qbittorrent_monitor.qbittorrent_client import QBittorrentClient
    >>> from qbittorrent_monitor.qbittorrent_client.core import QBittorrentClient
    >>> from qbittorrent_monitor.qbittorrent_client.optimized import OptimizedQBittorrentClient
"""

import warnings

# 发出弃用警告
warnings.warn(
    "从 qbittorrent_monitor.qbittorrent_client 导入已弃用，"
    "请使用 qbittorrent_monitor.qbittorrent_client 子模块导入。"
    "示例: from qbittorrent_monitor.qbittorrent_client import QBittorrentClient",
    DeprecationWarning,
    stacklevel=2
)

# 重新导出所有类（从新的子模块）
from .qbittorrent_client.base import (
    QBittorrentClientProtocol,
    ConnectionPoolProtocol,
    CacheManagerProtocol,
    BaseQBittorrentClient,
)
from .qbittorrent_client.connection_pool import (
    ConnectionPool,
    MultiTierConnectionPool,
)
from .qbittorrent_client.cache_manager import (
    CacheManager,
    CacheStats,
)
from .qbittorrent_client.core import (
    QBittorrentClient,
    APIErrorType,
    QBAPIError,
    with_retry,
)
from .qbittorrent_client.batch_operations import BatchOperations
from .qbittorrent_client.optimized import OptimizedQBittorrentClient

__all__ = [
    # 协议
    'QBittorrentClientProtocol',
    'ConnectionPoolProtocol',
    'CacheManagerProtocol',
    'BaseQBittorrentClient',
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
