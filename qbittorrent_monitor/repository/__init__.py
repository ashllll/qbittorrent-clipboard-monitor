"""Repository 模式模块

数据访问抽象层，解耦业务逻辑与数据存储。
"""

from .base import Repository, RepositoryError, RecordNotFoundError, DuplicateRecordError
from .entities import TorrentRecord, CategoryStats, SystemEvent, TorrentStatus
from .torrent import TorrentRepository
from .stats import StatsRepository
from .events import EventRepository

__all__ = [
    # 基础类
    "Repository",
    "RepositoryError",
    "RecordNotFoundError",
    "DuplicateRecordError",
    # 实体
    "TorrentRecord",
    "CategoryStats",
    "SystemEvent",
    # 仓库实现
    "TorrentRepository",
    "StatsRepository",
    "EventRepository",
]
