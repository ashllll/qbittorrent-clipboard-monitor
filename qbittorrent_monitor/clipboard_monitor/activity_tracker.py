"""智能活动跟踪器 - 根据剪贴板活动模式智能调整监控策略

此模块提供 ActivityTracker 类，用于跟踪剪贴板活动并根据
活动模式智能调整监控策略。
"""

import time
import logging
from collections import deque
from typing import Dict, Optional


logger = logging.getLogger(__name__)


class ActivityTracker:
    """智能活动跟踪器 - 优化指导文档建议
    
    根据剪贴板活动模式智能调整监控策略，
    记录活动历史并计算当前活动级别。
    
    Attributes:
        window_size: 活动历史窗口大小
        activity_history: 活动历史记录
        last_activity_time: 上次活动时间
        total_activities: 总活动次数
        current_level: 当前活动级别 (0-10)
    
    Example:
        >>> tracker = ActivityTracker(window_size=100)
        >>> tracker.record_activity(has_content=True)
        >>> level = await tracker.get_level()
    """
    
    def __init__(self, window_size: int = 100):
        """初始化活动跟踪器
        
        Args:
            window_size: 活动历史窗口大小
        """
        self.window_size = window_size
        self.activity_history: deque = deque(maxlen=window_size)
        self.last_activity_time = time.time()
        self.total_activities = 0
        self.current_level = 0  # 0-10 活动级别
    
    def record_activity(self, has_content: bool = False) -> None:
        """记录一次活动
        
        Args:
            has_content: 是否包含内容
        """
        current_time = time.time()
        is_active = has_content or self._is_recently_active(current_time)
        
        self.activity_history.append({
            'timestamp': current_time,
            'active': is_active
        })
        
        if is_active:
            self.last_activity_time = current_time
            self.total_activities += 1
        
        self._calculate_activity_level()
    
    def _is_recently_active(self, current_time: float, threshold: float = 5.0) -> bool:
        """检查最近是否活跃
        
        Args:
            current_time: 当前时间戳
            threshold: 活跃阈值（秒）
        
        Returns:
            如果最近活跃返回 True
        """
        return (current_time - self.last_activity_time) < threshold
    
    def _calculate_activity_level(self) -> None:
        """计算当前活动级别 (0-10)"""
        if not self.activity_history:
            self.current_level = 0
            return
        
        current_time = time.time()
        recent_window = 60  # 60秒窗口
        active_count = 0
        total_count = 0
        
        for entry in reversed(self.activity_history):
            if current_time - entry['timestamp'] > recent_window:
                break
            total_count += 1
            if entry['active']:
                active_count += 1
        
        if total_count == 0:
            self.current_level = 0
        else:
            activity_rate = active_count / total_count
            self.current_level = min(10, int(activity_rate * 10))
    
    async def get_level(self) -> int:
        """获取当前活动级别 (0-10)
        
        Returns:
            当前活动级别
        """
        return self.current_level
    
    def get_stats(self) -> Dict[str, any]:
        """获取活动统计
        
        Returns:
            包含活动统计信息的字典
        """
        return {
            'total_activities': self.total_activities,
            'current_level': self.current_level,
            'window_size': len(self.activity_history),
            'is_active': self._is_recently_active(time.time())
        }
    
    def is_high_activity(self, threshold: int = 7) -> bool:
        """检查是否为高活动状态
        
        Args:
            threshold: 高活动阈值
        
        Returns:
            如果是高活动状态返回 True
        """
        return self.current_level >= threshold
    
    def reset(self) -> None:
        """重置活动跟踪器"""
        self.activity_history.clear()
        self.last_activity_time = time.time()
        self.total_activities = 0
        self.current_level = 0
        logger.debug("ActivityTracker 已重置")
