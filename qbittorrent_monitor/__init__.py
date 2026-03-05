"""qBittorrent Clipboard Monitor - 精简版核心模块"""

from .__version__ import (
    __version__,
    PROJECT_NAME,
    PROJECT_DESCRIPTION,
)
from .config import Config, load_config
from .qb_client import QBClient
from .classifier import ContentClassifier
from .monitor import ClipboardMonitor

__all__ = [
    "__version__",
    "PROJECT_NAME",
    "PROJECT_DESCRIPTION",
    "Config",
    "load_config",
    "QBClient",
    "ContentClassifier",
    "ClipboardMonitor",
]
