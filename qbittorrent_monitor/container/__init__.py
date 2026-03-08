"""依赖注入容器模块

提供依赖管理和自动注入功能。
"""

from .container import Container, get_container, reset_container
from .bootstrap import bootstrap

__all__ = [
    "Container",
    "get_container",
    "reset_container",
    "bootstrap",
]
