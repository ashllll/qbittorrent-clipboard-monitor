"""
qbt 子包 - qBittorrent客户端模块

提供模块化的qBittorrent API功能
"""

# 延迟导入以避免循环依赖
def __getattr__(name):
    if name == "QBittorrentClient":
        from .qbittorrent_client import QBittorrentClient
        return QBittorrentClient
    elif name == "OptimizedQBittorrentClient":
        from .qbittorrent_client import OptimizedQBittorrentClient
        return OptimizedQBittorrentClient
    elif name == "ConnectionPoolManager":
        from .connection_pool import ConnectionPoolManager
        return ConnectionPoolManager
    elif name == "CacheManager":
        from .cache_manager import CacheManager
        return CacheManager
    elif name == "APIClient":
        from .api_client import APIClient
        return APIClient
    elif name == "TorrentManager":
        from .torrent_manager import TorrentManager
        return TorrentManager
    elif name == "CategoryManager":
        from .category_manager import CategoryManager
        return CategoryManager
    elif name == "MetricsCollector":
        from .metrics import MetricsCollector
        return MetricsCollector
    elif name == "BatchOperations":
        from .batch_operations import BatchOperations
        return BatchOperations
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
