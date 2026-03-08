"""版本信息模块"""

from __future__ import annotations

from typing import Tuple

__version__ = "3.0.0"
__version_info__: Tuple[int, int, int] = (3, 0, 0)

PROJECT_NAME = "qbittorrent-clipboard-monitor"
PROJECT_DESCRIPTION = "qBittorrent剪贴板监控与自动分类下载工具"
AUTHOR = "Kimi Claw"


def get_version_string() -> str:
    """获取版本字符串"""
    return __version__


def get_version_info() -> Tuple[int, int, int]:
    """获取版本信息元组"""
    return __version_info__
