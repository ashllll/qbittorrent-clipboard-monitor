"""
统一异常处理模块

定义项目中使用的各种异常类型，支持更精细的错误处理和分类。
"""

from typing import Any, Optional


class QBittorrentMonitorError(Exception):
    """项目基础异常类"""

    def __init__(
        self,
        message: str,
        details: Optional[Any] = None,
        retry_after: Optional[int] = None,
    ):
        super().__init__(message)
        self.details = details
        self.retry_after = retry_after


class ConfigError(QBittorrentMonitorError):
    """配置相关异常"""

    pass


class QBittorrentError(QBittorrentMonitorError):
    """qBittorrent操作异常基类"""

    pass


class NetworkError(QBittorrentError):
    """网络通信异常"""

    pass


class QbtAuthError(QBittorrentError):
    """qBittorrent认证异常"""

    pass


class QbtRateLimitError(QBittorrentError):
    """qBittorrent API限速异常"""

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message, retry_after=retry_after)


class QbtPermissionError(QBittorrentError):
    """qBittorrent权限异常"""

    pass


class AIError(QBittorrentMonitorError):
    """AI相关异常基类"""

    pass


class AIApiError(AIError):
    """AI API调用异常"""

    pass


class AICreditError(AIError):
    """AI额度不足异常"""

    def __init__(self, message: str):
        super().__init__(message, retry_after=3600)  # 1小时后重试


class AIRateLimitError(AIError):
    """AI API限速异常"""

    def __init__(self, message: str, retry_after: int = 300):
        super().__init__(message, retry_after=retry_after)


class ClassificationError(QBittorrentMonitorError):
    """分类相关异常"""

    pass


class ClipboardError(QBittorrentMonitorError):
    """剪贴板访问异常"""

    pass


class TorrentParseError(QBittorrentMonitorError):
    """种子解析异常"""

    pass


class NotificationError(QBittorrentMonitorError):
    """通知发送异常"""

    pass


class CrawlerError(QBittorrentMonitorError):
    """网页爬虫异常"""

    pass


class ParseError(CrawlerError):
    """网页解析异常"""

    pass
