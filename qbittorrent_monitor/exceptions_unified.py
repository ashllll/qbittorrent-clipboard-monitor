"""qBittorrent剪贴板监控器 - 统一异常处理模块

此模块提供项目所需的全部异常类，包括：
- 基础异常类 QBittorrentMonitorError
- 按模块分类的异常类（Config、Network、AI、QBT、Clipboard等）
- 异常严重程度分类（Critical/Error/Warning/Info）
- 错误码枚举 ErrorCode

使用示例:
    from qbittorrent_monitor.exceptions_unified import (
        QBittorrentMonitorError,
        ConfigurationError,
        NetworkError,
        AIError,
    )
    
    raise ConfigurationError(
        message="配置文件格式错误",
        error_code=ErrorCode.CONFIG_VALIDATION_ERROR,
        details={"file": "config.yaml"}
    )
"""

from __future__ import annotations

import warnings
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, Optional, Type, Callable
from dataclasses import dataclass


# =============================================================================
# 错误码体系
# =============================================================================

class ErrorCategory(Enum):
    """错误类别"""
    CONFIG = "CFG"          # 配置相关
    NETWORK = "NET"         # 网络相关
    QBITTORRENT = "QBT"     # qBittorrent相关
    AI = "AI"               # AI服务相关
    CLIPBOARD = "CLP"       # 剪贴板相关
    CRAWLER = "CRW"         # 爬虫相关
    CACHE = "CCH"           # 缓存相关
    SECURITY = "SEC"        # 安全相关
    RESOURCE = "RES"        # 资源相关
    SYSTEM = "SYS"          # 系统相关
    TORRENT = "TOR"         # 种子相关
    NOTIFICATION = "NOT"    # 通知相关
    DATABASE = "DB"         # 数据库相关


class ErrorSeverity(Enum):
    """错误严重程度等级"""
    CRITICAL = "critical"   # 系统无法继续运行，需要立即处理
    ERROR = "error"         # 功能异常，但可以降级或重试
    WARNING = "warning"     # 非致命问题，需要关注
    INFO = "info"           # 信息性提示


@dataclass(frozen=True)
class ErrorCode:
    """标准错误码
    
    Attributes:
        category: 错误类别
        code: 错误编号
        severity: 严重程度
    """
    category: ErrorCategory
    code: int
    severity: ErrorSeverity
    
    def __str__(self) -> str:
        return f"{self.category.value}-{self.code:04d}"


# 预定义错误码
ERROR_CODES = {
    # 配置错误 (CFG-0001 ~ CFG-0099)
    "CONFIG_VALIDATION_ERROR": ErrorCode(ErrorCategory.CONFIG, 1, ErrorSeverity.ERROR),
    "CONFIG_NOT_FOUND": ErrorCode(ErrorCategory.CONFIG, 2, ErrorSeverity.ERROR),
    "CONFIG_LOAD_ERROR": ErrorCode(ErrorCategory.CONFIG, 3, ErrorSeverity.ERROR),
    "CONFIG_SAVE_ERROR": ErrorCode(ErrorCategory.CONFIG, 4, ErrorSeverity.ERROR),
    "CONFIG_PARSE_ERROR": ErrorCode(ErrorCategory.CONFIG, 5, ErrorSeverity.ERROR),
    
    # 网络错误 (NET-0100 ~ NET-0199)
    "NETWORK_ERROR": ErrorCode(ErrorCategory.NETWORK, 100, ErrorSeverity.ERROR),
    "NETWORK_TIMEOUT": ErrorCode(ErrorCategory.NETWORK, 101, ErrorSeverity.ERROR),
    "NETWORK_CONNECTION_ERROR": ErrorCode(ErrorCategory.NETWORK, 102, ErrorSeverity.ERROR),
    "NETWORK_DNS_ERROR": ErrorCode(ErrorCategory.NETWORK, 103, ErrorSeverity.ERROR),
    "NETWORK_SSL_ERROR": ErrorCode(ErrorCategory.NETWORK, 104, ErrorSeverity.ERROR),
    
    # qBittorrent错误 (QBT-0200 ~ QBT-0299)
    "QBITTORRENT_ERROR": ErrorCode(ErrorCategory.QBITTORRENT, 200, ErrorSeverity.ERROR),
    "QBT_AUTH_ERROR": ErrorCode(ErrorCategory.QBITTORRENT, 201, ErrorSeverity.CRITICAL),
    "QBT_RATE_LIMIT": ErrorCode(ErrorCategory.QBITTORRENT, 202, ErrorSeverity.WARNING),
    "QBT_PERMISSION_ERROR": ErrorCode(ErrorCategory.QBITTORRENT, 203, ErrorSeverity.ERROR),
    "QBT_SERVER_ERROR": ErrorCode(ErrorCategory.QBITTORRENT, 204, ErrorSeverity.ERROR),
    "QBT_CONNECTION_ERROR": ErrorCode(ErrorCategory.QBITTORRENT, 205, ErrorSeverity.ERROR),
    "QBT_API_ERROR": ErrorCode(ErrorCategory.QBITTORRENT, 206, ErrorSeverity.ERROR),
    
    # AI错误 (AI-0300 ~ AI-0399)
    "AI_ERROR": ErrorCode(ErrorCategory.AI, 300, ErrorSeverity.ERROR),
    "AI_API_ERROR": ErrorCode(ErrorCategory.AI, 301, ErrorSeverity.ERROR),
    "AI_CREDIT_ERROR": ErrorCode(ErrorCategory.AI, 302, ErrorSeverity.WARNING),
    "AI_RATE_LIMIT": ErrorCode(ErrorCategory.AI, 303, ErrorSeverity.WARNING),
    "AI_RESPONSE_ERROR": ErrorCode(ErrorCategory.AI, 304, ErrorSeverity.ERROR),
    "AI_FALLBACK_ERROR": ErrorCode(ErrorCategory.AI, 305, ErrorSeverity.WARNING),
    "AI_TIMEOUT_ERROR": ErrorCode(ErrorCategory.AI, 306, ErrorSeverity.WARNING),
    "AI_INIT_ERROR": ErrorCode(ErrorCategory.AI, 307, ErrorSeverity.ERROR),
    
    # 剪贴板错误 (CLP-0400 ~ CLP-0499)
    "CLIPBOARD_ERROR": ErrorCode(ErrorCategory.CLIPBOARD, 400, ErrorSeverity.WARNING),
    "CLIPBOARD_PERMISSION_ERROR": ErrorCode(ErrorCategory.CLIPBOARD, 401, ErrorSeverity.ERROR),
    "CLIPBOARD_READ_ERROR": ErrorCode(ErrorCategory.CLIPBOARD, 402, ErrorSeverity.WARNING),
    "CLIPBOARD_WRITE_ERROR": ErrorCode(ErrorCategory.CLIPBOARD, 403, ErrorSeverity.WARNING),
    "CLIPBOARD_EMPTY": ErrorCode(ErrorCategory.CLIPBOARD, 404, ErrorSeverity.INFO),
    
    # 种子错误 (TOR-0500 ~ TOR-0599)
    "TORRENT_ERROR": ErrorCode(ErrorCategory.TORRENT, 500, ErrorSeverity.ERROR),
    "TORRENT_PARSE_ERROR": ErrorCode(ErrorCategory.TORRENT, 501, ErrorSeverity.ERROR),
    "MAGNET_PARSE_ERROR": ErrorCode(ErrorCategory.TORRENT, 502, ErrorSeverity.ERROR),
    "TORRENT_INVALID": ErrorCode(ErrorCategory.TORRENT, 503, ErrorSeverity.WARNING),
    "TORRENT_DUPLICATE": ErrorCode(ErrorCategory.TORRENT, 504, ErrorSeverity.INFO),
    
    # 通知错误 (NOT-0600 ~ NOT-0699)
    "NOTIFICATION_ERROR": ErrorCode(ErrorCategory.NOTIFICATION, 600, ErrorSeverity.WARNING),
    "NOTIFICATION_DELIVERY_ERROR": ErrorCode(ErrorCategory.NOTIFICATION, 601, ErrorSeverity.WARNING),
    "NOTIFICATION_TEMPLATE_ERROR": ErrorCode(ErrorCategory.NOTIFICATION, 602, ErrorSeverity.WARNING),
    
    # 爬虫错误 (CRW-0700 ~ CRW-0799)
    "CRAWLER_ERROR": ErrorCode(ErrorCategory.CRAWLER, 700, ErrorSeverity.ERROR),
    "CRAWLER_TIMEOUT_ERROR": ErrorCode(ErrorCategory.CRAWLER, 701, ErrorSeverity.WARNING),
    "CRAWLER_RATE_LIMIT_ERROR": ErrorCode(ErrorCategory.CRAWLER, 702, ErrorSeverity.WARNING),
    "CRAWLER_EXTRACTION_ERROR": ErrorCode(ErrorCategory.CRAWLER, 703, ErrorSeverity.ERROR),
    
    # 缓存错误 (CCH-0800 ~ CCH-0899)
    "CACHE_ERROR": ErrorCode(ErrorCategory.CACHE, 800, ErrorSeverity.WARNING),
    "CACHE_NOT_FOUND": ErrorCode(ErrorCategory.CACHE, 801, ErrorSeverity.INFO),
    "CACHE_WRITE_ERROR": ErrorCode(ErrorCategory.CACHE, 802, ErrorSeverity.WARNING),
    "CACHE_READ_ERROR": ErrorCode(ErrorCategory.CACHE, 803, ErrorSeverity.WARNING),
    
    # 资源错误 (RES-0900 ~ RES-0999)
    "RESOURCE_ERROR": ErrorCode(ErrorCategory.RESOURCE, 900, ErrorSeverity.ERROR),
    "RESOURCE_TIMEOUT_ERROR": ErrorCode(ErrorCategory.RESOURCE, 901, ErrorSeverity.WARNING),
    "RESOURCE_EXHAUSTED": ErrorCode(ErrorCategory.RESOURCE, 902, ErrorSeverity.ERROR),
    "RESOURCE_LIMIT_ERROR": ErrorCode(ErrorCategory.RESOURCE, 903, ErrorSeverity.WARNING),
    
    # 安全错误 (SEC-1000 ~ SEC-1099)
    "SECURITY_ERROR": ErrorCode(ErrorCategory.SECURITY, 1000, ErrorSeverity.CRITICAL),
    "AUTHENTICATION_ERROR": ErrorCode(ErrorCategory.SECURITY, 1001, ErrorSeverity.CRITICAL),
    "AUTHORIZATION_ERROR": ErrorCode(ErrorCategory.SECURITY, 1002, ErrorSeverity.CRITICAL),
    "VALIDATION_ERROR": ErrorCode(ErrorCategory.SECURITY, 1003, ErrorSeverity.ERROR),
    
    # 数据库错误 (DB-1100 ~ DB-1199)
    "DATABASE_ERROR": ErrorCode(ErrorCategory.DATABASE, 1100, ErrorSeverity.ERROR),
    "DATABASE_CONNECTION_ERROR": ErrorCode(ErrorCategory.DATABASE, 1101, ErrorSeverity.ERROR),
    "DATABASE_QUERY_ERROR": ErrorCode(ErrorCategory.DATABASE, 1102, ErrorSeverity.ERROR),
    "DATABASE_MIGRATION_ERROR": ErrorCode(ErrorCategory.DATABASE, 1103, ErrorSeverity.ERROR),
    
    # 系统错误 (SYS-9900 ~ SYS-9999)
    "SYSTEM_ERROR": ErrorCode(ErrorCategory.SYSTEM, 9900, ErrorSeverity.CRITICAL),
    "UNKNOWN_ERROR": ErrorCode(ErrorCategory.SYSTEM, 9999, ErrorSeverity.ERROR),
}


def get_error_code(name: str) -> Optional[ErrorCode]:
    """通过名称获取错误码
    
    Args:
        name: 错误码名称
        
    Returns:
        ErrorCode 或 None
    """
    return ERROR_CODES.get(name)


# =============================================================================
# 基础异常类
# =============================================================================

class QBittorrentMonitorError(Exception):
    """项目基础异常类
    
    所有项目异常的基类，提供统一的错误信息格式和序列化能力。
    
    Attributes:
        message: 错误消息
        details: 详细的错误信息（字典或任意类型）
        retry_after: 建议的重试等待时间（秒）
        error_code: 错误码
        severity: 错误严重程度
        timestamp: 异常发生时间
        context: 额外上下文信息
    """

    def __init__(
        self,
        message: str,
        details: Optional[Any] = None,
        retry_after: Optional[int] = None,
        error_code: Optional[ErrorCode] = None,
        severity: Optional[ErrorSeverity] = None
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.retry_after = retry_after
        self.error_code = error_code or self._default_error_code()
        self.severity = severity or self._default_severity()
        self.timestamp = datetime.now().isoformat()
        self.context: Dict[str, Any] = {}
    
    def _default_error_code(self) -> ErrorCode:
        """获取默认错误码"""
        return ERROR_CODES.get("UNKNOWN_ERROR", ErrorCode(ErrorCategory.SYSTEM, 9999, ErrorSeverity.ERROR))
    
    def _default_severity(self) -> ErrorSeverity:
        """获取默认严重程度"""
        return ErrorSeverity.ERROR
    
    def to_dict(self) -> Dict[str, Any]:
        """将异常转换为字典格式"""
        return {
            "error_type": self.__class__.__name__,
            "error_code": str(self.error_code) if self.error_code else None,
            "message": self.message,
            "severity": self.severity.value if self.severity else None,
            "details": self.details,
            "retry_after": self.retry_after,
            "timestamp": self.timestamp,
            "context": self.context,
        }
    
    def add_context(self, key: str, value: Any) -> "QBittorrentMonitorError":
        """添加上下文信息
        
        Args:
            key: 上下文键
            value: 上下文值
            
        Returns:
            self，支持链式调用
        """
        self.context[key] = value
        return self
    
    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}"
            f")"
        )


# =============================================================================
# 配置相关异常
# =============================================================================

class ConfigurationError(QBittorrentMonitorError):
    """配置错误基类
    
    配置加载、验证、保存相关的异常。
    """
    
    def _default_error_code(self) -> ErrorCode:
        return ERROR_CODES["CONFIG_LOAD_ERROR"]
    
    def _default_severity(self) -> ErrorSeverity:
        return ErrorSeverity.ERROR


class ConfigValidationError(ConfigurationError):
    """配置验证错误
    
    配置文件格式不正确或验证失败时抛出。
    
    Attributes:
        validation_errors: 验证错误列表
    """
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[list] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.validation_errors = validation_errors or []
        self.error_code = ERROR_CODES["CONFIG_VALIDATION_ERROR"]
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["validation_errors"] = self.validation_errors
        return data


class ConfigNotFoundError(ConfigurationError):
    """配置文件未找到错误"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.file_path = file_path
        self.error_code = ERROR_CODES["CONFIG_NOT_FOUND"]
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["file_path"] = self.file_path
        return data


class ConfigLoadError(ConfigurationError):
    """配置加载错误"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.file_path = file_path
        self.error_code = ERROR_CODES["CONFIG_LOAD_ERROR"]


# =============================================================================
# 网络相关异常
# =============================================================================

class NetworkError(QBittorrentMonitorError):
    """网络错误基类"""
    
    def _default_error_code(self) -> ErrorCode:
        return ERROR_CODES["NETWORK_ERROR"]
    
    def _default_severity(self) -> ErrorSeverity:
        return ErrorSeverity.ERROR


class NetworkTimeoutError(NetworkError):
    """网络超时错误"""
    
    def __init__(self, message: str, timeout: Optional[float] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.timeout = timeout
        self.error_code = ERROR_CODES["NETWORK_TIMEOUT"]
        self.retry_after = 5  # 建议5秒后重试


class NetworkConnectionError(NetworkError):
    """网络连接错误"""
    
    def __init__(
        self,
        message: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.host = host
        self.port = port
        self.error_code = ERROR_CODES["NETWORK_CONNECTION_ERROR"]


# =============================================================================
# qBittorrent 相关异常
# =============================================================================

class QBittorrentError(QBittorrentMonitorError):
    """qBittorrent 操作错误基类"""
    
    def _default_error_code(self) -> ErrorCode:
        return ERROR_CODES["QBITTORRENT_ERROR"]


class QbtAuthError(QBittorrentError):
    """qBittorrent 认证错误"""
    
    def __init__(self, message: str = "qBittorrent 认证失败", **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = ERROR_CODES["QBT_AUTH_ERROR"]
        self.severity = ErrorSeverity.CRITICAL


class QbtRateLimitError(QBittorrentError):
    """qBittorrent 速率限制错误"""
    
    def __init__(self, message: str, retry_after: int = 60, **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = ERROR_CODES["QBT_RATE_LIMIT"]
        self.retry_after = retry_after
        self.severity = ErrorSeverity.WARNING


class QbtPermissionError(QBittorrentError):
    """qBittorrent 权限错误"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = ERROR_CODES["QBT_PERMISSION_ERROR"]


class QbtServerError(QBittorrentError):
    """qBittorrent 服务器错误"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.status_code = status_code
        self.error_code = ERROR_CODES["QBT_SERVER_ERROR"]


class QbtConnectionError(QBittorrentError):
    """qBittorrent 连接错误"""
    
    def __init__(
        self,
        message: str = "无法连接到 qBittorrent",
        host: Optional[str] = None,
        port: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.host = host
        self.port = port
        self.error_code = ERROR_CODES["QBT_CONNECTION_ERROR"]


class QbtApiError(QBittorrentError):
    """qBittorrent API 错误
    
    API 调用返回错误响应时抛出。
    
    Attributes:
        endpoint: API 端点
        status_code: HTTP 状态码
        response: 响应内容
    """
    
    def __init__(
        self,
        message: str,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        response: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.endpoint = endpoint
        self.status_code = status_code
        self.response = response
        self.error_code = ERROR_CODES["QBT_API_ERROR"]
    
    def __str__(self) -> str:
        parts = [f"[{self.error_code}] {self.message}"]
        if self.endpoint:
            parts.append(f"endpoint={self.endpoint}")
        if self.status_code:
            parts.append(f"status={self.status_code}")
        return " | ".join(parts)


# =============================================================================
# AI 相关异常
# =============================================================================

class AIError(QBittorrentMonitorError):
    """AI/分类错误基类"""
    
    def _default_error_code(self) -> ErrorCode:
        return ERROR_CODES["AI_ERROR"]


class AIApiError(AIError):
    """AI API 调用错误
    
    注意：使用正确的驼峰命名 AIApiError，而非 AIAPIError
    """
    
    def __init__(self, message: str, provider: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.provider = provider
        self.error_code = ERROR_CODES["AI_API_ERROR"]


class AICreditError(AIError):
    """AI 积分/配额不足错误"""
    
    def __init__(self, message: str = "AI API 积分不足", **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = ERROR_CODES["AI_CREDIT_ERROR"]
        self.severity = ErrorSeverity.WARNING


class AIRateLimitError(AIError):
    """AI 速率限制错误"""
    
    def __init__(self, message: str, retry_after: int = 60, **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = ERROR_CODES["AI_RATE_LIMIT"]
        self.retry_after = retry_after
        self.severity = ErrorSeverity.WARNING


class AIResponseError(AIError):
    """AI 响应解析错误"""
    
    def __init__(self, message: str, raw_response: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.raw_response = raw_response
        self.error_code = ERROR_CODES["AI_RESPONSE_ERROR"]


class AIFallbackError(AIError):
    """AI 降级处理错误"""
    
    def __init__(self, message: str, fallback_method: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.fallback_method = fallback_method
        self.error_code = ERROR_CODES["AI_FALLBACK_ERROR"]
        self.severity = ErrorSeverity.WARNING


class AITimeoutError(AIError):
    """AI 调用超时错误"""
    
    def __init__(self, message: str = "AI 分类超时", timeout: Optional[float] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.timeout = timeout
        self.error_code = ERROR_CODES["AI_TIMEOUT_ERROR"]
        self.retry_after = 5
        self.severity = ErrorSeverity.WARNING


class AIInitError(AIError):
    """AI 客户端初始化错误"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = ERROR_CODES["AI_INIT_ERROR"]


# =============================================================================
# 分类相关异常
# =============================================================================

class ClassificationError(QBittorrentMonitorError):
    """分类错误"""
    
    def __init__(self, message: str, content_name: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.content_name = content_name


# =============================================================================
# 剪贴板相关异常
# =============================================================================

class ClipboardError(QBittorrentMonitorError):
    """剪贴板操作错误基类"""
    
    def _default_error_code(self) -> ErrorCode:
        return ERROR_CODES["CLIPBOARD_ERROR"]
    
    def _default_severity(self) -> ErrorSeverity:
        return ErrorSeverity.WARNING


class ClipboardPermissionError(ClipboardError):
    """剪贴板权限错误"""
    
    def __init__(self, message: str = "无法访问剪贴板", **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = ERROR_CODES["CLIPBOARD_PERMISSION_ERROR"]
        self.severity = ErrorSeverity.ERROR


class ClipboardReadError(ClipboardError):
    """剪贴板读取错误"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = ERROR_CODES["CLIPBOARD_READ_ERROR"]


class ClipboardWriteError(ClipboardError):
    """剪贴板写入错误"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = ERROR_CODES["CLIPBOARD_WRITE_ERROR"]


# =============================================================================
# 种子相关异常
# =============================================================================

class TorrentError(QBittorrentMonitorError):
    """种子相关错误基类"""
    
    def _default_error_code(self) -> ErrorCode:
        return ERROR_CODES["TORRENT_ERROR"]


class TorrentParseError(TorrentError):
    """种子解析错误"""
    
    def __init__(self, message: str, torrent_data: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.torrent_data = torrent_data
        self.error_code = ERROR_CODES["TORRENT_PARSE_ERROR"]


class MagnetParseError(TorrentError):
    """磁力链接解析错误"""
    
    def __init__(self, message: str, magnet: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.magnet = magnet
        self.error_code = ERROR_CODES["MAGNET_PARSE_ERROR"]


class InvalidMagnetError(TorrentError):
    """无效磁力链接错误"""
    
    def __init__(self, message: str, magnet: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.magnet = magnet
        self.error_code = ERROR_CODES["TORRENT_INVALID"]
        self.severity = ErrorSeverity.WARNING


class DuplicateTorrentError(TorrentError):
    """重复种子错误"""
    
    def __init__(self, message: str = "种子已存在", magnet_hash: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.magnet_hash = magnet_hash
        self.error_code = ERROR_CODES["TORRENT_DUPLICATE"]
        self.severity = ErrorSeverity.INFO


# =============================================================================
# 通知相关异常
# =============================================================================

class NotificationError(QBittorrentMonitorError):
    """通知系统错误基类"""
    
    def _default_error_code(self) -> ErrorCode:
        return ERROR_CODES["NOTIFICATION_ERROR"]
    
    def _default_severity(self) -> ErrorSeverity:
        return ErrorSeverity.WARNING


class NotificationDeliveryError(NotificationError):
    """通知发送错误"""
    
    def __init__(self, message: str, channel: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.channel = channel
        self.error_code = ERROR_CODES["NOTIFICATION_DELIVERY_ERROR"]


class NotificationTemplateError(NotificationError):
    """通知模板错误"""
    
    def __init__(self, message: str, template_name: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.template_name = template_name
        self.error_code = ERROR_CODES["NOTIFICATION_TEMPLATE_ERROR"]


# =============================================================================
# 爬虫相关异常
# =============================================================================

class CrawlerError(QBittorrentMonitorError):
    """网页爬虫错误基类"""
    
    def _default_error_code(self) -> ErrorCode:
        return ERROR_CODES["CRAWLER_ERROR"]


class CrawlerTimeoutError(CrawlerError):
    """爬虫超时错误"""
    
    def __init__(self, message: str, url: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.url = url
        self.error_code = ERROR_CODES["CRAWLER_TIMEOUT_ERROR"]
        self.severity = ErrorSeverity.WARNING


class CrawlerRateLimitError(CrawlerError):
    """爬虫速率限制错误"""
    
    def __init__(self, message: str, url: Optional[str] = None, retry_after: int = 60, **kwargs):
        super().__init__(message, **kwargs)
        self.url = url
        self.retry_after = retry_after
        self.error_code = ERROR_CODES["CRAWLER_RATE_LIMIT_ERROR"]
        self.severity = ErrorSeverity.WARNING


class CrawlerExtractionError(CrawlerError):
    """爬虫数据提取错误"""
    
    def __init__(self, message: str, url: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.url = url
        self.error_code = ERROR_CODES["CRAWLER_EXTRACTION_ERROR"]


# =============================================================================
# 缓存相关异常
# =============================================================================

class CacheError(QBittorrentMonitorError):
    """缓存系统错误基类"""
    
    def _default_error_code(self) -> ErrorCode:
        return ERROR_CODES["CACHE_ERROR"]
    
    def _default_severity(self) -> ErrorSeverity:
        return ErrorSeverity.WARNING


class CacheNotFoundError(CacheError):
    """缓存未找到错误"""
    
    def __init__(self, message: str, key: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.key = key
        self.error_code = ERROR_CODES["CACHE_NOT_FOUND"]
        self.severity = ErrorSeverity.INFO


class CacheWriteError(CacheError):
    """缓存写入错误"""
    
    def __init__(self, message: str, key: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.key = key
        self.error_code = ERROR_CODES["CACHE_WRITE_ERROR"]


class CacheReadError(CacheError):
    """缓存读取错误"""
    
    def __init__(self, message: str, key: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.key = key
        self.error_code = ERROR_CODES["CACHE_READ_ERROR"]


# =============================================================================
# 资源相关异常
# =============================================================================

class ResourceError(QBittorrentMonitorError):
    """资源管理错误基类"""
    
    def _default_error_code(self) -> ErrorCode:
        return ERROR_CODES["RESOURCE_ERROR"]


class ResourceTimeoutError(ResourceError):
    """资源获取超时错误"""
    
    def __init__(self, message: str, resource_name: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.resource_name = resource_name
        self.error_code = ERROR_CODES["RESOURCE_TIMEOUT_ERROR"]
        self.severity = ErrorSeverity.WARNING


class ResourceExhaustedError(ResourceError):
    """资源耗尽错误"""
    
    def __init__(self, message: str, resource_name: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.resource_name = resource_name
        self.error_code = ERROR_CODES["RESOURCE_EXHAUSTED"]


# =============================================================================
# 安全相关异常
# =============================================================================

class SecurityError(QBittorrentMonitorError):
    """安全相关错误基类"""
    
    def _default_error_code(self) -> ErrorCode:
        return ERROR_CODES["SECURITY_ERROR"]
    
    def _default_severity(self) -> ErrorSeverity:
        return ErrorSeverity.CRITICAL


class AuthenticationError(SecurityError):
    """认证错误"""
    
    def __init__(self, message: str = "认证失败", **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = ERROR_CODES["AUTHENTICATION_ERROR"]


class AuthorizationError(SecurityError):
    """授权错误"""
    
    def __init__(self, message: str = "权限不足", **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = ERROR_CODES["AUTHORIZATION_ERROR"]


class ValidationError(SecurityError):
    """数据验证错误"""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.field = field
        self.error_code = ERROR_CODES["VALIDATION_ERROR"]
        self.severity = ErrorSeverity.ERROR


# =============================================================================
# 数据库相关异常
# =============================================================================

class DatabaseError(QBittorrentMonitorError):
    """数据库错误基类"""
    
    def _default_error_code(self) -> ErrorCode:
        return ERROR_CODES["DATABASE_ERROR"]


class DatabaseConnectionError(DatabaseError):
    """数据库连接错误"""
    
    def __init__(self, message: str, db_path: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.db_path = db_path
        self.error_code = ERROR_CODES["DATABASE_CONNECTION_ERROR"]


class DatabaseQueryError(DatabaseError):
    """数据库查询错误"""
    
    def __init__(self, message: str, query: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.query = query
        self.error_code = ERROR_CODES["DATABASE_QUERY_ERROR"]


# =============================================================================
# 并发控制相关异常
# =============================================================================

class ConcurrencyError(QBittorrentMonitorError):
    """并发控制错误基类"""
    
    def _default_severity(self) -> ErrorSeverity:
        return ErrorSeverity.ERROR


class DeadlockError(ConcurrencyError):
    """死锁错误"""
    
    def _default_severity(self) -> ErrorSeverity:
        return ErrorSeverity.CRITICAL


class TaskTimeoutError(ConcurrencyError):
    """任务超时错误"""
    
    def __init__(self, message: str, task_name: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.task_name = task_name
        self.severity = ErrorSeverity.WARNING


# =============================================================================
# 状态管理相关异常
# =============================================================================

class StateError(QBittorrentMonitorError):
    """状态管理错误"""
    pass


# =============================================================================
# 重试策略相关异常（标记接口）
# =============================================================================

class RetryableError(QBittorrentMonitorError):
    """可重试错误标记
    
    继承此异常的异常表示可以通过重试解决。
    """
    
    def __init__(self, message: str, max_retries: int = 3, **kwargs):
        super().__init__(message, **kwargs)
        self.max_retries = max_retries
        self.severity = ErrorSeverity.INFO


class NonRetryableError(QBittorrentMonitorError):
    """不可重试错误标记
    
    继承此异常的异常表示重试无法解决问题。
    """
    
    def _default_severity(self) -> ErrorSeverity:
        return ErrorSeverity.ERROR


class CircuitBreakerOpenError(NonRetryableError):
    """熔断器打开错误
    
    当熔断器处于打开状态时抛出，表示服务暂时不可用。
    """
    
    def __init__(self, message: str, retry_after: int = 60, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


# =============================================================================
# 兼容性别名（带废弃警告）
# =============================================================================

class _DeprecatedAliasMeta(type):
    """用于创建废弃异常别名的元类"""
    
    def __new__(mcs, name, bases, namespace, **kwargs):
        # 移除 replacement 参数，不传递给 type.__new__
        replacement = kwargs.pop('replacement', None)
        cls = super().__new__(mcs, name, bases, namespace)
        cls._replacement = replacement
        return cls
    
    def __init__(cls, name, bases, namespace, **kwargs):
        # 消耗掉 replacement 参数
        super().__init__(name, bases, namespace)
    
    def __call__(cls, *args, **kwargs):
        if cls._replacement:
            warnings.warn(
                f"{cls.__name__} 已废弃，请使用 {cls._replacement.__name__}，"
                f"将在 v2.0 中移除",
                DeprecationWarning,
                stacklevel=2
            )
        return super().__call__(*args, **kwargs)


# 基础异常别名（向后兼容）
class QBMonitorError(QBittorrentMonitorError, metaclass=_DeprecatedAliasMeta, replacement=QBittorrentMonitorError):
    """已废弃：请使用 QBittorrentMonitorError"""
    pass


# 配置异常别名（向后兼容）
class ConfigError(ConfigurationError, metaclass=_DeprecatedAliasMeta, replacement=ConfigurationError):
    """已废弃：请使用 ConfigurationError"""
    pass


# qBittorrent 异常别名（向后兼容）
class QBClientError(QBittorrentError, metaclass=_DeprecatedAliasMeta, replacement=QBittorrentError):
    """已废弃：请使用 QBittorrentError"""
    pass


class QBAuthError(QbtAuthError, metaclass=_DeprecatedAliasMeta, replacement=QbtAuthError):
    """已废弃：请使用 QbtAuthError"""
    pass


class QBConnectionError(QbtConnectionError, metaclass=_DeprecatedAliasMeta, replacement=QbtConnectionError):
    """已废弃：请使用 QbtConnectionError"""
    pass


# AI 异常别名（向后兼容）- 修复 AIAPIError 笔误
class AIAPIError(AIApiError, metaclass=_DeprecatedAliasMeta, replacement=AIApiError):
    """已废弃：请使用 AIApiError（注意大小写）
    
    旧名称 AIAPIError 是一个笔误，正确的名称应该是 AIApiError。
    此别名保留用于向后兼容。
    """
    pass


# =============================================================================
# 模块导出列表
# =============================================================================

__all__ = [
    # 错误码相关
    "ErrorCategory",
    "ErrorSeverity",
    "ErrorCode",
    "ERROR_CODES",
    "get_error_code",
    
    # 基础异常
    "QBittorrentMonitorError",
    "QBMonitorError",  # 别名
    
    # 配置异常
    "ConfigurationError",
    "ConfigError",  # 别名
    "ConfigValidationError",
    "ConfigNotFoundError",
    "ConfigLoadError",
    
    # 网络异常
    "NetworkError",
    "NetworkTimeoutError",
    "NetworkConnectionError",
    
    # qBittorrent 异常
    "QBittorrentError",
    "QBClientError",  # 别名
    "QbtAuthError",
    "QBAuthError",  # 别名
    "QbtRateLimitError",
    "QbtPermissionError",
    "QbtServerError",
    "QbtConnectionError",
    "QBConnectionError",  # 别名
    "QbtApiError",
    
    # AI 异常
    "AIError",
    "AIApiError",
    "AIAPIError",  # 别名（修复笔误）
    "AICreditError",
    "AIRateLimitError",
    "AIResponseError",
    "AIFallbackError",
    "AITimeoutError",
    "AIInitError",
    
    # 分类异常
    "ClassificationError",
    
    # 剪贴板异常
    "ClipboardError",
    "ClipboardPermissionError",
    "ClipboardReadError",
    "ClipboardWriteError",
    
    # 种子异常
    "TorrentError",
    "TorrentParseError",
    "MagnetParseError",
    "InvalidMagnetError",
    "DuplicateTorrentError",
    
    # 通知异常
    "NotificationError",
    "NotificationDeliveryError",
    "NotificationTemplateError",
    
    # 爬虫异常
    "CrawlerError",
    "CrawlerTimeoutError",
    "CrawlerRateLimitError",
    "CrawlerExtractionError",
    
    # 缓存异常
    "CacheError",
    "CacheNotFoundError",
    "CacheWriteError",
    "CacheReadError",
    
    # 资源异常
    "ResourceError",
    "ResourceTimeoutError",
    "ResourceExhaustedError",
    
    # 安全异常
    "SecurityError",
    "AuthenticationError",
    "AuthorizationError",
    "ValidationError",
    
    # 数据库异常
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseQueryError",
    
    # 并发异常
    "ConcurrencyError",
    "DeadlockError",
    "TaskTimeoutError",
    
    # 状态异常
    "StateError",
    
    # 重试标记异常
    "RetryableError",
    "NonRetryableError",
    "CircuitBreakerOpenError",
]
