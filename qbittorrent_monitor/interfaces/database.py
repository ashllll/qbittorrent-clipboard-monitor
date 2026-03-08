"""数据库接口定义"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TorrentRecord:
    """种子记录"""
    magnet_hash: str
    name: str
    category: str
    status: str
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


@runtime_checkable
class IDatabase(Protocol):
    """数据库接口"""
    
    async def record_torrent(
        self,
        magnet_hash: str,
        name: str,
        category: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """记录种子"""
        ...
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        ...
    
    async def query_history(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[TorrentRecord]:
        """查询历史"""
        ...
