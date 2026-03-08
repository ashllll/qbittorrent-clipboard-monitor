"""qBittorrent Clipboard Monitor - 蜂群优化版核心模块"""

from __future__ import annotations

from .__version__ import (
    __version__,
    PROJECT_NAME,
    PROJECT_DESCRIPTION,
)
from .constants import Limits, Timeouts, CacheSizes, Defaults, Categories

# 蜂群优化：核心模块
from .core import MagnetProcessor, MagnetInfo, DebounceService, PacingService

# 蜂群优化：接口定义
from .interfaces import (
    IClassifier,
    ITorrentClient,
    IDatabase,
    IMetricsService,
    ClassificationResult,
    TorrentAddResult,
    TorrentRecord as InterfaceTorrentRecord,
)

# Phase 1-5：Repository 模式
from .repository import (
    Repository,
    TorrentRepository,
    StatsRepository,
    EventRepository,
    TorrentRecord,
    CategoryStats,
    SystemEvent,
)

# Phase 1-5：服务层
from .services import HistoryService, MetricsService

# Phase 1-5：依赖注入
from .container import Container, get_container, bootstrap

# Phase 1-5：性能优化
from .performance import TrieClassifier, BatchDatabaseWriter, BatchRecord

# Phase 1-5：安全加固
from .security_enhanced import (
    MagnetSecurityValidator,
    PathSecurityValidator,
    LogSecuritySanitizer,
    SecurityPolicy,
)

# 配置模块（新模块化结构）
from .config.base import Config
from .config.qb import QBConfig
from .config.ai import AIConfig
from .config.categories import CategoryConfig
from .config.database import DatabaseConfig
from .config.metrics import MetricsConfig
from .config.plugins import PluginConfig
from .config.manager import ConfigManager
from .config.env_loader import load_config

# 核心类
from .qb_client import QBClient
from .classifier import ContentClassifier
from .monitor import ClipboardMonitor

# 日志和安全
from .logging_filters import SensitiveDataFilter, setup_sensitive_logging
from .logger import (
    setup_logging,
    get_logger,
    LogConfig,
    LogFormat,
    configure_from_dict,
    configure_from_config,
    StructuredLogger,
)
from .security import (
    validate_magnet,
    sanitize_magnet,
    extract_magnet_hash_safe,
    validate_save_path,
    sanitize_filename,
    validate_url,
    validate_hostname,
    get_secure_headers,
)

# 指标模块
from . import metrics
from .metrics_server import MetricsServer, start_metrics_server

# Repository 模式（新模块）
from .repository import (
    Repository,
    RepositoryError,
    RecordNotFoundError,
    DuplicateRecordError,
    TorrentRepository,
    StatsRepository,
    TorrentRecord,
    CategoryStats,
    SystemEvent,
)

# Watchers 组件（新模块）
from .watchers import (
    DebounceFilter,
    RateLimiter,
    ClipboardWatcher,
    ClipboardCache,
)
from .watchers.clipboard_watcher import ClipboardEvent

# 插件系统
from .plugins import (
    BasePlugin,
    NotifierPlugin,
    ClassifierPlugin,
    HandlerPlugin,
    PluginManager,
    PluginMetadata,
    PluginState,
    PluginType,
    HookRegistry,
    HookType,
    register_hook,
    invoke_hooks,
)

__all__ = [
    # 版本信息
    "__version__",
    "PROJECT_NAME",
    "PROJECT_DESCRIPTION",
    # 常量
    "Limits",
    "Timeouts",
    "CacheSizes",
    "Defaults",
    "Categories",
    # 蜂群优化：核心模块
    "MagnetProcessor",
    "MagnetInfo",
    "DebounceService",
    "PacingService",
    # 蜂群优化：接口定义
    "IClassifier",
    "ITorrentClient",
    "IDatabase",
    "IMetricsService",
    "ClassificationResult",
    "TorrentAddResult",
    # Phase 1-5：Repository 模式
    "Repository",
    "TorrentRepository",
    "StatsRepository",
    "EventRepository",
    "TorrentRecord",
    "CategoryStats",
    "SystemEvent",
    # Phase 1-5：服务层
    "HistoryService",
    "MetricsService",
    # Phase 1-5：依赖注入
    "Container",
    "get_container",
    "bootstrap",
    # Phase 1-5：性能优化
    "TrieClassifier",
    "BatchDatabaseWriter",
    "BatchRecord",
    # Phase 1-5：安全加固
    "MagnetSecurityValidator",
    "PathSecurityValidator",
    "LogSecuritySanitizer",
    "SecurityPolicy",
    # 配置类（新模块化）
    "Config",
    "ConfigManager",
    "load_config",
    "QBConfig",
    "AIConfig",
    "CategoryConfig",
    "DatabaseConfig",
    "MetricsConfig",
    "PluginConfig",
    # 核心类
    "QBClient",
    "ContentClassifier",
    "ClipboardMonitor",
    # 日志和安全
    "SensitiveDataFilter",
    "setup_sensitive_logging",
    "setup_logging",
    "get_logger",
    "LogConfig",
    "LogFormat",
    "configure_from_dict",
    "configure_from_config",
    "StructuredLogger",
    "validate_magnet",
    "sanitize_magnet",
    "extract_magnet_hash_safe",
    "validate_save_path",
    "sanitize_filename",
    "validate_url",
    "validate_hostname",
    "get_secure_headers",
    # Web 模块
    "web",
    # 指标模块
    "metrics",
    "MetricsServer",
    "start_metrics_server",
    # Repository 模式
    "Repository",
    "RepositoryError",
    "RecordNotFoundError",
    "DuplicateRecordError",
    "TorrentRepository",
    "StatsRepository",
    "TorrentRecord",
    "CategoryStats",
    "SystemEvent",
    # Watchers 组件
    "DebounceFilter",
    "RateLimiter",
    "ClipboardWatcher",
    "ClipboardEvent",
    "ClipboardCache",
    # 插件系统
    "BasePlugin",
    "NotifierPlugin",
    "ClassifierPlugin",
    "HandlerPlugin",
    "PluginManager",
    "PluginMetadata",
    "PluginState",
    "PluginType",
    "HookRegistry",
    "HookType",
    "register_hook",
    "invoke_hooks",
]
