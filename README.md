# qBittorrent 剪贴板监控与自动分类下载器

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

自动监控剪贴板，智能识别磁力链接并使用 AI 自动分类添加到 qBittorrent。

## 核心功能

- **剪贴板监控** - 自动检测系统剪贴板中的磁力链接
- **AI 智能分类** - 使用 DeepSeek AI 自动识别内容类型（电影、电视剧、动漫等）
- **多协议支持** - 支持 Magnet、Thunder、QQ旋风、FlashGet 等协议
- **Web 管理界面** - 提供 Web UI 进行管理和监控
- **健康检查** - 内置健康检查端点和 Prometheus 监控指标

## 快速开始

### 环境要求

- Python 3.9+
- qBittorrent 4.0+
- Poetry（推荐）

### 安装

```bash
# 克隆项目
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 安装依赖
poetry install

# 配置环境
cp .env.example .env
# 编辑 .env 文件配置 qBittorrent 和 AI 相关参数
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

## 配置说明

主要配置项在 `.env` 文件中：

```bash
# qBittorrent 连接
QBT_HOST=localhost
QBT_PORT=8080
QBT_USERNAME=admin
QBT_PASSWORD=adminadmin

# AI 分类（可选）
AI_API_KEY=your_deepseek_api_key
AI_MODEL=deepseek-chat

# 监控设置
MONITOR_CHECK_INTERVAL=1.0
```

完整配置参考 [部署指南](docs/DEPLOYMENT_GUIDE.md)。

## Web 界面

启动后访问以下地址：

- **管理面板**: http://localhost:8000
- **健康检查**: http://localhost:8090/health
- **监控指标**: http://localhost:8091/metrics

## 项目结构

```
qbittorrent_monitor/
├── ai/              # AI 分类模块
├── crawler/         # 网页爬虫模块
├── monitor/         # 监控模块
├── qbt/             # qBittorrent API 客户端
├── web_crawler/     # 网页爬虫
├── web_interface/   # Web 管理界面
├── clipboard_monitor.py    # 剪贴板监控
├── config.py               # 配置管理
├── health_check.py         # 健康检查
└── notifications.py        # 通知系统
```

## 文档

- [安装指南](docs/guides/INSTALL.md)
- [启动指南](docs/guides/STARTUP_GUIDE.md)
- [部署指南](docs/DEPLOYMENT_GUIDE.md)
- [故障排除](docs/TROUBLESHOOTING.md)

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request！

---

⭐ 如果这个项目对您有帮助，请给个 Star 支持一下！
