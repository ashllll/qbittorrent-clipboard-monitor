"""配置模块常量定义

定义验证范围和常量值。
"""

from __future__ import annotations

# 有效的日志级别
VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})

# 端口范围限制
MIN_PORT: int = 1
MAX_PORT: int = 65535

# 超时范围限制
MIN_TIMEOUT: int = 1
MAX_TIMEOUT: int = 300

# 重试次数限制
MIN_RETRIES: int = 0
MAX_RETRIES: int = 10

# 检查间隔范围限制
MIN_CHECK_INTERVAL: float = 0.1
MAX_CHECK_INTERVAL: float = 60.0

# 分类限制
MAX_KEYWORDS: int = 1000
MAX_KEYWORD_LENGTH: int = 100

# 默认配置值
DEFAULT_QBIT_HOST: str = "localhost"
DEFAULT_QBIT_PORT: int = 8080
DEFAULT_QBIT_USERNAME: str = "admin"
DEFAULT_AI_MODEL: str = "MiniMax-M2.5"
DEFAULT_AI_BASE_URL: str = "https://api.minimaxi.com/v1"
DEFAULT_AI_TIMEOUT: int = 30
DEFAULT_AI_MAX_RETRIES: int = 3
DEFAULT_CHECK_INTERVAL: float = 1.0
DEFAULT_LOG_LEVEL: str = "INFO"
