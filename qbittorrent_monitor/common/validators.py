"""通用验证器模块

提供统一的输入验证函数，消除魔法数字分散问题。
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional, Set, TypeVar, Union

from .exceptions import (
    ConfigError,
    ValidationError,
    ErrorCode,
)

T = TypeVar("T")

# ============ 常量定义 ============

# 网络相关常量
MIN_PORT = 1
MAX_PORT = 65535
DEFAULT_PORT = 8080

# 超时相关常量（秒）
MIN_TIMEOUT = 1
MAX_TIMEOUT = 300
DEFAULT_TIMEOUT = 30

# 重试相关常量
MIN_RETRIES = 0
MAX_RETRIES = 10
DEFAULT_RETRIES = 3

# 检查间隔相关常量（秒）
MIN_CHECK_INTERVAL = 0.1
MAX_CHECK_INTERVAL = 60.0
DEFAULT_CHECK_INTERVAL = 1.0

# 日志级别常量
VALID_LOG_LEVELS: Set[str] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
DEFAULT_LOG_LEVEL = "INFO"

# 字符串长度限制
MIN_STRING_LENGTH = 1
MAX_STRING_LENGTH = 10000

# URL 相关常量
MAX_URL_LENGTH = 2048
VALID_URL_SCHEMES: Set[str] = {"http", "https"}

# 文件名相关常量
MAX_FILENAME_LENGTH = 255
MAX_PATH_LENGTH = 4096


class Validator:
    """验证器类
    
    提供链式验证接口。
    
    Example:
        >>> validator = Validator()
        >>> value = validator.check("port", 8080).is_port().value
    """
    
    def __init__(self, field_name: Optional[str] = None, value: Any = None):
        self.field_name = field_name or "value"
        self.value = value
        self._errors: list = []
    
    def check(self, field_name: str, value: Any) -> Validator:
        """开始验证新的值"""
        self.field_name = field_name
        self.value = value
        self._errors = []
        return self
    
    def is_not_none(self, message: Optional[str] = None) -> Validator:
        """验证值不为 None"""
        if self.value is None:
            self._errors.append(message or f"{self.field_name} 不能为 None")
        return self
    
    def is_not_empty(self, message: Optional[str] = None) -> Validator:
        """验证值不为空"""
        if not self.value:
            self._errors.append(message or f"{self.field_name} 不能为空")
        return self
    
    def is_string(self, message: Optional[str] = None) -> Validator:
        """验证值是字符串类型"""
        if not isinstance(self.value, str):
            self._errors.append(message or f"{self.field_name} 必须是字符串")
        return self
    
    def is_integer(self, message: Optional[str] = None) -> Validator:
        """验证值是整数类型"""
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            self._errors.append(message or f"{self.field_name} 必须是整数")
        return self
    
    def is_number(self, message: Optional[str] = None) -> Validator:
        """验证值是数字类型（int 或 float）"""
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            self._errors.append(message or f"{self.field_name} 必须是数字")
        return self
    
    def is_boolean(self, message: Optional[str] = None) -> Validator:
        """验证值是布尔类型"""
        if not isinstance(self.value, bool):
            self._errors.append(message or f"{self.field_name} 必须是布尔值")
        return self
    
    def is_port(self, message: Optional[str] = None) -> Validator:
        """验证值是有效的端口号"""
        self.is_integer()
        if self._errors:
            return self
        
        if not (MIN_PORT <= self.value <= MAX_PORT):
            self._errors.append(
                message or f"{self.field_name} 必须是 {MIN_PORT}-{MAX_PORT} 范围内的整数"
            )
        return self
    
    def is_timeout(self, message: Optional[str] = None) -> Validator:
        """验证值是有效的超时时间"""
        self.is_number()
        if self._errors:
            return self
        
        if not (MIN_TIMEOUT <= self.value <= MAX_TIMEOUT):
            self._errors.append(
                message or f"{self.field_name} 必须是 {MIN_TIMEOUT}-{MAX_TIMEOUT} 范围内的数字"
            )
        return self
    
    def is_retries(self, message: Optional[str] = None) -> Validator:
        """验证值是有效的重试次数"""
        self.is_integer()
        if self._errors:
            return self
        
        if not (MIN_RETRIES <= self.value <= MAX_RETRIES):
            self._errors.append(
                message or f"{self.field_name} 必须是 {MIN_RETRIES}-{MAX_RETRIES} 范围内的整数"
            )
        return self
    
    def is_interval(self, message: Optional[str] = None) -> Validator:
        """验证值是有效的检查间隔"""
        self.is_number()
        if self._errors:
            return self
        
        if not (MIN_CHECK_INTERVAL <= self.value <= MAX_CHECK_INTERVAL):
            self._errors.append(
                message or f"{self.field_name} 必须是 {MIN_CHECK_INTERVAL}-{MAX_CHECK_INTERVAL} 范围内的数字"
            )
        return self
    
    def is_log_level(self, message: Optional[str] = None) -> Validator:
        """验证值是有效的日志级别"""
        self.is_string()
        if self._errors:
            return self
        
        if self.value.upper() not in VALID_LOG_LEVELS:
            self._errors.append(
                message or f"{self.field_name} 必须是以下值之一: {', '.join(VALID_LOG_LEVELS)}"
            )
        return self
    
    def has_length(self, min_len: int = 0, max_len: int = MAX_STRING_LENGTH, 
                   message: Optional[str] = None) -> Validator:
        """验证值长度在范围内"""
        try:
            length = len(self.value)
            if length < min_len or length > max_len:
                self._errors.append(
                    message or f"{self.field_name} 长度必须在 {min_len}-{max_len} 之间"
                )
        except TypeError:
            self._errors.append(f"{self.field_name} 无法计算长度")
        return self
    
    def matches_pattern(self, pattern: str, message: Optional[str] = None) -> Validator:
        """验证值匹配正则表达式"""
        self.is_string()
        if self._errors:
            return self
        
        if not re.match(pattern, self.value):
            self._errors.append(message or f"{self.field_name} 格式无效")
        return self
    
    def is_one_of(self, choices: set, message: Optional[str] = None) -> Validator:
        """验证值在允许的集合中"""
        if self.value not in choices:
            choices_str = ", ".join(str(c) for c in choices)
            self._errors.append(message or f"{self.field_name} 必须是以下值之一: {choices_str}")
        return self
    
    def custom(self, validator: Callable[[Any], bool], message: str) -> Validator:
        """自定义验证"""
        try:
            if not validator(self.value):
                self._errors.append(f"{self.field_name}: {message}")
        except Exception as e:
            self._errors.append(f"{self.field_name} 验证失败: {str(e)}")
        return self
    
    def validate(self) -> Any:
        """执行验证并返回值或抛出异常"""
        if self._errors:
            raise ValidationError(
                "; ".join(self._errors),
                field=self.field_name,
                value=self.value,
            )
        return self.value


# ============ 独立验证函数 ============

def validate_port(value: Any, field_name: str = "port") -> int:
    """验证端口号
    
    Args:
        value: 要验证的值
        field_name: 字段名称（用于错误信息）
    
    Returns:
        验证后的整数端口号
    
    Raises:
        ValidationError: 验证失败时抛出
    """
    validator = Validator()
    return validator.check(field_name, value).is_port().validate()


def validate_timeout(value: Any, field_name: str = "timeout") -> float:
    """验证超时时间
    
    Args:
        value: 要验证的值
        field_name: 字段名称（用于错误信息）
    
    Returns:
        验证后的超时时间
    
    Raises:
        ValidationError: 验证失败时抛出
    """
    validator = Validator()
    return float(validator.check(field_name, value).is_timeout().validate())


def validate_retries(value: Any, field_name: str = "retries") -> int:
    """验证重试次数
    
    Args:
        value: 要验证的值
        field_name: 字段名称（用于错误信息）
    
    Returns:
        验证后的重试次数
    
    Raises:
        ValidationError: 验证失败时抛出
    """
    validator = Validator()
    return validator.check(field_name, value).is_retries().validate()


def validate_interval(value: Any, field_name: str = "interval") -> float:
    """验证检查间隔
    
    Args:
        value: 要验证的值
        field_name: 字段名称（用于错误信息）
    
    Returns:
        验证后的检查间隔
    
    Raises:
        ValidationError: 验证失败时抛出
    """
    validator = Validator()
    return float(validator.check(field_name, value).is_interval().validate())


def validate_log_level(value: Any, field_name: str = "log_level") -> str:
    """验证日志级别
    
    Args:
        value: 要验证的值
        field_name: 字段名称（用于错误信息）
    
    Returns:
        验证后的日志级别（大写）
    
    Raises:
        ValidationError: 验证失败时抛出
    """
    validator = Validator()
    validated = validator.check(field_name, value).is_log_level().validate()
    return str(validated).upper()


def validate_non_empty_string(value: Any, field_name: str = "value", 
                              min_length: int = MIN_STRING_LENGTH,
                              max_length: int = MAX_STRING_LENGTH) -> str:
    """验证非空字符串
    
    Args:
        value: 要验证的值
        field_name: 字段名称（用于错误信息）
        min_length: 最小长度
        max_length: 最大长度
    
    Returns:
        验证后的字符串
    
    Raises:
        ValidationError: 验证失败时抛出
    """
    validator = Validator()
    return validator.check(field_name, value).is_string().is_not_empty().has_length(
        min_length, max_length
    ).validate()


def validate_boolean(value: Any, field_name: str = "value") -> bool:
    """验证布尔值
    
    Args:
        value: 要验证的值
        field_name: 字段名称（用于错误信息）
    
    Returns:
        验证后的布尔值
    
    Raises:
        ValidationError: 验证失败时抛出
    """
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        value_lower = value.lower()
        if value_lower in ("true", "1", "yes", "on", "enabled"):
            return True
        elif value_lower in ("false", "0", "no", "off", "disabled", ""):
            return False
    
    raise ValidationError(
        f"{field_name} 必须是布尔值 (true/false)",
        field=field_name,
        value=value,
    )


def validate_range(
    value: Any,
    min_value: Optional[T] = None,
    max_value: Optional[T] = None,
    field_name: str = "value",
) -> T:
    """验证数值范围
    
    Args:
        value: 要验证的值
        min_value: 最小值（包含）
        max_value: 最大值（包含）
        field_name: 字段名称（用于错误信息）
    
    Returns:
        验证后的值
    
    Raises:
        ValidationError: 验证失败时抛出
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(
            f"{field_name} 必须是数字",
            field=field_name,
            value=value,
        )
    
    if min_value is not None and value < min_value:
        raise ValidationError(
            f"{field_name} 不能小于 {min_value}",
            field=field_name,
            value=value,
        )
    
    if max_value is not None and value > max_value:
        raise ValidationError(
            f"{field_name} 不能大于 {max_value}",
            field=field_name,
            value=value,
        )
    
    return value


def validate_url_scheme(url: str, allowed_schemes: Optional[set] = None) -> str:
    """验证 URL 协议
    
    Args:
        url: 要验证的 URL
        allowed_schemes: 允许的协议列表，默认 http/https
    
    Returns:
        验证后的 URL
    
    Raises:
        ValidationError: 验证失败时抛出
    """
    if allowed_schemes is None:
        allowed_schemes = VALID_URL_SCHEMES
    
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        
        if not parsed.scheme:
            raise ValidationError("URL 缺少协议", value=url)
        
        if parsed.scheme.lower() not in allowed_schemes:
            raise ValidationError(
                f"URL 使用不支持的协议 '{parsed.scheme}'",
                value=url,
            )
        
        return url
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"URL 解析失败: {str(e)}", value=url) from e


def create_range_validator(
    min_value: Optional[T] = None,
    max_value: Optional[T] = None,
    field_name: str = "value",
) -> Callable[[Any], T]:
    """创建范围验证器工厂函数
    
    Args:
        min_value: 最小值
        max_value: 最大值
        field_name: 字段名称
    
    Returns:
        验证器函数
    
    Example:
        >>> validate_positive = create_range_validator(min_value=1)
        >>> validate_percentage = create_range_validator(0, 100)
    """
    def validator(value: Any) -> T:
        return validate_range(value, min_value, max_value, field_name)
    return validator
