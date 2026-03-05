# qBittorrent Clipboard Monitor - Docker 镜像
# 多阶段构建优化镜像大小

# ============================================================================
# 构建阶段
# ============================================================================
FROM python:3.11-slim as builder

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY pyproject.toml ./

# 安装 Python 依赖
RUN pip install --no-cache-dir --user \
    aiohttp>=3.11 \
    openai>=1.76 \
    pyperclip>=1.9

# ============================================================================
# 生产阶段
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 从构建阶段复制依赖
COPY --from=builder /root/.local /home/appuser/.local

# 复制应用代码
COPY qbittorrent_monitor/ ./qbittorrent_monitor/
COPY run.py .

# 设置环境变量
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO

# 设置文件权限
RUN chown -R appuser:appuser /app

# 切换到非 root 用户
USER appuser

# 暴露端口（可选，用于健康检查）
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import qbittorrent_monitor; print('OK')" || exit 1

# 启动命令
ENTRYPOINT ["python", "run.py"]
