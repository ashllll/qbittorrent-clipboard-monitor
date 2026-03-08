# qBittorrent Clipboard Monitor v3.0

简洁高效的磁力链接剪贴板监控工具，自动检测剪贴板内容并添加到 qBittorrent。

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](https://www.docker.com/)

## 特性

- **⚡ 极简设计** - 核心代码仅 1000+ 行，易于理解和维护
- **🤖 智能分类** - 支持规则匹配和 AI 自动分类
- **🚀 异步高性能** - 基于 asyncio 和 aiohttp，性能优异
- **📦 开箱即用** - 合理的默认配置，无需复杂设置
- **🔄 智能轮询** - 自动调整检查频率，空闲时降低资源占用
- **💾 智能缓存** - 多重缓存机制避免重复处理
- **🔒 安全日志** - 自动过滤敏感信息，防止泄露
- **🌐 Web 管理** - 基于 FastAPI 的美观 Web 管理界面
- **🐳 Docker 支持** - 一键部署，支持 Docker Compose

## 快速开始

### Docker 部署（推荐）

> ⚠️ **Docker 使用限制**
> Docker 容器默认无法访问宿主机剪贴板，剪贴板监控功能在标准 Docker 模式下**不可用**。
> 如需使用剪贴板功能，请在宿主机直接运行或使用特殊网络模式（不推荐）。
> Web 管理界面在 Docker 中可正常使用。

```bash
# 克隆仓库
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入 qBittorrent 信息

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 本地安装

```bash
# 克隆仓库
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 安装依赖
pip install -e .

# 运行
python run.py
```

## 配置

### 配置文件

配置文件位于 `~/.config/qb-monitor/config.json`，首次运行会自动创建。

```json
{
  "qbittorrent": {
    "host": "localhost",
    "port": 8080,
    "username": "admin",
    "password": "adminadmin"
  },
  "ai": {
    "enabled": false,
    "api_key": "your-api-key",
    "model": "deepseek-chat",
    "base_url": "https://api.deepseek.com/v1"
  },
  "categories": {
    "movies": {
      "save_path": "/downloads/movies",
      "keywords": ["电影", "Movie", "1080p", "4K"]
    },
    "tv": {
      "save_path": "/downloads/tv",
      "keywords": ["S01", "电视剧", "Series"]
    }
  },
  "check_interval": 1.0
}
```

### 环境变量

支持通过环境变量配置，优先级高于配置文件：

```bash
# 复制模板
cp .env.example .env

# 编辑 .env 文件，填入实际配置
```

**支持的环境变量：**

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `QBIT_HOST` | qBittorrent 主机地址 | localhost |
| `QBIT_PORT` | qBittorrent 端口 | 8080 |
| `QBIT_USERNAME` | qBittorrent 用户名 | admin |
| `QBIT_PASSWORD` | qBittorrent 密码 | - |
| `QBIT_USE_HTTPS` | 使用 HTTPS | false |
| `AI_ENABLED` | 启用 AI 分类 | false |
| `AI_API_KEY` | AI API 密钥 | - |
| `AI_MODEL` | AI 模型 | deepseek-chat |
| `CHECK_INTERVAL` | 检查间隔（秒） | 1.0 |
| `LOG_LEVEL` | 日志级别 | INFO |

## 使用

### Web 管理界面（推荐）

```bash
# 启动 Web 界面（默认 http://127.0.0.1:8080）
python run.py --web

# 指定 Web 端口
python run.py --web --web-port 8888

# 允许外部访问
python run.py --web --web-host 0.0.0.0

# 完整示例
python run.py --web --web-host 0.0.0.0 --web-port 8080 --config ~/.qb-monitor.json
```

**Web 界面功能：**
- 📊 **仪表盘** - 实时统计、手动添加磁力链接、最近活动
- 📜 **历史记录** - 查看所有已处理的磁力链接，支持搜索和筛选
- 📁 **分类管理** - 可视化管理分类规则和保存路径
- ⚙️ **配置管理** - 在线修改配置，测试 qBittorrent 连接
- 📋 **实时日志** - WebSocket 推送的实时日志流

### 本地运行

```bash
# 基础使用（命令行模式）
python run.py

# 指定配置文件
python run.py --config /path/to/config.json

# 调整检查间隔
python run.py --interval 0.5

# 设置日志级别
python run.py --log-level DEBUG
```

### Docker 运行

```bash
# 构建镜像
docker build -t qb-monitor .

# 运行容器
docker run -d \
  --name qb-monitor \
  -e QBIT_HOST=192.168.1.100 \
  -e QBIT_PORT=8080 \
  -e QBIT_USERNAME=admin \
  -e QBIT_PASSWORD=yourpassword \
  qb-monitor
```

### Docker Compose（推荐）

```bash
# 1. 复制并编辑环境变量
cp .env.example .env
# 编辑 .env 文件，填入实际配置

# 2. 启动服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止服务
docker-compose down
```

## 工作原理

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   剪贴板     │────▶│  磁力提取    │────▶│  智能分类    │────▶│ qBittorrent  │
│   监控       │     │  & 去重      │     │  规则/AI     │     │   添加种子   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

1. **剪贴板监控** - 实时检测剪贴板变化
2. **磁力提取** - 从剪贴板内容提取磁力链接
3. **智能分类** - 根据文件名自动分类（规则 + AI）
4. **自动添加** - 添加到 qBittorrent 并设置分类

## 智能分类系统

### 规则分类

内置丰富的关键词库，自动识别内容类型：

| 分类 | 关键词示例 |
|------|-----------|
| `movies` | 1080p, 4K, BluRay, WEB-DL, 电影 |
| `tv` | S01, E01, Season, 电视剧 |
| `anime` | 动画, Anime, BD, 字幕组 |
| `music` | FLAC, MP3, Album, OST, 音乐 |
| `software` | Software, Portable, Windows |
| `games` | PC, Steam, CODEX, REPACK |
| `books` | PDF, EPUB, Ebook |
| `other` | 默认分类 |

### AI 分类

启用 AI 分类后，当规则分类置信度不足时，会自动调用 AI 进行判断：

```json
{
  "ai": {
    "enabled": true,
    "api_key": "sk-your-api-key",
    "model": "deepseek-chat",
    "base_url": "https://api.deepseek.com/v1",
    "timeout": 30,
    "max_retries": 3
  }
}
```

支持所有 OpenAI 兼容的 API，如 DeepSeek、OpenAI、Azure OpenAI 等。

## 高级功能

### 性能优化

- **智能轮询** - 根据剪贴板活动自动调整检查频率
- **多层缓存** - 内容哈希缓存 + 分类结果缓存
- **防抖处理** - 避免重复添加相同的磁力链接
- **并发控制** - 限制 AI 分类的并发请求数

### 统计信息

```python
from qbittorrent_monitor.monitor import ClipboardMonitor

# 获取统计
stats = monitor.get_stats()
print(f"""
运行统计:
- 运行时间: {stats['uptime_seconds']:.0f} 秒
- 处理数量: {stats['total_processed']}
- 成功添加: {stats['successful_adds']}
- 重复跳过: {stats['duplicates_skipped']}
- 平均耗时: {stats['avg_check_time_ms']:.3f} ms
""")
```

### 自定义回调

```python
def on_magnet_added(magnet: str, category: str):
    print(f"✓ 已添加到 [{category}]")
    # 发送通知、记录日志等

monitor.add_handler(on_magnet_added)
```

## 项目对比

| 指标 | v2.5 (原版) | v3.0 (优化版) | 改进 |
|------|------------|---------------|------|
| 代码行数 | 22,883 | ~1,000 | -96% |
| 文件数 | 56 | 8 | -86% |
| 依赖数 | 30+ | 4 | -87% |
| 启动时间 | 慢 | 快 | 显著提升 |
| 内存占用 | 高 | 低 | 大幅降低 |
| 可维护性 | 低 | 高 | 显著提升 |
| 日志安全 | 无过滤 | 敏感信息自动过滤 | 更安全 |
| 配置方式 | 仅配置文件 | 文件 + 环境变量 | 更灵活 |
| 分类精度 | 仅规则 | 规则 + AI | 更准确 |
| 性能监控 | 无 | 详细统计 | 更完善 |

## 文档

- [API 文档](docs/api.md) - 详细描述所有模块和类
- [部署指南](docs/deployment.md) - Docker、systemd、supervisor 部署
- [开发者文档](docs/development.md) - 开发环境设置、测试、贡献指南

## 技术栈

- Python 3.9+
- [aiohttp](https://docs.aiohttp.org/) - 异步 HTTP 客户端
- [openai](https://github.com/openai/openai-python) - AI 分类支持
- [pyperclip](https://github.com/asweigart/pyperclip) - 剪贴板访问
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- [Tailwind CSS](https://tailwindcss.com/) - 前端样式
- [WebSocket](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket) - 实时数据推送

## 测试

```bash
# 运行测试
pytest tests/ -v

# 运行测试并生成覆盖率报告
pytest tests/ -v --cov=qbittorrent_monitor
```

## 贡献

欢迎提交 Issue 和 Pull Request！

请参阅 [开发者文档](docs/development.md) 了解如何参与开发。

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

**注意**：本项目仅供学习和个人使用，请遵守当地法律法规。
