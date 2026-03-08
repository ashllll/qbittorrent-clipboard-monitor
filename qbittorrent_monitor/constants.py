"""常量定义模块

集中定义所有魔法数字，便于维护和统一修改。
"""

from typing import Final


# ============ 字节单位 ============
BYTES_PER_KB: Final[int] = 1024
BYTES_PER_MB: Final[int] = 1024 * 1024
BYTES_PER_GB: Final[int] = 1024 * 1024 * 1024


# ============ 剪贴板监控常量 ============
class MonitorConstants:
    """剪贴板监控相关常量"""
    
    # 缓存配置
    DEFAULT_CACHE_SIZE: Final[int] = 1000
    DEFAULT_CACHE_MEMORY_MB: Final[int] = 50
    MAX_CACHEABLE_CONTENT_MB: Final[int] = 10
    
    # 处理限制
    MAX_PROCESSED_CACHE_SIZE: Final[int] = 10_000
    MAX_MAGNETS_PER_CHECK: Final[int] = 100
    MAX_LOG_NAME_LENGTH: Final[int] = 50
    MAX_DB_NAME_LENGTH: Final[int] = 200
    
    # 时间配置（秒）
    DEFAULT_DEBOUNCE_SECONDS: Final[float] = 2.0
    CLIPBOARD_READ_TIMEOUT: Final[float] = 0.5
    DEBOUNCE_CLEANUP_MULTIPLIER: Final[float] = 2.0
    
    # 磁力链接限制
    MIN_MAGNET_LENGTH: Final[int] = 50
    CONTENT_HASH_SAMPLE_SIZE: Final[int] = 1000
    
    # 统计配置
    CHECK_TIME_WINDOW_SIZE: Final[int] = 100


# ============ 分类器常量 ============
class ClassifierConstants:
    """内容分类器相关常量"""
    
    # 缓存配置
    DEFAULT_CACHE_CAPACITY: Final[int] = 1000
    DEFAULT_BATCH_CONCURRENCY: Final[int] = 5
    
    # 置信度计算
    CONFIDENCE_BASE: Final[float] = 0.5
    CONFIDENCE_PER_MATCH: Final[float] = 0.1
    CONFIDENCE_BASE_MAX: Final[float] = 0.8
    CONFIDENCE_RATIO_MULTIPLIER: Final[float] = 0.2
    CONFIDENCE_RATIO_CAP: Final[float] = 0.15
    CONFIDENCE_MAX: Final[float] = 0.95
    CONFIDENCE_MIN_FOR_CACHING: Final[float] = 0.3
    
    # 阈值
    HIGH_CONFIDENCE_THRESHOLD: Final[float] = 0.7
    AI_BASE_CONFIDENCE: Final[float] = 0.85
    FALLBACK_CONFIDENCE: Final[float] = 0.3
    
    # AI 配置
    DEFAULT_AI_TIMEOUT: Final[float] = 30.0
    DEFAULT_AI_TEMPERATURE: Final[float] = 0.3
    DEFAULT_AI_MAX_TOKENS: Final[int] = 20
    
    # 关键词限制
    MAX_KEYWORDS_PER_CATEGORY: Final[int] = 1000
    MAX_KEYWORD_LENGTH: Final[int] = 100


# ============ 智能轮询常量 ============
class PacingConstants:
    """智能轮询相关常量"""
    
    DEFAULT_ACTIVE_INTERVAL: Final[float] = 0.5
    DEFAULT_IDLE_INTERVAL: Final[float] = 3.0
    DEFAULT_IDLE_THRESHOLD: Final[float] = 30.0
    DEFAULT_BURST_WINDOW: Final[float] = 5.0
    DEFAULT_BURST_THRESHOLD: Final[int] = 3


# ============ HTTP 状态码 ============
class HTTPStatus:
    """HTTP 状态码常量"""
    OK: Final[int] = 200
    UNAUTHORIZED: Final[int] = 401
    FORBIDDEN: Final[int] = 403
    NOT_FOUND: Final[int] = 404
    SERVER_ERROR_START: Final[int] = 500


# ============ 安全限制 ============
class SecurityLimits:
    """安全配置限制"""
    
    MAX_MAGNET_LENGTH: Final[int] = 8192
    MAX_PATH_LENGTH: Final[int] = 4096
    MAX_FILENAME_LENGTH: Final[int] = 255
    MAX_HOSTNAME_LENGTH: Final[int] = 253
    MAX_RETRIES: Final[int] = 10
    MIN_RETRY_DELAY: Final[float] = 0.5
    MAX_RETRY_DELAY: Final[float] = 60.0


# ============ 超时配置 ============
class TimeoutConstants:
    """超时配置常量"""
    
    CONNECT_TIMEOUT: Final[int] = 10
    READ_TIMEOUT: Final[int] = 30
    TOTAL_TIMEOUT: Final[int] = 60
    AI_REQUEST_TIMEOUT: Final[int] = 30
    QB_REQUEST_TIMEOUT: Final[int] = 30


# ============ 配置验证限制 ============
class ValidationLimits:
    """配置验证限制"""
    
    MIN_PORT: Final[int] = 1
    MAX_PORT: Final[int] = 65535
    MIN_TIMEOUT: Final[int] = 1
    MAX_TIMEOUT: Final[int] = 300
    MIN_RETRIES: Final[int] = 0
    MAX_RETRIES: Final[int] = 10
    MIN_CHECK_INTERVAL: Final[float] = 0.1
    MAX_CHECK_INTERVAL: Final[float] = 60.0
    MAX_AUTO_CLEANUP_DAYS: Final[int] = 365


# ============ 日志相关 ============
class LoggingConstants:
    """日志相关常量"""
    
    VALID_LOG_LEVELS: frozenset[str] = frozenset(
        {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    )
    DEFAULT_LOG_LEVEL: Final[str] = "INFO"


# ============ 重试配置 ============
class RetryConstants:
    """重试机制常量"""
    
    DEFAULT_MAX_RETRIES: Final[int] = 3
    DEFAULT_BASE_DELAY: Final[float] = 1.0
    DEFAULT_MAX_DELAY: Final[float] = 10.0
    DEFAULT_EXPONENTIAL_BASE: Final[float] = 2.0
    JITTER_PERCENTAGE: Final[float] = 0.2
