# 架构重构迁移指南 (v3.0 → v3.1)

本文档描述 qBittorrent Clipboard Monitor 从 v3.0 到 v3.1 的架构重构变更和迁移方法。

## 概述

v3.1 对项目架构进行了重构，主要改进：

1. **模块化配置系统** - 将 1000+ 行的 `config.py` 拆分为 10 个子模块
2. **Repository 模式** - 为数据库层引入 Repository 设计模式
3. **Watchers 组件** - 将监控器拆分为独立的可复用组件

所有变更保持**完全向后兼容**，现有代码无需修改即可继续工作。

---

## 1. 配置模块重构

### 新模块结构

```
qbittorrent_monitor/config/
├── __init__.py          # 公开 API 导出
├── constants.py         # 配置常量（范围限制等）
├── validators.py        # 验证工具函数
├── base.py             # Config 根类
├── qb.py               # QBConfig
├── ai.py               # AIConfig
├── categories.py       # CategoryConfig
├── database.py         # DatabaseConfig
├── metrics.py          # MetricsConfig
├── plugins.py          # PluginConfig
├── manager.py          # ConfigManager 热重载
└── env_loader.py       # 环境变量加载
```

### 向后兼容

```python
# 旧方式（仍然支持，但会发出 DeprecationWarning）
from qbittorrent_monitor.config import Config, load_config

# 新方式（推荐）
from qbittorrent_monitor.config.base import Config
from qbittorrent_monitor.config.env_loader import load_config
from qbittorrent_monitor.config.manager import ConfigManager
```

### 迁移示例

**原代码：**
```python
from qbittorrent_monitor.config import Config, QBConfig, load_config

config = load_config()
print(config.qbittorrent.host)
```

**新代码（可选）：**
```python
from qbittorrent_monitor.config.base import Config
from qbittorrent_monitor.config.qb import QBConfig
from qbittorrent_monitor.config.env_loader import load_config

config = load_config()
print(config.qbittorrent.host)
```

---

## 2. Repository 模式

### 新模块结构

```
qbittorrent_monitor/repository/
├── __init__.py          # 公开 API 导出
├── base.py             # Repository 抽象基类
├── torrent.py          # TorrentRepository
└── stats.py            # StatsRepository
```

### 数据模型

```python
from qbittorrent_monitor.repository import (
    TorrentRecord,       # 磁力链接记录
    CategoryStats,       # 分类统计
    SystemEvent,         # 系统事件
)
```

### Repository 类

```python
from qbittorrent_monitor.repository import (
    Repository,           # 抽象基类
    RepositoryError,      # 基础异常
    RecordNotFoundError,  # 记录不存在
    DuplicateRecordError, # 重复记录
    TorrentRepository,    # 磁力链接 Repository
    StatsRepository,      # 统计 Repository
)
```

### 使用示例

```python
import aiosqlite
from qbittorrent_monitor.repository import TorrentRepository, StatsRepository

async with aiosqlite.connect("monitor.db") as conn:
    # 创建 Repository 实例
    torrent_repo = TorrentRepository(conn)
    stats_repo = StatsRepository(conn)
    
    # 使用 Repository
    record = await torrent_repo.create({
        "magnet_hash": "abc123...",
        "name": "Movie Name",
        "category": "movies",
        "status": "success"
    })
    
    # 更新分类统计
    await stats_repo.update_category_stats("movies", "success")
    
    # 查询数据
    records = await torrent_repo.find(category="movies", limit=10)
    stats = await stats_repo.get_category_stats()
```

### 与旧代码的兼容

```python
# 旧方式（仍然支持，但会发出 DeprecationWarning）
from qbittorrent_monitor.database import DatabaseManager

# 新方式（推荐）
from qbittorrent_monitor.repository import TorrentRepository, StatsRepository
```

---

## 3. Watchers 组件

### 新模块结构

```
qbittorrent_monitor/watchers/
├── __init__.py              # 公开 API 导出
├── debounce.py             # DebounceFilter
├── rate_limiter.py         # RateLimiter
├── clipboard_watcher.py    # ClipboardWatcher
└── cache.py                # ClipboardCache
```

### 组件说明

| 组件 | 用途 | 类名 |
|------|------|------|
| DebounceFilter | 防抖过滤器，防止重复处理 | `DebounceFilter` |
| RateLimiter | 速率限制器，使用令牌桶算法 | `RateLimiter` |
| ClipboardWatcher | 纯剪贴板观察器 | `ClipboardWatcher` |
| ClipboardCache | 剪贴板内容缓存 | `ClipboardCache` |

### 使用示例

```python
from qbittorrent_monitor.watchers import (
    DebounceFilter,
    RateLimiter,
    ClipboardWatcher,
    ClipboardCache,
)
from qbittorrent_monitor.watchers.clipboard_watcher import ClipboardEvent

# 防抖过滤器
debounce = DebounceFilter(debounce_seconds=2.0)
if not debounce.is_debounced("magnet_hash"):
    process_magnet(magnet)

# 速率限制器
limiter = RateLimiter(max_per_second=10.0, burst_size=5)
if limiter.try_acquire():
    process_item()

# 剪贴板观察器
async def on_clipboard_change(event: ClipboardEvent):
    print(f"剪贴板变化: {event.content[:50]}")

watcher = ClipboardWatcher(check_interval=0.5)
watcher.add_listener(on_clipboard_change)
await watcher.start()

# 缓存
cache = ClipboardCache(max_size=1000)
result = cache.get(content)
if result is None:
    result = process_content(content)
    cache.put(content, result)
```

---

## 4. 新增导出

根模块 `qbittorrent_monitor` 新增以下导出：

```python
# Repository 模式
from qbittorrent_monitor import (
    Repository,
    RepositoryError,
    RecordNotFoundError,
    DuplicateRecordError,
    TorrentRepository,
    StatsRepository,
    TorrentRecord,
    CategoryStats,
    SystemEvent,
)

# Watchers 组件
from qbittorrent_monitor import (
    DebounceFilter,
    RateLimiter,
    ClipboardWatcher,
    ClipboardEvent,
    ClipboardCache,
)
```

---

## 5. 弃用警告

直接导入旧模块现在会发出 `DeprecationWarning`：

```python
# 会产生警告
from qbittorrent_monitor.config import Config
from qbittorrent_monitor.database import DatabaseManager

# 警告信息：
# qbittorrent_monitor.config 已弃用。
# 请使用 qbittorrent_monitor.config 子模块。
```

建议在新代码中使用新的导入路径。

---

## 6. 文件结构对比

### 重构前

```
qbittorrent_monitor/
├── config.py          # 1000+ 行
├── database.py        # 1000+ 行
├── monitor.py         # 700+ 行
└── ...
```

### 重构后

```
qbittorrent_monitor/
├── config/            # 配置模块（10个文件）
│   ├── __init__.py
│   ├── base.py
│   ├── qb.py
│   ├── ai.py
│   ├── categories.py
│   ├── database.py
│   ├── metrics.py
│   ├── plugins.py
│   ├── validators.py
│   ├── constants.py
│   ├── manager.py
│   └── env_loader.py
├── repository/        # Repository 模式
│   ├── __init__.py
│   ├── base.py
│   ├── torrent.py
│   └── stats.py
├── watchers/          # 监控组件
│   ├── __init__.py
│   ├── debounce.py
│   ├── rate_limiter.py
│   ├── clipboard_watcher.py
│   └── cache.py
├── config.py          # 向后兼容层
├── database.py        # 向后兼容层
├── monitor.py         # 使用 watchers 重构
└── ...
```

---

## 7. 性能改进

重构后的架构带来以下性能优势：

1. **按需导入** - 只导入需要的子模块，减少内存占用
2. **组件复用** - Watchers 组件可在其他场景独立使用
3. **Repository 抽象** - 便于未来更换存储后端（如 PostgreSQL、MongoDB）
4. **更清晰的依赖** - 减少循环依赖，提高代码可测试性

---

## 8. 迁移时间表

| 版本 | 说明 |
|------|------|
| v3.1 | 重构完成，向后兼容，发出 DeprecationWarning |
| v3.x | 保持兼容性，推荐使用新 API |
| v4.0 | 移除兼容层，仅支持新 API（计划中） |

---

## 9. 常见问题

### Q: 我需要立即迁移我的代码吗？
A: 不需要。现有代码继续工作，但建议在新功能中使用新 API。

### Q: 如何禁用弃用警告？
A: 可以使用警告过滤器：
```python
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="qbittorrent_monitor")
```

### Q: Repository 模式支持哪些数据库？
A: 目前仅支持 SQLite（通过 aiosqlite），但接口设计允许未来扩展。

### Q: 我可以单独使用 Watchers 组件吗？
A: 可以！所有 watchers 组件都是独立的，可在其他项目中使用。

---

## 10. 完整示例

### 重构后的 ClipboardMonitor 使用

```python
import asyncio
from qbittorrent_monitor import (
    Config, load_config,
    QBClient, ContentClassifier,
    ClipboardMonitor,
)

async def main():
    # 加载配置
    config = load_config()
    
    # 创建客户端
    qb = QBClient(config)
    await qb.login()
    
    # 创建监控器
    monitor = ClipboardMonitor(
        qb_client=qb,
        config=config,
        classifier=ContentClassifier(config),
    )
    
    # 启动监控
    await monitor.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### 使用独立组件

```python
from qbittorrent_monitor.watchers import ClipboardWatcher, DebounceFilter
from qbittorrent_monitor.repository import TorrentRepository
import aiosqlite

async def custom_monitor():
    # 使用独立组件构建自定义监控
    debounce = DebounceFilter(debounce_seconds=3.0)
    
    async def on_change(event):
        if debounce.is_debounced(event.content_hash):
            return
        print(f"处理: {event.content[:50]}")
    
    watcher = ClipboardWatcher(check_interval=0.5)
    watcher.add_listener(on_change)
    await watcher.start()
```

---

## 总结

本次重构将单体代码拆分为三个独立模块：

1. **config/** - 模块化配置系统
2. **repository/** - Repository 模式数据访问
3. **watchers/** - 可复用的监控组件

所有变更保持向后兼容，现有代码无需修改即可工作。建议在新代码中使用新 API，以获得更好的模块化体验和类型支持。
