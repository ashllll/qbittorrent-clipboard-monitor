"""
QBittorrent剪贴板监控与自动分类下载工具

提供磁力链接监控、AI智能分类、自动下载等功能。
"""

# 导入版本信息
from .__version__ import (
    __version__,
    __version_info__,
    PROJECT_NAME,
    PROJECT_DESCRIPTION,
    AUTHOR,
    get_version_string,
    get_version_info
)

__author__ = AUTHOR
__all__ = [
    # 版本信息
    "__version__",
    "__version_info__",
    "PROJECT_NAME",
    "PROJECT_DESCRIPTION",
    "get_version_string",
    "get_version_info",
    # 核心类
    "ConfigManager",
    "AppConfig",
    "QBittorrentClient",
    "AIClassifier",
    "ClipboardMonitor",
    # 异常类
    "ConfigError",
    "QBittorrentError",
    "NetworkError",
    "AIError",
    "ClassificationError",
] 