# qBittorrent Clipboard Monitor v3.0

简洁高效的磁力链接剪贴板监控工具，自动检测剪贴板内容并添加到 qBittorrent。

## 特性

- **极简设计** - 核心代码仅 1000+ 行，易于理解和维护
- **智能分类** - 支持规则匹配和 AI 自动分类
- **异步高性能** - 基于 asyncio 和 aiohttp
- **开箱即用** - 合理的默认配置，无需复杂设置

## 安装

```bash
# 克隆仓库
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 安装依赖
pip install -e .
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
    "enabled": true,
    "api_key": "your-api-key",
    "model": "deepseek-chat"
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

支持的环境变量：

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

### 本地运行

```bash
# 基础使用
python run.py

# 指定配置文件
python run.py --config /path/to/config.json

# 调整检查间隔
python run.py --interval 0.5

# 设置日志级别
python run.py --log-level DEBUG
```

### Docker 运行

#### Docker 基础用法

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
  -e AI_ENABLED=true \
  -e AI_API_KEY=your-api-key \
  qb-monitor
```

#### Docker Compose（推荐）

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

1. 监控系统剪贴板
2. 检测到磁力链接时自动提取
3. 根据文件名智能分类
4. 添加到 qBittorrent 对应分类

## 项目对比

| 指标 | v2.5 (原版) | v3.0 (优化版) | 改进 |
|------|------------|---------------|------|
| 代码行数 | 22,883 | ~800 | -96% |
| 文件数 | 56 | 8 | -86% |
| 依赖数 | 30+ | 4 | -87% |
| 启动时间 | 慢 | 快 | 显著提升 |
| 可维护性 | 低 | 高 | 显著提升 |
| 日志安全 | 无过滤 | 敏感信息自动过滤 | 更安全 |
| 配置方式 | 仅配置文件 | 文件 + 环境变量 | 更灵活 |

## 技术栈

- Python 3.9+
- aiohttp - 异步 HTTP 客户端
- openai - AI 分类支持
- pyperclip - 剪贴板访问

## 测试

```bash
pytest tests/ -v --cov=qbittorrent_monitor
```

## License

MIT
