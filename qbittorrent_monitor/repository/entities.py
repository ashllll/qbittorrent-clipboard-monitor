"""Repository 实体定义

数据类定义，与数据库表结构对应。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TorrentStatus(str, Enum):
    """Torrent 处理状态"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    INVALID = "invalid"


@dataclass
class TorrentRecord:
    """种子记录实体"""
    magnet_hash: str
    name: str = ""
    category: str = "other"
    status: str = "pending"
    error_message: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "magnet_hash": self.magnet_hash,
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class CategoryStats:
    """分类统计实体"""
    category: str
    total_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    duplicate_count: int = 0
    invalid_count: int = 0
    last_updated: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "category": self.category,
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "duplicate_count": self.duplicate_count,
            "invalid_count": self.invalid_count,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


@dataclass
class SystemEvent:
    """系统事件实体"""
    event_type: str
    message: str
    details: Optional[Dict[str, Any]] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "message": self.message,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
