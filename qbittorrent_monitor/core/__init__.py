"""核心功能模块 - 蜂群优化版

包含磁力链接处理、防抖、轮询等核心功能。
"""

from .magnet import MagnetProcessor, MagnetInfo
from .debounce import DebounceService
from .pacing import PacingService

__all__ = [
    "MagnetProcessor",
    "MagnetInfo",
    "DebounceService",
    "PacingService",
]
