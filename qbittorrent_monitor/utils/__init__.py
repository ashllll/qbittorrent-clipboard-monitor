"""工具模块

提供各种通用的工具类和辅助函数。
"""

from __future__ import annotations

# 从子模块导入工具函数
from .core import (
    extract_magnet_hash,
    get_magnet_display_name,
    is_valid_magnet,
    parse_magnet,
    parse_magnet_link,
)

# 从新子模块导入连接池管理器
from .connection_pool import ConnectionPoolManager

__all__ = [
    # 原有工具函数
    "extract_magnet_hash",
    "get_magnet_display_name",
    "is_valid_magnet",
    "parse_magnet",
    "parse_magnet_link",
    # 新工具类
    "ConnectionPoolManager",
]
