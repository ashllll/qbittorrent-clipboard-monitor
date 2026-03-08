"""正则表达式模式定义

集中管理所有正则表达式模式，避免重复编译。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Pattern, List


@dataclass(frozen=True)
class RegexPatterns:
    """正则表达式模式集合"""
    
    # 磁力链接相关
    MAGNET_URI: Pattern[str] = re.compile(
        r'^magnet:\?xt=urn:btih:[a-f0-9]{40}',
        re.IGNORECASE
    )
    
    # 磁力链接 hash 提取 (40位十六进制或32位base32)
    BTIH_HASH: Pattern[str] = re.compile(
        r'btih:([a-fA-F0-9]{40}|[a-z2-7]{32})',
        re.IGNORECASE
    )
    
    # 标准磁力链接匹配
    MAGNET_LINK: Pattern[str] = re.compile(
        r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{32,40}',
        re.IGNORECASE
    )
    
    # 路径遍历防护
    PATH_TRAVERSAL: list[Pattern[str]] = field(default_factory=lambda: [
        re.compile(r'\.\.[\\/]'),      # ../ 或 ..\
        re.compile(r'[\\/]\.\.'),      # /.. 或 \..
        re.compile(r'\.\.\Z'),         # 以 .. 结尾
        re.compile(r'^\.\.'),           # 以 .. 开头
        re.compile(r'[~]'),              # 用户目录扩展
        re.compile(r'\$\w+'),            # 环境变量扩展
    ])
    
    # 非法路径字符
    ILLEGAL_PATH_CHARS: Pattern[str] = re.compile(r'[<>:"|?*\x00-\x1f]')
    
    # 磁力链接参数名
    MAGNET_PARAM: Pattern[str] = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)=')
    
    # 允许的磁力链接字符
    MAGNET_ALLOWED_CHARS: Pattern[str] = re.compile(
        r'^[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=]+$',
        re.ASCII
    )


@dataclass(frozen=True)
class Patterns:
    """字符串模式集合（非正则）"""
    
    # Windows 保留名称
    WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset({
        'CON', 'PRN', 'AUX', 'NUL', 
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
        'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4',
        'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    })
    
    # 敏感字段名
    SENSITIVE_KEYS: frozenset[str] = frozenset({
        'password', 'passwd', 'pwd', 'secret', 
        'api_key', 'apikey', 'api_secret', 'apisecret',
        'token', 'access_token', 'accesstoken',
        'refresh_token', 'refreshtoken',
        'private_key', 'privatekey',
        'auth_token', 'authtoken',
        'bearer', 'credential', 'credentials',
        'session', 'cookie', 'sid',
    })
    
    # 有效的日志级别
    VALID_LOG_LEVELS: frozenset[str] = frozenset({
        'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    })
    
    # 支持的导出格式
    VALID_EXPORT_FORMATS: frozenset[str] = frozenset({'json', 'csv'})
    
    # 支持的协议
    ALLOWED_SCHEMES: frozenset[str] = frozenset({'http', 'https'})
    
    # 磁力链接标准参数
    VALID_MAGNET_PARAMS: frozenset[str] = frozenset({
        'xt', 'dn', 'tr', 'xl', 'as', 'xs', 'kt', 'mt', 'so'
    })


# RegexPatterns 类定义完成
