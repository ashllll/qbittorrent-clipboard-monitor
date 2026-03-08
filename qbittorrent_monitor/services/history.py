"""历史记录服务

封装历史记录相关的业务逻辑。
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
import json
from datetime import datetime

from ..repository import TorrentRepository, StatsRepository, EventRepository
from ..core.magnet import MagnetProcessor


class HistoryService:
    """历史记录服务 - 封装数据库操作"""
    
    def __init__(
        self,
        torrent_repo: TorrentRepository,
        stats_repo: Optional[StatsRepository] = None,
        event_repo: Optional[EventRepository] = None,
        magnet_processor: Optional[MagnetProcessor] = None
    ):
        self._torrent_repo = torrent_repo
        self._stats_repo = stats_repo
        self._event_repo = event_repo
        self._magnet_processor = magnet_processor or MagnetProcessor()
    
    async def record_torrent(
        self,
        magnet: str,
        category: str,
        status: str,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """记录种子处理
        
        Args:
            magnet: 磁力链接
            category: 分类
            status: 状态
            error_message: 错误信息
            
        Returns:
            记录字典
        """
        magnet_hash = self._magnet_processor.get_hash(magnet) or magnet[:40]
        name = self._magnet_processor.get_name(magnet) or ""
        
        record = await self._torrent_repo.record_torrent(
            magnet_hash=magnet_hash,
            name=name[:200],
            category=category,
            status=status,
            error_message=error_message
        )
        
        # 更新统计
        if self._stats_repo:
            await self._stats_repo.update_category_stats(category, status)
        
        return record.to_dict()
    
    async def query_history(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """查询历史记录"""
        records = await self._torrent_repo.query(
            category=category,
            status=status,
            limit=limit,
            offset=offset
        )
        return [r.to_dict() for r in records]
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self._stats_repo:
            return await self._stats_repo.get_overall_stats()
        
        # 回退到 torrent_repo 的统计
        return await self._torrent_repo.get_stats()
    
    async def export_data(
        self,
        output_path: str,
        format: str = "json"
    ) -> int:
        """导出数据"""
        records = await self._torrent_repo.query(limit=100000)
        stats = await self.get_stats()
        
        export_data = {
            "export_time": datetime.now().isoformat(),
            "total_records": len(records),
            "stats": stats,
            "records": [r.to_dict() for r in records],
        }
        
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        if format.lower() == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
        elif format.lower() == "csv":
            import csv
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                if records:
                    writer = csv.DictWriter(f, fieldnames=records[0].to_dict().keys())
                    writer.writeheader()
                    for record in records:
                        writer.writerow(record.to_dict())
        
        return len(records)
    
    async def log_event(
        self,
        event_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录系统事件"""
        if self._event_repo:
            await self._event_repo.log_event(event_type, message, details)
