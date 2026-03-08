"""统计 Repository

分类统计相关的数据访问操作。
"""

from __future__ import annotations

from typing import Optional, List
from datetime import datetime

from .entities import CategoryStats


class StatsRepository:
    """统计仓库"""
    
    def __init__(self, db_connection):
        self._db = db_connection
    
    async def get_category_stats(
        self,
        category: Optional[str] = None
    ) -> List[CategoryStats]:
        """获取分类统计"""
        if category:
            cursor = await self._db.execute(
                """
                SELECT category, total_count, success_count, failed_count, 
                       duplicate_count, invalid_count, last_updated
                FROM category_stats WHERE category = ?
                """,
                (category,)
            )
            rows = await cursor.fetchall()
        else:
            cursor = await self._db.execute(
                """
                SELECT category, total_count, success_count, failed_count, 
                       duplicate_count, invalid_count, last_updated
                FROM category_stats
                ORDER BY total_count DESC
                """
            )
            rows = await cursor.fetchall()
        
        return [self._row_to_entity(row) for row in rows]
    
    async def update_category_stats(self, category: str, status: str) -> None:
        """更新分类统计"""
        # 确保分类存在
        await self._db.execute(
            "INSERT OR IGNORE INTO category_stats (category) VALUES (?)",
            (category,)
        )
        
        now = datetime.now()
        
        # 根据状态更新计数
        if status == "success":
            await self._db.execute(
                """
                UPDATE category_stats SET
                    total_count = total_count + 1,
                    success_count = success_count + 1,
                    last_updated = ?
                WHERE category = ?
                """,
                (now, category)
            )
        elif status == "failed":
            await self._db.execute(
                """
                UPDATE category_stats SET
                    total_count = total_count + 1,
                    failed_count = failed_count + 1,
                    last_updated = ?
                WHERE category = ?
                """,
                (now, category)
            )
        elif status == "duplicate":
            await self._db.execute(
                """
                UPDATE category_stats SET
                    total_count = total_count + 1,
                    duplicate_count = duplicate_count + 1,
                    last_updated = ?
                WHERE category = ?
                """,
                (now, category)
            )
        elif status == "invalid":
            await self._db.execute(
                """
                UPDATE category_stats SET
                    total_count = total_count + 1,
                    invalid_count = invalid_count + 1,
                    last_updated = ?
                WHERE category = ?
                """,
                (now, category)
            )
        
        await self._db.commit()
    
    async def get_overall_stats(self) -> dict:
        """获取整体统计"""
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
        
        # 获取今天的统计
        from datetime import timedelta
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM torrent_records WHERE created_at >= ?",
            (today,)
        )
        today_count = (await cursor.fetchone())[0]
        
        return {
            "total_records": row[0] or 0,
            "success_count": row[1] or 0,
            "failed_count": row[2] or 0,
            "duplicate_count": row[3] or 0,
            "invalid_count": row[4] or 0,
            "today_count": today_count,
        }
    
    def _row_to_entity(self, row) -> CategoryStats:
        """将数据库行转换为实体"""
        last_updated = row[6]
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        
        return CategoryStats(
            category=row[0],
            total_count=row[1] or 0,
            success_count=row[2] or 0,
            failed_count=row[3] or 0,
            duplicate_count=row[4] or 0,
            invalid_count=row[5] or 0,
            last_updated=last_updated,
        )
