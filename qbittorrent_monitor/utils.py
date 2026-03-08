"""工具函数模块 - 安全版本

提供安全的磁力链接解析和hash提取功能。
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Optional

from .security import (
    validate_magnet,
    sanitize_magnet,
    extract_magnet_hash_safe,
    sanitize_filename
)


def parse_magnet(magnet: str) -> Optional[str]:
    """
    解析磁力链接，返回显示名称（安全版本）
    
    Args:
        magnet: 磁力链接字符串
        
    Returns:
        显示名称（dn参数值），解析失败返回None
    """
    # 首先验证磁力链接
    is_valid, error = validate_magnet(magnet)
    if not is_valid:
        return None
    
    # 清理磁力链接
    magnet = sanitize_magnet(magnet)
    
    try:
        parsed = urllib.parse.urlparse(magnet)
        params = urllib.parse.parse_qs(parsed.query)
        if "dn" in params:
            # 清理显示名称
            name: str = params["dn"][0]
            result: str = sanitize_filename(name)
            return result
    except Exception:
        pass
    return None


def extract_magnet_hash(magnet: str) -> Optional[str]:
    """
    提取磁力链接的hash（安全版本）
    
    Args:
        magnet: 磁力链接字符串
        
    Returns:
        40位十六进制hash字符串，无效时返回None
    """
    # 首先验证磁力链接
    is_valid: bool
    error: Optional[str]
    is_valid, error = validate_magnet(magnet)
    if not is_valid:
        return None
    
    result: Optional[str] = extract_magnet_hash_safe(magnet)
    return result


def is_valid_magnet(magnet: str) -> bool:
    """
    检查是否为有效的磁力链接
    
    Args:
        magnet: 要检查的字符串
        
    Returns:
        是否为有效的磁力链接
    """
    is_valid: bool
    _: Optional[str]
    is_valid, _ = validate_magnet(magnet)
    return is_valid


def get_magnet_display_name(magnet: str, max_length: int = 100) -> str:
    """
    获取磁力链接的显示名称（用于日志和界面显示）
    
    优先尝试解析 dn 参数（种子名称），如果没有则使用 hash 截断
    
    Args:
        magnet: 磁力链接
        max_length: 最大长度
        
    Returns:
        安全的显示字符串
    """
    # 首先尝试解析种子名称（dn 参数）
    name = parse_magnet(magnet)
    if name:
        if len(name) > max_length:
            return name[:max_length] + "..."
        return name
    
    # 没有名称时，使用 hash 截断
    magnet_hash = extract_magnet_hash(magnet)
    if magnet_hash:
        return f"magnet:...{magnet_hash[-8:]}"
    
    # 回退到原始截断
    if len(magnet) > max_length:
        return magnet[:max_length] + "..."
    return magnet


# 向后兼容：保留旧函数名
parse_magnet_link = parse_magnet
