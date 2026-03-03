# qBittorrent 剪贴板监控与自动分类下载器

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

自动监控剪贴板，智能识别磁力链接并使用 AI 自动分类添加到 qBittorrent。

## 核心功能

- **剪贴板监控** - 自动检测系统剪贴板中的磁力链接
- **AI 智能分类** - 使用 DeepSeek AI 自动识别内容类型（电影、电视剧、动漫等）
- **Ruflo AI 编排** - 可选集成 Ruflo 实现多 Agent 协作和自学习优化
- **多协议支持** - 支持 Magnet、Thunder、QQ旋风、FlashGet 等协议
- **Web 管理界面** - 提供 Web UI 进行管理和监控
- **健康检查** - 内置健康检查端点和 Prometheus 监控指标

## 快速开始

### 环境要求

- Python 3.9+
- qBittorrent 4.0+
- Node.js 18+ (可选，用于 Ruflo AI 集成)
- Poetry（推荐）

### 安装

```bash
# 克隆项目
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 安装依赖
poetry install

# 配置环境
cp qbittorrent_monitor/config.json.example qbittorrent_monitor/config.json
# 编辑 config.json 配置 qBittorrent 和 AI 相关参数
```

### 启动

```bash
# 使用启动脚本
./run.sh  # Linux/macOS
run.bat   # Windows

# 或直接运行
poetry run python run.py --web
```

### Docker 部署

```bash
docker-compose up -d
```

---

## 🤖 Ruflo AI 集成 (可选)

本项目支持集成 [Ruflo](https://github.com/ruvnet/ Ruflo) 实现更强大的 AI 功能。

### 什么是 Ruflo?

Ruflo 是一个企业级 AI Agent 编排框架，可以:
- 部署 60+ 专业 Agent 协同工作
- 使用 Swarm 模式批量处理任务
- 自学习优化，持续改进分类准确率

### 安装 Ruflo

```bash
# 方法 1: 一键安装 (推荐)
curl -fsSL https://cdn.jsdelivr.net/gh/ruvnet/claude-flow@main/scripts/install.sh | bash

# 方法 2: 使用 npm
npm install -g claude-flow

# 方法 3: 使用 npx
npx ruflo@latest init --wizard
```

### 启用 Ruflo

编辑 `qbittorrent_monitor/config.json`，设置:

```json
{
  "ruflo": {
    "enabled": true,
    "ruflo_path": "npx ruflo@latest",
    "default_agent": "classifier",
    "swarm_topology": "mesh",
    "max_agents": 5,
    "learning_enabled": true,
    "feedback_storage_path": ".ruflo_feedback"
  }
}
```

### Ruflo 功能说明

#### 1. 增强型分类
Ruflo 使用多 Agent 协作进行更准确的内容分析:
```
torrent_name → [Agent: 关键词提取] → [Agent: 类型分析] → [Agent: 分类决策] → 结果
```

#### 2. Swarm 批量处理
并行处理多个下载任务，适合批量 URL 场景:
```python
# 批量分类
results = await classifier.classify_batch(torrent_names, categories)
```

#### 3. 自学习优化
当您手动调整分类时，系统会自动学习:
```python
# 记录纠正
classifier.record_correction(torrent_name, predicted_category, actual_category)

# 查看学习统计
stats = classifier.get_learning_stats()
# 返回: {'total_feedback': 10, 'learned_patterns': 8, 'accuracy_percent': 85.0}
```

### Ruflo 配置选项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `enabled` | false | 是否启用 Ruflo |
| `ruflo_path` | npx ruflo@latest | Ruflo 路径 |
| `default_agent` | classifier | 默认 Agent 名称 |
| `swarm_topology` | mesh | Swarm 拓扑 (mesh/hierarchical/ring/star) |
| `max_agents` | 5 | 最大 Agent 数量 |
| `timeout` | 30 | Agent 执行超时(秒) |
| `learning_enabled` | true | 是否启用自学习 |
| `cache_ttl_hours` | 24 | 缓存有效期(小时) |

---

## 配置说明

主要配置项在 `qbittorrent_monitor/config.json` 文件中：

### qBittorrent 连接

```json
{
  "qbittorrent": {
    "host": "localhost",
    "port": 8080,
    "username": "admin",
    "password": "adminadmin",
    "use_https": false,
    "verify_ssl": true
  }
}
```

### AI 分类配置

```json
{
  "deepseek": {
    "api_key": "your_deepseek_api_key",
    "model": "deepseek-chat",
    "base_url": "https://api.deepseek.com",
    "timeout": 10
  }
}
```

### 分类设置

```json
{
  "categories": {
    "movies": {
      "savePath": "/downloads/movies/",
      "keywords": ["电影", "Movie", "1080p", "4K", "BluRay"],
      "priority": 10
    },
    "tv": {
      "savePath": "/downloads/tv/",
      "keywords": ["S01", "电视剧", "Series", "Episode"],
      "priority": 8
    },
    "anime": {
      "savePath": "/downloads/anime/",
      "keywords": ["动画", "Anime"],
      "priority": 6
    }
  }
}
```

完整配置参考 [部署指南](docs/DEPLOYMENT_GUIDE.md)。

---

## Web 界面

启动后访问以下地址：

- **管理面板**: http://localhost:8000
- **健康检查**: http://localhost:8090/health
- **监控指标**: http://localhost:8091/metrics

---

## 项目结构

```
qbittorrent_monitor/
├── __init__.py              # 模块入口
├── config.py                 # 配置管理
├── clipboard_monitor.py     # 剪贴板监控
├── clipboard_actions.py     # 动作执行
├── clipboard_poller.py      # 剪贴板轮询
├── clipboard_processor.py   # 内容处理器
├── qbittorrent_client.py    # qBittorrent 客户端
├── ai_classifier.py        # AI 分类器
├── ruflo_classifier.py      # Ruflo AI 集成 ⭐
├── web_crawler.py           # 网页爬虫
├── notifications.py         # 通知系统
├── health_check.py          # 健康检查
├── monitoring.py            # 监控模块
├── workflow_engine.py       # 工作流引擎
├── resilience.py            # 弹性组件
├── retry.py                 # 重试机制
├── circuit_breaker.py       # 断路器
├── exceptions.py            # 异常定义
├── utils.py                 # 工具函数
│
├── qbt/                     # qBittorrent 子包
│   ├── qbittorrent_client.py
│   ├── api_client.py
│   ├── connection_pool.py
│   └── ...
│
├── web_crawler/             # 网页爬虫子包
│   ├── core.py
│   ├── adapters.py
│   └── ...
│
└── web_interface/           # Web 管理界面
    ├── app.py
    ├── static/
    └── templates/
```

---

## 文档

- [安装指南](docs/guides/INSTALL.md)
- [启动指南](docs/guides/STARTUP_GUIDE.md)
- [部署指南](docs/DEPLOYMENT_GUIDE.md)
- [故障排除](docs/TROUBLESHOOTING.md)
- [Ruflo 集成文档](RUFLO_INTEGRATION.md)

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。

---

## 贡献

欢迎提交 Issue 和 Pull Request！

---

⭐ 如果这个项目对您有帮助，请给个 Star 支持一下！
