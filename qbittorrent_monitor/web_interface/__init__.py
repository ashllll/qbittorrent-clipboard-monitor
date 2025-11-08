"""
Web管理界面模块

提供基于FastAPI的Web管理界面
"""

from .app import (
    WebInterface,
    WebSocketManager,
    start_web_interface,
    stop_web_interface,
    get_web_interface
)

__all__ = [
    'WebInterface',
    'WebSocketManager',
    'start_web_interface',
    'stop_web_interface',
    'get_web_interface'
]
