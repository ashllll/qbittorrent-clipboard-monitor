"""指标服务

非全局的指标收集服务。
"""

from __future__ import annotations

import time
from typing import Optional, Callable, Any
from contextlib import contextmanager
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class MetricValue:
    """指标值"""
    count: int = 0
    total: float = 0.0
    min: float = float('inf')
    max: float = 0.0
    
    def record(self, value: float) -> None:
        """记录值"""
        self.count += 1
        self.total += value
        self.min = min(self.min, value)
        self.max = max(self.max, value)
    
    @property
    def avg(self) -> float:
        """平均值"""
        return self.total / self.count if self.count > 0 else 0.0


class MetricsService:
    """指标服务 - 非全局，每个实例独立"""
    
    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, MetricValue] = defaultdict(MetricValue)
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    def record_torrent_processed(self, category: str = "unknown") -> None:
        """记录处理的种子"""
        if self._enabled:
            self._counters[f"torrents_processed_{category}"] += 1
    
    def record_torrent_added(
        self,
        success: bool,
        category: str = "unknown",
        reason: Optional[str] = None
    ) -> None:
        """记录种子添加结果"""
        if not self._enabled:
            return
        
        if success:
            self._counters[f"torrents_added_success_{category}"] += 1
        else:
            key = f"torrents_added_failed_{category}"
            if reason:
                key += f"_{reason}"
            self._counters[key] += 1
    
    def record_duplicate_skipped(self, reason: str = "duplicate") -> None:
        """记录跳过的重复"""
        if self._enabled:
            self._counters[f"duplicates_skipped_{reason}"] += 1
    
    def record_classification(self, method: str, category: str) -> None:
        """记录分类"""
        if self._enabled:
            self._counters[f"classifications_{method}_{category}"] += 1
    
    def record_clipboard_change(self) -> None:
        """记录剪贴板变化"""
        if self._enabled:
            self._counters["clipboard_changes"] += 1
    
    def set_cache_size(self, cache_type: str, size: int) -> None:
        """设置缓存大小"""
        if self._enabled:
            self._gauges[f"cache_size_{cache_type}"] = size
    
    def set_cache_hit_rate(self, cache_type: str, hit_rate: float) -> None:
        """设置缓存命中率"""
        if self._enabled:
            self._gauges[f"cache_hit_rate_{cache_type}"] = hit_rate
    
    def set_pending_magnets(self, count: int) -> None:
        """设置待处理磁力链接数"""
        if self._enabled:
            self._gauges["pending_magnets"] = count
    
    def set_monitor_running(self, running: bool) -> None:
        """设置监控状态"""
        if self._enabled:
            self._gauges["monitor_running"] = 1.0 if running else 0.0
    
    def record_duration(self, metric_name: str, duration: float) -> None:
        """记录持续时间"""
        if self._enabled:
            self._histograms[metric_name].record(duration)
    
    def get_stats(self) -> dict[str, Any]:
        """获取统计"""
        if not self._enabled:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: {
                    "count": v.count,
                    "avg": v.avg,
                    "min": v.min if v.min != float('inf') else 0,
                    "max": v.max
                }
                for k, v in self._histograms.items()
            }
        }
    
    @contextmanager
    def timed(self, metric_name: str):
        """计时上下文管理器"""
        if not self._enabled:
            yield
            return
        
        start = time.time()
        try:
            yield
        finally:
            self.record_duration(metric_name, time.time() - start)
