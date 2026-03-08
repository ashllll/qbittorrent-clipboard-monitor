"""
日志过滤器模块

提供敏感信息过滤功能，防止密码、API密钥等泄露到日志
"""

from __future__ import annotations

import re
import logging
from typing import Pattern, List, Tuple, Optional, Any, Union

# 类型别名
PatternReplacement = Tuple[Pattern[str], str]


class SensitiveDataFilter(logging.Filter):
    """
    敏感信息过滤器
    
    过滤日志中的敏感信息，包括：
    - API密钥
    - 密码
    - 令牌
    - 磁力链接hash
    - 私钥
    - 认证头
    - Cookie
    - 连接字符串
    """
    
    # 定义需要过滤的模式列表
    SENSITIVE_PATTERNS: List[PatternReplacement] = [
        # API密钥（各种格式）- 更全面的匹配
        (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([\w\-]{10,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(api[_-]?secret["\']?\s*[:=]\s*["\']?)([^\s"\']{8,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(sk-[a-zA-Z0-9]{20,})', re.IGNORECASE), r'***'),
        
        # 密码 - 多种格式
        (re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^\s"\']{3,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(passwd["\']?\s*[:=]\s*["\']?)([^\s"\']{3,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(pwd["\']?\s*[:=]\s*["\']?)([^\s"\']{3,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'("password"\s*:\s*")([^"]{3,})"', re.IGNORECASE), r'\1***"'),
        
        # 令牌 - 多种格式
        (re.compile(r'(token["\']?\s*[:=]\s*["\']?)([\w\-\.]{10,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(access[_-]?token["\']?\s*[:=]\s*["\']?)([^\s"\']{10,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(refresh[_-]?token["\']?\s*[:=]\s*["\']?)([^\s"\']{10,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(bearer\s+)([\w\-\.]{10,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(Authorization["\']?\s*[:=]\s*["\']?\s*bearer\s+)([^\s"\']+)', re.IGNORECASE), r'\1***'),
        
        # 磁力链接hash（保留前8位，隐藏后32位）- 支持32位和40位hash
        (re.compile(r'(magnet:\?xt=urn:btih:)([a-f0-9]{8})[a-f0-9]{32}', re.IGNORECASE), r'\1\2***'),
        (re.compile(r'(magnet:\?xt=urn:btih:)([a-f0-9]{8})[a-f0-9]{24}', re.IGNORECASE), r'\1\2***'),
        
        # 私钥
        (re.compile(r'(private[_-]?key["\']?\s*[:=]\s*["\']?)([^\s"\']{10,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(secret["\']?\s*[:=]\s*["\']?)([^\s"\']{3,})', re.IGNORECASE), r'\1***'),
        
        # 数据库连接字符串中的密码
        (re.compile(r'(://[^:]+:)([^@]+)(@)', re.IGNORECASE), r'\1***\3'),
        
        # Cookie中的敏感信息
        (re.compile(r'(SID|session|auth)["\']?\s*[:=]\s*["\']?([^;\s"\']{5,})', re.IGNORECASE), r'\1=***'),
        
        # 配置文件中显示的密码
        (re.compile(r'("password"\s*:\s*").*?(")', re.IGNORECASE), r'\1***\2'),
        (re.compile(r'(username\s*=\s*)(\S+)', re.IGNORECASE), r'\1***'),
        
        # SSH密钥
        (re.compile(r'(ssh-[a-z]+\s+)([A-Za-z0-9+/=]{20,})', re.IGNORECASE), r'\1***'),
        
        # URL中的认证信息
        (re.compile(r'(https?://)([^:]+):([^@]+)@', re.IGNORECASE), r'\1\2:***@'),
    ]
    
    # 需要完全过滤的字段名
    SENSITIVE_KEYS: set[str] = {
        'password', 'passwd', 'pwd', 'secret', 'api_key', 'apikey',
        'api_secret', 'apisecret', 'token', 'access_token', 'accesstoken',
        'refresh_token', 'refreshtoken', 'private_key', 'privatekey',
        'auth_token', 'authtoken', 'bearer', 'credential', 'credentials',
        'session', 'cookie', 'sid',
    }
    
    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self.patterns: List[PatternReplacement] = self.SENSITIVE_PATTERNS
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录中的敏感信息
        
        Args:
            record: 日志记录对象
            
        Returns:
            True（始终通过，但内容可能被修改）
        """
        # 安全处理：先格式化再过滤
        if record.args:
            # 尝试安全格式化
            try:
                # 使用 % 格式化前过滤参数
                safe_args = tuple(
                    self._filter_sensitive_data(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
                # 应用过滤后的格式化
                formatted = record.msg % safe_args
                record.msg = self._filter_sensitive_data(formatted)
                record.args = ()  # 清空参数，因为已经格式化
            except (TypeError, ValueError):
                # 格式化失败，单独过滤
                if isinstance(record.msg, str):
                    record.msg = self._filter_sensitive_data(record.msg)
                # 仍然尝试过滤参数
                record.args = tuple(
                    self._filter_sensitive_data(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        else:
            # 过滤消息
            if isinstance(record.msg, str):
                record.msg = self._filter_sensitive_data(record.msg)
        
        # 过滤异常信息
        if record.exc_info and record.exc_info[1]:
            exc_str = str(record.exc_info[1])
            filtered_exc = self._filter_sensitive_data(exc_str)
            if filtered_exc != exc_str:
                # 创建新的异常对象（保留类型）
                try:
                    record.exc_info = (
                        record.exc_info[0],
                        record.exc_info[0](filtered_exc),
                        record.exc_info[2]
                    )
                except Exception:
                    pass  # 如果无法创建新异常，保留原始异常
        
        return True
    
    def _filter_sensitive_data(self, text: Any) -> Any:
        """
        过滤文本中的敏感数据
        
        Args:
            text: 原始文本
            
        Returns:
            过滤后的文本
        """
        if not isinstance(text, str):
            return text
        
        filtered_text: str = text
        for pattern, replacement in self.patterns:
            filtered_text = pattern.sub(replacement, filtered_text)
        
        return filtered_text
    
    @classmethod
    def filter_dict(cls, data: Any, mask: str = "***") -> Any:
        """
        过滤字典中的敏感字段
        
        Args:
            data: 原始字典
            mask: 遮盖字符串
            
        Returns:
            过滤后的字典
        """
        if not isinstance(data, dict):
            return data
        
        filtered: dict[Any, Any] = {}
        for key, value in data.items():
            key_lower = key.lower()
            # 检查是否为敏感字段
            if any(s in key_lower for s in cls.SENSITIVE_KEYS):
                filtered[key] = mask
            elif isinstance(value, dict):
                filtered[key] = cls.filter_dict(value, mask)
            elif isinstance(value, list):
                filtered[key] = [
                    cls.filter_dict(item, mask) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                filtered[key] = value
        
        return filtered


class RedactingFormatter(logging.Formatter):
    """
    自动遮盖敏感信息的日志格式化器
    """
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None) -> None:
        super().__init__(fmt, datefmt)
        self._filter = SensitiveDataFilter()
    
    def format(self, record: logging.LogRecord) -> str:
        # 先应用过滤器
        self._filter.filter(record)
        return super().format(record)


def setup_sensitive_logging(
    level: str = "INFO",
    logger_name: Optional[str] = None,
    log_file: Optional[str] = None,
    file_mode: str = "a"
) -> logging.Logger:
    """
    设置带有敏感信息过滤的日志记录器
    
    Args:
        level: 日志级别
        logger_name: 日志记录器名称
        log_file: 日志文件路径（可选）
        file_mode: 文件模式
        
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有处理器
    logger.handlers = []
    
    # 添加敏感信息过滤器
    sensitive_filter = SensitiveDataFilter()
    logger.addFilter(sensitive_filter)
    
    # 配置格式化器
    formatter = RedactingFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 配置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper()))
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    logger.addHandler(console_handler)
    
    # 配置文件处理器（如果指定）
    if log_file:
        file_handler = logging.FileHandler(log_file, mode=file_mode)
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        logger.addHandler(file_handler)
    
    return logger


def install_global_filter() -> None:
    """
    为根日志记录器安装全局敏感信息过滤器
    """
    root_logger = logging.getLogger()
    sensitive_filter = SensitiveDataFilter()
    
    # 添加到根记录器
    root_logger.addFilter(sensitive_filter)
    
    # 为所有现有处理器添加过滤器
    for handler in root_logger.handlers:
        handler.addFilter(sensitive_filter)


def sanitize_for_log(obj: Any) -> str:
    """
    将对象转换为安全的日志字符串
    
    Args:
        obj: 任意对象
        
    Returns:
        安全的字符串表示
    """
    if obj is None:
        return "None"
    
    text: str = str(obj)
    
    # 应用敏感信息过滤
    filter_instance = SensitiveDataFilter()
    result: str = filter_instance._filter_sensitive_data(text)
    return result
