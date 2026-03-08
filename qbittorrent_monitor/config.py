"""配置管理模块（向后兼容层）

此模块保留以提供向后兼容。新代码应直接使用 qbittorrent_monitor.config 包。

例如：
    # 旧方式（仍然支持）
    from qbittorrent_monitor.config import Config, load_config
    
    # 新方式（推荐）
    from qbittorrent_monitor.config.base import Config
    from qbittorrent_monitor.config.env_loader import load_config
    from qbittorrent_monitor.config.manager import ConfigManager

迁移说明：
    - 所有类和函数已移动到子模块
    - 此文件现在只是导入和转发
    - 计划在 v4.0 中移除此兼容层
"""

from __future__ import annotations

import warnings

# 发出弃用警告
warnings.warn(
    "直接导入 qbittorrent_monitor.config 已弃用。"
    "请使用 qbittorrent_monitor.config 子模块，"
    "例如: from qbittorrent_monitor.config.base import Config",
    DeprecationWarning,
    stacklevel=2
)

# 重新导出所有公开 API 以保持向后兼容
from .config.base import Config
from .config.qb import QBConfig
from .config.ai import AIConfig
from .config.categories import CategoryConfig, get_default_categories
from .config.database import DatabaseConfig
from .config.metrics import MetricsConfig
from .config.plugins import PluginConfig
from .config.manager import ConfigManager
from .config.env_loader import load_config
from .config.constants import (
    VALID_LOG_LEVELS,
    MIN_PORT, MAX_PORT,
    MIN_TIMEOUT, MAX_TIMEOUT,
    MIN_RETRIES, MAX_RETRIES,
    MIN_CHECK_INTERVAL, MAX_CHECK_INTERVAL,
)
from .config.validators import parse_bool, parse_int, parse_float
from .exceptions import ConfigError

__all__ = [
    # 主配置类
    "Config",
    "ConfigManager",
    "load_config",
    # 子配置类
    "QBConfig",
    "AIConfig",
    "CategoryConfig",
    "DatabaseConfig",
    "MetricsConfig",
    "PluginConfig",
    # 工具函数
    "get_default_categories",
    "parse_bool",
    "parse_int",
    "parse_float",
    # 常量
    "VALID_LOG_LEVELS",
    "MIN_PORT", "MAX_PORT",
    "MIN_TIMEOUT", "MAX_TIMEOUT",
    "MIN_RETRIES", "MAX_RETRIES",
    "MIN_CHECK_INTERVAL", "MAX_CHECK_INTERVAL",
    # 异常
    "ConfigError",
]
