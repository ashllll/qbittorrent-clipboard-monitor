"""
种子信息数据类模块
"""

from dataclasses import dataclass


@dataclass
class TorrentInfo:
    """种子信息数据类"""
    title: str
    detail_url: str
    magnet_link: str = ""
    size: str = ""
    seeders: int = 0
    leechers: int = 0
    category: str = ""
    status: str = "pending"  # pending, extracted, added, failed, duplicate
