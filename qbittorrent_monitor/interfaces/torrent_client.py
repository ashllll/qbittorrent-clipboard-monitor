"""Torrent 客户端接口定义"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class TorrentAddResult:
    """种子添加结果"""
    success: bool
    error_message: Optional[str] = None
    torrent_id: Optional[str] = None


@runtime_checkable
class ITorrentClient(Protocol):
    """Torrent 客户端接口"""
    
    async def add_torrent(
        self,
        magnet: str,
        category: Optional[str] = None,
        save_path: Optional[str] = None
    ) -> TorrentAddResult:
        """添加种子
        
        Args:
            magnet: 磁力链接
            category: 分类
            save_path: 保存路径
            
        Returns:
            添加结果
        """
        ...
    
    async def get_version(self) -> str:
        """获取客户端版本"""
        ...
    
    async def ensure_categories(self) -> None:
        """确保分类存在"""
        ...
