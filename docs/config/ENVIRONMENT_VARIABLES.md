# 环境变量配置指南

> **文档版本**: v2.5.0  
> **更新日期**: 2026-03-12

本文档详细说明 qBittorrent剪贴板监控器 支持的所有环境变量及其使用方法。

---

## 目录

- [配置优先级](#配置优先级)
- [快速参考](#快速参考)
- [详细说明](#详细说明)
  - [qBittorrent连接](#qbittorrent连接)
  - [AI分类器](#ai分类器)
  - [监控配置](#监控配置)
  - [日志配置](#日志配置)
  - [爬虫配置](#爬虫配置)
  - [性能优化](#性能优化)
  - [Web界面](#web界面)
  - [通知配置](#通知配置)
- [Docker环境](#docker环境)
- [Kubernetes配置](#kubernetes配置)
- [最佳实践](#最佳实践)

---

## 配置优先级

```
命令行参数 > 环境变量 > 配置文件 > 代码默认值
```

环境变量会**覆盖**配置文件中的对应配置项，适合用于：
- 敏感信息（API密钥、密码）管理
- 容器化部署
- CI/CD流水线
- 不同环境的快速切换

---

## 快速参考

### 必需的环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `QBT_HOST` | qBittorrent主机地址 | `192.168.1.40` |
| `QBT_USERNAME` | qBittorrent用户名 | `admin` |
| `QBT_PASSWORD` | qBittorrent密码 | `your_password` |
| `DEEPSEEK_API_KEY` | DeepSeek API密钥 | `sk-abc123...` |

### 完整环境变量清单

```bash
# qBittorrent连接
QBT_HOST=localhost
QBT_PORT=8080
QBT_USERNAME=admin
QBT_PASSWORD=adminadmin
QBT_USE_HTTPS=false
QBT_VERIFY_SSL=true

# AI分类器
AI_PROVIDER=deepseek
AI_API_KEY=your_deepseek_api_key_here
AI_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 监控
MONITOR_CHECK_INTERVAL=1.0
MONITOR_ADAPTIVE_INTERVAL=true
MONITOR_MIN_INTERVAL=0.1
MONITOR_MAX_INTERVAL=5.0

# 缓存
CACHE_ENABLE_DUPLICATE_FILTER=true
CACHE_SIZE=1000
CACHE_TTL_SECONDS=300

# 日志
LOG_LEVEL=INFO
LOG_FILE=logs/qbittorrent-monitor.log

# 爬虫
CRAWLER_ENABLED=false
CRAWLER_MAX_CONCURRENT=5
CRAWLER_DELAY=1.0

# 性能
PERFORMANCE_FAST_START=true
PERFORMANCE_MEMORY_POOL=true
PERFORMANCE_BATCH_SIZE=10

# Web界面
WEB_ENABLED=false
WEB_HOST=0.0.0.0
WEB_PORT=8081

# 通知
NOTIFICATIONS_ENABLED=false
NOTIFICATION_EMAIL_SMTP_HOST=smtp.gmail.com
NOTIFICATION_EMAIL_SMTP_PORT=587
```

---

## 详细说明

### qBittorrent连接

| 变量名 | 配置映射 | 类型 | 默认值 | 说明 |
|--------|----------|------|--------|------|
| `QBT_HOST` | `qbittorrent.host` | string | `localhost` | qBittorrent服务器地址 |
| `QBT_PORT` | `qbittorrent.port` | integer | `8080` | Web UI端口 |
| `QBT_USERNAME` | `qbittorrent.username` | string | `admin` | 登录用户名 |
| `QBT_PASSWORD` | `qbittorrent.password` | string | `password` | 登录密码 |
| `QBT_USE_HTTPS` | `qbittorrent.use_https` | boolean | `false` | 启用HTTPS |
| `QBT_VERIFY_SSL` | `qbittorrent.verify_ssl` | boolean | `true` | 验证SSL证书 |
| `QBT_PATH_MAPPING` | `qbittorrent.path_mapping` | JSON | `[]` | 路径映射规则 |

**示例:**

```bash
# 基本配置
export QBT_HOST=192.168.1.40
export QBT_PORT=8989
export QBT_USERNAME=admin
export QBT_PASSWORD=secure_password

# HTTPS配置
export QBT_USE_HTTPS=true
export QBT_VERIFY_SSL=true
```

**路径映射格式:**

```bash
export QBT_PATH_MAPPING='[{"source_prefix": "/downloads", "target_prefix": "/vol1/downloads"}]'
```

---

### AI分类器

| 变量名 | 配置映射 | 类型 | 默认值 | 说明 |
|--------|----------|------|--------|------|
| `AI_PROVIDER` | - | string | `deepseek` | AI提供商 |
| `AI_API_KEY` | `deepseek.api_key` | string | `""` | API密钥 |
| `AI_MODEL` | `deepseek.model` | string | `deepseek-chat` | 模型名称 |
| `DEEPSEEK_API_KEY` | `deepseek.api_key` | string | `""` | DeepSeek专用密钥 |
| `DEEPSEEK_BASE_URL` | `deepseek.base_url` | string | `https://api.deepseek.com` | API基础URL |
| `DEEPSEEK_TIMEOUT` | `deepseek.timeout` | integer | `30` | 请求超时(秒) |
| `DEEPSEEK_MAX_RETRIES` | `deepseek.max_retries` | integer | `3` | 最大重试次数 |

**示例:**

```bash
# DeepSeek配置
export DEEPSEEK_API_KEY=sk-abc123def456
export DEEPSEEK_BASE_URL=https://api.deepseek.com
export AI_MODEL=deepseek-chat

# OpenAI配置
export AI_PROVIDER=openai
export AI_API_KEY=sk-openai123
export AI_MODEL=gpt-3.5-turbo
export DEEPSEEK_BASE_URL=https://api.openai.com/v1
```

---

### 监控配置

| 变量名 | 配置映射 | 类型 | 默认值 | 说明 |
|--------|----------|------|--------|------|
| `CHECK_INTERVAL` | `check_interval` | float | `2.0` | 剪贴板检查间隔(秒) |
| `MONITOR_CHECK_INTERVAL` | `check_interval` | float | `2.0` | 同上 |
| `MONITOR_ADAPTIVE_INTERVAL` | - | boolean | `true` | 自适应间隔 |
| `MONITOR_MIN_INTERVAL` | - | float | `0.1` | 最小检查间隔 |
| `MONITOR_MAX_INTERVAL` | - | float | `5.0` | 最大检查间隔 |

**示例:**

```bash
# 高频监控（响应更快，占用更多CPU）
export CHECK_INTERVAL=0.5

# 低频监控（资源占用更低）
export CHECK_INTERVAL=5.0

# 自适应监控
export MONITOR_ADAPTIVE_INTERVAL=true
export MONITOR_MIN_INTERVAL=0.5
export MONITOR_MAX_INTERVAL=10.0
```

---

### 日志配置

| 变量名 | 配置映射 | 类型 | 默认值 | 说明 |
|--------|----------|------|--------|------|
| `LOG_LEVEL` | `log_level` | string | `INFO` | 日志级别 |
| `LOG_FILE` | `log_file` | string | `magnet_monitor.log` | 日志文件路径 |
| `LOG_FORMAT` | - | string | `json` | 日志格式 |

**支持的日志级别:**
- `DEBUG` - 调试信息
- `INFO` - 一般信息（推荐）
- `WARNING` - 警告信息
- `ERROR` - 错误信息
- `CRITICAL` - 严重错误

**示例:**

```bash
# 开发环境
export LOG_LEVEL=DEBUG
export LOG_FILE=logs/debug.log

# 生产环境
export LOG_LEVEL=INFO
export LOG_FILE=/var/log/qbmonitor/app.log

# 仅控制台输出
export LOG_FILE=""
```

---

### 爬虫配置

| 变量名 | 配置映射 | 类型 | 默认值 | 说明 |
|--------|----------|------|--------|------|
| `CRAWLER_ENABLED` | `web_crawler.enabled` | boolean | `true` | 启用爬虫 |
| `CRAWLER_PAGE_TIMEOUT` | `web_crawler.page_timeout` | integer | `60000` | 页面超时(毫秒) |
| `CRAWLER_MAX_CONCURRENT` | `web_crawler.max_concurrent_extractions` | integer | `3` | 最大并发数 |
| `CRAWLER_DELAY` | `web_crawler.inter_request_delay` | float | `1.5` | 请求间延迟(秒) |
| `CRAWLER_MAX_RETRIES` | `web_crawler.max_retries` | integer | `3` | 最大重试次数 |
| `CRAWLER_AI_CLASSIFY` | `web_crawler.ai_classify_torrents` | boolean | `true` | AI分类 |
| `CRAWLER_PROXY` | `web_crawler.proxy` | string | - | 爬虫代理 |

**示例:**

```bash
# 禁用爬虫
export CRAWLER_ENABLED=false

# 高性能爬虫配置
export CRAWLER_PAGE_TIMEOUT=120000
export CRAWLER_MAX_CONCURRENT=5
export CRAWLER_DELAY=0.5

# 使用代理
export CRAWLER_PROXY=http://127.0.0.1:7890
```

---

### 性能优化

| 变量名 | 配置映射 | 类型 | 默认值 | 说明 |
|--------|----------|------|--------|------|
| `PERFORMANCE_FAST_START` | - | boolean | `true` | 快速启动模式 |
| `PERFORMANCE_MEMORY_POOL` | - | boolean | `true` | 内存池优化 |
| `PERFORMANCE_BATCH_SIZE` | - | integer | `10` | 批处理大小 |
| `HOT_RELOAD` | `hot_reload` | boolean | `true` | 配置热加载 |

**示例:**

```bash
# 高性能模式
export PERFORMANCE_FAST_START=true
export PERFORMANCE_MEMORY_POOL=true
export PERFORMANCE_BATCH_SIZE=20

# 低资源模式
export PERFORMANCE_BATCH_SIZE=5
export HOT_RELOAD=false
```

---

### Web界面

| 变量名 | 配置映射 | 类型 | 默认值 | 说明 |
|--------|----------|------|--------|------|
| `WEB_ENABLED` | - | boolean | `false` | 启用Web界面 |
| `WEB_HOST` | - | string | `0.0.0.0` | Web服务绑定地址 |
| `WEB_PORT` | - | integer | `8081` | Web服务端口 |
| `WEB_AUTH_ENABLED` | - | boolean | `false` | 启用认证 |
| `WEB_AUTH_USERNAME` | - | string | `admin` | 认证用户名 |
| `WEB_AUTH_PASSWORD` | - | string | - | 认证密码 |

**示例:**

```bash
# 启用Web界面
export WEB_ENABLED=true
export WEB_HOST=0.0.0.0
export WEB_PORT=8081

# 启用认证
export WEB_AUTH_ENABLED=true
export WEB_AUTH_USERNAME=admin
export WEB_AUTH_PASSWORD=secure_password
```

---

### 通知配置

| 变量名 | 配置映射 | 类型 | 默认值 | 说明 |
|--------|----------|------|--------|------|
| `NOTIFICATIONS_ENABLED` | `notifications.enabled` | boolean | `false` | 启用通知 |
| `NOTIFICATION_SERVICES` | `notifications.services` | JSON | `[]` | 通知服务列表 |
| `NOTIFICATION_WEBHOOK_URL` | `notifications.webhook_url` | string | - | Webhook URL |
| `NOTIFICATION_API_TOKEN` | `notifications.api_token` | string | - | API令牌 |
| `NOTIFICATION_CHAT_ID` | `notifications.chat_id` | string | - | 聊天ID |
| `NOTIFICATION_EMAIL_SMTP_HOST` | - | string | - | SMTP主机 |
| `NOTIFICATION_EMAIL_SMTP_PORT` | - | integer | `587` | SMTP端口 |
| `NOTIFICATION_EMAIL_USERNAME` | - | string | - | 邮箱用户名 |
| `NOTIFICATION_EMAIL_PASSWORD` | - | string | - | 邮箱密码 |
| `NOTIFICATION_EMAIL_TO` | - | string | - | 收件人 |

**示例:**

```bash
# Telegram通知
export NOTIFICATIONS_ENABLED=true
export NOTIFICATION_SERVICES='["telegram"]'
export NOTIFICATION_API_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
export NOTIFICATION_CHAT_ID=123456789

# 邮件通知
export NOTIFICATIONS_ENABLED=true
export NOTIFICATION_SERVICES='["email"]'
export NOTIFICATION_EMAIL_SMTP_HOST=smtp.gmail.com
export NOTIFICATION_EMAIL_SMTP_PORT=587
export NOTIFICATION_EMAIL_USERNAME=your_email@gmail.com
export NOTIFICATION_EMAIL_PASSWORD=your_app_password
export NOTIFICATION_EMAIL_TO=recipient@example.com

# 多服务通知
export NOTIFICATION_SERVICES='["telegram", "discord", "email"]'
```

---

### 缓存配置

| 变量名 | 配置映射 | 类型 | 默认值 | 说明 |
|--------|----------|------|--------|------|
| `CACHE_ENABLE_DUPLICATE_FILTER` | - | boolean | `true` | 启用重复过滤 |
| `CACHE_SIZE` | - | integer | `1000` | 缓存大小 |
| `CACHE_TTL_SECONDS` | - | integer | `300` | 缓存TTL(秒) |

**示例:**

```bash
# 大缓存配置
export CACHE_SIZE=5000
export CACHE_TTL_SECONDS=3600

# 小内存配置
export CACHE_SIZE=500
export CACHE_TTL_SECONDS=180
```

---

## Docker环境

### Docker Compose示例

```yaml
version: '3.8'

services:
  qbittorrent-monitor:
    image: qbittorrent-monitor:latest
    container_name: qbittorrent-monitor
    environment:
      # qBittorrent配置
      - QBT_HOST=host.docker.internal
      - QBT_PORT=8080
      - QBT_USERNAME=admin
      - QBT_PASSWORD=${QBT_PASSWORD}
      
      # AI配置
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - AI_MODEL=deepseek-chat
      
      # 日志配置
      - LOG_LEVEL=INFO
      - LOG_FILE=/app/logs/qbmonitor.log
      
      # 监控配置
      - CHECK_INTERVAL=2.0
      
      # Web界面
      - WEB_ENABLED=true
      - WEB_PORT=8081
      
      # 通知配置
      - NOTIFICATIONS_ENABLED=true
      - NOTIFICATION_SERVICES=["telegram"]
      - NOTIFICATION_API_TOKEN=${TELEGRAM_BOT_TOKEN}
      - NOTIFICATION_CHAT_ID=${TELEGRAM_CHAT_ID}
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    ports:
      - "8081:8081"
    restart: unless-stopped
```

### Docker Run示例

```bash
docker run -d \
  --name qbittorrent-monitor \
  -e QBT_HOST=192.168.1.40 \
  -e QBT_PORT=8080 \
  -e QBT_USERNAME=admin \
  -e QBT_PASSWORD=your_password \
  -e DEEPSEEK_API_KEY=sk-your-api-key \
  -e LOG_LEVEL=INFO \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  qbittorrent-monitor:latest
```

---

## Kubernetes配置

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: qbittorrent-monitor-config
data:
  LOG_LEVEL: "INFO"
  CHECK_INTERVAL: "2.0"
  HOT_RELOAD: "true"
  CRAWLER_ENABLED: "true"
  WEB_ENABLED: "true"
  WEB_PORT: "8081"
```

### Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: qbittorrent-monitor-secrets
type: Opaque
stringData:
  QBT_PASSWORD: "your_password"
  DEEPSEEK_API_KEY: "sk-your-api-key"
  NOTIFICATION_API_TOKEN: "your_bot_token"
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qbittorrent-monitor
spec:
  replicas: 1
  selector:
    matchLabels:
      app: qbittorrent-monitor
  template:
    metadata:
      labels:
        app: qbittorrent-monitor
    spec:
      containers:
      - name: qbittorrent-monitor
        image: qbittorrent-monitor:latest
        envFrom:
        - configMapRef:
            name: qbittorrent-monitor-config
        - secretRef:
            name: qbittorrent-monitor-secrets
        ports:
        - containerPort: 8081
```

---

## 最佳实践

### 1. 敏感信息管理

```bash
# ❌ 不要直接在命令行中输入密码
docker run -e QBT_PASSWORD=mypassword ...

# ✅ 使用环境变量文件
docker run --env-file .env ...

# ✅ 使用Docker Secrets (Swarm)
docker run -e QBT_PASSWORD_FILE=/run/secrets/qbt_pass ...

# ✅ 使用Kubernetes Secrets
envFrom:
  - secretRef:
      name: qbittorrent-monitor-secrets
```

### 2. 环境分层管理

```
.env.development    # 开发环境
.env.staging        # 预发布环境
.env.production     # 生产环境（不提交到版本控制）
```

### 3. 配置验证

```bash
# 启动前验证配置
docker run --rm qbittorrent-monitor:latest python -m qbittorrent_monitor.config_validator

# 或者
python scripts/config/validate_config.py --env-file .env
```

### 4. 常用组合配置

#### 最小配置（仅必需项）

```bash
QBT_HOST=localhost
QBT_PORT=8080
QBT_USERNAME=admin
QBT_PASSWORD=password
DEEPSEEK_API_KEY=sk-your-key
```

#### 推荐配置（开发）

```bash
# 连接
QBT_HOST=localhost
QBT_PORT=8080
QBT_USERNAME=admin
QBT_PASSWORD=password

# AI
DEEPSEEK_API_KEY=sk-your-key
AI_MODEL=deepseek-chat

# 日志
LOG_LEVEL=DEBUG
LOG_FILE=logs/app.log

# 监控
CHECK_INTERVAL=1.0
HOT_RELOAD=true

# 通知（开发时禁用）
NOTIFICATIONS_ENABLED=false
```

#### 推荐配置（生产）

```bash
# 连接
QBT_HOST=192.168.1.40
QBT_PORT=8080
QBT_USERNAME=admin
QBT_PASSWORD_FILE=/run/secrets/qbt_pass
QBT_USE_HTTPS=true
QBT_VERIFY_SSL=true

# AI
DEEPSEEK_API_KEY_FILE=/run/secrets/api_key
AI_MODEL=deepseek-chat

# 日志
LOG_LEVEL=INFO
LOG_FILE=/var/log/qbmonitor/app.log

# 监控
CHECK_INTERVAL=2.0
HOT_RELOAD=false

# 通知
NOTIFICATIONS_ENABLED=true
NOTIFICATION_SERVICES=["telegram", "email"]
NOTIFICATION_API_TOKEN_FILE=/run/secrets/tg_token
```

---

## 相关文档

- [配置参考手册](./CONFIGURATION_REFERENCE.md)
- [多环境配置指南](./guides/MULTI_ENVIRONMENT.md)
- [Docker部署指南](../DEPLOYMENT_GUIDE.md)
