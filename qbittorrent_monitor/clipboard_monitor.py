"""剪贴板监控器模块 (向后兼容)

警告: 此文件为兼容代理，请从 clipboard_monitor 子模块导入。

推荐的新导入方式:
    >>> from qbittorrent_monitor.clipboard_monitor import ClipboardMonitor
    >>> from qbittorrent_monitor.clipboard_monitor.core import ClipboardMonitor
    >>> from qbittorrent_monitor.clipboard_monitor.optimized import OptimizedClipboardMonitor
"""

import warnings

# 发出弃用警告
warnings.warn(
    "从 qbittorrent_monitor.clipboard_monitor 导入已弃用，"
    "请使用 qbittorrent_monitor.clipboard_monitor 子模块导入。"
    "示例: from qbittorrent_monitor.clipboard_monitor import ClipboardMonitor",
    DeprecationWarning,
    stacklevel=2
)

# 重新导出所有类（从新的子模块）
from .clipboard_monitor.base import (
    BaseClipboardMonitor,
    ActivityTrackerProtocol,
    BatchProcessorProtocol,
    MonitorStats,
)
from .clipboard_monitor.activity_tracker import ActivityTracker
from .clipboard_monitor.batch_processor import SmartBatcher
from .clipboard_monitor.core import ClipboardMonitor, PacingConfig, MagnetExtractor
from .clipboard_monitor.optimized import OptimizedClipboardMonitor, AdvancedStats

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
    # 工具类和配置
    'PacingConfig',
    'MagnetExtractor',
    'AdvancedStats',
]
