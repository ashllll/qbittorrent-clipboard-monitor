"""
qbt 子包 - qBittorrent客户端模块

提供模块化的qBittorrent API功能
"""

from .client import QBittorrentClient
from .optimized import OptimizedQBittorrentClient

__all__ = [
    'QBittorrentClient',
    'OptimizedQBittorrentClient'
]
