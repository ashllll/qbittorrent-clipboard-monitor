# qBittorrent Clipboard Monitor

简洁高效的磁力链接剪贴板监控工具，自动识别并添加到 qBittorrent，支持 AI 智能分类。

## 功能特性

- 🔍 **剪贴板监控** - 自动检测磁力链接
- 🤖 **AI 分类** - 使用 DeepSeek/OpenAI 自动识别内容类型
- 📂 **自动分类** - 电影/电视剧/动画/音乐等自动分类
- ⚡ **轻量高效** - 精简代码，快速启动
- 🔧 **易于配置** - 简洁的 JSON 配置

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 安装依赖
pip install -e .
# 或使用 Poetry
poetry install
```

### 配置

首次运行会自动创建默认配置文件：

```bash
python run.py
```

配置文件位置：`~/.config/qb-monitor/config.json`

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
      "keywords": ["Movie", "1080p", "4K"]
    },
    "tv": {
      "save_path": "/downloads/tv",
      "keywords": ["S01", "Series"]
    }
  },
  "check_interval": 1.0
}
```

### 启动

```bash
# 基础模式
python run.py

# 自定义配置
python run.py --config /path/to/config.json

# 更快检查间隔
python run.py --interval 0.5

# 调试模式
python run.py --log-level DEBUG
```

## 使用方法

1. 启动程序
2. 复制任意包含磁力链接的文本
3. 程序自动检测、分类并添加到 qBittorrent

示例输出：
```
==================================================
qBittorrent剪贴板监控与自动分类下载工具
版本: 3.0.0
==================================================
2024-01-15 10:30:00 - INFO - qBittorrent连接成功 (版本: 4.6.0)
2024-01-15 10:30:00 - INFO - 剪贴板监控已启动
2024-01-15 10:30:00 - INFO - 检查间隔: 1.0秒
2024-01-15 10:30:00 - INFO - 按 Ctrl+C 停止
2024-01-15 10:35:23 - INFO - 发现 1 个磁力链接
2024-01-15 10:35:23 - INFO - 分类结果: The.Matrix.1999... -> movies
2024-01-15 10:35:24 - INFO - ✓ 已添加到 [movies]
```

## 分类规则

### 规则分类（优先）

根据关键词自动匹配：

| 分类 | 关键词示例 |
|------|-----------|
| movies | Movie, 1080p, 4K, BluRay |
| tv | S01, E01, Series, Season |
| anime | 动画, Anime, [GM-Team] |
| music | Music, FLAC, MP3, Album |
| software | Software, Portable |

### AI 分类（备用）

当规则无法匹配时，使用 AI 分析内容并选择最合适的分类。

## 命令行参数

```
python run.py --help

选项:
  -c, --config PATH       配置文件路径
  -i, --interval FLOAT    检查间隔（秒）
  -l, --log-level TEXT    日志级别 (DEBUG/INFO/WARNING/ERROR)
  -v, --version          显示版本
```

## 开发

### 运行测试

```bash
pytest

# 带覆盖率
pytest --cov=qbittorrent_monitor --cov-report=html
```

### 代码格式化

```bash
black qbittorrent_monitor/
mypy qbittorrent_monitor/
```

## 项目结构

```
qbittorrent_monitor/
├── __init__.py          # 包入口
├── __version__.py       # 版本信息
├── config.py           # 配置管理（~150行）
├── exceptions.py       # 异常定义（~50行）
├── qb_client.py        # qBittorrent客户端（~150行）
├── classifier.py       # AI分类器（~120行）
├── monitor.py          # 剪贴板监控（~180行）
└── utils.py            # 工具函数（~30行）

tests/                   # 测试文件
run.py                   # 启动脚本
pyproject.toml          # 项目配置
```

## 技术栈

- Python 3.9+
- aiohttp - 异步 HTTP 客户端
- openai - AI API 调用
- pyperclip - 剪贴板访问

## 版本历史

### v3.0.0 (2024-03)
- ✨ 完全重构，精简代码 60%+
- ✨ 简化配置系统
- ✨ 完善单元测试
- 🗑️ 移除过度工程化组件

### v2.5.0 (原版本)
- 包含大量未使用的复杂功能
- 代码量 ~22,000 行

## License

MIT License
