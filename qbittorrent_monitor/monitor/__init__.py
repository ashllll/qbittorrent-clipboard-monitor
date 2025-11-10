"""
monitor 子包 - 剪贴板监控模块

提供模块化的剪贴板监控功能
"""

# 延迟导入以避免循环依赖
def __getattr__(name):
    if name == "ClipboardMonitor":
        from .monitor import ClipboardMonitor
        return ClipboardMonitor
    elif name == "ActivityTracker":
        from .activity import ActivityTracker
        return ActivityTracker
    elif name == "SmartBatcher":
        from .batcher import SmartBatcher
        return SmartBatcher
    elif name == "OptimizedClipboardMonitor":
        from .optimized import OptimizedClipboardMonitor
        return OptimizedClipboardMonitor
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
