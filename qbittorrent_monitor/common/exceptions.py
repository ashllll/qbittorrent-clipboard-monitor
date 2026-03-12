"""统一的异常体系和错误代码

提供结构化的错误处理和统一的错误日志格式。

注意：此模块保留以提供向后兼容。
新代码应使用 qbittorrent_monitor.exceptions_unified 模块。
"""

from __future__ import annotations

import warnings
from enum import Enum
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    import logging


# 发出模块级别的弃用警告
warnings.warn(
    "qbittorrent_monitor.common.exceptions 已弃用。"
    "请使用 qbittorrent_monitor.exceptions_unified 模块，"
    "例如: from qbittorrent_monitor.exceptions_unified import ConfigurationError",
    DeprecationWarning,
    stacklevel=2
)


# 从新的统一异常模块重新导出
from ..exceptions_unified import (
    QBittorrentMonitorError as _QBittorrentMonitorError,
    QBittorrentMonitorError as QBMonitorError,
    ConfigurationError as _ConfigurationError,
    ConfigurationError as ConfigError,
    QBittorrentError as _QBittorrentError,
    QBittorrentError as QBClientError,
    QbtAuthError as QBAuthError,
    QbtConnectionError as QBConnectionError,
    AIError as _AIError,
    AIError,
    ClassificationError as _ClassificationError,
    ClassificationError,
    ValidationError as _ValidationError,
    ValidationError,
    SecurityError as _SecurityError,
    SecurityError,
)


class ErrorCode(Enum):
    """错误代码枚举（保留以提供向后兼容）
    
    错误代码格式: 模块(2位) + 类别(2位) + 序号(2位)
    
    注意：新代码应使用 qbittorrent_monitor.exceptions_unified 中的错误码体系。
    
    模块代码:
        01 - 通用 (Common)
        10 - 配置 (Config)
        20 - qBittorrent 客户端 (QBClient)
        30 - AI 分类 (AI)
        40 - 分类器 (Classifier)
        50 - 监控器 (Monitor)
        60 - 安全 (Security)
        70 - 数据库 (Database)
    
    类别代码:
        00 - 成功
        10 - 输入错误 (Validation)
        20 - 认证错误 (Authentication)
        30 - 连接错误 (Connection)
        40 - 超时错误 (Timeout)
        50 - 内部错误 (Internal)
        60 - 资源错误 (Resource)
        70 - 安全错误 (Security)
    """
    
    # 通用错误 (01xx)
    UNKNOWN_ERROR = "015000"
    NOT_IMPLEMENTED = "015001"
    INVALID_ARGUMENT = "011000"
    
    # 配置错误 (10xx)
    CONFIG_INVALID = "101000"
    CONFIG_FILE_NOT_FOUND = "106001"
    CONFIG_FILE_INVALID = "101002"
    CONFIG_ENV_INVALID = "101003"
    CONFIG_MISSING_REQUIRED = "101004"
    CONFIG_TYPE_ERROR = "101005"
    CONFIG_RANGE_ERROR = "101006"
    
    # qBittorrent 客户端错误 (20xx)
    QB_AUTH_FAILED = "202001"
    QB_SESSION_EXPIRED = "202002"
    QB_CONNECTION_FAILED = "203001"
    QB_CONNECTION_TIMEOUT = "204001"
    QB_SERVER_ERROR = "205001"
    QB_API_ERROR = "205002"
    QB_TORRENT_EXISTS = "205003"
    QB_INVALID_MAGNET = "201001"
    QB_ADD_FAILED = "205004"
    
    # AI 错误 (30xx)
    AI_NOT_CONFIGURED = "306001"
    AI_REQUEST_FAILED = "305001"
    AI_TIMEOUT = "304001"
    AI_RATE_LIMITED = "304002"
    AI_INVALID_RESPONSE = "301001"
    AI_CLASSIFICATION_FAILED = "305002"
    
    # 分类器错误 (40xx)
    CLASSIFICATION_FAILED = "405001"
    CLASSIFICATION_CACHE_ERROR = "405002"
    
    # 监控器错误 (50xx)
    MONITOR_CLIPBOARD_ERROR = "505001"
    MONITOR_PROCESSING_ERROR = "505002"
    MONITOR_DATABASE_ERROR = "505003"
    
    # 安全错误 (60xx)
    SECURITY_VALIDATION_FAILED = "601001"
    SECURITY_PATH_TRAVERSAL = "607001"
    SECURITY_INVALID_INPUT = "601002"
    SECURITY_SENSITIVE_DATA_LEAK = "607002"
    
    # 数据库错误 (70xx)
    DB_CONNECTION_FAILED = "703001"
    DB_QUERY_FAILED = "705001"
    DB_MIGRATION_FAILED = "705002"


def get_error_code(exception: Exception) -> ErrorCode:
    """获取异常的错误代码
    
    Args:
        exception: 异常对象
        
    Returns:
        错误代码，如果不是 QBMonitorError 则返回 UNKNOWN_ERROR
    """
    if isinstance(exception, _QBittorrentMonitorError):
        # 将新的错误码映射到旧的 ErrorCode
        if hasattr(exception, 'error_code') and exception.error_code:
            code_str = str(exception.error_code)
            # 尝试匹配旧的错误码
            for code in ErrorCode:
                if code.value == code_str:
                    return code
    return ErrorCode.UNKNOWN_ERROR


def format_error_message(
    exception: Exception,
    include_context: bool = True,
    include_traceback: bool = False,
) -> str:
    """格式化错误消息
    
    Args:
        exception: 异常对象
        include_context: 是否包含上下文信息
        include_traceback: 是否包含堆栈跟踪
        
    Returns:
        格式化的错误消息
    """
    parts = []
    
    if isinstance(exception, _QBittorrentMonitorError):
        error_code = get_error_code(exception)
        parts.append(f"[{error_code.value}] {exception.message}")
        if include_context and exception.context:
            context_str = ", ".join(f"{k}={v}" for k, v in exception.context.items())
            parts.append(f"({context_str})")
    else:
        parts.append(f"[{type(exception).__name__}] {str(exception)}")
    
    if include_traceback:
        import traceback
        parts.append("\n堆栈跟踪:\n")
        parts.append(traceback.format_exc())
    
    return " ".join(parts)


# 模块导出
__all__ = [
    # 错误码
    "ErrorCode",
    "get_error_code",
    "format_error_message",
    # 异常类（从新的模块重新导出）
    "QBMonitorError",
    "ConfigError",
    "QBClientError",
    "QBAuthError",
    "QBConnectionError",
    "AIError",
    "ClassificationError",
    "ValidationError",
    "SecurityError",
]
