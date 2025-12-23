# qBittorrent 剪贴板监控器 - 部署指南

> 📅 **最后更新**: 2025-11-12
> 🎯 **版本**: v2.4.0
> 👥 **适用对象**: 系统管理员、DevOps工程师、技术用户

---

## 📋 目录

- [快速开始](#快速开始)
- [系统要求](#系统要求)
- [环境配置](#环境配置)
- [安装部署](#安装部署)
- [配置说明](#配置说明)
- [服务管理](#服务管理)
- [监控和健康检查](#监控和健康检查)
- [故障排除](#故障排除)
- [性能优化](#性能优化)
- [安全配置](#安全配置)

---

## 🚀 快速开始

### 一键部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 2. 安装Poetry（如果尚未安装）
curl -sSL https://install.python-poetry.org | python3 -

# 3. 安装项目依赖
poetry install

# 4. 安装开发依赖（如果需要）
poetry install --with dev

# 5. 配置验证（可选）
python qbittorrent_monitor/config_validator.py --fix

# 6. 启动服务
./run.sh  # Linux/macOS
# 或
run.bat   # Windows
```

### 手动部署

详细步骤请参考 [手动安装部署](#安装部署) 部分。

---

## 💻 系统要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 | 说明 |
|------|----------|----------|------|
| CPU | 2核 | 4核+ | AI分类和高并发监控需要更多CPU |
| 内存 | 2GB | 4GB+ | 缓存和连接池占用内存 |
| 磁盘 | 5GB | 20GB+ | 用于日志、缓存和临时文件 |
| 网络 | 1Mbps | 10Mbps+ | AI API调用需要稳定网络 |

### 软件要求

| 软件 | 版本要求 | 必需 | 说明 |
|------|----------|------|------|
| Python | 3.9 - 3.12 | ✅ | 核心运行环境 |
| qBittorrent | 4.3+ | ✅ | Web API需启用 |
| Git | 2.0+ | ✅ | 代码管理 |
| 操作系统 | Linux/macOS/Windows | ✅ | 跨平台支持 |

### Python依赖

```bash
# 核心依赖
python>=3.9,<3.13
aiohttp>=3.11.0
pydantic>=2.11.0
pyperclip>=1.9.0
openai>=1.76.0
tenacity>=9.0.0
watchdog>=6.0.0
dynaconf>=3.2.0
click>=8.1.0
apprise>=1.9.0

# 网页爬虫依赖（可选）
crawl4ai>=0.6.3

# Web界面依赖（可选）
fastapi>=0.115.0
uvicorn>=0.35.0

# 监控依赖（可选）
psutil>=5.9.0
aiohttp-cors>=0.7.0
```

---

## 🔧 环境配置

### 1. Python环境管理

项目使用智能环境管理器自动处理Python环境：

```bash
# 检查环境状态
python scripts/environment_manager.py --info

# 运行系统检查
python scripts/environment_manager.py --check

# 强制重新创建环境
python scripts/environment_manager.py --force
```

### 2. 虚拟环境创建

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 升级pip
pip install --upgrade pip setuptools wheel
```

### 3. 依赖安装

```bash
# 使用Poetry（推荐）
curl -sSL https://install.python-poetry.org | python3 -
poetry install

# 安装开发依赖
poetry install --with dev
```

### 4. 环境变量配置

创建 `.env` 文件：

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置
nano .env
```

核心配置项：

```bash
# qBittorrent配置
QBT_HOST=localhost
QBT_PORT=8080
QBT_USERNAME=admin
QBT_PASSWORD=adminadmin

# AI分类器配置
AI_PROVIDER=deepseek
AI_API_KEY=your_deepseek_api_key_here
AI_MODEL=deepseek-chat

# 监控配置
MONITOR_CHECK_INTERVAL=1.0
MONITOR_ADAPTIVE_INTERVAL=true
LOG_LEVEL=INFO
```

### 5. 配置验证

```bash
# 验证配置
python qbittorrent_monitor/config_validator.py

# 交互式修复配置
python qbittorrent_monitor/config_validator.py --fix

# 生成配置模板
python qbittorrent_monitor/config_validator.py --template
```

---

## 📦 安装部署

### 方法1：源码部署

```bash
# 1. 克隆代码
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 2. 环境配置
python scripts/environment_manager.py

# 3. 配置验证
python qbittorrent_monitor/config_validator.py --fix

# 4. 启动服务
./run.sh
```

### 方法2：开发模式部署

```bash
# 1. 克隆代码
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 2. 安装开发依赖
scripts/setup_dev.sh

# 3. 运行测试
scripts/run_tests.sh

# 4. 启动开发模式
python -m qbittorrent_monitor.main --debug
```

### 方法3：系统服务部署（Linux）

#### Systemd服务配置

创建服务文件：

```bash
sudo nano /etc/systemd/system/qbittorrent-monitor.service
```

内容：

```ini
[Unit]
Description=qBittorrent Clipboard Monitor
After=network.target qbittorrent.service
Wants=network.target

[Service]
Type=simple
User=your-username
Group=your-username
WorkingDirectory=/path/to/qbittorrent-clipboard-monitor
ExecStart=/path/to/qbittorrent-clipboard-monitor/venv/bin/python start.py
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
TimeoutStopSec=30
Restart=on-failure
RestartSec=10

# 环境变量
Environment=PYTHONPATH=/path/to/qbittorrent-clipboard-monitor
Environment=QBT_HOST=localhost
Environment=QBT_PORT=8080
Environment=QBT_USERNAME=admin
Environment=QBT_PASSWORD=adminadmin

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
# 重新加载systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start qbittorrent-monitor

# 设置开机自启
sudo systemctl enable qbittorrent-monitor

# 查看服务状态
sudo systemctl status qbittorrent-monitor

# 查看服务日志
sudo journalctl -u qbittorrent-monitor -f
```

### 方法4：Docker部署（可选）

虽然您提到不需要Docker化，但提供Dockerfile供参考：

```dockerfile
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建非root用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8090 8091

# 启动命令
CMD ["python", "start.py"]
```

---

## ⚙️ 配置说明

### 完整配置文件示例

```yaml
# config.yaml
qbittorrent:
  host: "localhost"
  port: 8080
  username: "admin"
  password: "adminadmin"
  connection_pool_size: 20
  request_timeout: 30
  max_retries: 3
  circuit_breaker_threshold: 5

ai:
  provider: "deepseek"
  api_key: "your_api_key"
  model: "deepseek-chat"
  timeout: 30
  max_retries: 3
  retry_delay: 1.0

monitoring:
  check_interval: 1.0
  adaptive_interval: true
  min_interval: 0.1
  max_interval: 5.0
  enable_ai_classification: true
  enable_duplicate_filter: true

caching:
  enable_duplicate_filter: true
  cache_size: 1000
  l1_cache_size: 1000
  l2_cache_size_mb: 100
  ttl_seconds: 300
  enable_persistence: true

logging:
  level: "INFO"
  file: "logs/qbittorrent-monitor.log"
  max_size_mb: 100
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

health_check:
  enabled: true
  host: "0.0.0.0"
  port: 8090
  check_interval: 30

prometheus:
  enabled: true
  host: "0.0.0.0"
  port: 8091
  prefix: "qbittorrent_monitor"

web_interface:
  enabled: false
  host: "0.0.0.0"
  port: 8081

notifications:
  enabled: false
  email:
    smtp_host: ""
    smtp_port: 587
    username: ""
    password: ""
    to: ""
```

### 环境变量映射

| 环境变量 | 配置路径 | 说明 |
|----------|----------|------|
| `QBT_HOST` | `qbittorrent.host` | qBittorrent主机地址 |
| `QBT_PORT` | `qbittorrent.port` | qBittorrent端口 |
| `QBT_USERNAME` | `qbittorrent.username` | qBittorrent用户名 |
| `QBT_PASSWORD` | `qbittorrent.password` | qBittorrent密码 |
| `AI_PROVIDER` | `ai.provider` | AI服务提供商 |
| `AI_API_KEY` | `ai.api_key` | AI API密钥 |
| `LOG_LEVEL` | `logging.level` | 日志级别 |

---

## 🎮 服务管理

### 启动服务

```bash
# 使用启动脚本
./run.sh

# 或直接启动
python start.py

# 开发模式启动
python start.py --debug

# 后台启动
nohup python start.py > logs/startup.log 2>&1 &
```

### 停止服务

```bash
# 优雅关闭（推荐）
# 发送SIGTERM信号
kill -TERM <pid>

# 强制关闭
kill -KILL <pid>

# 或使用Ctrl+C（前台运行时）
```

### 服务状态检查

```bash
# 检查进程状态
ps aux | grep qbittorrent-monitor

# 检查端口占用
netstat -tlnp | grep :8080
netstat -tlnp | grep :8090

# 检查日志
tail -f logs/qbittorrent-monitor.log
```

### 日志管理

```bash
# 查看实时日志
tail -f logs/qbittorrent-monitor.log

# 查看错误日志
grep "ERROR" logs/qbittorrent-monitor.log

# 日志轮转
logrotate -f /etc/logrotate.d/qbittorrent-monitor
```

---

## 📊 监控和健康检查

### 健康检查端点

服务启动后，可通过以下端点进行健康检查：

```bash
# 基本健康检查
curl http://localhost:8090/health

# 就绪检查
curl http://localhost:8090/health/ready

# 存活检查
curl http://localhost:8090/health/live

# 组件检查
curl http://localhost:8090/health/components

# 指标检查
curl http://localhost:8090/health/metrics

# 详细检查
curl http://localhost:8090/health/detailed
```

### Prometheus指标

```bash
# 获取Prometheus格式指标
curl http://localhost:8091/metrics
```

可用指标：

- `qbittorrent_monitor_clipboard_changes_total` - 剪贴板变化次数
- `qbittorrent_monitor_torrents_added_total` - 添加种子数
- `qbittorrent_monitor_ai_classifications_total` - AI分类次数
- `qbittorrent_monitor_processing_duration_seconds` - 处理时间
- `qbittorrent_monitor_memory_usage_bytes` - 内存使用量
- `qbittorrent_monitor_cpu_usage_percent` - CPU使用率

### 监控系统集成

#### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "qBittorrent Monitor Dashboard",
    "panels": [
      {
        "title": "剪贴板监控率",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(qbittorrent_monitor_clipboard_changes_total[5m])",
            "legendFormat": "变化率/秒"
          }
        ]
      },
      {
        "title": "种子添加统计",
        "type": "stat",
        "targets": [
          {
            "expr": "increase(qbittorrent_monitor_torrents_added_total[1h])",
            "legendFormat": "1小时添加"
          }
        ]
      }
    ]
  }
}
```

---

## 🔧 故障排除

### 常见问题及解决方案

#### 1. Python环境问题

**问题**: `ModuleNotFoundError: No module named 'xxx'`

**解决方案**:
```bash
# 重新安装依赖
pip install -r requirements.txt

# 或使用环境管理器
python scripts/environment_manager.py --force
```

#### 2. qBittorrent连接失败

**问题**: `ConnectionError: Failed to connect to qBittorrent`

**解决方案**:
```bash
# 检查qBittorrent是否运行
systemctl status qbittorrent-nox

# 检查Web API是否启用
# Web UI -> 工具 -> 选项 -> Web UI -> Web用户界面

# 检查网络连接
telnet localhost 8080
```

#### 3. AI分类器错误

**问题**: `AIApiError: API密钥无效或网络连接失败`

**解决方案**:
```bash
# 检查API密钥
echo $AI_API_KEY

# 测试网络连接
curl -I https://api.deepseek.com

# 检查配置
python qbittorrent_monitor/config_validator.py
```

#### 4. 权限问题

**问题**: `PermissionError: 无法创建日志文件`

**解决方案**:
```bash
# 创建日志目录
mkdir -p logs
chmod 755 logs

# 检查文件权限
ls -la logs/

# 修复权限
chmod +x run.sh
```

#### 5. 端口冲突

**问题**: `Address already in use: Port 8080`

**解决方案**:
```bash
# 查找占用端口的进程
netstat -tlnp | grep :8080
lsof -i :8080

# 杀死进程
kill -9 <pid>

# 或更改配置中的端口号
sed -i 's/QBT_PORT=8080/QBT_PORT=8081/' .env
```

#### 6. 内存不足

**问题**: `MemoryError: 内存不足`

**解决方案**:
```bash
# 检查内存使用
free -h
ps aux --sort=-%mem | head

# 调整配置
# 减少 cache_size
# 增加内存清理频率
```

### 日志分析

#### 重要日志关键词

```bash
# 查看错误日志
grep -E "(ERROR|CRITICAL)" logs/qbittorrent-monitor.log

# 查看警告日志
grep "WARNING" logs/qbittorrent-monitor.log

# 查看连接错误
grep -i "connection\|timeout\|failed" logs/qbittorrent-monitor.log

# 查看AI相关错误
grep -i "ai\|classification\|deepseek" logs/qbittorrent-monitor.log
```

#### 日志级别调整

```bash
# 临时调整日志级别
export LOG_LEVEL=DEBUG
python start.py

# 或修改.env文件
echo "LOG_LEVEL=DEBUG" >> .env
```

### 性能问题诊断

#### 1. 高CPU使用

```bash
# 检查CPU使用
top -p $(pgrep -f qbittorrent-monitor)

# 检查监控间隔
grep "check_interval" .env

# 优化建议
# - 增加监控间隔
# - 减少AI分类频率
# - 启用缓存优化
```

#### 2. 高内存使用

```bash
# 检查内存使用
ps aux --sort=-%mem | grep qbittorrent-monitor

# 检查缓存大小
grep -i "cache" .env

# 优化建议
# - 减少缓存大小
# - 启用内存清理
# - 重启服务释放内存
```

#### 3. 网络问题

```bash
# 检查网络连接
ping 8.8.8.8
curl -I https://api.deepseek.com

# 检查DNS解析
nslookup api.deepseek.com

# 检查代理设置
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

---

## ⚡ 性能优化

### 系统级优化

#### 1. 文件描述符限制

```bash
# 查看当前限制
ulimit -n

# 临时增加限制
ulimit -n 65536

# 永久设置
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf
```

#### 2. 内核参数优化

```bash
# 编辑sysctl配置
sudo nano /etc/sysctl.conf

# 添加以下内容
net.core.somaxconn = 65536
net.ipv4.tcp_max_syn_backlog = 65536
net.core.netdev_max_backlog = 5000

# 应用配置
sudo sysctl -p
```

#### 3. CPU亲和性设置

```bash
# 绑定进程到特定CPU核心
taskset -c 0,1 python start.py

# 查看CPU亲和性
taskset -p $(pgrep -f qbittorrent-monitor)
```

### 应用级优化

#### 1. 监控间隔优化

```bash
# 根据系统负载调整
# 高负载系统: 2.0-5.0秒
# 低负载系统: 0.5-1.0秒

# 启用自适应间隔
MONITOR_ADAPTIVE_INTERVAL=true
MONITOR_MIN_INTERVAL=0.1
MONITOR_MAX_INTERVAL=5.0
```

#### 2. 缓存优化

```bash
# 增加缓存大小
CACHE_SIZE=5000
CACHE_TTL_SECONDS=1800

# 启用双层缓存
L1_CACHE_SIZE=2000
L2_CACHE_SIZE_MB=200
```

#### 3. AI分类优化

```bash
# 批量分类减少API调用
AI_BATCH_SIZE=5
AI_CACHE_RESULTS=true

# 使用本地规则优先
LOCAL_RULES_PRIORITY=true
```

#### 4. 网络优化

```bash
# 连接池优化
QBT_CONNECTION_POOL_SIZE=30
QBT_REQUEST_TIMEOUT=60

# 启用连接复用
ENABLE_CONNECTION_REUSE=true
```

### 监控性能指标

```bash
# 定期检查性能
watch -n 5 'curl -s http://localhost:8090/health/metrics | grep -E "(cpu|memory|duration)"'

# 生成性能报告
curl -s http://localhost:8090/health/detailed | jq '.metrics'
```

---

## 🔒 安全配置

### 1. API密钥安全

```bash
# 使用环境变量而非配置文件
export AI_API_KEY="your_api_key"

# 限制文件权限
chmod 600 .env
chown $USER:$USER .env

# 定期轮换密钥
# 设置自动提醒
```

### 2. 网络安全

```bash
# 防火墙配置
sudo ufw allow 8080/tcp  # qBittorrent
sudo ufw allow 8090/tcp  # 健康检查
sudo ufw enable

# 限制访问IP
# 在qBittorrent中设置IP白名单
```

### 3. 日志安全

```bash
# 定期清理敏感日志
find logs/ -name "*.log" -mtime +30 -delete

# 加密敏感配置
gpg --symmetric --cipher-algo AES256 .env
```

### 4. 进程安全

```bash
# 以非root用户运行
sudo useradd -m -s /bin/bash qbmonitor
sudo chown -R qbmonitor:qbmonitor /path/to/qbittorrent-clipboard-monitor
sudo -u qbmonitor python start.py

# 限制进程权限
# 使用SELinux/AppArmor
```

---

## 📞 技术支持

### 获取帮助

- **GitHub Issues**: [提交问题](https://github.com/ashllll/qbittorrent-clipboard-monitor/issues)
- **文档**: [项目文档](https://github.com/ashllll/qbittorrent-clipboard-monitor/wiki)
- **社区**: [GitHub Discussions](https://github.com/ashllll/qbittorrent-clipboard-monitor/discussions)

### 诊断信息收集

```bash
# 生成诊断报告
python -c "
import sys
import platform
import subprocess

print('=== 系统信息 ===')
print(f'Python: {sys.version}')
print(f'平台: {platform.platform()}')
print(f'架构: {platform.architecture()}')

print('\n=== 依赖信息 ===')
subprocess.run(['pip', 'list'], check=False)

print('\n=== 进程信息 ===')
subprocess.run(['ps', 'aux'], check=False)
" > diagnostics.txt
```

### 联系方式

- **邮箱**: project@example.com
- **维护者**: [GitHub用户名](https://github.com/ashllll)

---

*📝 本文档持续更新，如有问题请提交Issue或PR*