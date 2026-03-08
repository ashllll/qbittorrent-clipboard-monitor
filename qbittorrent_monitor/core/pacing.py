"""智能轮询服务 - 蜂群优化版

独立职责：管理剪贴板检查的智能轮询间隔。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class PacingConfig:
    """轮询配置"""
    active_interval: float = 0.5       # 活跃状态检查间隔
    idle_interval: float = 3.0         # 空闲状态检查间隔
    idle_threshold_seconds: float = 30.0  # 进入空闲状态的阈值
    burst_window_seconds: float = 5.0  # 突发变化检测窗口
    burst_threshold: int = 3           # 触发活跃状态的连续变化次数


class PacingService:
    """智能轮询服务
    
    根据剪贴板活动状态自动调整检查间隔。
    """
    
    def __init__(self, config: Optional[PacingConfig] = None):
        self.config = config or PacingConfig()
        
        self._last_change_time: float = 0.0
        self._change_count_in_window: int = 0
        self._window_start_time: float = time.time()
    
    def record_activity(self) -> None:
        """记录剪贴板活动"""
        now = time.time()
        self._last_change_time = now
        
        # 检查是否在突发窗口内
        if now - self._window_start_time <= self.config.burst_window_seconds:
            self._change_count_in_window += 1
        else:
            # 窗口过期，重置
            self._change_count_in_window = 1
            self._window_start_time = now
    
    def get_interval(self) -> float:
        """计算当前检查间隔
        
        Returns:
            建议的检查间隔（秒）
        """
        now = time.time()
        time_since_last_change = now - self._last_change_time
        
        # 如果在突发窗口内有多次变化，使用活跃间隔
        if self._change_count_in_window >= self.config.burst_threshold:
            return self.config.active_interval
        
        # 如果窗口过期，重置计数
        if now - self._window_start_time > self.config.burst_window_seconds:
            self._change_count_in_window = 0
            self._window_start_time = now
        
        # 根据空闲状态选择间隔
        if time_since_last_change > self.config.idle_threshold_seconds:
            return self.config.idle_interval
        
        return self.config.active_interval
    
    def get_stats(self) -> Dict[str, float]:
        """获取轮询统计"""
        return {
            "change_count_in_window": self._change_count_in_window,
            "time_since_last_change": time.time() - self._last_change_time,
            "current_interval": self.get_interval(),
        }
