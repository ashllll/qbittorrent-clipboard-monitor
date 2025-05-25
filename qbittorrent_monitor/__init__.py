"""
QBittorrent剪贴板监控与自动分类下载工具

提供磁力链接监控、AI智能分类、自动下载等功能。
"""

__version__ = "2.1.0"
__author__ = "QBittorrent Monitor Team"

from .config import ConfigManager, AppConfig
from .qbittorrent_client import QBittorrentClient
from .ai_classifier import AIClassifier
from .clipboard_monitor import ClipboardMonitor
from .exceptions import *

__all__ = [
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