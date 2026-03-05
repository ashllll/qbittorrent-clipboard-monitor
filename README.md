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

## 使用

```bash
# 基础使用
python run.py

# 指定配置文件
python run.py --config /path/to/config.json

# 调整检查间隔
python run.py --interval 0.5
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
