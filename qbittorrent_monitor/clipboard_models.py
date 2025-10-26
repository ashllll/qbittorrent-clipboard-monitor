"""
剪贴板处理相关数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class TorrentRecord:
    magnet_link: str
    torrent_hash: str
    torrent_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    category: Optional[str] = None
    status: str = "pending"  # pending, success, failed, duplicate
    error_message: Optional[str] = None
    classification_method: Optional[str] = None
    save_path: Optional[str] = None


@dataclass
class ProcessingTask:
    kind: str  # magnet, url, ignore
    content: str
