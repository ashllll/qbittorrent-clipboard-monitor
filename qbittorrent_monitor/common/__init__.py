"""通用工具模块

提供跨模块共享的工具函数、装饰器、验证器和异常类。
"""

from .exceptions import (
    QBMonitorError,
    ConfigError,
    QBClientError,
    QBAuthError,
    QBConnectionError,
    AIError,
    ClassificationError,
    ValidationError,
    SecurityError,
    ErrorCode,
    get_error_code,
    format_error_message,
)
from .decorators import (
    safe_operation,
    async_safe_operation,
    retry_with_backoff,
    log_execution_time,
    validate_input,
)
from .validators import (
    validate_port,
    validate_timeout,
    validate_retries,
    validate_interval,
    validate_log_level,
    validate_non_empty_string,
    validate_boolean,
    validate_range,
    Validator,
)

__all__ = [
    # 异常类
    "QBMonitorError",
    "ConfigError",
    "QBClientError",
    "QBAuthError",
    "QBConnectionError",
    "AIError",
    "ClassificationError",
    "ValidationError",
    "SecurityError",
    "ErrorCode",
    "get_error_code",
    "format_error_message",
    # 装饰器
    "safe_operation",
    "async_safe_operation",
    "retry_with_backoff",
    "log_execution_time",
    "validate_input",
    # 验证器
    "validate_port",
    "validate_timeout",
    "validate_retries",
    "validate_interval",
    "validate_log_level",
    "validate_non_empty_string",
    "validate_boolean",
    "validate_range",
    "Validator",
]
