"""核心异常定义（向后兼容层）

此模块保留以提供向后兼容。新代码应使用 qbittorrent_monitor.exceptions_unified 模块。

迁移说明：
    - 所有异常类已移动到 exceptions_unified 模块
    - 此文件现在只是导入和转发
    - 计划在 v2.0 中移除此兼容层

旧方式（仍然支持，但会发出弃用警告）：
    from qbittorrent_monitor.exceptions import ConfigError, AIError

新方式（推荐）：
    from qbittorrent_monitor.exceptions_unified import (
        ConfigurationError,  # 注意：ConfigError 更名为 ConfigurationError
        AIError,
    )
"""

from __future__ import annotations

import warnings

# 发出模块级别的弃用警告
warnings.warn(
    "从 qbittorrent_monitor.exceptions 导入已弃用。"
    "请使用 qbittorrent_monitor.exceptions_unified 模块，"
    "例如: from qbittorrent_monitor.exceptions_unified import ConfigurationError, NetworkError",
    DeprecationWarning,
    stacklevel=2
)

# 重新导出所有异常以保持向后兼容
# 基础异常
from .exceptions_unified import (
    QBittorrentMonitorError,
    QBMonitorError,
)

# 配置异常
from .exceptions_unified import (
    ConfigurationError,
    ConfigError,  # 别名，向后兼容
    ConfigValidationError,
    ConfigNotFoundError,
    ConfigLoadError,
)

# 网络异常
from .exceptions_unified import (
    NetworkError,
    NetworkTimeoutError,
    NetworkConnectionError,
)

# qBittorrent 异常
from .exceptions_unified import (
    QBittorrentError,
    QBClientError,  # 别名，向后兼容
    QbtAuthError,
    QBAuthError,  # 别名，向后兼容
    QbtRateLimitError,
    QbtPermissionError,
    QbtServerError,
    QbtConnectionError,
    QBConnectionError,  # 别名，向后兼容
    QbtApiError,
)

# AI 异常
from .exceptions_unified import (
    AIError,
    AIApiError,
    AIAPIError,  # 别名，向后兼容（修复笔误）
    AICreditError,
    AIRateLimitError,
    AIResponseError,
    AIFallbackError,
    AITimeoutError,
    AIInitError,
)

# 分类异常
from .exceptions_unified import ClassificationError

# 剪贴板异常
from .exceptions_unified import (
    ClipboardError,
    ClipboardPermissionError,
    ClipboardReadError,
    ClipboardWriteError,
)

# 种子异常
from .exceptions_unified import (
    TorrentError,
    TorrentParseError,
    MagnetParseError,
    InvalidMagnetError,
    DuplicateTorrentError,
)

# 通知异常
from .exceptions_unified import (
    NotificationError,
    NotificationDeliveryError,
    NotificationTemplateError,
)

# 爬虫异常
from .exceptions_unified import (
    CrawlerError,
    CrawlerTimeoutError,
    CrawlerRateLimitError,
    CrawlerExtractionError,
)

# 缓存异常
from .exceptions_unified import (
    CacheError,
    CacheNotFoundError,
    CacheWriteError,
    CacheReadError,
)

# 资源异常
from .exceptions_unified import (
    ResourceError,
    ResourceTimeoutError,
    ResourceExhaustedError,
)

# 安全异常
from .exceptions_unified import (
    SecurityError,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
)

# 数据库异常
from .exceptions_unified import (
    DatabaseError,
    DatabaseConnectionError,
    DatabaseQueryError,
)

# 并发异常
from .exceptions_unified import (
    ConcurrencyError,
    DeadlockError,
    TaskTimeoutError,
)

# 状态异常
from .exceptions_unified import StateError

# 重试标记异常
from .exceptions_unified import (
    RetryableError,
    NonRetryableError,
    CircuitBreakerOpenError,
)

# 错误码相关
from .exceptions_unified import (
    ErrorCategory,
    ErrorSeverity,
    ErrorCode,
    ERROR_CODES,
    get_error_code,
)

# 模块导出列表
__all__ = [
    # 基础异常
    "QBittorrentMonitorError",
    "QBMonitorError",
    
    # 配置异常
    "ConfigurationError",
    "ConfigError",
    "ConfigValidationError",
    "ConfigNotFoundError",
    "ConfigLoadError",
    
    # 网络异常
    "NetworkError",
    "NetworkTimeoutError",
    "NetworkConnectionError",
    
    # qBittorrent 异常
    "QBittorrentError",
    "QBClientError",
    "QbtAuthError",
    "QBAuthError",
    "QbtRateLimitError",
    "QbtPermissionError",
    "QbtServerError",
    "QbtConnectionError",
    "QBConnectionError",
    "QbtApiError",
    
    # AI 异常
    "AIError",
    "AIApiError",
    "AIAPIError",
    "AICreditError",
    "AIRateLimitError",
    "AIResponseError",
    "AIFallbackError",
    "AITimeoutError",
    "AIInitError",
    
    # 分类异常
    "ClassificationError",
    
    # 剪贴板异常
    "ClipboardError",
    "ClipboardPermissionError",
    "ClipboardReadError",
    "ClipboardWriteError",
    
    # 种子异常
    "TorrentError",
    "TorrentParseError",
    "MagnetParseError",
    "InvalidMagnetError",
    "DuplicateTorrentError",
    
    # 通知异常
    "NotificationError",
    "NotificationDeliveryError",
    "NotificationTemplateError",
    
    # 爬虫异常
    "CrawlerError",
    "CrawlerTimeoutError",
    "CrawlerRateLimitError",
    "CrawlerExtractionError",
    
    # 缓存异常
    "CacheError",
    "CacheNotFoundError",
    "CacheWriteError",
    "CacheReadError",
    
    # 资源异常
    "ResourceError",
    "ResourceTimeoutError",
    "ResourceExhaustedError",
    
    # 安全异常
    "SecurityError",
    "AuthenticationError",
    "AuthorizationError",
    "ValidationError",
    
    # 数据库异常
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseQueryError",
    
    # 并发异常
    "ConcurrencyError",
    "DeadlockError",
    "TaskTimeoutError",
    
    # 状态异常
    "StateError",
    
    # 重试标记异常
    "RetryableError",
    "NonRetryableError",
    "CircuitBreakerOpenError",
    
    # 错误码相关
    "ErrorCategory",
    "ErrorSeverity",
    "ErrorCode",
    "ERROR_CODES",
    "get_error_code",
]
