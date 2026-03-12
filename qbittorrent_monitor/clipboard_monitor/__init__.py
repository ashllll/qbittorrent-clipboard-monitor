"""剪贴板监控模块 - 向后兼容导出

此模块提供剪贴板监控功能，包括：
- ClipboardMonitor: 核心监控器类
- OptimizedClipboardMonitor: 优化版监控器
- ActivityTracker: 活动跟踪器
- SmartBatcher: 智能批处理器

示例:
    >>> from qbittorrent_monitor.clipboard_monitor import ClipboardMonitor
    >>> monitor = ClipboardMonitor(qb_client, config)
    >>> await monitor.start()
"""

# 基类和接口
from .base import BaseClipboardMonitor, ActivityTrackerProtocol, BatchProcessorProtocol, MonitorStats

# 核心组件
from .activity_tracker import ActivityTracker
from .batch_processor import SmartBatcher
from .core import ClipboardMonitor
from .optimized import OptimizedClipboardMonitor

__all__ = [
    # 基类和协议
    'BaseClipboardMonitor',
    'ActivityTrackerProtocol',
    'BatchProcessorProtocol',
    'MonitorStats',
    # 核心组件
    'ActivityTracker',
    'SmartBatcher',
    'ClipboardMonitor',
    'OptimizedClipboardMonitor',
]
