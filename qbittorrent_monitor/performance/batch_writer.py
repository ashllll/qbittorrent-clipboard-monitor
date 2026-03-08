"""批量数据库写入

通过批量写入显著提升数据库性能。
"""

from __future__ import annotations

import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque


@dataclass
class BatchRecord:
    """批量写入记录"""
    magnet_hash: str
    name: str
    category: str
    status: str
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class BatchDatabaseWriter:
    """批量数据库写入器
    
    性能提升:
    - 单条写入: ~5-10ms/条
    - 批量写入(100条): ~50-100ms/批次
    - 提升: ~5-10x
    
    使用示例:
        writer = BatchDatabaseWriter(db_path, batch_size=100)
        await writer.start()
        
        await writer.write(BatchRecord(...))
        await writer.write(BatchRecord(...))
        
        await writer.flush()  # 强制刷新
        await writer.stop()
    """
    
    def __init__(
        self,
        db_connection,
        batch_size: int = 100,
        flush_interval: float = 5.0,
        max_queue_size: int = 1000
    ):
        self._db = db_connection
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._max_queue_size = max_queue_size
        
        self._queue: deque[BatchRecord] = deque()
        self._stats_written = 0
        self._running = False
        self._flush_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def start(self) -> None:
        """启动批量写入器"""
        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush())
    
    async def stop(self) -> None:
        """停止批量写入器，刷新剩余数据"""
        self._running = False
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # 刷新剩余数据
        await self.flush()
    
    async def write(self, record: BatchRecord) -> None:
        """写入记录（加入批量队列）
        
        Args:
            record: 要写入的记录
        """
        async with self._lock:
            # 队列满时立即刷新
            if len(self._queue) >= self._max_queue_size:
                await self._flush_batch()
            
            self._queue.append(record)
            
            # 达到批次大小立即刷新
            if len(self._queue) >= self._batch_size:
                await self._flush_batch()
    
    async def flush(self) -> int:
        """强制刷新所有待写入数据
        
        Returns:
            刷新的记录数
        """
        async with self._lock:
            return await self._flush_batch()
    
    async def _flush_batch(self) -> int:
        """刷新一批数据
        
        Returns:
            刷新的记录数
        """
        if not self._queue:
            return 0
        
        # 取出一批数据
        batch = []
        while self._queue and len(batch) < self._batch_size:
            batch.append(self._queue.popleft())
        
        if not batch:
            return 0
        
        # 批量插入
        try:
            await self._bulk_insert(batch)
            self._stats_written += len(batch)
            return len(batch)
        except Exception as e:
            # 失败时放回队列（避免数据丢失）
            for record in reversed(batch):
                self._queue.appendleft(record)
            raise
    
    async def _bulk_insert(self, records: List[BatchRecord]) -> None:
        """执行批量插入"""
        # 使用 INSERT OR REPLACE 批量插入
        values = []
        for r in records:
            values.append((
                r.magnet_hash,
                r.name,
                r.category,
                r.status,
                r.error_message,
                r.timestamp
            ))
        
        # SQLite 批量插入
        await self._db.executemany(
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
            values
        )
        await self._db.commit()
    
    async def _periodic_flush(self) -> None:
        """定期刷新任务"""
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # 记录错误但继续运行
                import logging
                logging.getLogger(__name__).error(f"批量写入错误: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取写入统计"""
        return {
            "written": self._stats_written,
            "pending": len(self._queue),
            "batch_size": self._batch_size,
            "flush_interval": self._flush_interval,
        }
