# 结构化日志系统使用文档

## 概述

qbittorrent-clipboard-monitor 现在提供完整的结构化日志系统，支持多种输出格式、文件轮转和敏感信息过滤。

## 特性

- **多种日志格式**: 文本、JSON、详细格式
- **彩色控制台输出**: 按日志级别自动着色
- **文件轮转**: 按大小（10MB）和时间（7天）自动轮转
- **多目标输出**: 支持不同级别输出到不同文件
- **敏感信息过滤**: 自动过滤密码、API密钥等敏感信息
- **上下文绑定**: 支持结构化日志记录

## 配置

### 配置文件 (config.json)

```json
{
  "log_level": "INFO",
  "logging": {
    "level": "INFO",
    "format": "text",
    "console_enabled": true,
    "console_color": true,
    "file_enabled": true,
    "file_path": "logs/qb-monitor.log",
    "file_max_bytes": 10485760,
    "file_backup_count": 5,
    "file_max_age_days": 7,
    "separate_levels": false,
    "debug_separate": false
  }
}
```

### 配置项说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `level` | string | INFO | 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `format` | string | text | 日志格式 (text/json/detailed) |
| `console_enabled` | bool | true | 是否输出到控制台 |
| `console_color` | bool | true | 是否启用彩色输出 |
| `file_enabled` | bool | true | 是否输出到文件 |
| `file_path` | string | logs/qb-monitor.log | 日志文件路径 |
| `file_max_bytes` | int | 10485760 | 单个文件最大大小（字节） |
| `file_backup_count` | int | 5 | 保留的备份文件数量 |
| `file_max_age_days` | int | 7 | 日志文件最大保留天数 |
| `separate_levels` | bool | false | 是否将错误日志单独存放 |
| `debug_separate` | bool | false | 是否将调试日志单独存放 |

## 命令行参数

```bash
# 基本使用
python run.py

# 指定配置文件
python run.py --config ~/.qb-monitor.json

# 设置日志级别
python run.py --log-level DEBUG

# JSON格式输出
python run.py --log-format json

# 禁用彩色输出
python run.py --no-color
```

## 代码中使用

### 基础用法

```python
from qbittorrent_monitor.logger import get_logger

logger = get_logger(__name__)

logger.info("服务启动")
logger.warning("检测到重复请求")
logger.error("连接失败", extra={"host": "localhost", "port": 8080})
```

### 带上下文的日志

```python
# 绑定上下文
request_logger = logger.bind(request_id="req-12345", user="admin")
request_logger.info("处理请求")

# 输出: {"message": "处理请求", "request_id": "req-12345", "user": "admin"}
```

### 异常日志

```python
try:
    process_magnet(link)
except Exception:
    logger.exception("处理磁力链接失败")
```

## 日志格式示例

### 文本格式

```
2026-03-08 12:34:56 - qb-monitor - INFO - 服务启动成功
2026-03-08 12:34:57 - qb-monitor - WARNING - 检测到重复磁力链接
```

### JSON 格式

```json
{
  "timestamp": "2026-03-08T12:34:56.123456Z",
  "level": "INFO",
  "logger": "qb-monitor",
  "message": "服务启动成功",
  "source": {
    "file": "/path/to/file.py",
    "line": 42,
    "function": "main"
  },
  "host": "server-01",
  "project": "qb-monitor"
}
```

### 详细格式

```
2026-03-08 12:34:56.123456 [INFO] qb-monitor
  File: /path/to/file.py:42 (in main)
  Message: 服务启动成功
```

## 敏感信息过滤

日志系统自动过滤以下敏感信息：

- API 密钥: `api_key=***`
- 密码: `password=***`
- 令牌: `token=***`
- 数据库连接字符串中的密码
- 磁力链接 hash 的部分内容

## 文件轮转

日志文件自动轮转规则：

1. **按大小轮转**: 当文件达到 10MB 时自动创建新文件
2. **按时间清理**: 超过 7 天的日志文件自动删除
3. **备份保留**: 默认保留 5 个备份文件

轮转后的文件名示例：
- `qb-monitor.log` (当前)
- `qb-monitor.log.1` (上一个)
- `qb-monitor.log.2` (更早的)

## 与旧版兼容

旧版代码使用方式仍然兼容：

```python
import logging
from qbittorrent_monitor.logging_filters import setup_sensitive_logging

# 旧方式（仍然可用）
setup_sensitive_logging("INFO")
logger = logging.getLogger(__name__)
```

推荐使用新方式：

```python
from qbittorrent_monitor.logger import get_logger

logger = get_logger(__name__)
```
