# 🌊 qBittorrent 剪贴板监控与自动分类下载器

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

自动监控剪贴板，智能识别磁力链接并使用 AI 自动分类添加到 qBittorrent。

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 🔄 **剪贴板监控** | 自动检测系统剪贴板中的磁力链接 |
| 🤖 **AI 智能分类** | 使用 DeepSeek AI 自动识别内容类型 |
| 🐝 **Ruflo AI 编排** | 多 Agent 协作 + 自学习优化 |
| 🕷️ **Playwright 爬虫** | JavaScript 动态页面渲染 |
| 🔍 **Crawl4AI 爬虫** | AI 驱动的智能爬取 |
| 🌐 **多协议支持** | Magnet、Thunder、QQ旋风、FlashGet |
| 🎨 **Web 管理界面** | 完整的管理面板 |
| 📊 **健康检查** | Prometheus 监控指标 |

---

## 🚀 快速开始

### 环境要求

- Python 3.9+
- qBittorrent 4.0+
- Node.js 18+ (可选，用于 Ruflo AI)
- Poetry (推荐)

### 安装

```bash
# 克隆项目
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 安装依赖
poetry install

# 或安装额外功能
poetry install --extras scraper  # 爬虫功能
```

### 配置

```bash
# 复制配置示例
cp qbittorrent_monitor/config.json.example qbittorrent_monitor/config.json

# 编辑配置文件
vim qbittorrent_monitor/config.json
```

### 启动

```bash
# 基础模式
poetry run python run.py

# 启动 Web 界面
poetry run python run.py --web
```

---

## 📦 项目结构

```
qbittorrent_monitor/
├── 🎯 核心模块
│   ├── clipboard_monitor.py    # 剪贴板监控
│   ├── clipboard_actions.py    # 动作执行
│   ├── clipboard_poller.py      # 剪贴板轮询
│   ├── clipboard_processor.py   # 内容处理
│   └── clipboard_models.py     # 数据模型
│
├── 🤖 AI 模块
│   ├── ai_classifier.py       # AI 分类器
│   ├── ruflo_classifier.py   # Ruflo AI 集成 ⭐
│   └── fallback.py            # 降级策略
│
├── 🕷️ 爬虫模块
│   ├── web_crawler.py         # Crawl4AI 爬虫
│   ├── playwright_crawler.py   # Playwright 爬虫 ⭐
│   └── crawler/               # 爬虫工具
│
├── 🌐 qBittorrent 客户端
│   ├── qbittorrent_client.py # 主客户端
│   └── qbt/                   # 客户端子包
│
├── ⚙️ 配置与工具
│   ├── config.py              # 配置管理
│   ├── utils.py               # 工具函数
│   └── exceptions.py          # 异常定义
│
├── 🛡️ 弹性组件
│   ├── resilience.py          # 基础弹性
│   ├── circuit_breaker.py     # 断路器
│   ├── retry.py               # 重试机制
│   └── enhanced_cache.py     # 增强缓存
│
├── 🌊 工作流
│   ├── workflow_engine.py    # 工作流引擎
│   ├── rss_manager.py      # RSS 管理
│   └── notifications.py      # 通知系统
│
└── 🎨 Web 界面
    ├── web_interface/        # Web 管理面板
    ├── health_check.py       # 健康检查
    └── monitoring.py          # 监控模块
```

---

## 🤖 AI 智能分类

### 基础 AI 分类 (DeepSeek/OpenAI)

```python
from qbittorrent_monitor import AIClassifier

classifier = AIClassifier(config.deepseek)
category = await classifier.classify(torrent_name, categories)
```

### Ruflo AI 编排 (可选) ⭐

[Ruflo](https://github.com/ruvnet/ruflo) 提供更强大的 AI 功能:

```bash
# 安装
npm install -g claude-flow
npx ruflo@latest init --wizard
```

配置启用:
```json
{
  "ruflo": {
    "enabled": true,
    "learning_enabled": true,
    "swarm_topology": "mesh"
  }
}
```

功能:
- 🐝 **Swarm 批量处理** - 多 Agent 协作
- 🧠 **自学习优化** - 从用户纠正中学习
- 📈 **持续改进** - 越用越聪明

---

## 🕷️ 爬虫方案

### 方案对比

| 爬虫 | 类型 | 适用场景 |
|------|------|----------|
| **Playwright** | 浏览器自动化 | 动态页面、JavaScript 渲染 |
| **Crawl4AI** | AI 爬虫 | AI 增强内容提取 |
| **内置解析** | 协议解析 | 磁力/Thunder/FlashGet 链接 |

### Playwright 用法

```python
from qbittorrent_monitor import PlaywrightCrawler

# 爬取单个页面
crawler = PlaywrightCrawler(config)
result = await crawler.crawl_page("https://example.com")
print(result['magnets'])  # 自动提取 magnet 链接

# 批量爬取
results = await crawler.crawl_multiple(urls, max_concurrent=3)

# 快速提取
from qbittorrent_monitor.playwright_crawler import quick_extract_magnets
magnets = await quick_extract_magnets(url)
```

安装:
```bash
pip install playwright
playwright install chromium
```

---

## ⚙️ 配置说明

### 完整配置示例

```json
{
  "qbittorrent": {
    "host": "localhost",
    "port": 8080,
    "username": "admin",
    "password": "adminadmin"
  },
  "deepseek": {
    "api_key": "your_api_key",
    "model": "deepseek-chat"
  },
  "categories": {
    "movies": {
      "savePath": "/downloads/movies/",
      "keywords": ["电影", "Movie", "1080p", "4K", "BluRay"]
    },
    "tv": {
      "savePath": "/downloads/tv/",
      "keywords": ["S01", "电视剧", "Series"]
    },
    "anime": {
      "savePath": "/downloads/anime/",
      "keywords": ["动画", "Anime"]
    },
    "music": {
      "savePath": "/downloads/music/",
      "keywords": ["音乐", "Music", "FLAC"]
    },
    "games": {
      "savePath": "/downloads/games/",
      "keywords": ["游戏", "Game"]
    },
    "software": {
      "savePath": "/downloads/software/",
      "keywords": ["软件", "Software"]
    },
    "adult": {
      "savePath": "/downloads/adult/",
      "keywords": ["成人", "18+"]
    },
    "other": {
      "savePath": "/downloads/other/",
      "keywords": []
    }
  },
  "ruflo": {
    "enabled": false,
    "learning_enabled": true,
    "swarm_topology": "mesh"
  },
  "web_crawler": {
    "enabled": true,
    "page_timeout": 60000,
    "max_concurrent_extractions": 3
  }
}
```

---

## 🌐 Web 界面

启动后访问:

| 服务 | 地址 |
|------|------|
| 管理面板 | http://localhost:8000 |
| 健康检查 | http://localhost:8090/health |
| Prometheus 指标 | http://localhost:8091/metrics |

---

## 📚 文档

- [Ruflo 集成文档](RUFLO_INTEGRATION.md)
- [优化规划](OPTIMIZATION_PLAN.md)
- [部署指南](docs/DEPLOYMENT_GUIDE.md)
- [故障排除](docs/TROUBLESHOOTING.md)

---

## 📊 代码统计

```
Python 文件: 58
代码行数: ~22,883
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📜 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。

---

⭐ 如果这个项目对您有帮助，请给个 Star 支持一下！
