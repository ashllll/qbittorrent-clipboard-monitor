# qBittorrent剪贴板监控器 - 统一异常处理架构规划

## 1. 异常层次结构设计

### 1.1 建议的异常继承树

```
QBittorrentMonitorError (项目基类)
├── ConfigurationError (配置相关)
│   ├── ConfigValidationError
│   ├── ConfigNotFoundError
│   └── ConfigLoadError
├── QBittorrentError (qBittorrent操作)
│   ├── NetworkError
│   │   ├── NetworkTimeoutError
│   │   └── NetworkConnectionError
│   ├── QbtAuthError
│   ├── QbtRateLimitError
│   ├── QbtPermissionError
│   └── QbtServerError
├── AIError (AI/分类相关)
│   ├── AIApiError
│   ├── AICreditError
│   ├── AIRateLimitError
│   ├── AIResponseError
│   └── AIFallbackError
├── ClassificationError (分类特定)
├── ClipboardError (剪贴板操作)
│   ├── ClipboardPermissionError
│   ├── ClipboardReadError
│   └── ClipboardWriteError
├── TorrentError (种子相关)
│   ├── TorrentParseError
│   └── MagnetParseError
├── NotificationError (通知系统)
│   ├── NotificationDeliveryError
│   └── NotificationTemplateError
├── CrawlerError (网页爬虫)
│   ├── CrawlerTimeoutError
│   ├── CrawlerRateLimitError
│   └── CrawlerExtractionError
├── CacheError (缓存系统)
│   ├── CacheNotFoundError
│   ├── CacheWriteError
│   └── CacheReadError
├── ResourceError (资源管理)
│   ├── ResourceTimeoutError
│   └── ResourceExhaustedError
├── SecurityError (安全相关)
│   ├── AuthenticationError
│   └── AuthorizationError
├── DataError (数据相关)
│   └── DataCorruptionError
├── ConcurrencyError (并发控制)
│   ├── DeadlockError
│   └── TaskTimeoutError
├── StateError (状态管理)
├── RetryableError (可重试标记)
└── NonRetryableError (不可重试标记)
    └── CircuitBreakerOpenError
```

### 1.2 按模块划分的异常类别

| 模块 | 主要异常 | 说明 |
|------|----------|------|
| config | ConfigurationError | 配置加载、验证、保存相关 |
| qbittorrent_client | QBittorrentError, NetworkError | qBittorrent API交互相关 |
| ai_classifier | AIError, ClassificationError | AI分类服务相关 |
| clipboard_monitor | ClipboardError | 剪贴板监控相关 |
| notifications | NotificationError | 通知发送相关 |
| web_crawler | CrawlerError | 网页爬取相关 |
| cache | CacheError | 缓存操作相关 |
| security | SecurityError | 认证授权相关 |
| resilience | RetryableError, NonRetryableError | 重试和断路器相关 |

### 1.3 按严重程度的分类策略

```python
class ErrorSeverity:
    """错误严重程度等级"""
    CRITICAL = "critical"      # 系统无法继续运行，需要立即处理
    ERROR = "error"            # 功能异常，但可以降级或重试
    WARNING = "warning"        # 非致命问题，需要关注
    INFO = "info"              # 信息性提示
```

各异常的默认严重程度：

| 严重程度 | 异常类别 | 示例 |
|----------|----------|------|
| CRITICAL | SecurityError, DataCorruptionError | 认证失败、数据损坏 |
| ERROR | QBittorrentError, AIError | API调用失败、网络错误 |
| WARNING | CacheError, NotificationError | 缓存未命中、通知发送失败 |
| INFO | RetryableError | 重试提示 |

---

## 2. 异常合并与清理

### 2.1 重复/相似异常识别

| 重复异常 | 位置 | 建议处理 |
|----------|------|----------|
| `ResourceExhaustedError` | exceptions.py + exceptions_enhanced.py | 保留exceptions.py版本 |
| `TimeoutError` | exceptions_enhanced.py + Python内置 | 重命名为 `OperationTimeoutError` |
| `RetryableError` | retry.py + exceptions_enhanced.py | 统一迁移到exceptions.py |
| `NonRetryableError` | retry.py + exceptions_enhanced.py | 统一迁移到exceptions.py |
| `CircuitBreakerOpenError` | retry.py + exceptions_enhanced.py + circuit_breaker.py | 统一迁移到exceptions.py |
| `ConfigError` | exceptions.py + config_enhanced.py(EnhancedConfigError) | 统一使用ConfigError |
| `AIAPIError` (笔误) | ai_classifier.py:468 | 修正为 `AIApiError` |

### 2.2 合并建议

1. **统一异常定义位置**：所有异常定义集中到 `exceptions.py`
2. **删除 `exceptions_enhanced.py`**：将其中的异常类合并到主异常文件
3. **保留 `retry.py` 中的导入**：但改为从 exceptions.py 导入
4. **修正命名不一致**：统一使用驼峰命名（如 AIApiError 而非 AIAPIError）

### 2.3 废弃旧异常的策略

```python
# 在 exceptions.py 中添加兼容性导入和警告
import warnings

def _deprecated_alias(old_name: str, new_class: type):
    """创建废弃的别名类，保留向后兼容"""
    class DeprecatedAlias(new_class):
        def __init__(self, *args, **kwargs):
            warnings.warn(
                f"{old_name} 已废弃，请使用 {new_class.__name__}",
                DeprecationWarning,
                stacklevel=2
            )
            super().__init__(*args, **kwargs)
    DeprecatedAlias.__name__ = old_name
    return DeprecatedAlias

# 废弃别名示例
EnhancedConfigError = _deprecated_alias("EnhancedConfigError", ConfigError)
```

---

## 3. 统一的异常处理机制

### 3.1 全局异常处理器设计

```python
# exceptions.py - 全局异常处理器

import logging
import functools
from typing import Callable, TypeVar, Any, Optional

logger = logging.getLogger(__name__)
T = TypeVar('T')

class GlobalExceptionHandler:
    """全局异常处理器
    
    提供统一的异常处理、日志记录和错误转换功能。
    """
    
    _handlers: dict[type[Exception], Callable[[Exception], Any]] = {}
    _default_handler: Optional[Callable[[Exception], Any]] = None
    
    @classmethod
    def register(cls, exc_type: type[Exception], handler: Callable[[Exception], Any]):
        """注册特定异常类型的处理器"""
        cls._handlers[exc_type] = handler
    
    @classmethod
    def set_default(cls, handler: Callable[[Exception], Any]):
        """设置默认处理器"""
        cls._default_handler = handler
    
    @classmethod
    def handle(cls, exc: Exception) -> Any:
        """处理异常"""
        # 查找最匹配的处理器
        for exc_type, handler in cls._handlers.items():
            if isinstance(exc, exc_type):
                return handler(exc)
        
        # 使用默认处理器
        if cls._default_handler:
            return cls._default_handler(exc)
        
        # 重新抛出
        raise exc


def handle_exceptions(
    *exceptions: type[Exception],
    default_return: Any = None,
    log_level: int = logging.ERROR,
    reraise: bool = False
) -> Callable:
    """异常处理装饰器
    
    Args:
        exceptions: 要捕获的异常类型
        default_return: 异常时的默认返回值
        log_level: 日志级别
        reraise: 是否重新抛出异常
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T | Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T | Any:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                logger.log(log_level, f"{func.__name__} 执行失败: {e}")
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator
```

### 3.2 异常转换/包装模式

```python
# exceptions.py - 异常转换工具

from contextlib import contextmanager
from typing import TypeVar, Type, Optional

T = TypeVar('T', bound=QBittorrentMonitorError)

@contextmanager
def exception_context(
    target_exc: Type[T],
    message: Optional[str] = None,
    preserve_cause: bool = True
):
    """异常转换上下文管理器
    
    将捕获的异常转换为目标异常类型，同时保留原始异常链。
    
    示例:
        with exception_context(NetworkError, "连接失败"):
            requests.get(url)
    """
    try:
        yield
    except Exception as e:
        if isinstance(e, QBittorrentMonitorError):
            # 已经是项目异常，直接抛出
            raise
        
        msg = message or str(e)
        new_exc = target_exc(msg)
        
        if preserve_cause:
            raise new_exc from e
        else:
            raise new_exc


def wrap_exception(
    exception: Exception,
    target_type: Type[T],
    message: Optional[str] = None
) -> T:
    """将异常包装为目标类型
    
    Args:
        exception: 原始异常
        target_type: 目标异常类型
        message: 可选的自定义消息
    
    Returns:
        包装后的异常实例
    """
    msg = message or str(exception)
    wrapped = target_type(msg)
    wrapped.__cause__ = exception
    return wrapped
```

### 3.3 错误码体系

```python
# exceptions.py - 错误码体系

from enum import Enum
from dataclasses import dataclass

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

@dataclass(frozen=True)
class ErrorCode:
    """标准错误码"""
    category: ErrorCategory
    code: int
    severity: str
    
    def __str__(self) -> str:
        return f"{self.category.value}-{self.code:04d}"

# 预定义错误码
ERROR_CODES = {
    # 配置错误 (CFG-0001 ~ CFG-0099)
    "CONFIG_VALIDATION_ERROR": ErrorCode(ErrorCategory.CONFIG, 1, "ERROR"),
    "CONFIG_NOT_FOUND": ErrorCode(ErrorCategory.CONFIG, 2, "ERROR"),
    "CONFIG_LOAD_ERROR": ErrorCode(ErrorCategory.CONFIG, 3, "ERROR"),
    
    # 网络错误 (NET-0100 ~ NET-0199)
    "NETWORK_ERROR": ErrorCode(ErrorCategory.NETWORK, 100, "ERROR"),
    "NETWORK_TIMEOUT": ErrorCode(ErrorCategory.NETWORK, 101, "ERROR"),
    "NETWORK_CONNECTION_ERROR": ErrorCode(ErrorCategory.NETWORK, 102, "ERROR"),
    
    # qBittorrent错误 (QBT-0200 ~ QBT-0299)
    "QBITTORRENT_ERROR": ErrorCode(ErrorCategory.QBITTORRENT, 200, "ERROR"),
    "QBT_AUTH_ERROR": ErrorCode(ErrorCategory.QBITTORRENT, 201, "CRITICAL"),
    "QBT_RATE_LIMIT": ErrorCode(ErrorCategory.QBITTORRENT, 202, "WARNING"),
    "QBT_PERMISSION_ERROR": ErrorCode(ErrorCategory.QBITTORRENT, 203, "ERROR"),
    "QBT_SERVER_ERROR": ErrorCode(ErrorCategory.QBITTORRENT, 204, "ERROR"),
    
    # AI错误 (AI-0300 ~ AI-0399)
    "AI_ERROR": ErrorCode(ErrorCategory.AI, 300, "ERROR"),
    "AI_API_ERROR": ErrorCode(ErrorCategory.AI, 301, "ERROR"),
    "AI_CREDIT_ERROR": ErrorCode(ErrorCategory.AI, 302, "WARNING"),
    "AI_RATE_LIMIT": ErrorCode(ErrorCategory.AI, 303, "WARNING"),
    "AI_RESPONSE_ERROR": ErrorCode(ErrorCategory.AI, 304, "ERROR"),
    "AI_FALLBACK_ERROR": ErrorCode(ErrorCategory.AI, 305, "WARNING"),
    
    # 其他...
}
```

---

## 4. 异常最佳实践规范

### 4.1 何时创建新异常 vs 使用现有异常

**创建新异常的情况：**
1. 新的错误类型需要特殊的处理逻辑
2. 需要携带特定的错误上下文信息
3. 属于不同的功能模块边界
4. 需要不同的重试策略

**使用现有异常的情况：**
1. 错误语义与现有异常一致
2. 只需要传递不同的错误消息
3. 临时性的错误包装

```python
# ✅ 好的实践：为特定错误创建专门的异常
class QbtRateLimitError(QBittorrentError):
    """qBittorrent API限速异常"""
    
    def __init__(self, message: str, retry_after: int = 60, ...):
        super().__init__(message, ...)
        self.retry_after = retry_after  # 特定上下文

# ❌ 不好的实践：为每种HTTP状态码创建异常
class Qbt403Error(QBittorrentError):  # 过于细化
    pass
class Qbt404Error(QBittorrentError):  # 过于细化
    pass
```

### 4.2 异常消息规范

```python
# ✅ 好的实践：清晰、具体、可操作
raise NetworkError(
    f"无法连接到qBittorrent服务器 "
    f"(host={host}, port={port}, 错误: {original_error})"
)

# ❌ 不好的实践：模糊、无上下文
raise NetworkError("连接失败")

# ✅ 好的实践：包含关键上下文
raise ConfigValidationError(
    f"配置验证失败",
    validation_errors=[
        {"field": "qbittorrent.port", "error": "必须在1-65535之间", "value": 99999},
        {"field": "ai.api_key", "error": "不能为空"},
    ]
)
```

### 4.3 异常链保留（__cause__）

```python
# ✅ 好的实践：始终保留异常链
try:
    response = await session.get(url)
except aiohttp.ClientError as e:
    raise NetworkError(f"请求失败: {url}") from e

# ✅ 好的实践：转换异常类型但保留上下文
try:
    config = yaml.safe_load(content)
except yaml.YAMLError as e:
    raise ConfigError(f"YAML解析失败: {file_path}") from e

# ❌ 不好的实践：丢失原始异常信息
try:
    response = await session.get(url)
except Exception:
    raise NetworkError("请求失败")  # 丢失了原始异常
```

---

## 5. 具体实施计划

### 第一阶段：统一异常定义文件（Week 1）

1. **重构 `exceptions.py`**
   - 添加错误码体系
   - 添加全局异常处理器
   - 添加异常转换工具
   - 统一异常基类属性

2. **合并 `exceptions_enhanced.py`**
   - 将 `RetryableError`、`NonRetryableError`、`CircuitBreakerOpenError` 移到 `exceptions.py`
   - 删除 `exceptions_enhanced.py`（或保留为空文件作为兼容层）

3. **更新 `retry.py`**
   - 从 `exceptions.py` 导入异常类
   - 删除本地定义的异常类

### 第二阶段：修复代码问题（Week 1-2）

1. **修正命名错误**
   - 修复 `ai_classifier.py:468` 的 `AIAPIError` → `AIApiError`

2. **更新所有导入语句**
   - 统一使用 `from qbittorrent_monitor.exceptions import ...`
   - 删除从 `exceptions_enhanced` 的导入

3. **修复异常继承关系**
   - 确保所有自定义异常继承自 `QBittorrentMonitorError`

### 第三阶段：添加兼容性层（Week 2）

1. **向后兼容支持**
   - 在 `__init__.py` 中导出所有公共异常
   - 添加废弃别名（如 `EnhancedConfigError` → `ConfigError`）

2. **更新文档**
   - 更新异常使用指南
   - 添加迁移说明

### 第四阶段：测试与验证（Week 2-3）

1. **单元测试**
   - 测试所有异常类的创建和序列化
   - 测试异常转换和包装
   - 测试全局异常处理器

2. **集成测试**
   - 验证异常在重试机制中的工作
   - 验证异常在断路器中的分类

---

## 6. 向后兼容策略

### 6.1 别名保留方案

```python
# qbittorrent_monitor/exceptions.py

# 为已删除/重命名的异常提供兼容性别名
import warnings
import sys

class _DeprecatedMeta(type):
    """用于创建废弃异常类的元类"""
    
    def __init__(cls, name, bases, namespace, *, replacement=None):
        super().__init__(name, bases, namespace)
        cls._replacement = replacement
    
    def __call__(cls, *args, **kwargs):
        if cls._replacement:
            warnings.warn(
                f"{cls.__name__} 已废弃，请使用 {cls._replacement.__name__}",
                DeprecationWarning,
                stacklevel=2
            )
        return super().__call__(*args, **kwargs)


# 废弃别名
class TimeoutError(QBittorrentMonitorError, metaclass=_DeprecatedMeta, replacement=NetworkTimeoutError):
    """已废弃：请使用 NetworkTimeoutError"""
    pass


class EnhancedConfigError(ConfigError, metaclass=_DeprecatedMeta, replacement=ConfigError):
    """已废弃：请使用 ConfigError"""
    pass
```

### 6.2 导入重定向

```python
# qbittorrent_monitor/__init__.py

# 统一导出所有公共异常
from .exceptions import (
    # 基础异常
    QBittorrentMonitorError,
    
    # 配置异常
    ConfigurationError,  # 重命名：ConfigError → ConfigurationError
    ConfigValidationError,
    ConfigNotFoundError,
    ConfigLoadError,
    
    # qBittorrent异常
    QBittorrentError,
    NetworkError,
    NetworkTimeoutError,
    NetworkConnectionError,
    QbtAuthError,
    QbtRateLimitError,
    QbtPermissionError,
    QbtServerError,
    
    # AI异常
    AIError,
    AIApiError,
    AICreditError,
    AIRateLimitError,
    AIResponseError,
    AIFallbackError,
    
    # 其他异常...
    ClassificationError,
    ClipboardError,
    TorrentError,
    NotificationError,
    CrawlerError,
    CacheError,
    ResourceError,
    SecurityError,
    DataError,
    ConcurrencyError,
    StateError,
    RetryableError,
    NonRetryableError,
    CircuitBreakerOpenError,
    
    # 兼容性别名（带废弃警告）
    ConfigError,  # 别名：ConfigurationError
    EnhancedConfigError,  # 废弃
)
```

### 6.3 废弃警告

```python
# 在异常类中自动触发废弃警告

class ConfigError(ConfigurationError):
    """已废弃：请使用 ConfigurationError
    
    保留此别名以维持向后兼容。
    """
    
    def __init__(self, *args, **kwargs):
        import warnings
        warnings.warn(
            "ConfigError 已废弃，将在 v2.0 中移除，请使用 ConfigurationError",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)
```

---

## 7. 文件结构建议

```
qbittorrent_monitor/
├── exceptions/
│   ├── __init__.py          # 统一导出所有异常
│   ├── base.py              # 异常基类和通用工具
│   ├── config.py            # 配置相关异常
│   ├── network.py           # 网络和qBittorrent异常
│   ├── ai.py                # AI和分类异常
│   ├── system.py            # 系统级异常（缓存、资源、并发）
│   └── compatibility.py     # 向后兼容别名
├── exceptions.py            # 主异常文件（可重定向到包）
└── ...
```

或者保持单文件结构（推荐用于中小型项目）：

```
qbittorrent_monitor/
├── exceptions.py            # 统一异常定义（约500-800行）
├── exceptions_legacy.py     # 兼容性别名（可选）
└── ...
```

---

## 8. 实施检查清单

- [ ] 创建重构后的 `exceptions.py`
- [ ] 合并 `exceptions_enhanced.py` 内容
- [ ] 更新 `retry.py` 导入
- [ ] 修复 `ai_classifier.py` 中的 `AIAPIError` 笔误
- [ ] 更新 `config_enhanced.py` 中的异常导入
- [ ] 更新 `__init__.py` 导出列表
- [ ] 添加废弃警告和兼容性别名
- [ ] 编写异常相关单元测试
- [ ] 更新项目文档
- [ ] 验证所有模块导入正常
- [ ] 运行完整测试套件

---

## 附录：关键代码片段

### 基类完整实现

```python
class QBittorrentMonitorError(Exception):
    """项目基础异常类
    
    所有项目异常的基类，提供统一的错误信息格式和序列化能力。
    
    Attributes:
        message: 错误消息
        details: 详细的错误信息（字典或任意类型）
        retry_after: 建议的重试等待时间（秒）
        error_code: 错误码
        severity: 错误严重程度
    """

    def __init__(
        self,
        message: str,
        details: Optional[Any] = None,
        retry_after: Optional[int] = None,
        error_code: Optional[str] = None,
        severity: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.retry_after = retry_after
        self.error_code = error_code or self._default_error_code()
        self.severity = severity or self._default_severity()
        self.timestamp = datetime.now().isoformat()
        self.context: Dict[str, Any] = {}
    
    def _default_error_code(self) -> str:
        """获取默认错误码"""
        return f"{self.__class__.__name__.upper()}_ERROR"
    
    def _default_severity(self) -> str:
        """获取默认严重程度"""
        return "ERROR"
    
    def to_dict(self) -> Dict[str, Any]:
        """将异常转换为字典格式"""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "severity": self.severity,
            "details": self.details,
            "retry_after": self.retry_after,
            "timestamp": self.timestamp,
            "context": self.context,
        }
    
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
```

---

*文档版本: 1.0*  
*最后更新: 2026-03-12*  
*作者: Python软件架构师*
