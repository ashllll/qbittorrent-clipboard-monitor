"""
日志过滤器模块

提供敏感信息过滤功能，防止密码、API密钥等泄露到日志
"""

import re
import logging
from typing import Pattern, List, Tuple, Optional


class SensitiveDataFilter(logging.Filter):
    """
    敏感信息过滤器
    
    过滤日志中的敏感信息，包括：
    - API密钥
    - 密码
    - 令牌
    - 磁力链接hash
    - 私钥
    """
    
    # 定义需要过滤的模式列表
    SENSITIVE_PATTERNS: List[Tuple[Pattern, str]] = [
        # API密钥（各种格式）
        (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([\w-]+)', re.IGNORECASE), r'\1***'),
        (re.compile(r'(api[_-]?secret["\']?\s*[:=]\s*["\']?)([^\s"\']+)', re.IGNORECASE), r'\1***'),
        
        # 密码
        (re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^\s"\']+)', re.IGNORECASE), r'\1***'),
        (re.compile(r'(passwd["\']?\s*[:=]\s*["\']?)([^\s"\']+)', re.IGNORECASE), r'\1***'),
        (re.compile(r'(pwd["\']?\s*[:=]\s*["\']?)([^\s"\']+)', re.IGNORECASE), r'\1***'),
        
        # 令牌
        (re.compile(r'(token["\']?\s*[:=]\s*["\']?)([\w-]+)', re.IGNORECASE), r'\1***'),
        (re.compile(r'(access[_-]?token["\']?\s*[:=]\s*["\']?)([^\s"\']+)', re.IGNORECASE), r'\1***'),
        (re.compile(r'(refresh[_-]?token["\']?\s*[:=]\s*["\']?)([^\s"\']+)', re.IGNORECASE), r'\1***'),
        (re.compile(r'(bearer\s+)([\w-]+)', re.IGNORECASE), r'\1***'),
        
        # 磁力链接hash（保留前8位，隐藏后32位）
        (re.compile(r'(magnet:\?xt=urn:btih:)([a-f0-9]{40})', re.IGNORECASE), r'\1\2***'),
        
        # 私钥
        (re.compile(r'(private[_-]?key["\']?\s*[:=]\s*["\']?)([^\s"\']+)', re.IGNORECASE), r'\1***'),
        (re.compile(r'(secret["\']?\s*[:=]\s*["\']?)([^\s"\']+)', re.IGNORECASE), r'\1***'),
        
        # 数据库连接字符串中的密码
        (re.compile(r'(://[^:]+:)([^@]+)(@)', re.IGNORECASE), r'\1***\3'),
    ]
    
    def __init__(self, name: str = ""):
        super().__init__(name)
        self.patterns = self.SENSITIVE_PATTERNS
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录中的敏感信息
        
        Args:
            record: 日志记录对象
            
        Returns:
            True（始终通过，但内容可能被修改）
        """
        # 过滤消息
        if isinstance(record.msg, str):
            record.msg = self._filter_sensitive_data(record.msg)
        
        # 过滤参数
        if record.args:
            record.args = tuple(
                self._filter_sensitive_data(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        
        return True
    
    def _filter_sensitive_data(self, text: str) -> str:
        """
        过滤文本中的敏感数据
        
        Args:
            text: 原始文本
            
        Returns:
            过滤后的文本
        """
        if not isinstance(text, str):
            return text
        
        filtered_text = text
        for pattern, replacement in self.patterns:
            filtered_text = pattern.sub(replacement, filtered_text)
        
        return filtered_text


def setup_sensitive_logging(
    level: str = "INFO",
    logger_name: Optional[str] = None
) -> logging.Logger:
    """
    设置带有敏感信息过滤的日志记录器
    
    Args:
        level: 日志级别
        logger_name: 日志记录器名称
        
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
    
    # 配置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper()))
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # 添加过滤器到处理器
    console_handler.addFilter(sensitive_filter)
    logger.addHandler(console_handler)
    
    return logger
