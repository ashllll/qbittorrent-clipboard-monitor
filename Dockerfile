# 多阶段构建
FROM python:3.9-slim as builder

# 设置工作目录
WORKDIR /app

# 安装Poetry
RUN pip install poetry

# 复制项目配置文件
COPY pyproject.toml poetry.lock* ./

# 配置Poetry
RUN poetry config virtualenvs.create false

# 安装依赖
RUN poetry install --no-dev --no-root

# 生产阶段
FROM python:3.9-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 创建非root用户
RUN useradd --create-home --shell /bin/bash qbmonitor

# 设置工作目录
WORKDIR /app

# 从builder阶段复制Python环境
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY qbittorrent_monitor/ ./qbittorrent_monitor/
COPY README.md ./

# 创建必要的目录
RUN mkdir -p /app/logs /app/config && \
    chown -R qbmonitor:qbmonitor /app

# 切换到非root用户
USER qbmonitor

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

# 暴露端口（如果启用Web UI）
EXPOSE 8080

# 启动命令
CMD ["python", "-m", "qbittorrent_monitor.main", "start"] 