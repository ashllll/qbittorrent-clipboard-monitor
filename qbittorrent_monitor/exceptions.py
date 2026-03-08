"""核心异常定义"""

from __future__ import annotations


class QBMonitorError(Exception):
    """基础异常"""
    pass


class ConfigError(QBMonitorError):
    """配置错误"""
    pass


class QBClientError(QBMonitorError):
    """qBittorrent客户端错误"""
    pass


class QBAuthError(QBClientError):
    """认证错误"""
    pass


class QBConnectionError(QBClientError):
    """连接错误"""
    pass


class AIError(QBMonitorError):
    """AI分类错误"""
    pass


class ClassificationError(QBMonitorError):
    """分类错误"""
    pass
