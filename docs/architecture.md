# qBittorrent Clipboard Monitor 架构设计

本文档描述项目的整体架构设计、模块关系和数据流。

## 目录

- [系统架构](#系统架构)
- [模块设计](#模块设计)
- [数据流](#数据流)
- [错误处理架构](#错误处理架构)
- [扩展性设计](#扩展性设计)

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      qBittorrent Clipboard Monitor               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Clipboard  │    │   Content    │    │  qBittorrent │      │
│  │   Monitor    │───▶│  Classifier  │───▶│   Client     │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│          │                   │                   │              │
│          ▼                   ▼                   ▼              │
│  ┌──────────────────────────────────────────────────────┐      │
│  │                    Common Module                      │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │      │
│  │  │Exceptions│  │Decorators│  │Validators│           │      │
│  │  └──────────┘  └──────────┘  └──────────┘           │      │
│  └──────────────────────────────────────────────────────┘      │
│          │                   │                   │              │
│          ▼                   ▼                   ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Database   │    │   Security   │    │   Metrics    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 核心模块职责

| 模块 | 职责 | 关键类/函数 |
|------|------|-------------|
| **monitor** | 剪贴板监控 | `ClipboardMonitor`, `MagnetExtractor` |
| **classifier** | 内容分类 | `ContentClassifier`, `LRUCache` |
| **qb_client** | qBittorrent 通信 | `QBClient`, `QBAPIError` |
| **common** | 通用工具 | `safe_operation`, `Validator`, `ErrorCode` |
| **config** | 配置管理 | `Config`, `ConfigManager` |
| **security** | 安全验证 | `validate_magnet`, `sanitize_filename` |
| **database** | 数据持久化 | `DatabaseManager` |
| **metrics** | 指标收集 | Prometheus 指标导出 |

## 模块设计

### Common 模块（核心设计）

Common 模块提供跨模块共享的工具，是本次代码质量提升的核心。

```
┌─────────────────────────────────────────┐
│           Common Module                  │
├─────────────────────────────────────────┤
│                                          │
│  ┌─────────────────────────────────┐    │
│  │        Exceptions               │    │
│  │  • QBMonitorError (base)        │    │
│  │  • ConfigError                  │    │
│  │  • QBClientError                │    │
│  │  • ValidationError              │    │
│  │  • ErrorCode (enum)             │    │
│  └─────────────────────────────────┘    │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │        Decorators               │    │
│  │  • @safe_operation              │    │
│  │  • @async_safe_operation        │    │
│  │  • @retry_with_backoff          │    │
│  │  • @log_execution_time          │    │
│  └─────────────────────────────────┘    │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │        Validators               │    │
│  │  • Validator (class)            │    │
│  │  • validate_port()              │    │
│  │  • validate_timeout()           │    │
│  │  • validate_range()             │    │
│  └─────────────────────────────────┘    │
│                                          │
└─────────────────────────────────────────┘
```

#### 统一异常体系

```python
# 错误代码体系: 模块(2位) + 类别(2位) + 序号(2位)
# 例如: 101000 = 配置模块 + 输入错误 + 第0号错误

class QBMonitorError(Exception):
    """基础异常类"""
    def __init__(
        self,
        message: str,
        error_code: Optional[ErrorCode] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        ...

# 使用示例
raise ConfigError(
    "端口配置无效",
    error_code=ErrorCode.CONFIG_INVALID,
    context={"port": 99999, "valid_range": "1-65535"},
)
```

#### 装饰器设计

```python
# 安全操作装饰器 - 统一错误处理
@async_safe_operation(
    error_message="API调用失败",
    error_code=ErrorCode.QB_API_ERROR,
)
async def api_call():
    ...

# 重试装饰器 - 指数退避
@retry_with_backoff(
    max_retries=3,
    base_delay=1.0,
    retry_on=(aiohttp.ClientError, asyncio.TimeoutError),
)
async def unreliable_operation():
    ...
```

#### 验证器设计

```python
# 链式验证
port = (Validator()
    .check("port", value)
    .is_not_none()
    .is_integer()
    .is_port()
    .validate())

# 独立验证函数
port = validate_port(value, "QBIT_PORT")
timeout = validate_timeout(value, "AI_TIMEOUT")
```

### Monitor 模块

```
┌─────────────────────────────────────────┐
│        Clipboard Monitor                 │
├─────────────────────────────────────────┤
│                                          │
│  ┌──────────────┐  ┌──────────────┐     │
│  │ MonitorStats │  │ PacingConfig │     │
│  └──────────────┘  └──────────────┘     │
│                                          │
│  ┌──────────────┐  ┌──────────────┐     │
│  │ClipBoardCache│  │MagnetExtractor│    │
│  └──────────────┘  └──────────────┘     │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │      ClipboardMonitor           │    │
│  │  • start() / stop()             │    │
│  │  • _check_clipboard()           │    │
│  │  • _process_magnet()            │    │
│  └─────────────────────────────────┘    │
│                                          │
└─────────────────────────────────────────┘
```

### Classifier 模块

```
┌─────────────────────────────────────────┐
│        Content Classifier                │
├─────────────────────────────────────────┤
│                                          │
│  ┌─────────────────────────────────┐    │
│  │    ClassificationResult         │    │
│  │  • category: str                │    │
│  │  • confidence: float            │    │
│  │  • method: str (rule/ai/fallback)│   │
│  └─────────────────────────────────┘    │
│                                          │
│  ┌──────────────┐  ┌──────────────┐     │
│  │  LRUCache    │  │   Keywords   │     │
│  │  (capacity)  │  │   Library    │     │
│  └──────────────┘  └──────────────┘     │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │     ContentClassifier           │    │
│  │  • classify()                   │    │
│  │  • _rule_classify()             │    │
│  │  • _ai_classify_with_timeout()  │    │
│  └─────────────────────────────────┘    │
│                                          │
└─────────────────────────────────────────┘
```

### QBClient 模块

```
┌─────────────────────────────────────────┐
│        QBClient (qBittorrent API)        │
├─────────────────────────────────────────┤
│                                          │
│  ┌──────────────┐  ┌──────────────┐     │
│  │  APIErrorType│  │   QBAPIError │     │
│  │  (enum)      │  │   (exception)│     │
│  └──────────────┘  └──────────────┘     │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │         QBClient                │    │
│  │  • add_torrent()                │    │
│  │  • get_categories()             │    │
│  │  • create_category()            │    │
│  │  • _login()                     │    │
│  │  • _handle_response_error()     │    │
│  └─────────────────────────────────┘    │
│                                          │
│  ┌──────────────┐  ┌──────────────┐     │
│  │  @with_retry │  │  HTTP Session│     │
│  └──────────────┘  └──────────────┘     │
│                                          │
└─────────────────────────────────────────┘
```

## 数据流

### 磁力链接处理流程

```
剪贴板内容
    │
    ▼
┌─────────────────┐
│ ClipboardMonitor│
│ _check_clipboard│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ MagnetExtractor │
│    extract()    │
└────────┬────────┘
         │ 磁力链接列表
         ▼
┌─────────────────┐
│ ClipboardMonitor│
│ _process_content│
└────────┬────────┘
         │ 逐个处理
         ▼
┌─────────────────┐
│ ClipboardMonitor│
│ _process_magnet │
└────────┬────────┘
         │
         ├──────────────┐
         ▼              ▼
┌─────────────────┐ ┌──────────┐
│ ContentClassifier│ │ Database │
│   classify()    │ │  Record  │
└────────┬────────┘ └──────────┘
         │ 分类结果
         ▼
┌─────────────────┐
│    QBClient     │
│  add_torrent()  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  qBittorrent    │
│    Server       │
└─────────────────┘
```

### 配置加载流程

```
环境变量 ──┐
          │
配置文件 ──┼──▶ Config.load() ──▶ Config.validate() ──▶ Config 对象
          │
默认值  ──┘
```

## 错误处理架构

### 错误传播路径

```
底层异常 (aiohttp, asyncio)
         │
         ▼
┌─────────────────┐
│  @safe_operation │ ──▶ 日志记录
│  装饰器捕获      │
└────────┬────────┘
         │
         ▼ 包装为
┌─────────────────┐
│  QBMonitorError │ ──▶ 统一错误代码
│  (带 context)   │
└────────┬────────┘
         │
         ▼ 可选：用户处理
┌─────────────────┐
│  业务逻辑处理    │ ──▶ 降级、重试、退出
└─────────────────┘
```

### 错误处理模式

```python
# 模式1: 自动处理（装饰器）
@async_safe_operation(
    error_message="数据库操作失败",
    error_code=ErrorCode.DB_QUERY_FAILED,
    reraise=False,  # 不抛出，返回默认值
    default_return=[],
)
async def query_database():
    ...

# 模式2: 手动处理
async def process_with_fallback():
    try:
        return await primary_operation()
    except QBConnectionError as e:
        logger.warning(f"主操作失败: {e}")
        return await fallback_operation()
    except QBMonitorError as e:
        logger.error(f"操作失败: {e}")
        raise
```

## 扩展性设计

### 插件系统架构

```
┌─────────────────────────────────────────┐
│           Plugin System                  │
├─────────────────────────────────────────┤
│                                          │
│  ┌─────────────────────────────────┐    │
│  │      Plugin Interface           │    │
│  │  • on_torrent_added()           │    │
│  │  • on_classification_done()     │    │
│  │  • on_error()                   │    │
│  └─────────────────────────────────┘    │
│                   ▲                      │
│         ┌────────┼────────┐              │
│         │        │        │              │
│         ▼        ▼        ▼              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Webhook  │ │ DingTalk │ │  Custom  │ │
│  │ Notifier │ │ Notifier │ │  Plugin  │ │
│  └──────────┘ └──────────┘ └──────────┘ │
│                                          │
└─────────────────────────────────────────┘
```

### 分类器扩展

```python
# 通过配置扩展关键词
config.categories["custom"] = CategoryConfig(
    save_path="/downloads/custom",
    keywords=["custom-keyword1", "custom-keyword2"],
)

# 分类器自动合并默认和自定义关键词
```

### 添加新验证器

```python
# 在 common/validators.py 中添加

def validate_custom(value: Any, field_name: str = "value") -> Any:
    """验证自定义格式"""
    validator = Validator()
    return (validator
        .check(field_name, value)
        .is_not_none()
        .custom(_custom_validator, "格式无效")
        .validate())
```

### 添加新装饰器

```python
# 在 common/decorators.py 中添加

def rate_limited(
    max_calls: int,
    period: float,
) -> Callable[[F], F]:
    """速率限制装饰器"""
    def decorator(func: F) -> F:
        calls = []
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            now = time.time()
            # 清理过期调用记录
            calls[:] = [c for c in calls if now - c < period]
            
            if len(calls) >= max_calls:
                raise QBMonitorError(
                    "速率限制 exceeded",
                    error_code=ErrorCode.RATE_LIMITED,
                )
            
            calls.append(now)
            return await func(*args, **kwargs)
        
        return cast(F, wrapper)
    return decorator
```

## 性能考虑

### 缓存策略

| 组件 | 缓存类型 | 容量 | 策略 |
|------|----------|------|------|
| ClipboardCache | 内容哈希 | 1000 | LRU |
| LRUCache (classifier) | 分类结果 | 1000 | LRU |
| QBClient session | 连接池 | 10/5 | 连接复用 |

### 异步设计

```python
# 使用 asyncio.gather 并发处理
async def process_batch(magnets: List[str]):
    tasks = [process_magnet(m) for m in magnets]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

# 使用信号量限制并发
semaphore = asyncio.Semaphore(5)

async def limited_operation():
    async with semaphore:
        return await actual_operation()
```

## 安全设计

### 多层验证

```
输入层: 剪贴板内容验证
    │
    ▼
处理层: 磁力链接验证 (security.validate_magnet)
    │
    ▼
输出层: API 调用验证 (QBClient 参数检查)
    │
    ▼
持久层: 路径验证 (security.validate_save_path)
```

### 敏感信息保护

```python
# 日志过滤
from qbittorrent_monitor.logging_filters import sanitize_for_log

logger.info(f"连接: {sanitize_for_log(url)}")

# 配置保护
config.save()  # 自动设置 0o600 权限
```

## 监控和可观测性

### 指标收集

```python
# 业务指标
metrics_module.record_torrent_processed(category="movies")
metrics_module.record_classification(method="rule", category="tv")

# 性能指标
with metrics_module.timed_api_call(endpoint="/torrents/add"):
    await client.add_torrent(magnet)
```

### 日志追踪

```python
# 上下文日志
logger.info(f"处理磁力链接 [hash={magnet_hash[:8]}...]")

# 结构化日志
logger.info("添加种子", extra={
    "magnet_hash": magnet_hash,
    "category": category,
    "duration_ms": duration * 1000,
})
```
