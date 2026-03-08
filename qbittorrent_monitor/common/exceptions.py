"""统一的异常体系和错误代码

提供结构化的错误处理和统一的错误日志格式。
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    import logging


class ErrorCode(Enum):
    """错误代码枚举
    
    错误代码格式: 模块(2位) + 类别(2位) + 序号(2位)
    
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


class QBMonitorError(Exception):
    """基础异常类
    
    所有自定义异常的基类，提供统一的错误代码和上下文信息。
    
    Attributes:
        message: 错误消息
        error_code: 错误代码
        context: 错误上下文信息
        cause: 原始异常（如果有）
    
    Example:
        >>> raise QBMonitorError(
        ...     "配置加载失败",
        ...     error_code=ErrorCode.CONFIG_FILE_NOT_FOUND,
        ...     context={"path": "/path/to/config.json"}
        ... )
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[ErrorCode] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or ErrorCode.UNKNOWN_ERROR
        self.context = context or {}
        self.cause = cause
    
    def __str__(self) -> str:
        parts = [f"[{self.error_code.value}] {self.message}"]
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"({context_str})")
        if self.cause:
            parts.append(f"[原因: {type(self.cause).__name__}: {self.cause}]")
        return " ".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，便于序列化"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "context": self.context,
            "cause": str(self.cause) if self.cause else None,
        }
    
    def log(self, logger: logging.Logger, level: int = None) -> None:
        """记录错误日志
        
        Args:
            logger: 日志记录器
            level: 日志级别，默认为 ERROR
        """
        import logging
        level = level or logging.ERROR
        logger.log(level, str(self))


class ConfigError(QBMonitorError):
    """配置错误
    
    配置加载、验证或解析失败时抛出。
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[ErrorCode] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        if error_code is None:
            error_code = ErrorCode.CONFIG_INVALID
        super().__init__(message, error_code, context, cause)


class QBClientError(QBMonitorError):
    """qBittorrent 客户端错误
    
    与 qBittorrent 服务器通信失败时抛出。
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[ErrorCode] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        if error_code is None:
            error_code = ErrorCode.QB_API_ERROR
        super().__init__(message, error_code, context, cause)


class QBAuthError(QBClientError):
    """认证错误
    
    登录失败或会话过期时抛出。
    """
    
    def __init__(
        self,
        message: str = "认证失败",
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message,
            ErrorCode.QB_AUTH_FAILED,
            context,
            cause,
        )


class QBConnectionError(QBClientError):
    """连接错误
    
    无法连接到 qBittorrent 服务器时抛出。
    """
    
    def __init__(
        self,
        message: str = "无法连接到 qBittorrent 服务器",
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message,
            ErrorCode.QB_CONNECTION_FAILED,
            context,
            cause,
        )


class AIError(QBMonitorError):
    """AI 分类错误
    
    AI 请求失败或返回无效响应时抛出。
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[ErrorCode] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        if error_code is None:
            error_code = ErrorCode.AI_REQUEST_FAILED
        super().__init__(message, error_code, context, cause)


class ClassificationError(QBMonitorError):
    """分类错误
    
    内容分类失败时抛出。
    """
    
    def __init__(
        self,
        message: str = "分类失败",
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message,
            ErrorCode.CLASSIFICATION_FAILED,
            context,
            cause,
        )


class ValidationError(QBMonitorError):
    """验证错误
    
    输入验证失败时抛出。
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        ctx = context or {}
        if field:
            ctx["field"] = field
        if value is not None:
            ctx["value"] = value
        super().__init__(
            message,
            ErrorCode.INVALID_ARGUMENT,
            ctx,
        )


class SecurityError(QBMonitorError):
    """安全错误
    
    安全检查失败时抛出。
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[ErrorCode] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        if error_code is None:
            error_code = ErrorCode.SECURITY_VALIDATION_FAILED
        super().__init__(message, error_code, context)


def get_error_code(exception: Exception) -> ErrorCode:
    """获取异常的错误代码
    
    Args:
        exception: 异常对象
        
    Returns:
        错误代码，如果不是 QBMonitorError 则返回 UNKNOWN_ERROR
    """
    if isinstance(exception, QBMonitorError):
        return exception.error_code
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
    
    if isinstance(exception, QBMonitorError):
        parts.append(f"[{exception.error_code.value}] {exception.message}")
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
