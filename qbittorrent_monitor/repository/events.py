"""事件 Repository

系统事件日志相关的数据访问操作。
"""

from __future__ import annotations

import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from .entities import SystemEvent


class EventRepository:
    """事件仓库"""
    
    def __init__(self, db_connection):
        self._db = db_connection
    
    async def log_event(
        self,
        event_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> SystemEvent:
        """记录系统事件"""
        details_json = json.dumps(details, ensure_ascii=False) if details else None
        now = datetime.now()
        
        cursor = await self._db.execute(
            """
            INSERT INTO system_events (event_type, message, details, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (event_type, message, details_json, now)
        )
        await self._db.commit()
        
        return SystemEvent(
            id=cursor.lastrowid,
            event_type=event_type,
            message=message,
            details=details,
            created_at=now,
        )
    
    async def get_events(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SystemEvent]:
        """获取系统事件"""
        conditions = []
        params = []
        
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT id, event_type, message, details, created_at
            FROM system_events {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        
        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_entity(row) for row in rows]
    
    def _row_to_entity(self, row) -> SystemEvent:
        """将数据库行转换为实体"""
        details = None
        if row[3]:
            try:
                details = json.loads(row[3])
            except json.JSONDecodeError:
                details = {"raw": row[3]}
        
        created_at = row[4]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        return SystemEvent(
            id=row[0],
            event_type=row[1],
            message=row[2],
            details=details,
            created_at=created_at,
        )
