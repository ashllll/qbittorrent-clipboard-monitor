"""配置验证工具模块

提供安全的数据解析和验证函数。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..exceptions import ConfigError
from ..security import validate_hostname, validate_url

logger = logging.getLogger(__name__)


def parse_bool(value: str) -> bool:
    """解析布尔值字符串
    
    Args:
        value: 要解析的字符串
        
    Returns:
        布尔值
        
    Raises:
        ConfigError: 当值无法解析为布尔值时抛出
    """
    if value.lower() in ("true", "1", "yes", "on", "enabled"):
        return True
    elif value.lower() in ("false", "0", "no", "off", "disabled", ""):
        return False
    else:
        raise ConfigError(f"无法解析为布尔值: {value}")


def parse_int(
    value: str,
    name: str,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None
) -> int:
    """安全地解析整数
    
    Args:
        value: 要解析的字符串
        name: 配置项名称（用于错误信息）
        min_val: 最小值限制
        max_val: 最大值限制
        
    Returns:
        整数值
        
    Raises:
        ConfigError: 当值无效时抛出
    """
    try:
        result = int(value)
    except ValueError:
        raise ConfigError(f"{name} 必须是整数，当前值: {value}")
    
    if min_val is not None and result < min_val:
        raise ConfigError(f"{name} 不能小于 {min_val}，当前值: {result}")
    
    if max_val is not None and result > max_val:
        raise ConfigError(f"{name} 不能大于 {max_val}，当前值: {result}")
    
    return result


def parse_float(
    value: str,
    name: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None
) -> float:
    """安全地解析浮点数
    
    Args:
        value: 要解析的字符串
        name: 配置项名称（用于错误信息）
        min_val: 最小值限制
        max_val: 最大值限制
        
    Returns:
        浮点数值
        
    Raises:
        ConfigError: 当值无效时抛出
    """
    try:
        result = float(value)
    except ValueError:
        raise ConfigError(f"{name} 必须是数字，当前值: {value}")
    
    if min_val is not None and result < min_val:
        raise ConfigError(f"{name} 不能小于 {min_val}，当前值: {result}")
    
    if max_val is not None and result > max_val:
        raise ConfigError(f"{name} 不能大于 {max_val}，当前值: {result}")
    
    return result


def validate_non_empty_string(value: str, name: str) -> str:
    """验证非空字符串
    
    Args:
        value: 要验证的字符串
        name: 配置项名称
        
    Returns:
        去除首尾空格的字符串
        
    Raises:
        ConfigError: 当值为空时抛出
    """
    stripped = value.strip()
    if not stripped:
        raise ConfigError(f"{name} 不能是空字符串")
    return stripped


def validate_api_key(api_key: str, name: str = "API_KEY") -> None:
    """验证 API 密钥格式
    
    Args:
        api_key: API 密钥
        name: 配置项名称
        
    Raises:
        ConfigError: 当密钥格式无效时抛出
    """
    if not api_key or not isinstance(api_key, str):
        raise ConfigError(f"{name} 必须设置")
    
    if len(api_key) < 10:
        raise ConfigError(f"{name} 格式无效，密钥长度过短")
    
    # 检查是否包含可疑字符
    if '\n' in api_key or '\r' in api_key or '\x00' in api_key:
        raise ConfigError(f"{name} 包含非法字符")


def validate_keyword(keyword: str, category_name: str, index: int) -> None:
    """验证分类关键词
    
    Args:
        keyword: 关键词
        category_name: 分类名称
        index: 关键词索引
        
    Raises:
        ConfigError: 当关键词无效时抛出
    """
    from .constants import MAX_KEYWORD_LENGTH
    
    if not isinstance(keyword, str):
        raise ConfigError(f"分类 '{category_name}' 的关键词 #{index+1} 必须是字符串")
    
    if len(keyword) > MAX_KEYWORD_LENGTH:
        raise ConfigError(
            f"分类 '{category_name}' 的关键词 #{index+1} 过长（最大{MAX_KEYWORD_LENGTH}字符）"
        )
    
    if '\x00' in keyword or '\n' in keyword or '\r' in keyword:
        raise ConfigError(f"分类 '{category_name}' 的关键词 #{index+1} 包含非法字符")


def validate_keywords_list(keywords: list, category_name: str) -> None:
    """验证关键词列表
    
    Args:
        keywords: 关键词列表
        category_name: 分类名称
        
    Raises:
        ConfigError: 当列表无效时抛出
    """
    from .constants import MAX_KEYWORDS
    
    if not isinstance(keywords, list):
        raise ConfigError(f"分类 '{category_name}' 的 keywords 必须是字符串列表")
    
    if len(keywords) > MAX_KEYWORDS:
        raise ConfigError(f"分类 '{category_name}' 的关键词数量超过限制 ({MAX_KEYWORDS})")
    
    for i, keyword in enumerate(keywords):
        validate_keyword(keyword, category_name, i)
