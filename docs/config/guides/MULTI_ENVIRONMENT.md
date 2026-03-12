# 多环境配置指南

> **文档版本**: v2.5.0  
> **更新日期**: 2026-03-12

本文档介绍如何在不同环境（开发、测试、生产、Docker）中配置 qBittorrent剪贴板监控器。

---

## 目录

- [环境概述](#环境概述)
- [开发环境](#开发环境)
- [测试环境](#测试环境)
- [生产环境](#生产环境)
- [Docker环境](#docker环境)
- [环境切换](#环境切换)
- [配置继承](#配置继承)
- [最佳实践](#最佳实践)

---

## 环境概述

| 环境 | 用途 | 主要特点 |
|------|------|----------|
| **开发** | 本地开发调试 | 详细日志、热加载、调试功能开启 |
| **测试** | 自动化测试 | 禁用外部服务、快速执行、隔离性 |
| **预发布** | 发布前验证 | 接近生产配置、测试数据 |
| **生产** | 正式运行 | 性能优化、安全检查、监控告警 |
| **Docker** | 容器化部署 | 环境变量优先、持久化卷 |

---

## 开发环境

### 特点

- ✅ 配置热加载 (`hot_reload: true`)
- ✅ 详细日志 (`log_level: DEBUG`)
- ✅ 快速重试 (`max_retries: 1`)
- ✅ 本地qBittorrent连接
- ❌ 通知关闭（避免干扰）

### 配置文件: `config.development.json`

```json
{
    "qbittorrent": {
        "host": "localhost",
        "port": 8080,
        "username": "admin",
        "password": "adminadmin",
        "use_https": false,
        "verify_ssl": false,
        "use_nas_paths_directly": false,
        "path_mapping": []
    },
    "deepseek": {
        "api_key": "${DEEPSEEK_API_KEY}",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        "timeout": 30,
        "max_retries": 1,
        "retry_delay": 1.0,
        "few_shot_examples": [
            {
                "torrent_name": "Game.of.Thrones.S08E06.1080p.WEB.H264-MEMENTO",
                "category": "tv"
            },
            {
                "torrent_name": "Avengers.Endgame.2019.1080p.BluRay.x264-SPARKS",
                "category": "movies"
            }
        ]
    },
    "categories": {
        "movies": {
            "savePath": "/downloads/movies/",
            "keywords": ["电影", "Movie", "1080p", "4K"],
            "description": "电影作品",
            "priority": 8
        },
        "tv": {
            "savePath": "/downloads/tv/",
            "keywords": ["S01", "S02", "剧集", "电视剧"],
            "description": "电视剧、连续剧",
            "priority": 10
        },
        "anime": {
            "savePath": "/downloads/anime/",
            "keywords": ["动画", "动漫", "Anime"],
            "description": "日本动画、动漫",
            "priority": 12
        },
        "music": {
            "savePath": "/downloads/music/",
            "keywords": ["音乐", "Music", "FLAC"],
            "description": "音乐专辑、单曲",
            "priority": 6
        },
        "games": {
            "savePath": "/downloads/games/",
            "keywords": ["游戏", "Game", "ISO"],
            "description": "电子游戏",
            "priority": 7
        },
        "software": {
            "savePath": "/downloads/software/",
            "keywords": ["软件", "Software", "App"],
            "description": "应用程序、软件",
            "priority": 5
        },
        "adult": {
            "savePath": "/downloads/adult/",
            "keywords": ["成人", "18+", "xxx"],
            "description": "成人内容",
            "priority": 15
        },
        "other": {
            "savePath": "/downloads/other/",
            "keywords": [],
            "description": "其他内容",
            "priority": 1
        }
    },
    "web_crawler": {
        "enabled": true,
        "page_timeout": 30000,
        "wait_for": 2,
        "max_retries": 1,
        "max_concurrent_extractions": 1,
        "inter_request_delay": 2.0,
        "ai_classify_torrents": true,
        "add_torrents_paused": false
    },
    "notifications": {
        "enabled": false,
        "console": {
            "enabled": true,
            "colored": true,
            "show_details": true,
            "show_statistics": true
        },
        "services": []
    },
    "check_interval": 1.0,
    "max_retries": 1,
    "retry_delay": 2.0,
    "hot_reload": true,
    "log_level": "DEBUG",
    "log_file": "logs/development.log",
    "add_torrents_paused": false,
    "ai_classify_torrents": true
}
```

### 环境变量: `.env.development`

```bash
# qBittorrent连接
QBT_HOST=localhost
QBT_PORT=8080
QBT_USERNAME=admin
QBT_PASSWORD=adminadmin

# AI配置（从环境变量读取）
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}

# 日志配置
LOG_LEVEL=DEBUG
LOG_FILE=logs/development.log

# 监控配置
CHECK_INTERVAL=1.0
HOT_RELOAD=true

# 禁用通知（开发环境）
NOTIFICATIONS_ENABLED=false

# 爬虫配置
CRAWLER_ENABLED=true
CRAWLER_PAGE_TIMEOUT=30000
CRAWLER_MAX_CONCURRENT=1
```

### 启动命令

```bash
# 使用开发配置
python run.py --config config.development.json --env-file .env.development

# 或使用环境变量
export CONFIG_ENV=development
python run.py
```

---

## 测试环境

### 特点

- ✅ 快速执行 (`check_interval: 0.1`)
- ✅ 禁用外部服务（爬虫、通知）
- ✅ 最少日志 (`log_level: WARNING`)
- ✅ 关闭热加载
- ✅ 使用Mock数据

### 配置文件: `config.testing.json`

```json
{
    "qbittorrent": {
        "host": "mock-qbittorrent",
        "port": 8080,
        "username": "test",
        "password": "test",
        "use_https": false,
        "verify_ssl": false
    },
    "deepseek": {
        "api_key": "test-key",
        "model": "deepseek-chat",
        "base_url": "https://mock-api.deepseek.com",
        "timeout": 5,
        "max_retries": 0,
        "retry_delay": 0.1
    },
    "categories": {
        "movies": {
            "savePath": "/tmp/downloads/movies/",
            "keywords": ["Movie"],
            "description": "测试-电影",
            "priority": 8
        },
        "tv": {
            "savePath": "/tmp/downloads/tv/",
            "keywords": ["TV"],
            "description": "测试-电视剧",
            "priority": 10
        },
        "other": {
            "savePath": "/tmp/downloads/other/",
            "keywords": [],
            "description": "测试-其他",
            "priority": 1
        }
    },
    "web_crawler": {
        "enabled": false
    },
    "notifications": {
        "enabled": false
    },
    "check_interval": 0.1,
    "max_retries": 0,
    "retry_delay": 0.1,
    "hot_reload": false,
    "log_level": "WARNING",
    "log_file": null,
    "add_torrents_paused": true,
    "ai_classify_torrents": false
}
```

### 环境变量: `.env.testing`

```bash
# 测试模式
TESTING=true

# 禁用所有外部服务
CRAWLER_ENABLED=false
NOTIFICATIONS_ENABLED=false

# 最小日志
LOG_LEVEL=WARNING
LOG_FILE=

# 快速检查
CHECK_INTERVAL=0.1
HOT_RELOAD=false
```

### 测试执行

```bash
# 运行测试
pytest tests/ --config config.testing.json

# 使用测试环境变量
export CONFIG_ENV=testing
pytest tests/
```

---

## 生产环境

### 特点

- ✅ 性能优化
- ✅ 安全检查（HTTPS、SSL验证）
- ✅ 通知开启
- ✅ 关闭热加载
- ✅ 详细监控

### 配置文件: `config.production.json`

```json
{
    "qbittorrent": {
        "host": "192.168.1.40",
        "port": 8989,
        "username": "admin",
        "password": "${QBT_PASSWORD}",
        "use_https": true,
        "verify_ssl": true,
        "use_nas_paths_directly": true,
        "path_mapping": [
            {
                "source_prefix": "/downloads",
                "target_prefix": "/vol1/downloads",
                "description": "本地到NAS的路径映射"
            }
        ]
    },
    "deepseek": {
        "api_key": "${DEEPSEEK_API_KEY}",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 1.0
    },
    "categories": {
        "movies": {
            "savePath": "/vol1/downloads/movies/",
            "keywords": ["电影", "Movie", "1080p", "4K", "BluRay", "Remux", "WEB-DL"],
            "description": "电影作品",
            "priority": 8,
            "rules": [
                {
                    "type": "regex",
                    "pattern": "\\.(19|20)\\d{2}\\.",
                    "score": 4
                }
            ]
        },
        "tv": {
            "savePath": "/vol1/downloads/tv/",
            "keywords": ["S01", "S02", "剧集", "电视剧", "Series", "Episode"],
            "description": "电视剧、连续剧",
            "priority": 10,
            "rules": [
                {
                    "type": "regex",
                    "pattern": "S\\d+E\\d+",
                    "score": 5
                }
            ]
        },
        "anime": {
            "savePath": "/vol1/downloads/anime/",
            "keywords": ["动画", "动漫", "Anime", "Fansub"],
            "description": "日本动画、动漫",
            "priority": 12
        },
        "music": {
            "savePath": "/vol1/downloads/music/",
            "keywords": ["音乐", "专辑", "Music", "Album", "FLAC", "MP3"],
            "description": "音乐专辑、单曲",
            "priority": 6
        },
        "games": {
            "savePath": "/vol1/downloads/games/",
            "keywords": ["游戏", "Game", "ISO", "PC", "PS5", "Switch"],
            "description": "电子游戏",
            "priority": 7
        },
        "software": {
            "savePath": "/vol1/downloads/software/",
            "keywords": ["软件", "Software", "App"],
            "description": "应用程序、软件",
            "priority": 5
        },
        "adult": {
            "savePath": "/vol1/downloads/adult/",
            "keywords": ["成人", "18+", "xxx", "Porn"],
            "description": "成人内容",
            "priority": 15
        },
        "other": {
            "savePath": "/vol1/downloads/other/",
            "keywords": [],
            "description": "其他内容",
            "priority": 1
        }
    },
    "web_crawler": {
        "enabled": true,
        "page_timeout": 60000,
        "wait_for": 3,
        "delay_before_return": 2,
        "max_retries": 3,
        "base_delay": 5,
        "max_delay": 60,
        "max_concurrent_extractions": 3,
        "inter_request_delay": 1.5,
        "ai_classify_torrents": true,
        "add_torrents_paused": false
    },
    "notifications": {
        "enabled": true,
        "console": {
            "enabled": true,
            "colored": false,
            "show_details": true,
            "show_statistics": true
        },
        "services": ["telegram"],
        "api_token": "${TELEGRAM_BOT_TOKEN}",
        "chat_id": "${TELEGRAM_CHAT_ID}"
    },
    "check_interval": 2.0,
    "max_retries": 3,
    "retry_delay": 5.0,
    "hot_reload": false,
    "log_level": "INFO",
    "log_file": "/var/log/qbittorrent-monitor/app.log",
    "add_torrents_paused": false,
    "ai_classify_torrents": true
}
```

### 环境变量: `.env.production` (不提交到版本控制)

```bash
# qBittorrent连接
QBT_HOST=192.168.1.40
QBT_PORT=8989
QBT_USERNAME=admin
QBT_PASSWORD=your_secure_password
QBT_USE_HTTPS=true
QBT_VERIFY_SSL=true

# AI配置
DEEPSEEK_API_KEY=sk-your-secure-api-key

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=/var/log/qbittorrent-monitor/app.log

# 监控配置
CHECK_INTERVAL=2.0
HOT_RELOAD=false

# 通知配置
NOTIFICATIONS_ENABLED=true
NOTIFICATION_SERVICES=["telegram"]
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789

# 爬虫配置
CRAWLER_ENABLED=true
CRAWLER_MAX_CONCURRENT=3
```

### 部署命令

```bash
# 使用生产配置启动
python run.py --config config.production.json --env-file .env.production

# 使用 systemd 服务
sudo systemctl start qbittorrent-monitor

# 使用 Docker
export CONFIG_ENV=production
docker-compose -f docker-compose.prod.yml up -d
```

---

## Docker环境

### Docker Compose配置

#### 开发环境: `docker-compose.yml`

```yaml
version: '3.8'

services:
  qbittorrent-monitor:
    build:
      context: .
      dockerfile: Dockerfile.dev
    container_name: qbittorrent-monitor-dev
    environment:
      - CONFIG_ENV=development
      - QBT_HOST=host.docker.internal
      - QBT_PORT=8080
      - QBT_USERNAME=admin
      - QBT_PASSWORD=adminadmin
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - LOG_LEVEL=DEBUG
      - HOT_RELOAD=true
    volumes:
      - ./qbittorrent_monitor:/app/qbittorrent_monitor
      - ./logs:/app/logs
      - ./config.development.json:/app/config.json:ro
    ports:
      - "8081:8081"
    command: python run.py --config /app/config.json
    restart: "no"
```

#### 生产环境: `docker-compose.prod.yml`

```yaml
version: '3.8'

services:
  qbittorrent-monitor:
    image: qbittorrent-monitor:latest
    container_name: qbittorrent-monitor
    environment:
      - CONFIG_ENV=production
      - QBT_HOST=${QBT_HOST}
      - QBT_PORT=${QBT_PORT}
      - QBT_USERNAME=${QBT_USERNAME}
      - QBT_PASSWORD=${QBT_PASSWORD}
      - QBT_USE_HTTPS=true
      - QBT_VERIFY_SSL=true
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - LOG_LEVEL=INFO
      - HOT_RELOAD=false
      - NOTIFICATIONS_ENABLED=true
      - NOTIFICATION_SERVICES=["telegram"]
      - NOTIFICATION_API_TOKEN=${TELEGRAM_BOT_TOKEN}
      - NOTIFICATION_CHAT_ID=${TELEGRAM_CHAT_ID}
    volumes:
      - ./config.production.json:/app/config.json:ro
      - ./logs:/app/logs
      - /etc/localtime:/etc/localtime:ro
    ports:
      - "8081:8081"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Dockerfile示例

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY qbittorrent_monitor/ ./qbittorrent_monitor/
COPY run.py .

# 创建日志目录
RUN mkdir -p /app/logs

# 非root用户运行
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8081

CMD ["python", "run.py"]
```

---

## 环境切换

### 使用环境变量切换

```bash
# 开发环境
export CONFIG_ENV=development
python run.py

# 测试环境
export CONFIG_ENV=testing
pytest tests/

# 生产环境
export CONFIG_ENV=production
python run.py
```

### 使用命令行参数

```bash
# 指定配置文件
python run.py --config config.development.json
python run.py --config config.production.json

# 指定环境变量文件
python run.py --env-file .env.production
```

### 使用脚本切换

```bash
#!/bin/bash
# scripts/switch_env.sh

ENV=${1:-development}

if [ ! -f ".env.${ENV}" ]; then
    echo "Error: .env.${ENV} not found"
    exit 1
fi

if [ ! -f "config.${ENV}.json" ]; then
    echo "Error: config.${ENV}.json not found"
    exit 1
fi

# 备份当前配置
cp .env .env.backup 2>/dev/null || true
cp config.json config.json.backup 2>/dev/null || true

# 切换配置
cp ".env.${ENV}" .env
cp "config.${ENV}.json" config.json

echo "Switched to ${ENV} environment"
echo "To restore: cp .env.backup .env && cp config.json.backup config.json"
```

---

## 配置继承

### 基础配置 + 环境特定配置

```python
# config_loader.py
import json
import os
from pathlib import Path

def load_config(env=None):
    """加载配置，支持继承"""
    if env is None:
        env = os.getenv('CONFIG_ENV', 'development')
    
    # 加载基础配置
    base_config = {}
    base_path = Path('config.base.json')
    if base_path.exists():
        with open(base_path) as f:
            base_config = json.load(f)
    
    # 加载环境特定配置
    env_path = Path(f'config.{env}.json')
    if env_path.exists():
        with open(env_path) as f:
            env_config = json.load(f)
        # 深度合并
        base_config = deep_merge(base_config, env_config)
    
    return base_config

def deep_merge(base, override):
    """深度合并字典"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
```

---

## 最佳实践

### 1. 敏感信息管理

```bash
# ❌ 不要这样做
# config.production.json
{
  "qbittorrent": {
    "password": "my_real_password"  # 不安全！
  }
}

# ✅ 使用环境变量占位符
# config.production.json
{
  "qbittorrent": {
    "password": "${QBT_PASSWORD}"  # 从环境变量读取
  }
}

# .env.production (添加到 .gitignore)
QBT_PASSWORD=my_real_password
```

### 2. 版本控制策略

```gitignore
# .gitignore
# 忽略包含敏感信息的配置文件
.env.production
.env.staging
config.*.local.json

# 允许提交模板
!config.development.json
!config.example.json
!config.base.json
```

### 3. 配置验证

```bash
# 在切换环境前验证配置
python scripts/config/validate_config.py --config config.production.json

# CI/CD中验证
- name: Validate Config
  run: |
    python scripts/config/validate_config.py \
      --config config.${{ matrix.environment }}.json \
      --schema docs/config/schema/config.schema.json
```

### 4. 配置文档化

每个环境配置文件应包含注释说明：

```json
{
  "_comment": "生产环境配置 - 使用HTTPS、启用通知、关闭热加载",
  "qbittorrent": {
    "_comment": "使用NAS内网地址，启用SSL验证",
    "host": "192.168.1.40"
  }
}
```

---

## 相关文档

- [配置参考手册](../CONFIGURATION_REFERENCE.md)
- [环境变量说明](../ENVIRONMENT_VARIABLES.md)
- [部署指南](../../DEPLOYMENT_GUIDE.md)
