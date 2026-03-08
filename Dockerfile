# qBittorrent Clipboard Monitor - 优化版 Docker 镜像
# 特性：多阶段构建、Alpine 基础镜像、多架构支持、非 root 用户

# ============================================================================
# 构建参数
# ============================================================================
ARG PYTHON_VERSION=3.11
ARG ALPINE_VERSION=3.19

# ============================================================================
# 依赖构建阶段
# ============================================================================
FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS builder

# 构建参数
ARG TARGETARCH
ARG TARGETVARIANT

# 安装编译依赖
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    libffi-dev \
    openssl-dev

# 创建虚拟环境（更好的隔离性）
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 升级 pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 复制依赖定义
COPY pyproject.toml .

# 安装 Python 依赖（分离层以优化缓存）
RUN pip install --no-cache-dir \
    aiohttp>=3.11 \
    openai>=1.76 \
    pyperclip>=1.9

# ============================================================================
# 生产运行阶段
# ============================================================================
FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS production

# 构建参数
ARG APP_VERSION=3.0.0
ARG BUILD_DATE
ARG VCS_REF

# 元数据标签
LABEL maintainer="qBittorrent Monitor Team" \
      org.opencontainers.image.title="qBittorrent Clipboard Monitor" \
      org.opencontainers.image.description="简洁高效的 qBittorrent 剪贴板监控工具" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/qbittorrent-clipboard-monitor"

# 创建非 root 用户和组
RUN addgroup -g 1000 -S appgroup && \
    adduser -u 1000 -S appuser -G appgroup

# 安装运行时依赖（pyperclip 可能需要 xclip/xsel）
RUN apk add --no-cache \
    libffi \
    openssl \
    ca-certificates \
    tzdata \
    xclip \
    xsel

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 设置工作目录
WORKDIR /app

# 复制应用代码（分层优化缓存）
COPY --chown=appuser:appgroup qbittorrent_monitor/ ./qbittorrent_monitor/
COPY --chown=appuser:appgroup run.py .

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 设置文件权限
RUN chmod -R 755 /app && \
    chmod +x run.py

# 切换到非 root 用户
USER appuser:appgroup

# 健康检查（使用 Python 直接检查模块导入和版本信息）
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "
import sys;
from qbittorrent_monitor import __version__;
print(f'OK - v{__version__}');
sys.exit(0)
" || exit 1

# 启动命令
ENTRYPOINT ["python", "run.py"]
CMD ["--log-level", "INFO"]

# ============================================================================
# 开发调试阶段（可选，包含更多工具）
# ============================================================================
FROM production AS development

USER root

# 安装开发工具
RUN apk add --no-cache \
    bash \
    curl \
    vim \
    procps

# 重新切换回非 root 用户
USER appuser:appgroup

# 开发模式默认命令
CMD ["--log-level", "DEBUG"]
