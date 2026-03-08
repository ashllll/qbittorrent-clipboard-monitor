"""插件系统模块

提供可扩展的插件架构，支持通知、分类、处理等多种插件类型。

使用示例:
    >>> from qbittorrent_monitor.plugins import PluginManager
    >>> manager = PluginManager()
    >>> await manager.load_plugins()
    >>> await manager.enable_plugin("webhook_notifier")
"""

from .base import (
    BasePlugin,
    NotifierPlugin,
    ClassifierPlugin,
    HandlerPlugin,
    PluginMetadata,
    PluginState,
    PluginType,
)
from .manager import PluginManager
from .hooks import HookRegistry, HookType, HookCallback, register_hook, invoke_hooks

__all__ = [
    # 插件基类
    "BasePlugin",
    "NotifierPlugin",
    "ClassifierPlugin",
    "HandlerPlugin",
    # 插件元数据
    "PluginMetadata",
    "PluginState",
    "PluginType",
    # 管理器
    "PluginManager",
    # 钩子系统
    "HookRegistry",
    "HookType",
    "HookCallback",
    "register_hook",
    "invoke_hooks",
]
