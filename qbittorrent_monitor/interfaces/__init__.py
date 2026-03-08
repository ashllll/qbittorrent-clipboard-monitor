"""接口定义模块 - 蜂群优化版

使用 Protocol 定义接口，支持依赖注入和测试 mock。
"""

from .classifier import IClassifier, ClassificationResult
from .torrent_client import ITorrentClient, TorrentAddResult
from .database import IDatabase, TorrentRecord
from .metrics import IMetricsService

__all__ = [
    "IClassifier",
    "ClassificationResult",
    "ITorrentClient",
    "TorrentAddResult",
    "IDatabase",
    "TorrentRecord",
    "IMetricsService",
]
