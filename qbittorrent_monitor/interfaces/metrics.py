"""指标服务接口定义"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Optional


@runtime_checkable
class IMetricsService(Protocol):
    """指标服务接口"""
    
    def record_torrent_processed(self, category: str = "unknown") -> None:
        """记录处理的种子"""
        ...
    
    def record_torrent_added(
        self,
        success: bool,
        category: str = "unknown",
        reason: Optional[str] = None
    ) -> None:
        """记录种子添加结果"""
        ...
    
    def record_duplicate_skipped(self, reason: str = "duplicate") -> None:
        """记录跳过的重复"""
        ...
    
    def record_classification(
        self,
        method: str,
        category: str
    ) -> None:
        """记录分类"""
        ...
    
    def set_cache_size(self, cache_type: str, size: int) -> None:
        """设置缓存大小"""
        ...
    
    def set_monitor_running(self, running: bool) -> None:
        """设置监控状态"""
        ...
