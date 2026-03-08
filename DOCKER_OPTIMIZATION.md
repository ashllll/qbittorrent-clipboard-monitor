# Docker 配置优化说明

本文档详细说明 qbittorrent-clipboard-monitor 项目的 Docker 配置优化内容。

## 优化概览

| 优化项 | 原配置 | 优化后 | 改进效果 |
|--------|--------|--------|----------|
| 基础镜像 | `python:3.11-slim` (约 120MB) | `python:3.11-alpine` (约 50MB) | 镜像体积减少约 60% |
| 多架构支持 | 无 | amd64/arm64/armv7 | 支持更多平台 |
| 非 root 用户 | 有 (UID 随机) | 固定 UID/GID 1000 | 更好的权限管理 |
| 健康检查 | 基础导入检查 | 版本信息检查 | 更可靠的健康状态 |
| 构建缓存 | 单层构建 | 多阶段分离 | 更快的增量构建 |
| 安全选项 | 基础 | 只读文件系统 + 能力降级 | 更高的安全性 |

## 文件结构

```
.
├── Dockerfile              # 多阶段 Dockerfile
├── docker-compose.yml      # 完整编排配置
├── .dockerignore           # Docker 构建忽略文件
├── docker-build.sh         # 多架构构建脚本
└── DOCKER_OPTIMIZATION.md  # 本文档
```

## 快速开始

### 1. 本地构建

```bash
# 基础构建
./docker-build.sh build

# 构建特定标签
./docker-build.sh build -t v3.0.0

# 仅构建 ARM64 版本
./docker-build.sh build -p linux/arm64 -t arm64-latest
```

### 2. 使用 Docker Compose

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 开发模式（带热重载）
docker-compose --profile dev up -d qb-monitor-dev
```

### 3. 多架构构建并推送

```bash
# 推送到 Docker Hub
./docker-build.sh push -t v3.0.0 -r docker.io/yourusername

# 推送到私有仓库
./docker-build.sh push -t v3.0.0 -r registry.example.com/qb-monitor
```

## Dockerfile 详解

### 多阶段构建

```
┌─────────────────┐     ┌─────────────────┐
│  builder 阶段   │────▶│ production 阶段 │
│  (编译依赖)     │     │  (运行环境)     │
└─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │ development 阶段│
                        │  (开发调试)     │
                        └─────────────────┘
```

### 关键特性

1. **虚拟环境隔离**
   - 使用 Python venv 隔离依赖
   - 避免与系统 Python 冲突

2. **非 root 用户**
   - UID/GID 固定为 1000
   - 便于主机目录权限映射

3. **安全加固**
   - `no-new-privileges:true` - 禁止提升权限
   - `read_only: true` - 只读根文件系统
   - `cap_drop: ALL` - 移除所有能力
   - 临时目录使用 tmpfs

4. **健康检查**
   - 30秒间隔检查
   - 检测模块导入和版本
   - 10秒启动延迟避免误判

## Docker Compose 详解

### 服务配置

#### qb-monitor (生产模式)

- **自动重启**: `unless-stopped`
- **资源限制**: 最多 1 CPU / 512MB 内存
- **健康检查**: 30秒间隔，3次失败判定为不健康
- **日志轮转**: 10MB 单文件，最多 3 个备份

#### qb-monitor-dev (开发模式)

- **源码挂载**: 支持热重载
- **交互终端**: 便于调试
- **调试日志**: 默认 DEBUG 级别

### 网络配置

```yaml
networks:
  qb-monitor-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.25.0.0/16
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `QBIT_HOST` | localhost | qBittorrent 主机地址 |
| `QBIT_PORT` | 8080 | qBittorrent Web UI 端口 |
| `QBIT_USERNAME` | admin | 登录用户名 |
| `QBIT_PASSWORD` | - | 登录密码（必填） |
| `AI_ENABLED` | false | 是否启用 AI 分类 |
| `AI_API_KEY` | - | AI 服务 API 密钥 |
| `CHECK_INTERVAL` | 1.0 | 剪贴板检查间隔（秒）|
| `LOG_LEVEL` | INFO | 日志级别 |

## 构建参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `PYTHON_VERSION` | 3.11 | Python 版本 |
| `ALPINE_VERSION` | 3.19 | Alpine Linux 版本 |
| `APP_VERSION` | 3.0.0 | 应用版本号 |
| `BUILD_DATE` | - | 构建时间戳 |
| `VCS_REF` | - | Git 提交哈希 |

## 镜像大小对比

```bash
# 查看镜像大小
docker images qbittorrent-clipboard-monitor

# 典型结果
REPOSITORY                        TAG       SIZE
qbittorrent-clipboard-monitor     alpine    ~65MB
qbittorrent-clipboard-monitor     slim      ~145MB
```

## 安全建议

### 1. 敏感信息

使用 Docker Secrets 或环境变量文件：

```bash
# .env 文件（确保在 .gitignore 中）
QBIT_PASSWORD=your_secure_password
AI_API_KEY=your_api_key
```

### 2. 只读文件系统

生产环境启用 `read_only: true`，配合 tmpfs 处理临时文件。

### 3. 网络隔离

建议使用自定义网络，避免使用 `network_mode: host`：

```yaml
networks:
  qb-monitor-network:
    external: true  # 使用预先创建的网络
```

## 故障排查

### 健康检查失败

```bash
# 查看健康检查详情
docker inspect --format='{{.State.Health}}' qbittorrent-clipboard-monitor

# 手动执行健康检查
docker exec qbittorrent-clipboard-monitor python -c "from qbittorrent_monitor import __version__; print(__version__)"
```

### 权限问题

```bash
# 确保配置文件可读
docker exec qbittorrent-clipboard-monitor ls -la /app/config.json

# 检查用户 ID
docker exec qbittorrent-clipboard-monitor id
```

### 构建失败

```bash
# 清理缓存后重试
./docker-build.sh clean
./docker-build.sh build

# 详细输出
DOCKER_BUILDKIT=1 docker build --progress=plain .
```

## 性能优化

### 1. 构建缓存

- 依赖安装在代码复制之前
- 使用 `.dockerignore` 减少上下文

### 2. 运行时性能

- 资源限制防止资源耗尽
- 只读文件系统减少 I/O

### 3. 启动速度

- Alpine 基础镜像启动更快
- 健康检查 start_period 避免过早判定

## 更新日志

### v3.0.0 (2024)

- 初始优化版本
- 迁移到 Alpine 基础镜像
- 添加多架构构建支持
- 实现安全加固选项
