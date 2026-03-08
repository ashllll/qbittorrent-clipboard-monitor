# API 文档

本文档详细描述 qBittorrent Clipboard Monitor 的所有模块、类和函数。

## 目录

- [架构概览](#架构概览)
- [配置模块 (config)](#配置模块-config)
- [客户端模块 (qb_client)](#客户端模块-qb_client)
- [分类模块 (classifier)](#分类模块-classifier)
- [监控模块 (monitor)](#监控模块-monitor)
- [工具模块 (utils)](#工具模块-utils)
- [异常模块 (exceptions)](#异常模块-exceptions)
- [日志过滤器 (logging_filters)](#日志过滤器-logging_filters)

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          架构图                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │   剪贴板监控     │────▶│   内容分类器     │────▶│  qBittorrent   │   │
│  │  ClipboardMonitor│     │ ContentClassifier│     │    QBClient     │   │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘   │
│           │                       │                       │            │
│           ▼                       ▼                       ▼            │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │   剪贴板缓存     │     │   LRU 缓存      │     │   API 重试机制   │   │
│  │ ClipboardCache  │     │    LRUCache     │     │   with_retry    │   │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        配置管理 (Config)                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │  QBConfig   │  │  AIConfig   │  │     CategoryConfig      │  │   │
│  │  │ qBittorrent │  │  AI 分类    │  │       分类规则          │  │   │
│  │  │   连接配置   │  │   配置      │  │                         │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 数据流

```
系统剪贴板 → 内容提取 → 磁力链接解析 → 内容分类 → qBittorrent API → 下载任务
                │              │              │
                ▼              ▼              ▼
           哈希缓存       规则匹配       创建分类
           (去重)      AI 自动分类    添加种子
```

---

## 配置模块 (config)

配置模块提供灵活的配置管理，支持 JSON 配置文件和环境变量。

### QBConfig

qBittorrent 连接配置。

```python
from qbittorrent_monitor.config import QBConfig

config = QBConfig(
    host="localhost",        # 服务器地址
    port=8080,              # Web UI 端口
    username="admin",       # 用户名
    password="adminadmin",  # 密码
    use_https=False         # 是否使用 HTTPS
)

# 验证配置
config.validate()

# 异步验证连接
result = await config.verify_connection(timeout=10)
# 返回: {"success": True, "version": "4.6.0", "message": "..."}
```

**属性说明：**

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | str | "localhost" | 服务器主机名或 IP |
| `port` | int | 8080 | Web UI 端口 (1-65535) |
| `username` | str | "admin" | 登录用户名 |
| `password` | str | "adminadmin" | 登录密码 |
| `use_https` | bool | False | 使用 HTTPS 连接 |

---

### AIConfig

AI 分类器配置。

```python
from qbittorrent_monitor.config import AIConfig

config = AIConfig(
    enabled=True,
    api_key="sk-xxxxxxxxxxxxxxxx",
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
    timeout=30,
    max_retries=3
)

config.validate()
```

**属性说明：**

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | True | 是否启用 AI 分类 |
| `api_key` | str | "" | API 密钥（启用时必需） |
| `model` | str | "deepseek-chat" | AI 模型名称 |
| `base_url` | str | "https://api.deepseek.com/v1" | API 基础 URL |
| `timeout` | int | 30 | 请求超时秒数 (1-300) |
| `max_retries` | int | 3 | 最大重试次数 (0-10) |

---

### CategoryConfig

分类配置。

```python
from qbittorrent_monitor.config import CategoryConfig

config = CategoryConfig(
    save_path="/downloads/movies",
    keywords=["电影", "Movie", "1080p", "4K"]
)

config.validate("movies")
```

**属性说明：**

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `save_path` | str | "" | 下载保存路径 |
| `keywords` | List[str] | [] | 匹配关键词列表 |

---

### Config

应用配置根对象。

```python
from qbittorrent_monitor.config import Config, QBConfig, AIConfig, CategoryConfig

# 方式1: 直接创建
config = Config(
    qbittorrent=QBConfig(host="192.168.1.100", password="secret"),
    ai=AIConfig(enabled=True, api_key="sk-xxx"),
    categories={
        "movies": CategoryConfig(save_path="/downloads/movies", keywords=["Movie"]),
        "tv": CategoryConfig(save_path="/downloads/tv", keywords=["S01"]),
    },
    check_interval=1.0,
    log_level="INFO"
)

# 验证配置
config.validate(strict=True)

# 方式2: 从字典加载
config = Config.from_dict({
    "qbittorrent": {"host": "localhost", "port": 8080, ...},
    "ai": {"enabled": False, ...},
    ...
})

# 方式3: 从文件加载
config = Config.load("/path/to/config.json")

# 保存到文件
config.save("/path/to/config.json")

# 转换为字典
data = config.to_dict()

# 验证 qBittorrent 连接
result = await config.verify_qb_connection()
```

**属性说明：**

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `qbittorrent` | QBConfig | QBConfig() | qBittorrent 配置 |
| `ai` | AIConfig | AIConfig() | AI 分类配置 |
| `categories` | Dict[str, CategoryConfig] | {} | 分类规则字典 |
| `check_interval` | float | 1.0 | 剪贴板检查间隔 (0.1-60.0) |
| `log_level` | str | "INFO" | 日志级别 |

---

### ConfigManager

配置管理器，支持热重载。

```python
from qbittorrent_monitor.config import ConfigManager

# 创建管理器（启用自动重载）
manager = ConfigManager(
    config_path="~/.config/qb-monitor/config.json",
    auto_reload=True,
    reload_interval=5.0
)

# 获取配置（自动检查更新）
config = manager.get_config()

# 强制重新加载
config = manager.reload()

# 注册配置变更回调
def on_config_change(new_config):
    print("配置已更新！")
    print(f"新的检查间隔: {new_config.check_interval}")

manager.on_change(on_config_change)

# 移除回调
manager.remove_callback(on_config_change)
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `config_path` | Path | ~/.config/qb-monitor/config.json | 配置文件路径 |
| `auto_reload` | bool | False | 是否自动重载 |
| `reload_interval` | float | 5.0 | 重载检查间隔 |

---

### load_config()

便捷的加载配置函数。

```python
from qbittorrent_monitor.config import load_config

# 加载默认配置
config = load_config()

# 加载指定配置文件
config = load_config("/path/to/config.json")

# 非严格模式（只警告不报错）
config = load_config(strict=False)
```

**加载顺序：**
1. 从配置文件加载（不存在则创建默认配置）
2. 从环境变量加载并覆盖
3. 验证配置有效性

**环境变量：**

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `QBIT_HOST` | 服务器地址 | `192.168.1.100` |
| `QBIT_PORT` | 服务器端口 | `8080` |
| `QBIT_USERNAME` | 用户名 | `admin` |
| `QBIT_PASSWORD` | 密码 | `secret` |
| `QBIT_USE_HTTPS` | 使用 HTTPS | `true` |
| `AI_ENABLED` | 启用 AI | `true` |
| `AI_API_KEY` | API 密钥 | `sk-xxx` |
| `AI_MODEL` | 模型名称 | `deepseek-chat` |
| `AI_BASE_URL` | API 地址 | `https://api.deepseek.com/v1` |
| `AI_TIMEOUT` | 超时时间 | `30` |
| `AI_MAX_RETRIES` | 最大重试 | `3` |
| `CHECK_INTERVAL` | 检查间隔 | `1.0` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

---

## 客户端模块 (qb_client)

异步 qBittorrent Web API 客户端。

### QBClient

```python
from qbittorrent_monitor.config import load_config
from qbittorrent_monitor.qb_client import QBClient

config = load_config()

# 使用异步上下文管理器
async with QBClient(config) as qb:
    # 获取版本
    version = await qb.get_version()
    print(f"qBittorrent 版本: {version}")
    
    # 添加磁力链接
    success = await qb.add_torrent(
        magnet="magnet:?xt=urn:btih:...",
        category="movies",
        save_path="/downloads/movies"
    )
    
    # 获取分类列表
    categories = await qb.get_categories()
    
    # 创建分类
    await qb.create_category("custom", "/downloads/custom")
    
    # 确保配置中的分类都存在
    await qb.ensure_categories()
```

**方法说明：**

#### get_version()

```python
async def get_version() -> str
```

获取 qBittorrent 版本。

**返回：** 版本字符串，失败返回 `"unknown"`

---

#### add_torrent()

```python
async def add_torrent(
    magnet: str,
    category: Optional[str] = None,
    save_path: Optional[str] = None
) -> bool
```

添加磁力链接到 qBittorrent。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `magnet` | str | 磁力链接 |
| `category` | Optional[str] | 分类名称 |
| `save_path` | Optional[str] | 保存路径 |

**返回：** 是否添加成功

**示例：**

```python
success = await qb.add_torrent(
    "magnet:?xt=urn:btih:abc123...&dn=Movie.Name",
    category="movies",
    save_path="/mnt/downloads/movies"
)
```

---

#### get_categories()

```python
async def get_categories() -> Dict[str, Any]
```

获取所有分类。

**返回：** 分类字典 `{name: {savePath: "..."}}`

---

#### create_category()

```python
async def create_category(name: str, save_path: str) -> bool
```

创建新分类。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | str | 分类名称 |
| `save_path` | str | 保存路径 |

**返回：** 是否创建成功

---

#### ensure_categories()

```python
async def ensure_categories() -> None
```

确保配置中的所有分类都存在，不存在则自动创建。

---

### 重试装饰器 (with_retry)

```python
from qbittorrent_monitor.qb_client import with_retry

class MyClient:
    @with_retry(
        max_retries=3,        # 最大重试次数
        base_delay=1.0,       # 初始延迟
        max_delay=10.0,       # 最大延迟
        exponential_base=2.0, # 指数基数
        retry_on=(aiohttp.ClientError, asyncio.TimeoutError)
    )
    async def unstable_operation(self):
        # 可能失败的操作
        pass
```

---

### 异常类

#### QBAPIError

```python
from qbittorrent_monitor.qb_client import QBAPIError, APIErrorType

try:
    await qb.add_torrent(...)
except QBAPIError as e:
    print(f"错误类型: {e.error_type}")  # APIErrorType.AUTH_ERROR
    print(f"状态码: {e.status_code}")    # 401
    print(f"端点: {e.endpoint}")          # "/torrents/add"
    print(f"重试次数: {e.retry_count}")   # 3
```

---

## 分类模块 (classifier)

内容智能分类器，支持规则匹配和 AI 自动分类。

### ClassificationResult

分类结果数据类。

```python
from qbittorrent_monitor.classifier import ClassificationResult

result = ClassificationResult(
    category="movies",      # 分类名称
    confidence=0.85,        # 置信度 0.0-1.0
    method="ai",           # 分类方法: "rule", "ai", "fallback"
    cached=False,          # 是否来自缓存
    timestamp=1234567890.0 # 时间戳
)

print(result.category)    # "movies"
print(result.confidence)  # 0.85
print(result.method)      # "ai"
```

---

### ContentClassifier

```python
from qbittorrent_monitor.config import load_config
from qbittorrent_monitor.classifier import ContentClassifier

config = load_config()
classifier = ContentClassifier(config, cache_size=1000)

# 单个分类
result = await classifier.classify("Movie.Name.2024.1080p.BluRay.x264")
print(f"分类: {result.category}, 置信度: {result.confidence}")

# 批量分类
names = ["Movie.1", "TV.Show.S01E01", "Music.Album"]
results = await classifier.classify_batch(
    names,
    use_cache=True,
    timeout=30.0,
    max_concurrent=5
)

# 获取缓存统计
stats = classifier.get_cache_stats()
print(f"缓存命中率: {stats['hit_rate']:.2%}")

# 清空缓存
classifier.clear_cache()

# 预加载缓存
classifier.preload_cache(
    names=["known1", "known2"],
    results=["movies", "tv"]
)
```

**内置分类：**

| 分类 | 关键词示例 |
|------|-----------|
| `movies` | 1080p, 4K, BluRay, WEB-DL, 电影, Movie |
| `tv` | S01, E01, Season, Episode, 电视剧 |
| `anime` | 动画, Anime, BD, 剧场版, 字幕组 |
| `music` | FLAC, MP3, Album, OST, 音乐 |
| `software` | Software, Portable, Windows, Linux |
| `games` | PC, Steam, CODEX, REPACK |
| `books` | PDF, EPUB, Ebook, 书籍 |
| `other` | 默认分类 |

---

#### classify()

```python
async def classify(
    name: str,
    use_cache: bool = True,
    timeout: Optional[float] = None
) -> ClassificationResult
```

分类单个内容。

**分类流程：**
1. 检查缓存
2. 规则匹配（高置信度直接返回）
3. AI 分类（如启用）
4. 规则匹配（低置信度）
5. 降级到 "other"

---

#### classify_batch()

```python
async def classify_batch(
    names: List[str],
    use_cache: bool = True,
    timeout: Optional[float] = None,
    max_concurrent: int = 5
) -> List[ClassificationResult]
```

批量分类内容，支持并发控制。

---

### LRUCache

LRU 缓存实现。

```python
from qbittorrent_monitor.classifier import LRUCache

cache = LRUCache(capacity=1000)

# 添加缓存
result = ClassificationResult(category="movies", confidence=0.9, method="rule")
cache.put("key", result)

# 获取缓存
result = cache.get("key")
if result:
    print("缓存命中！")

# 获取统计
stats = cache.get_cache_stats()
# {
#     "size": 100,
#     "capacity": 1000,
#     "hits": 500,
#     "misses": 100,
#     "hit_rate": 0.833
# }

# 清空缓存
cache.clear()
```

---

## 监控模块 (monitor)

剪贴板监控核心模块。

### ClipboardMonitor

```python
from qbittorrent_monitor.config import load_config
from qbittorrent_monitor.qb_client import QBClient
from qbittorrent_monitor.monitor import ClipboardMonitor

config = load_config()

async with QBClient(config) as qb:
    monitor = ClipboardMonitor(qb, config)
    
    # 添加处理回调
    def on_magnet_added(magnet: str, category: str):
        print(f"✓ 已添加到 [{category}]: {magnet[:50]}...")
    
    monitor.add_handler(on_magnet_added)
    
    # 启动监控
    await monitor.start()
```

**回调函数签名：**

```python
def handler(magnet: str, category: str) -> None:
    """
    磁力链接处理回调
    
    Args:
        magnet: 磁力链接
        category: 分类名称
    """
    pass
```

---

#### 自定义轮询配置

```python
from qbittorrent_monitor.monitor import ClipboardMonitor, PacingConfig

# 自定义智能轮询参数
pacing = PacingConfig(
    active_interval=0.5,          # 活跃状态检查间隔
    idle_interval=3.0,            # 空闲状态检查间隔
    idle_threshold_seconds=30.0,  # 进入空闲状态的阈值
    burst_window_seconds=5.0,     # 突发变化检测窗口
    burst_threshold=3             # 触发活跃状态的连续变化次数
)

monitor = ClipboardMonitor(qb, config, pacing_config=pacing)
```

---

#### 获取统计信息

```python
# 获取统计
stats = monitor.get_stats()
print(f"""
运行时间: {stats['uptime_seconds']:.0f} 秒
处理数量: {stats['total_processed']}
成功添加: {stats['successful_adds']}
失败添加: {stats['failed_adds']}
重复跳过: {stats['duplicates_skipped']}
检查次数: {stats['checks_performed']}
剪贴板变化: {stats['clipboard_changes']}
每分钟检查: {stats['checks_per_minute']:.2f}
平均耗时: {stats['avg_check_time_ms']:.3f} ms
""")

# 清空缓存
monitor.clear_cache()
```

---

#### 停止监控

```python
# 方法1: 在另一个任务中调用
monitor.stop()

# 方法2: 发送 KeyboardInterrupt (Ctrl+C)
```

---

### MonitorStats

监控统计信息。

```python
from qbittorrent_monitor.monitor import MonitorStats
from datetime import datetime

stats = MonitorStats()
stats.start_time = datetime.now()

# 记录检查耗时
stats.record_check_time(0.5)  # 0.5 ms

# 获取统计
print(f"运行时间: {stats.uptime_seconds} 秒")
print(f"每分钟检查: {stats.checks_per_minute:.2f}")

# 导出为字典
data = stats.to_dict()
```

---

### ClipboardCache

剪贴板内容哈希缓存。

```python
from qbittorrent_monitor.monitor import ClipboardCache

cache = ClipboardCache(max_size=1000)

# 添加缓存
cache.put("剪贴板内容", "result_hash")

# 获取缓存
result = cache.get("剪贴板内容")
if result:
    print("缓存命中！")

# 清空缓存
cache.clear()

# 获取缓存大小
print(f"缓存项数: {len(cache)}")
```

---

### MagnetExtractor

优化的磁力链接提取器。

```python
from qbittorrent_monitor.monitor import MagnetExtractor

# 从文本中提取磁力链接
text = """
这里有一些磁力链接：
magnet:?xt=urn:btih:ABC123...&dn=Movie
另一个：magnet:?xt=urn:btih:DEF456...&dn=TV.Show
"""

magnets = MagnetExtractor.extract(text)
# 返回: ["magnet:?xt=urn:btih:ABC123...", "magnet:?xt=urn:btih:DEF456..."]

# 验证磁力链接
is_valid = MagnetExtractor._is_valid_magnet("magnet:?xt=urn:btih:abc123")

# 提取 hash
hash_value = MagnetExtractor._extract_hash("magnet:?xt=urn:btih:ABC123")
# 返回: "abc123" (小写)
```

---

## 工具模块 (utils)

实用工具函数。

### parse_magnet()

解析磁力链接，获取显示名称。

```python
from qbittorrent_monitor.utils import parse_magnet

name = parse_magnet("magnet:?xt=urn:btih:...&dn=Movie.Name.2024")
# 返回: "Movie.Name.2024"

name = parse_magnet("invalid")
# 返回: None
```

---

### extract_magnet_hash()

提取磁力链接的 info hash。

```python
from qbittorrent_monitor.utils import extract_magnet_hash

hash_value = extract_magnet_hash("magnet:?xt=urn:btih:ABC123DEF456")
# 返回: "abc123def456" (小写)

hash_value = extract_magnet_hash("invalid")
# 返回: None
```

---

## 异常模块 (exceptions)

### 异常层次结构

```
QBMonitorError (基类)
├── ConfigError          配置错误
├── QBClientError        qBittorrent 客户端错误
│   ├── QBAuthError      认证错误
│   └── QBConnectionError 连接错误
├── AIError              AI 分类错误
└── ClassificationError  分类错误
```

### 使用示例

```python
from qbittorrent_monitor.exceptions import (
    QBMonitorError,
    ConfigError,
    QBClientError,
    QBAuthError,
    QBConnectionError,
    AIError,
    ClassificationError
)

try:
    config = load_config()
except ConfigError as e:
    print(f"配置错误: {e}")

try:
    async with QBClient(config) as qb:
        await qb.add_torrent(...)
except QBAuthError as e:
    print(f"认证失败: {e}")
except QBConnectionError as e:
    print(f"连接失败: {e}")
except QBClientError as e:
    print(f"客户端错误: {e}")
```

---

## 日志过滤器 (logging_filters)

### SensitiveDataFilter

敏感信息过滤器，防止密码、API 密钥泄露到日志。

```python
import logging
from qbittorrent_monitor.logging_filters import SensitiveDataFilter

# 为现有日志记录器添加过滤器
logger = logging.getLogger("my_logger")
filter = SensitiveDataFilter()
logger.addFilter(filter)

# 日志中的敏感信息会被自动过滤
logger.info("API key: sk-1234567890abcdef")
# 输出: API key: ***

logger.info("Password: mysecretpassword")
# 输出: Password: ***

logger.info("Magnet: magnet:?xt=urn:btih:ABC123...")
# 输出: Magnet: magnet:?xt=urn:btih:ABC123***
```

**过滤内容：**

| 类型 | 示例 | 过滤结果 |
|------|------|----------|
| API 密钥 | `api_key=sk-12345` | `api_key=***` |
| 密码 | `password=secret` | `password=***` |
| 令牌 | `token=abc123` | `token=***` |
| 磁力链接 | `magnet:?xt=urn:btih:abc123...` | `magnet:?xt=urn:btih:abc123***` |
| 数据库 URL | `postgresql://user:pass@host` | `postgresql://user:***@host` |

---

### setup_sensitive_logging()

快速配置带敏感信息过滤的日志。

```python
from qbittorrent_monitor.logging_filters import setup_sensitive_logging

# 配置日志
logger = setup_sensitive_logging(
    level="INFO",
    logger_name="qb_monitor"
)

# 使用日志
logger.info("Starting with password: secret123")
# 输出: Starting with password: ***
```

---

## 完整使用示例

### 基本使用

```python
import asyncio
from qbittorrent_monitor.config import load_config
from qbittorrent_monitor.qb_client import QBClient
from qbittorrent_monitor.monitor import ClipboardMonitor

async def main():
    # 加载配置
    config = load_config()
    
    # 创建客户端并启动监控
    async with QBClient(config) as qb:
        # 确保分类存在
        await qb.ensure_categories()
        
        # 创建监控器
        monitor = ClipboardMonitor(qb, config)
        
        # 启动监控
        await monitor.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### 自定义分类器

```python
from qbittorrent_monitor.classifier import ContentClassifier

# 使用自定义关键词
config.categories["movies"].keywords.extend([
    "HDR", "Dolby", "Atmos", "REMUX"
])

classifier = ContentClassifier(config)

# 在监控器中使用自定义分类器
monitor = ClipboardMonitor(qb, config, classifier=classifier)
```

### 事件处理

```python
def on_magnet_detected(magnet: str, category: str):
    """磁力链接检测到但未处理"""
    print(f"检测到: {category}")

def on_magnet_added(magnet: str, category: str):
    """磁力链接成功添加"""
    print(f"✓ 已添加: {category}")

def on_magnet_failed(magnet: str, category: str):
    """磁力链接添加失败"""
    print(f"✗ 添加失败: {category}")

monitor.add_handler(on_magnet_added)
```

### 错误处理

```python
import asyncio
from qbittorrent_monitor.config import load_config, ConfigError
from qbittorrent_monitor.qb_client import QBClient, QBAuthError, QBConnectionError

async def safe_monitor():
    try:
        config = load_config()
    except ConfigError as e:
        print(f"配置错误，请检查配置文件: {e}")
        return
    
    try:
        async with QBClient(config) as qb:
            version = await qb.get_version()
            print(f"已连接到 qBittorrent {version}")
            
            monitor = ClipboardMonitor(qb, config)
            await monitor.start()
            
    except QBAuthError:
        print("认证失败，请检查用户名和密码")
    except QBConnectionError:
        print("无法连接到 qBittorrent，请检查服务器地址和端口")
    except KeyboardInterrupt:
        print("用户中断")
```
