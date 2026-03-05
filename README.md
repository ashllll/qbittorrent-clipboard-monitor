# qBittorrent Clipboard Monitor v3.0

简洁高效的磁力链接剪贴板监控工具，自动识别并添加到 qBittorrent。

## 特性

- ✂️ **剪贴板监控** - 自动检测磁力链接
- 🤖 **AI 智能分类** - 支持 DeepSeek/OpenAI 自动分类
- 📂 **自动分类** - 电影/剧集/动画/音乐/软件自动归档
- 🚀 **轻量高效** - 代码精简，运行快速
- ⚙️ **简单配置** - JSON 配置，开箱即用

## 快速开始

### 安装

```bash
# 使用 Poetry
poetry install

# 或使用 pip
pip install aiohttp openai pyperclip
```

### 配置

```bash
# 首次运行会自动生成配置文件
python run.py

# 或指定配置路径
python run.py --config ~/.qb-monitor.json
```

配置文件示例 (`~/.config/qb-monitor/config.json`):

```json
{
  "qbittorrent": {
    "host": "localhost",
    "port": 8080,
    "username": "admin",
    "password": "your-password"
  },
  "ai": {
    "enabled": true,
    "api_key": "your-deepseek-api-key",
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

### 使用

```bash
# 基础模式
python run.py

# 自定义检查间隔（秒）
python run.py --interval 0.5

# 调试模式
python run.py --log-level DEBUG
```

## 工作原理

1. **监控剪贴板** - 每秒检查剪贴板内容
2. **识别磁力链接** - 正则匹配 `magnet:?xt=urn:btih:` 格式
3. **智能分类** - 先尝试关键词匹配，如开启 AI 则使用 AI 分类
4. **自动添加** - 调用 qBittorrent Web API 添加种子

## 分类逻辑

1. **关键词匹配** - 根据配置的关键词快速匹配
2. **AI 分类** - 若关键词未匹配且 AI 启用，则使用 AI 分析
3. **默认分类** - 以上都未匹配则归入 "other"

## 测试

```bash
# 运行测试
poetry run pytest

# 带覆盖率
poetry run pytest --cov=qbittorrent_monitor
```

## 项目结构

```
qbittorrent_monitor/
├── __init__.py          # 包入口
├── __version__.py       # 版本信息
├── config.py           # 配置管理 (~120行)
├── exceptions.py       # 异常定义 (~30行)
├── qb_client.py        # qBittorrent客户端 (~150行)
├── classifier.py       # AI分类器 (~100行)
├── monitor.py          # 剪贴板监控 (~150行)
└── utils.py            # 工具函数 (~30行)

run.py                  # 启动脚本 (~100行)
pyproject.toml          # 项目配置
tests/                  # 测试目录
```

**总代码量: ~700行** (原版本 ~22,000行)

## 优化改进

| 方面 | 原版 | 优化版 |
|-----|------|-------|
| 代码行数 | ~22,000 | ~700 |
| 文件数 | 50+ | 8 |
| 启动时间 | 慢 | 快 |
| 配置复杂度 | 高 | 低 |
| 维护难度 | 高 | 低 |
| 测试覆盖 | ~0% | 80%+ |

## License

MIT
