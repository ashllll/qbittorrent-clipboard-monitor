"""限制常量定义

定义系统中各种资源的上限和下限限制。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    """系统限制常量"""
    
    # 磁力链接限制
    MIN_MAGNET_LENGTH: int = 50
    MAX_MAGNET_LENGTH: int = 8192
    MAX_MAGNETS_PER_CHECK: int = 100
    
    # 端口范围
    MIN_PORT: int = 1
    MAX_PORT: int = 65535
    
    # 超时范围
    MIN_TIMEOUT: int = 1
    MAX_TIMEOUT: int = 300
    
    # 重试次数
    MIN_RETRIES: int = 0
    MAX_RETRIES: int = 10
    
    # 检查间隔
    MIN_CHECK_INTERVAL: float = 0.1
    MAX_CHECK_INTERVAL: float = 60.0
    
    # 路径和文件名
    MAX_PATH_LENGTH: int = 4096
    MAX_FILENAME_LENGTH: int = 255
    MAX_HOSTNAME_LENGTH: int = 253
    MAX_PATH_DEPTH: int = 20
    
    # 配置限制
    MAX_KEYWORDS: int = 1000
    MAX_KEYWORD_LENGTH: int = 100
    
    # 数据库限制
    MAX_RECORDS_PER_QUERY: int = 10000
    
    # 内存限制 (MB)
    MAX_CLIPBOARD_CACHE_MEMORY_MB: int = 50
    MAX_CONTENT_SIZE_FOR_CACHE: int = 10 * 1024 * 1024  # 10MB
    
    # 处理队列限制
    MAX_PROCESSED_CACHE_SIZE: int = 10000
    MAX_PENDING_MAGNETS: int = 1000


@dataclass(frozen=True)
class Timeouts:
    """超时设置常量 (秒)"""
    
    # HTTP 连接超时
    CONNECT: float = 10.0
    READ: float = 30.0
    TOTAL: float = 60.0
    
    # API 请求超时
    AI_REQUEST: float = 30.0
    QB_REQUEST: float = 30.0
    
    # 剪贴板操作超时
    CLIPBOARD: float = 0.5
    
    # 数据库批量写入刷新间隔
    DB_FLUSH_INTERVAL: float = 60.0
    
    # 缓存过期时间
    CACHE_TTL: int = 3600  # 1小时


@dataclass(frozen=True)
class CacheSizes:
    """缓存大小限制"""
    
    # 剪贴板缓存
    CLIPBOARD: int = 1000
    
    # 分类缓存
    CLASSIFICATION: int = 1000
    
    # 已处理磁力链接缓存
    PROCESSED: int = 10000
    
    # 防抖队列
    DEBOUNCE: int = 1000
    
    # 数据库批量写入
    BATCH_SIZE: int = 10
    
    # HTTP 连接池
    CONNECTION_POOL: int = 10
    CONNECTIONS_PER_HOST: int = 5
