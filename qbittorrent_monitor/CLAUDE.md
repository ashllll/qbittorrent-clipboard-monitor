# qbittorrent_monitor 模块 - 核心业务逻辑

> 🔙 [返回主目录](../CLAUDE.md)
>
> 📍 **位置**: `./qbittorrent_monitor/`
>
> 📅 **最后更新**: 2026-03-03

---

## 📖 模块概述

`qbittorrent_monitor` 是项目的核心业务模块，负责实现剪贴板监控、AI 智能分类、磁力链接解析、qBittorrent API 交互等核心功能。

### 🎯 核心职责
- 实时监控剪贴板内容变化
- 智能解析磁力链接和各种协议
- AI 智能分类内容
- 与 qBittorrent API 交互
- 弹性网络管理和缓存
- 网页爬虫和内容抓取

---

## 📦 模块结构

```
qbittorrent_monitor/
├── __init__.py              # 模块入口
├── __version__.py           # 版本信息
├── config.py                # 配置管理 (1033行)
├── config_validator.py      # 配置验证
├── exceptions.py            # 统一异常定义
├── clipboard_monitor.py    # 剪贴板监控 (1144行)
│   ├── ClipboardMonitor    # 主监控器
│   ├── ActivityTracker     # 活动跟踪
│   ├── SmartBatcher        # 智能批处理
│   └── OptimizedClipboardMonitor
├── clipboard_poller.py     # 剪贴板轮询
├── clipboard_processor.py  # 内容处理器
├── clipboard_actions.py    # 动作执行
├── clipboard_models.py     # 数据模型
├── qbittorrent_client.py    # qBittorrent客户端 (1197行)
│   ├── QBittorrentClient   # 主客户端
│   └── OptimizedQBittorrentClient
├── ai_classifier.py        # AI分类器 (964行)
├── web_crawler.py          # 网页爬虫 (1614行)
│   ├── WebCrawler          # 主爬虫
│   ├── SiteConfig          # 网站配置
│   ├── SmartConcurrencyController
│   ├── MemoryMonitor
│   ├── ConfigurableSiteAdapter
│   └── OptimizedAsyncWebCrawler
├── notifications.py        # 通知系统
├── health_check.py         # 健康检查
├── monitoring.py           # 监控模块 (850行)
├── workflow_engine.py      # 工作流引擎 (752行)
├── rss_manager.py          # RSS管理器
├── startup.py              # 启动管理
├── utils.py                # 工具函数
├── resilience.py           # 弹性组件
│   ├── RateLimiter
│   ├── CircuitBreaker
│   ├── LRUCache
│   └── MetricsTracker
├── circuit_breaker.py      # 断路器实现 (714行)
│   ├── UnifiedCircuitBreaker
│   ├── FixedWindowRateLimiter
│   ├── SlidingWindowRateLimiter
│   ├── TokenBucketRateLimiter
│   └── TrafficController
├── retry.py                # 重试机制 (716行)
│   ├── RetryConfig
│   ├── RetryableError
│   └── RetryWithCircuitBreaker
├── fallback.py            # 降级策略
├── enhanced_cache.py       # 增强缓存
├── intelligent_filter.py   # 智能过滤
├── graceful_shutdown.py    # 优雅关闭
├── concurrency.py          # 并发管理
├── resource_manager.py     # 资源管理
├── prometheus_metrics.py   # Prometheus指标
│
├── qbt/                    # qBittorrent客户端子包
│   ├── __init__.py
│   ├── qbittorrent_client.py
│   ├── api_client.py
│   ├── connection_pool.py
│   ├── cache_manager.py
│   ├── torrent_manager.py
│   ├── category_manager.py
│   ├── batch_operations.py
│   └── metrics.py
│
├── web_crawler/            # 网页爬虫子包
│   ├── __init__.py
│   ├── core.py
│   ├── adapters.py
│   ├── models.py
│   ├── optimizer.py
│   ├── cache.py
│   ├── resilience.py
│   └── stats.py
│
├── crawler/                # 爬虫工具子包
│   ├── __init__.py
│   ├── crawler_stats.py
│   ├── resource_pool.py
│   └── torrent_info.py
│
└── web_interface/          # Web管理界面
    ├── __init__.py
    ├── app.py
    ├── static/
    └── templates/
```

---

## 📊 代码统计

| 模块 | 行数 | 说明 |
|------|------|------|
| web_crawler.py | 1614 | 网页爬虫 |
| qbittorrent_client.py | 1197 | qBittorrent客户端 |
| clipboard_monitor.py | 1144 | 剪贴板监控 |
| config.py | 1033 | 配置管理 |
| ai_classifier.py | 964 | AI分类器 |
| monitoring.py | 850 | 监控模块 |
| web_interface/app.py | 766 | Web界面 |
| workflow_engine.py | 752 | 工作流引擎 |
| retry.py | 716 | 重试机制 |
| circuit_breaker.py | 714 | 断路器 |
| **总计** | **~21,000** | 56个Python文件 |

---

## 🔧 核心模块说明

### 1. 配置管理 (`config.py`)

```python
from qbittorrent_monitor.config import ConfigManager, AppConfig
```

- 支持 JSON/YAML/TOML 格式
- 环境变量覆盖
- 配置热重载
- 密码安全存储

### 2. 剪贴板监控 (`clipboard_monitor.py`)

```python
from qbittorrent_monitor.clipboard_monitor import ClipboardMonitor
```

- 异步监控
- 自适应间隔
- 智能批处理
- 活动跟踪

### 3. qBittorrent客户端 (`qbittorrent_client.py`)

```python
from qbittorrent_monitor.qbittorrent_client import QBittorrentClient
```

- 100% 官方Web API v2支持
- 连接池管理
- 自动重试
- 断路器保护

### 4. AI分类器 (`ai_classifier.py`)

```python
from qbittorrent_monitor.ai_classifier import AIClassifier
```

- DeepSeek/OpenAI/Claude支持
- 关键词规则分类
- 结果缓存
- 错误降级

### 5. 网页爬虫 (`web_crawler.py`)

```python
from qbittorrent_monitor.web_crawler import WebCrawler
```

- crawl4ai集成
- JavaScript渲染
- 反反爬策略
- 批量URL处理

---

## 🛡️ 弹性组件

### resilience.py
- `RateLimiter` - 基础速率限制
- `CircuitBreaker` - 基础断路器
- `LRUCache` - LRU缓存
- `MetricsTracker` - 指标追踪

### circuit_breaker.py
- `UnifiedCircuitBreaker` - 统一断路器
- `FixedWindowRateLimiter` - 固定窗口限速
- `SlidingWindowRateLimiter` - 滑动窗口限速
- `TokenBucketRateLimiter` - 令牌桶限速
- `TrafficController` - 流量控制器

### retry.py
- `RetryConfig` - 重试配置
- `RetryableError` - 可重试错误
- `RetryWithCircuitBreaker` - 带断路器的重试

---

## 🚀 使用示例

```python
import asyncio
from qbittorrent_monitor.config import ConfigManager
from qbittorrent_monitor.clipboard_monitor import ClipboardMonitor
from qbittorrent_monitor.qbittorrent_client import QBittorrentClient

async def main():
    config = await ConfigManager().load_config()
    async with QBittorrentClient(config.qbittorrent, config) as client:
        monitor = ClipboardMonitor(client, config)
        await monitor.start()

asyncio.run(main())
```

---

## 📚 参考资料

- [qBittorrent Web API](https://github.com/qbittorrent/qBittorrent/wiki/Web-API-Documentation)
- [DeepSeek API](https://docs.deepseek.com/)
- [crawl4ai](https://github.com/unclecode/crawl4ai)

---

*本项目由 AI 助手优化整理*
