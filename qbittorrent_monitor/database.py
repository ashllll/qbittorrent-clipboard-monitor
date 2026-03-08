"""SQLite 数据持久化层（向后兼容层）

此模块保留以提供向后兼容。新代码应使用 Repository 模式。

例如：
    # 旧方式（仍然支持）
    from qbittorrent_monitor.database import DatabaseManager
    
    # 新方式（推荐）
    from qbittorrent_monitor.repository import TorrentRepository, StatsRepository
    from qbittorrent_monitor.repository.base import RepositoryError

迁移说明：
    - DatabaseManager 已拆分为 TorrentRepository 和 StatsRepository
    - 此文件现在只是导入和转发
    - 计划在 v4.0 中移除此兼容层
"""

from __future__ import annotations

import warnings

# 发出弃用警告
warnings.warn(
    "qbittorrent_monitor.database 已弃用。"
    "请使用 qbittorrent_monitor.repository 模块，"
    "例如: from qbittorrent_monitor.repository import TorrentRepository",
    DeprecationWarning,
    stacklevel=2
)

# 重新导出所有公开 API 以保持向后兼容
from qbittorrent_monitor.repository import (
    # 基础接口
    Repository,
    RepositoryError,
    RecordNotFoundError,
    DuplicateRecordError,
    # 具体 Repository
    TorrentRepository as DatabaseManager,  # 别名保持兼容
    StatsRepository,
    # 数据模型
    TorrentRecord,
    CategoryStats,
    SystemEvent,
)

# 保留旧的 TorrentStatus 别名
from qbittorrent_monitor.repository import TorrentStatus

# 保留旧的 extract_magnet_hash 函数
from qbittorrent_monitor.utils import extract_magnet_hash

__all__ = [
    # 数据模型
    "TorrentRecord",
    "CategoryStats",
    "SystemEvent",
    "TorrentStatus",
    # Repository 类
    "Repository",
    "DatabaseManager",  # 保持兼容
    "TorrentRepository",
    "StatsRepository",
    # 异常
    "RepositoryError",
    "RecordNotFoundError",
    "DuplicateRecordError",
    # 工具函数
    "extract_magnet_hash",
]
