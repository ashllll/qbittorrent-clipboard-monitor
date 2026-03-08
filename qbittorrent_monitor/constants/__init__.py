"""常量管理模块

集中管理应用程序中的所有常量和默认值。
"""

from .limits import Limits, Timeouts, CacheSizes
from .defaults import Defaults, Categories
from .patterns import Patterns, RegexPatterns

__all__ = [
    "Limits",
    "Timeouts", 
    "CacheSizes",
    "Defaults",
    "Categories",
    "Patterns",
    "RegexPatterns",
]
