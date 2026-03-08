"""配置管理模块

支持从 JSON 配置文件和环境变量加载配置，提供配置验证、热重载等功能。
环境变量优先级高于配置文件。

配置项说明：
    - qbittorrent: qBittorrent 连接配置
    - ai: AI 分类器配置
    - categories: 分类规则配置
    - check_interval: 剪贴板检查间隔（秒）
    - log_level: 日志级别

环境变量：
    QBIT_HOST: qBittorrent 服务器地址 (默认: localhost)
    QBIT_PORT: qBittorrent 服务器端口 (默认: 8080)
    QBIT_USERNAME: qBittorrent 用户名 (默认: admin)
    QBIT_PASSWORD: qBittorrent 密码（必需）
    QBIT_USE_HTTPS: 是否使用 HTTPS (默认: false)
    AI_ENABLED: 是否启用 AI 分类 (默认: true)
    AI_API_KEY: AI API 密钥
    AI_MODEL: AI 模型名称 (默认: deepseek-chat)
    AI_BASE_URL: AI API 基础 URL
    AI_TIMEOUT: AI 请求超时时间 (默认: 30)
    AI_MAX_RETRIES: AI 请求最大重试次数 (默认: 3)
    CHECK_INTERVAL: 剪贴板检查间隔 (默认: 1.0)
    LOG_LEVEL: 日志级别 (默认: INFO)

使用示例：
    >>> from qbittorrent_monitor.config import load_config
    >>> config = load_config()
    >>> print(config.qbittorrent.host)
    'localhost'
    
    # 使用热重载
    >>> from qbittorrent_monitor.config import ConfigManager
    >>> manager = ConfigManager()
    >>> config = manager.get_config()
"""

from __future__ import annotations

# 基础配置
from .base import Config

# 子配置类
from .qb import QBConfig
from .ai import AIConfig
from .categories import CategoryConfig, get_default_categories
from .database import DatabaseConfig
from .metrics import MetricsConfig
from .plugins import PluginConfig

# 管理器
from .manager import ConfigManager

# 验证工具
from .validators import parse_bool, parse_int, parse_float

# 常量
from .constants import (
    VALID_LOG_LEVELS,
    MIN_PORT, MAX_PORT,
    MIN_TIMEOUT, MAX_TIMEOUT,
    MIN_RETRIES, MAX_RETRIES,
    MIN_CHECK_INTERVAL, MAX_CHECK_INTERVAL,
)

# 加载函数（向后兼容）
from .env_loader import load_config

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
]
