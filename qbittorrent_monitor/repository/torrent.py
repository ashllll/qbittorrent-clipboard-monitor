"""种子记录 Repository

Torrent 相关的数据访问操作。
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from datetime import datetime

from .base import Repository, QueryOptions
from .entities import TorrentRecord


class TorrentRepository(Repository[TorrentRecord]):
    """种子记录仓库"""
    
    def __init__(self, db_connection):
        self._db = db_connection
    
    async def get_by_hash(self, magnet_hash: str) -> Optional[TorrentRecord]:
        """根据磁力链接hash获取记录"""
        cursor = await self._db.execute(
            """
            SELECT id, magnet_hash, name, category, status, error_message, created_at, updated_at
            FROM torrent_records WHERE magnet_hash = ?
            """,
            (magnet_hash,)
        )
        row = await cursor.fetchone()
        return self._row_to_entity(row) if row else None
    
    async def exists(self, magnet_hash: str) -> bool:
        """检查记录是否存在"""
        cursor = await self._db.execute(
            "SELECT 1 FROM torrent_records WHERE magnet_hash = ?",
            (magnet_hash,)
        )
        return (await cursor.fetchone()) is not None
    
    async def record_torrent(
        self,
        magnet_hash: str,
        name: str,
        category: str,
        status: str,
        error_message: Optional[str] = None
    ) -> TorrentRecord:
        """记录种子（业务方法）"""
        now = datetime.now()
        
        await self._db.execute(
            """
            INSERT INTO torrent_records 
            (magnet_hash, name, category, status, error_message, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(magnet_hash) DO UPDATE SET
            name = excluded.name,
            category = excluded.category,
            status = excluded.status,
            error_message = excluded.error_message,
            updated_at = excluded.updated_at
            """,
            (magnet_hash, name, category, status, error_message, now)
        )
        await self._db.commit()
        
        # 获取记录 ID
        cursor = await self._db.execute(
            "SELECT id FROM torrent_records WHERE magnet_hash = ?",
            (magnet_hash,)
        )
        row = await cursor.fetchone()
        record_id = row[0] if row else None
        
        return TorrentRecord(
            id=record_id,
            magnet_hash=magnet_hash,
            name=name,
            category=category,
            status=status,
            error_message=error_message,
            created_at=now,
            updated_at=now,
        )
    
    async def query(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[TorrentRecord]:
        """查询记录"""
        conditions = []
        params = []
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT id, magnet_hash, name, category, status, error_message, created_at, updated_at
            FROM torrent_records {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        
        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_entity(row) for row in rows]
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        cursor = await self._db.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'duplicate' THEN 1 ELSE 0 END) as duplicate,
                SUM(CASE WHEN status = 'invalid' THEN 1 ELSE 0 END) as invalid
            FROM torrent_records
            """
        )
        row = await cursor.fetchone()
        
        return {
            "total_records": row[0] or 0,
            "success_count": row[1] or 0,
            "failed_count": row[2] or 0,
            "duplicate_count": row[3] or 0,
            "invalid_count": row[4] or 0,
        }
    
    # Repository 接口实现
    async def get_by_id(self, id: int) -> Optional[TorrentRecord]:
        cursor = await self._db.execute(
            """
            SELECT id, magnet_hash, name, category, status, error_message, created_at, updated_at
            FROM torrent_records WHERE id = ?
            """,
            (id,)
        )
        row = await cursor.fetchone()
        return self._row_to_entity(row) if row else None
    
    async def create(self, entity: TorrentRecord) -> TorrentRecord:
        return await self.record_torrent(
            magnet_hash=entity.magnet_hash,
            name=entity.name,
            category=entity.category,
            status=entity.status,
            error_message=entity.error_message
        )
    
    async def update(self, entity: TorrentRecord) -> TorrentRecord:
        return await self.record_torrent(
            magnet_hash=entity.magnet_hash,
            name=entity.name,
            category=entity.category,
            status=entity.status,
            error_message=entity.error_message
        )
    
    async def delete(self, id: int) -> bool:
        await self._db.execute(
            "DELETE FROM torrent_records WHERE id = ?",
            (id,)
        )
        await self._db.commit()
        return True
    
    async def list(self, options: QueryOptions) -> List[TorrentRecord]:
        return await self.query(limit=options.limit, offset=options.offset)
    
    def _row_to_entity(self, row) -> TorrentRecord:
        """将数据库行转换为实体"""
        created_at = row[6]
        updated_at = row[7]
        
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        
        return TorrentRecord(
            id=row[0],
            magnet_hash=row[1],
            name=row[2],
            category=row[3],
            status=row[4],
            error_message=row[5],
            created_at=created_at,
            updated_at=updated_at,
        )
