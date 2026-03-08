# 部署指南

本文档介绍 qBittorrent Clipboard Monitor 的各种部署方式。

## 目录

- [Docker 部署](#docker-部署)
  - [Docker 基础用法](#docker-基础用法)
  - [Docker Compose 部署](#docker-compose-部署)
  - [构建优化](#构建优化)
- [systemd 部署](#systemd-部署)
  - [创建服务文件](#创建服务文件)
  - [管理命令](#管理命令)
- [Supervisor 部署](#supervisor-部署)
  - [配置文件](#配置文件)
  - [管理命令](#管理命令-1)
- [Python 虚拟环境部署](#python-虚拟环境部署)
- [Windows 服务部署](#windows-服务部署)

---

## Docker 部署

### Docker 基础用法

#### 1. 构建镜像

```bash
# 克隆仓库
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 构建镜像
docker build -t qb-monitor:latest .
```

#### 2. 运行容器

```bash
# 基础运行
docker run -d \
  --name qb-monitor \
  -e QBIT_HOST=192.168.1.100 \
  -e QBIT_PORT=8080 \
  -e QBIT_USERNAME=admin \
  -e QBIT_PASSWORD=yourpassword \
  qb-monitor:latest

# 启用 AI 分类
docker run -d \
  --name qb-monitor \
  -e QBIT_HOST=192.168.1.100 \
  -e QBIT_PORT=8080 \
  -e QBIT_USERNAME=admin \
  -e QBIT_PASSWORD=yourpassword \
  -e AI_ENABLED=true \
  -e AI_API_KEY=sk-your-api-key \
  -e AI_MODEL=deepseek-chat \
  qb-monitor:latest

# 使用主机网络（Linux）
docker run -d \
  --name qb-monitor \
  --network host \
  -e QBIT_HOST=localhost \
  -e QBIT_PORT=8080 \
  -e QBIT_USERNAME=admin \
  -e QBIT_PASSWORD=yourpassword \
  qb-monitor:latest
```

#### 3. 常用 Docker 命令

```bash
# 查看日志
docker logs -f qb-monitor

# 查看日志（最近 100 行）
docker logs --tail 100 qb-monitor

# 查看容器状态
docker ps -a | grep qb-monitor

# 停止容器
docker stop qb-monitor

# 启动容器
docker start qb-monitor

# 重启容器
docker restart qb-monitor

# 进入容器
docker exec -it qb-monitor /bin/bash

# 查看容器资源使用
docker stats qb-monitor

# 删除容器
docker rm -f qb-monitor

# 更新镜像
docker pull qb-monitor:latest
docker stop qb-monitor
docker rm qb-monitor
docker run -d --name qb-monitor ...
```

---

### Docker Compose 部署

推荐使用 Docker Compose 进行部署，配置更简洁，管理更方便。

#### 1. 准备环境变量文件

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# qBittorrent 配置（必需）
QBIT_HOST=192.168.1.100
QBIT_PORT=8080
QBIT_USERNAME=admin
QBIT_PASSWORD=your_secure_password
QBIT_USE_HTTPS=false

# AI 配置（可选）
AI_ENABLED=true
AI_API_KEY=sk-your-api-key-here
AI_MODEL=deepseek-chat
AI_BASE_URL=https://api.deepseek.com/v1

# 应用配置
CHECK_INTERVAL=1.0
LOG_LEVEL=INFO
```

#### 2. 创建 docker-compose.yml

项目已提供默认的 `docker-compose.yml`，内容如下：

```yaml
version: '3.8'

services:
  qb-monitor:
    build: .
    container_name: qbittorrent-clipboard-monitor
    restart: unless-stopped
    
    environment:
      # qBittorrent 配置
      - QBIT_HOST=${QBIT_HOST:-localhost}
      - QBIT_PORT=${QBIT_PORT:-8080}
      - QBIT_USERNAME=${QBIT_USERNAME:-admin}
      - QBIT_PASSWORD=${QBIT_PASSWORD}
      - QBIT_USE_HTTPS=${QBIT_USE_HTTPS:-false}
      
      # AI 配置（可选）
      - AI_ENABLED=${AI_ENABLED:-false}
      - AI_API_KEY=${AI_API_KEY}
      - AI_MODEL=${AI_MODEL:-deepseek-chat}
      - AI_BASE_URL=${AI_BASE_URL:-https://api.deepseek.com/v1}
      
      # 应用配置
      - CHECK_INTERVAL=${CHECK_INTERVAL:-1.0}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    
    # 如果使用主机网络模式（Linux），可以直接访问主机的 qBittorrent
    # network_mode: host
    
    # 或者使用桥接网络
    networks:
      - qb-monitor-network
    
    # 健康检查
    healthcheck:
      test: ["CMD", "python", "-c", "import qbittorrent_monitor; print('OK')"]
      interval: 30s
      timeout: 5s
      start_period: 5s
      retries: 3

networks:
  qb-monitor-network:
    driver: bridge
```

#### 3. 使用 Docker Compose 管理

```bash
# 构建并启动服务
docker-compose up -d

# 构建镜像（重新构建）
docker-compose build

# 查看日志
docker-compose logs -f

# 查看最近 100 行日志
docker-compose logs --tail 100

# 停止服务
docker-compose stop

# 启动服务
docker-compose start

# 重启服务
docker-compose restart

# 停止并删除容器
docker-compose down

# 停止并删除容器和镜像
docker-compose down --rmi all

# 更新服务（拉取最新代码后）
docker-compose pull
docker-compose up -d

# 查看服务状态
docker-compose ps

# 执行命令
docker-compose exec qb-monitor python -c "print('Hello')"
```

#### 4. Docker Compose 高级配置

##### 使用外部网络

如果你已经有其他 Docker 网络，可以让服务加入：

```yaml
services:
  qb-monitor:
    # ... 其他配置
    networks:
      - existing-network
      - qb-monitor-network

networks:
  existing-network:
    external: true
  qb-monitor-network:
    driver: bridge
```

##### 使用配置文件

将配置文件挂载到容器中：

```yaml
services:
  qb-monitor:
    # ... 其他配置
    volumes:
      - ./config.json:/app/config.json:ro
    environment:
      - CONFIG_PATH=/app/config.json
```

##### 资源限制

```yaml
services:
  qb-monitor:
    # ... 其他配置
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          cpus: '0.25'
          memory: 128M
```

##### 日志配置

```yaml
services:
  qb-monitor:
    # ... 其他配置
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

### 构建优化

#### 多阶段构建说明

项目 Dockerfile 使用多阶段构建优化镜像大小：

```dockerfile
# 构建阶段
FROM python:3.11-slim as builder
# 安装编译依赖和 Python 包

# 生产阶段
FROM python:3.11-slim
# 仅复制必要的依赖和代码
```

#### 优化技巧

1. **使用 .dockerignore**

创建 `.dockerignore` 文件：

```
.git
.gitignore
README.md
*.md
.pytest_cache
__pycache__
*.pyc
*.pyo
*.pyd
.tox
.coverage
.env
.venv
venv/
```

2. **使用 BuildKit 加速构建**

```bash
export DOCKER_BUILDKIT=1
docker build -t qb-monitor:latest .
```

3. **压缩镜像层**

```bash
docker build --squash -t qb-monitor:latest .
```

---

## systemd 部署

systemd 是 Linux 系统的主流服务管理器，适合在物理机或虚拟机上部署。

### 创建服务文件

创建文件 `/etc/systemd/system/qb-monitor.service`：

```ini
[Unit]
Description=qBittorrent Clipboard Monitor
After=network.target qbittorrent-nox.service
Wants=network.target

[Service]
Type=simple
User=your-username
Group=your-group

# 工作目录
WorkingDirectory=/opt/qb-monitor

# 环境变量
Environment="QBIT_HOST=localhost"
Environment="QBIT_PORT=8080"
Environment="QBIT_USERNAME=admin"
Environment="QBIT_PASSWORD=yourpassword"
Environment="AI_ENABLED=false"
Environment="CHECK_INTERVAL=1.0"
Environment="LOG_LEVEL=INFO"

# 或者使用环境变量文件
# EnvironmentFile=/opt/qb-monitor/.env

# 启动命令
ExecStart=/opt/qb-monitor/venv/bin/python run.py

# 重启策略
Restart=always
RestartSec=10

# 日志输出
StandardOutput=journal
StandardError=journal

# 资源限制
# LimitAS=1G
# LimitRSS=500M

[Install]
WantedBy=multi-user.target
```

### 管理命令

```bash
# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务（开机自启）
sudo systemctl enable qb-monitor

# 启动服务
sudo systemctl start qb-monitor

# 停止服务
sudo systemctl stop qb-monitor

# 重启服务
sudo systemctl restart qb-monitor

# 查看状态
sudo systemctl status qb-monitor

# 查看日志
sudo journalctl -u qb-monitor -f

# 查看日志（最近 100 行）
sudo journalctl -u qb-monitor -n 100

# 查看日志（今天）
sudo journalctl -u qb-monitor --since today

# 禁用服务
sudo systemctl disable qb-monitor
```

### 完整安装脚本

```bash
#!/bin/bash
# install.sh - systemd 安装脚本

set -e

INSTALL_DIR="/opt/qb-monitor"
SERVICE_FILE="/etc/systemd/system/qb-monitor.service"
USER="qb-monitor"

echo "=== qBittorrent Clipboard Monitor 安装脚本 ==="

# 创建用户
if ! id "$USER" &>/dev/null; then
    echo "创建用户: $USER"
    sudo useradd -r -s /bin/false "$USER"
fi

# 创建安装目录
echo "创建安装目录: $INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"

# 复制文件
echo "复制应用文件"
sudo cp -r qbittorrent_monitor "$INSTALL_DIR/"
sudo cp run.py "$INSTALL_DIR/"
sudo cp config.example.json "$INSTALL_DIR/config.json"
sudo cp .env.example "$INSTALL_DIR/.env"

# 创建虚拟环境
echo "创建 Python 虚拟环境"
cd "$INSTALL_DIR"
sudo python3 -m venv venv
sudo venv/bin/pip install --upgrade pip
sudo venv/bin/pip install aiohttp openai pyperclip

# 设置权限
echo "设置权限"
sudo chown -R "$USER:$USER" "$INSTALL_DIR"

# 创建服务文件
echo "创建 systemd 服务"
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=qBittorrent Clipboard Monitor
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python run.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable qb-monitor

echo ""
echo "=== 安装完成 ==="
echo "请编辑配置文件: sudo nano $INSTALL_DIR/.env"
echo "然后启动服务: sudo systemctl start qb-monitor"
echo "查看日志: sudo journalctl -u qb-monitor -f"
```

---

## Supervisor 部署

Supervisor 是 Python 编写的进程管理工具，适合在没有 systemd 的系统中使用。

### 安装 Supervisor

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install supervisor

# CentOS/RHEL
sudo yum install supervisor

# 使用 pip
pip install supervisor
```

### 配置文件

创建配置文件 `/etc/supervisor/conf.d/qb-monitor.conf`：

```ini
[program:qb-monitor]
command=/opt/qb-monitor/venv/bin/python run.py

; 工作目录
directory=/opt/qb-monitor

; 环境变量
environment=QBIT_HOST="localhost",QBIT_PORT="8080",QBIT_USERNAME="admin",QBIT_PASSWORD="yourpassword",AI_ENABLED="false",CHECK_INTERVAL="1.0",LOG_LEVEL="INFO"

; 或者使用环境变量文件
; environment=PATH="/opt/qb-monitor/venv/bin"
; env_file=/opt/qb-monitor/.env

; 进程管理
user=qb-monitor
autostart=true
autorestart=true
startsecs=10
startretries=3

; 停止信号
stopsignal=TERM
stopwaitsecs=10

; 日志
stdout_logfile=/var/log/supervisor/qb-monitor.log
stderr_logfile=/var/log/supervisor/qb-monitor-error.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
stderr_logfile_maxbytes=10MB
stderr_logfile_backups=5

; 进程名
process_name=%(program_name)s
```

### 管理命令

```bash
# 重新加载配置
sudo supervisorctl reread
sudo supervisorctl update

# 启动程序
sudo supervisorctl start qb-monitor

# 停止程序
sudo supervisorctl stop qb-monitor

# 重启程序
sudo supervisorctl restart qb-monitor

# 查看状态
sudo supervisorctl status qb-monitor

# 查看所有程序状态
sudo supervisorctl status

# 查看日志
sudo tail -f /var/log/supervisor/qb-monitor.log

# 查看错误日志
sudo tail -f /var/log/supervisor/qb-monitor-error.log
```

---

## Python 虚拟环境部署

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 2. 创建虚拟环境
python3 -m venv venv

# 3. 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 4. 安装依赖
pip install -e .

# 5. 复制配置文件
cp config.example.json ~/.config/qb-monitor/config.json
# 编辑配置文件
nano ~/.config/qb-monitor/config.json

# 6. 运行
python run.py
```

### 后台运行

#### 使用 nohup

```bash
nohup python run.py > qb-monitor.log 2>&1 &
echo $! > qb-monitor.pid

# 停止
kill $(cat qb-monitor.pid)
```

#### 使用 screen

```bash
# 创建会话
screen -S qb-monitor

# 在会话中运行
python run.py

# 分离会话: Ctrl+A, D

# 重新连接
screen -r qb-monitor

# 停止
screen -X -S qb-monitor quit
```

#### 使用 tmux

```bash
# 创建会话
tmux new -s qb-monitor

# 在会话中运行
python run.py

# 分离会话: Ctrl+B, D

# 重新连接
tmux attach -t qb-monitor

# 停止
tmux kill-session -t qb-monitor
```

---

## Windows 服务部署

### 使用 NSSM（推荐）

NSSM（Non-Sucking Service Manager）是将任意程序作为 Windows 服务运行的工具。

#### 1. 下载 NSSM

```powershell
# 下载 NSSM
Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "nssm.zip"
Expand-Archive -Path "nssm.zip" -DestinationPath "C:\nssm"
```

#### 2. 安装服务

```powershell
# 创建服务
C:\nssm\nssm-2.24\win64\nssm.exe install qb-monitor

# 在弹出的窗口中设置:
# Path: C:\path\to\qb-monitor\venv\Scripts\python.exe
# Startup directory: C:\path\to\qb-monitor
# Arguments: run.py
```

或使用命令行：

```powershell
$pythonPath = "C:\path\to\qb-monitor\venv\Scripts\python.exe"
$workingDir = "C:\path\to\qb-monitor"

C:\nssm\nssm-2.24\win64\nssm.exe install qb-monitor $pythonPath
C:\nssm\nssm-2.24\win64\nssm.exe set qb-monitor Application $pythonPath
C:\nssm\nssm-2.24\win64\nssm.exe set qb-monitor AppDirectory $workingDir
C:\nssm\nssm-2.24\win64\nssm.exe set qb-monitor AppParameters run.py

# 设置环境变量
C:\nssm\nssm-2.24\win64\nssm.exe set qb-monitor AppEnvironmentExtra "QBIT_HOST=localhost" "QBIT_PORT=8080" "QBIT_USERNAME=admin" "QBIT_PASSWORD=yourpassword"
```

#### 3. 管理服务

```powershell
# 启动服务
net start qb-monitor

# 停止服务
net stop qb-monitor

# 删除服务
C:\nssm\nssm-2.24\win64\nssm.exe remove qb-monitor confirm

# 查看服务状态
sc query qb-monitor
```

---

## 部署对比

| 部署方式 | 难度 | 适用场景 | 优点 | 缺点 |
|---------|------|---------|------|------|
| Docker | 简单 | 所有环境 | 隔离性好、易于管理 | 需要 Docker 环境 |
| Docker Compose | 简单 | 生产环境 | 配置简洁、易于扩展 | 需要 Docker Compose |
| systemd | 中等 | Linux 物理机/VM | 原生集成、开机自启 | 仅支持 systemd 系统 |
| Supervisor | 中等 | 无 systemd 的系统 | 功能丰富、易于管理 | 需要额外安装 |
| Python venv | 简单 | 开发/测试 | 轻量级、易于调试 | 无进程管理 |
| NSSM | 中等 | Windows 服务器 | 原生 Windows 服务 | 仅 Windows |

---

## 安全建议

1. **使用环境变量存储敏感信息**
   - 不要将密码直接写入配置文件
   - 使用 `.env` 文件并确保权限正确（600）

2. **限制网络访问**
   - 使用防火墙限制 qBittorrent Web UI 访问
   - 仅允许必要的主机连接

3. **使用 HTTPS**
   - 生产环境启用 `QBIT_USE_HTTPS=true`
   - 配置有效的 SSL 证书

4. **定期更新**
   - 及时更新依赖包
   - 关注安全公告

5. **日志安全**
   - 项目已内置敏感信息过滤
   - 定期检查日志确保无敏感信息泄露
