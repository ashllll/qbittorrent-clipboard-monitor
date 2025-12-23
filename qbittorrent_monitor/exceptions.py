"""
统一异常处理模块

定义项目中使用的各种异常类型，支持更精细的错误处理和分类。
"""

from typing import Optional, Any, Dict, List, Union


class QBittorrentMonitorError(Exception):
    """项目基础异常类"""

    def __init__(self, message: str, details: Optional[Any] = None, retry_after: Optional[int] = None):
        super().__init__(message)
        self.details = details
        self.retry_after = retry_after
        self.error_code = None
        self.timestamp = None
        self.context = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """将异常转换为字典格式，便于日志记录"""
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "details": self.details,
            "retry_after": self.retry_after,
            "error_code": self.error_code,
            "timestamp": self.timestamp,
            "context": self.context
        }


class ConfigError(QBittorrentMonitorError):
    """配置相关异常"""
    pass


class ConfigValidationError(ConfigError):
    """配置验证异常"""
    
    def __init__(self, message: str, validation_errors: List[Dict[str, Any]]):
        super().__init__(message, details={"validation_errors": validation_errors})
        self.validation_errors = validation_errors
        self.error_code = "CONFIG_VALIDATION_ERROR"


class ConfigNotFoundError(ConfigError):
    """配置文件未找到异常"""
    
    def __init__(self, config_path: str):
        super().__init__(f"配置文件未找到: {config_path}", details={"path": config_path})
        self.config_path = config_path
        self.error_code = "CONFIG_NOT_FOUND"


class QBittorrentError(QBittorrentMonitorError):
    """qBittorrent操作异常基类"""
    
    def __init__(self, message: str, details: Optional[Any] = None, 
                 retry_after: Optional[int] = None, qbt_error_code: Optional[str] = None):
        super().__init__(message, details, retry_after)
        self.qbt_error_code = qbt_error_code
        self.error_code = qbt_error_code or "QBITTORRENT_ERROR"


class NetworkError(QBittorrentError):
    """网络通信异常"""
    
    def __init__(self, message: str, url: Optional[str] = None, 
                 status_code: Optional[int] = None, retry_after: Optional[int] = None):
        super().__init__(message, details={"url": url, "status_code": status_code}, retry_after=retry_after)
        self.url = url
        self.status_code = status_code
        self.error_code = "NETWORK_ERROR"


class NetworkTimeoutError(NetworkError):
    """网络超时异常"""
    
    def __init__(self, message: str, url: Optional[str] = None, timeout: Optional[float] = None):
        super().__init__(message, url=url, status_code=None, retry_after=None)
        self.timeout = timeout
        self.error_code = "NETWORK_TIMEOUT"


class NetworkConnectionError(NetworkError):
    """网络连接异常"""
    
    def __init__(self, message: str, url: Optional[str] = None, host: Optional[str] = None, port: Optional[int] = None):
        super().__init__(message, url=url, status_code=None, retry_after=None)
        self.host = host
        self.port = port
        self.error_code = "NETWORK_CONNECTION_ERROR"


class QbtAuthError(QBittorrentError):
    """qBittorrent认证异常"""
    
    def __init__(self, message: str, auth_details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details=auth_details)
        self.error_code = "QBT_AUTH_ERROR"


class QbtRateLimitError(QBittorrentError):
    """qBittorrent API限速异常"""
    
    def __init__(self, message: str, retry_after: int = 60, rate_limit_info: Optional[Dict[str, Any]] = None):
        super().__init__(message, details=rate_limit_info, retry_after=retry_after)
        self.error_code = "QBT_RATE_LIMIT"
        self.rate_limit_info = rate_limit_info


class QbtPermissionError(QBittorrentError):
    """qBittorrent权限异常"""
    
    def __init__(self, message: str, operation: Optional[str] = None, resource: Optional[str] = None):
        super().__init__(message, details={"operation": operation, "resource": resource})
        self.error_code = "QBT_PERMISSION_ERROR"


class QbtServerError(QBittorrentError):
    """qBittorrent服务器异常"""
    
    def __init__(self, message: str, status_code: int, response_body: Optional[str] = None):
        super().__init__(message, details={"status_code": status_code, "response_body": response_body})
        self.status_code = status_code
        self.response_body = response_body
        self.error_code = "QBT_SERVER_ERROR"


class AIError(QBittorrentMonitorError):
    """AI相关异常基类"""
    
    def __init__(self, message: str, model: Optional[str] = None, 
                 provider: Optional[str] = None, details: Optional[Any] = None, 
                 retry_after: Optional[int] = None):
        super().__init__(message, details, retry_after)
        self.model = model
        self.provider = provider
        self.error_code = "AI_ERROR"


class AIApiError(AIError):
    """AI API调用异常"""
    
    def __init__(self, message: str, model: Optional[str] = None, 
                 provider: Optional[str] = None, status_code: Optional[int] = None, 
                 response: Optional[Dict[str, Any]] = None, retry_after: Optional[int] = None):
        super().__init__(message, model, provider, {"status_code": status_code, "response": response}, retry_after)
        self.status_code = status_code
        self.response = response
        self.error_code = "AI_API_ERROR"


class AICreditError(AIError):
    """AI额度不足异常"""
    
    def __init__(self, message: str, model: Optional[str] = None, 
                 provider: Optional[str] = None, credit_info: Optional[Dict[str, Any]] = None):
        super().__init__(message, model, provider, credit_info, retry_after=3600)  # 1小时后重试
        self.credit_info = credit_info
        self.error_code = "AI_CREDIT_ERROR"


class AIRateLimitError(AIError):
    """AI API限速异常"""
    
    def __init__(self, message: str, model: Optional[str] = None, 
                 provider: Optional[str] = None, retry_after: int = 300, 
                 rate_limit_info: Optional[Dict[str, Any]] = None):
        super().__init__(message, model, provider, rate_limit_info, retry_after)
        self.rate_limit_info = rate_limit_info
        self.error_code = "AI_RATE_LIMIT"


class AIResponseError(AIError):
    """AI响应解析异常"""
    
    def __init__(self, message: str, model: Optional[str] = None, 
                 provider: Optional[str] = None, raw_response: Optional[str] = None):
        super().__init__(message, model, provider, {"raw_response": raw_response})
        self.raw_response = raw_response
        self.error_code = "AI_RESPONSE_ERROR"


class AIFallbackError(AIError):
    """AI降级异常"""
    
    def __init__(self, message: str, model: Optional[str] = None, 
                 provider: Optional[str] = None, fallback_used: Optional[str] = None):
        super().__init__(message, model, provider, {"fallback_used": fallback_used})
        self.fallback_used = fallback_used
        self.error_code = "AI_FALLBACK_ERROR"


class ClassificationError(QBittorrentMonitorError):
    """分类相关异常"""
    
    def __init__(self, message: str, content: Optional[str] = None, 
                 categories: Optional[List[str]] = None, confidence: Optional[float] = None):
        super().__init__(message, details={"content": content, "categories": categories, "confidence": confidence})
        self.content = content
        self.categories = categories
        self.confidence = confidence
        self.error_code = "CLASSIFICATION_ERROR"


class ClipboardError(QBittorrentMonitorError):
    """剪贴板访问异常"""
    
    def __init__(self, message: str, clipboard_type: Optional[str] = None):
        super().__init__(message, details={"clipboard_type": clipboard_type})
        self.clipboard_type = clipboard_type
        self.error_code = "CLIPBOARD_ERROR"


class ClipboardPermissionError(ClipboardError):
    """剪贴板权限异常"""
    
    def __init__(self, message: str, application_name: Optional[str] = None):
        super().__init__(message, clipboard_type="permission")
        self.application_name = application_name
        self.error_code = "CLIPBOARD_PERMISSION_ERROR"


class ClipboardReadError(ClipboardError):
    """剪贴板读取异常"""
    
    def __init__(self, message: str, content_type: Optional[str] = None):
        super().__init__(message, clipboard_type="read")
        self.content_type = content_type
        self.error_code = "CLIPBOARD_READ_ERROR"


class ClipboardWriteError(ClipboardError):
    """剪贴板写入异常"""
    
    def __init__(self, message: str, content_length: Optional[int] = None):
        super().__init__(message, clipboard_type="write")
        self.content_length = content_length
        self.error_code = "CLIPBOARD_WRITE_ERROR"


class TorrentParseError(QBittorrentMonitorError):
    """种子解析异常"""
    
    def __init__(self, message: str, torrent_data: Optional[str] = None, parse_step: Optional[str] = None):
        super().__init__(message, details={"torrent_data": torrent_data, "parse_step": parse_step})
        self.torrent_data = torrent_data
        self.parse_step = parse_step
        self.error_code = "TORRENT_PARSE_ERROR"


class MagnetParseError(TorrentParseError):
    """磁力链接解析异常"""
    
    def __init__(self, message: str, magnet_link: Optional[str] = None):
        super().__init__(message, torrent_data=magnet_link, parse_step="magnet")
        self.magnet_link = magnet_link
        self.error_code = "MAGNET_PARSE_ERROR"


class NotificationError(QBittorrentMonitorError):
    """通知发送异常"""
    
    def __init__(self, message: str, channel: Optional[str] = None, notification_type: Optional[str] = None):
        super().__init__(message, details={"channel": channel, "type": notification_type})
        self.channel = channel
        self.notification_type = notification_type
        self.error_code = "NOTIFICATION_ERROR"


class NotificationDeliveryError(NotificationError):
    """通知投递异常"""
    
    def __init__(self, message: str, channel: Optional[str] = None, 
                 recipient: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message, channel, "delivery")
        self.recipient = recipient
        self.status_code = status_code
        self.error_code = "NOTIFICATION_DELIVERY_ERROR"


class NotificationTemplateError(NotificationError):
    """通知模板异常"""
    
    def __init__(self, message: str, template_name: Optional[str] = None, template_vars: Optional[Dict[str, Any]] = None):
        super().__init__(message, "template", "rendering")
        self.template_name = template_name
        self.template_vars = template_vars
        self.error_code = "NOTIFICATION_TEMPLATE_ERROR"


class CrawlerError(QBittorrentMonitorError):
    """网页爬虫异常"""
    
    def __init__(self, message: str, url: Optional[str] = None, site_name: Optional[str] = None):
        super().__init__(message, details={"url": url, "site_name": site_name})
        self.url = url
        self.site_name = site_name
        self.error_code = "CRAWLER_ERROR"


class CrawlerTimeoutError(CrawlerError):
    """爬虫超时异常"""
    
    def __init__(self, message: str, url: Optional[str] = None, timeout: Optional[float] = None):
        super().__init__(message, url)
        self.timeout = timeout
        self.error_code = "CRAWLER_TIMEOUT"


class CrawlerRateLimitError(CrawlerError):
    """爬虫限速异常"""
    
    def __init__(self, message: str, url: Optional[str] = None, retry_after: Optional[int] = None):
        super().__init__(message, url, retry_after=retry_after)
        self.error_code = "CRAWLER_RATE_LIMIT"


class CrawlerExtractionError(CrawlerError):
    """爬虫数据提取异常"""
    
    def __init__(self, message: str, url: Optional[str] = None, extraction_step: Optional[str] = None):
        super().__init__(message, url)
        self.extraction_step = extraction_step
        self.error_code = "CRAWLER_EXTRACTION_ERROR"


class ParseError(CrawlerError):
    """网页解析异常"""
    
    def __init__(self, message: str, url: Optional[str] = None, 
                 parser_type: Optional[str] = None, raw_content: Optional[str] = None):
        super().__init__(message, url)
        self.parser_type = parser_type
        self.raw_content = raw_content
        self.error_code = "PARSE_ERROR"


class CacheError(QBittorrentMonitorError):
    """缓存相关异常"""
    
    def __init__(self, message: str, cache_key: Optional[str] = None, cache_type: Optional[str] = None):
        super().__init__(message, details={"cache_key": cache_key, "cache_type": cache_type})
        self.cache_key = cache_key
        self.cache_type = cache_type
        self.error_code = "CACHE_ERROR"


class CacheNotFoundError(CacheError):
    """缓存未命中异常"""
    
    def __init__(self, message: str, cache_key: Optional[str] = None, cache_type: Optional[str] = None):
        super().__init__(message, cache_key, cache_type)
        self.error_code = "CACHE_NOT_FOUND"


class CacheWriteError(CacheError):
    """缓存写入异常"""
    
    def __init__(self, message: str, cache_key: Optional[str] = None, 
                 cache_type: Optional[str] = None, reason: Optional[str] = None):
        super().__init__(message, cache_key, cache_type)
        self.reason = reason
        self.error_code = "CACHE_WRITE_ERROR"


class CacheReadError(CacheError):
    """缓存读取异常"""
    
    def __init__(self, message: str, cache_key: Optional[str] = None, 
                 cache_type: Optional[str] = None, reason: Optional[str] = None):
        super().__init__(message, cache_key, cache_type)
        self.reason = reason
        self.error_code = "CACHE_READ_ERROR"


class ResourceError(QBittorrentMonitorError):
    """资源相关异常"""
    
    def __init__(self, message: str, resource_type: Optional[str] = None, resource_id: Optional[str] = None):
        super().__init__(message, details={"resource_type": resource_type, "resource_id": resource_id})
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.error_code = "RESOURCE_ERROR"


class ResourceTimeoutError(ResourceError):
    """资源超时异常"""
    
    def __init__(self, message: str, resource_type: Optional[str] = None, 
                 resource_id: Optional[str] = None, timeout: Optional[float] = None):
        super().__init__(message, resource_type, resource_id)
        self.timeout = timeout
        self.error_code = "RESOURCE_TIMEOUT"


class ResourceExhaustedError(ResourceError):
    """资源耗尽异常"""
    
    def __init__(self, message: str, resource_type: Optional[str] = None, 
                 resource_limit: Optional[int] = None, resource_count: Optional[int] = None):
        super().__init__(message, resource_type)
        self.resource_limit = resource_limit
        self.resource_count = resource_count
        self.error_code = "RESOURCE_EXHAUSTED"


class SecurityError(QBittorrentMonitorError):
    """安全相关异常"""
    
    def __init__(self, message: str, security_issue: Optional[str] = None):
        super().__init__(message, details={"security_issue": security_issue})
        self.security_issue = security_issue
        self.error_code = "SECURITY_ERROR"


class AuthenticationError(SecurityError):
    """认证异常"""
    
    def __init__(self, message: str, auth_type: Optional[str] = None, user: Optional[str] = None):
        super().__init__(message, "authentication")
        self.auth_type = auth_type
        self.user = user
        self.error_code = "AUTHENTICATION_ERROR"


class AuthorizationError(SecurityError):
    """授权异常"""
    
    def __init__(self, message: str, operation: Optional[str] = None, resource: Optional[str] = None):
        super().__init__(message, "authorization")
        self.operation = operation
        self.resource = resource
        self.error_code = "AUTHORIZATION_ERROR"


class DataCorruptionError(QBittorrentMonitorError):
    """数据损坏异常"""
    
    def __init__(self, message: str, data_type: Optional[str] = None, 
                 data_source: Optional[str] = None, checksum: Optional[str] = None):
        super().__init__(message, details={"data_type": data_type, "data_source": data_source, "checksum": checksum})
        self.data_type = data_type
        self.data_source = data_source
        self.checksum = checksum
        self.error_code = "DATA_CORRUPTION"


class ConcurrencyError(QBittorrentMonitorError):
    """并发处理异常"""
    
    def __init__(self, message: str, operation: Optional[str] = None, 
                 resource_id: Optional[str] = None, concurrent_ops: Optional[int] = None):
        super().__init__(message, details={"operation": operation, "resource_id": resource_id, "concurrent_ops": concurrent_ops})
        self.operation = operation
        self.resource_id = resource_id
        self.concurrent_ops = concurrent_ops
        self.error_code = "CONCURRENCY_ERROR"


class DeadlockError(ConcurrencyError):
    """死锁异常"""
    
    def __init__(self, message: str, resources: Optional[List[str]] = None):
        super().__init__(message, "deadlock", None, len(resources) if resources else None)
        self.resources = resources
        self.error_code = "DEADLOCK_ERROR"


class TaskTimeoutError(ConcurrencyError):
    """任务超时异常"""
    
    def __init__(self, message: str, task_id: Optional[str] = None, timeout: Optional[float] = None):
        super().__init__(message, "task_timeout", task_id)
        self.task_id = task_id
        self.timeout = timeout
        self.error_code = "TASK_TIMEOUT"


class StateError(QBittorrentMonitorError):
    """状态转换异常"""
    
    def __init__(self, message: str, current_state: Optional[str] = None, 
                 target_state: Optional[str] = None, operation: Optional[str] = None):
        super().__init__(message, details={"current_state": current_state, "target_state": target_state, "operation": operation})
        self.current_state = current_state
        self.target_state = target_state
        self.operation = operation
        self.error_code = "STATE_ERROR" 