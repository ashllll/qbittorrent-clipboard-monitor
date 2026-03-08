# Prometheus 指标导出

qBittorrent Clipboard Monitor 内置了 Prometheus 指标导出功能，可以方便地监控应用运行状态。

## 快速开始

### 1. 使用 Docker Compose（推荐）

```bash
# 启动完整监控栈
docker-compose -f docker-compose.monitoring.yml up -d

# 访问各服务
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9091
# 指标端点: http://localhost:9090/metrics
```

### 2. 本地运行

```bash
# 安装依赖
pip install prometheus-client

# 启动应用（默认启用指标导出）
python run.py

# 访问指标端点
curl http://localhost:9090/metrics
```

## 配置说明

### 配置文件 (config.json)

```json
{
  "metrics": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 9090,
    "path": "/metrics"
  }
}
```

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `METRICS_ENABLED` | `true` | 是否启用指标导出 |
| `METRICS_HOST` | `0.0.0.0` | 监听地址 |
| `METRICS_PORT` | `9090` | 监听端口 |
| `METRICS_PATH` | `/metrics` | 指标端点路径 |

## 指标列表

### Counter（计数器）

| 指标名称 | 标签 | 说明 |
|----------|------|------|
| `qbmonitor_torrents_processed_total` | category | 处理的磁力链接总数 |
| `qbmonitor_torrents_added_success_total` | category | 成功添加的种子数 |
| `qbmonitor_torrents_added_failed_total` | category, reason | 添加失败的种子数 |
| `qbmonitor_duplicates_skipped_total` | reason | 跳过的重复种子数 |
| `qbmonitor_clipboard_changes_total` | - | 剪贴板内容变化次数 |
| `qbmonitor_api_calls_total` | endpoint, status | API 调用次数 |
| `qbmonitor_classifications_total` | method, category | 分类操作次数 |

### Gauge（仪表盘）

| 指标名称 | 说明 |
|----------|------|
| `qbmonitor_monitor_running` | 监控器运行状态 (1=运行中, 0=停止) |
| `qbmonitor_clipboard_check_interval_seconds` | 当前检查间隔（秒） |
| `qbmonitor_cache_size` | 缓存大小 |
| `qbmonitor_cache_hit_rate` | 缓存命中率 (0.0-1.0) |
| `qbmonitor_pending_magnets` | 待处理的磁力链接数 |
| `qbmonitor_processed_magnets_count` | 已处理的磁力链接数 |
| `qbmonitor_ai_client_available` | AI 客户端可用状态 |
| `qbmonitor_qbittorrent_connected` | qBittorrent 连接状态 |

### Histogram（直方图）

| 指标名称 | 说明 |
|----------|------|
| `qbmonitor_clipboard_check_duration_seconds` | 剪贴板检查耗时 |
| `qbmonitor_torrent_add_duration_seconds` | 种子添加耗时 |
| `qbmonitor_classify_duration_seconds` | 分类耗时 |
| `qbmonitor_api_call_duration_seconds` | API 调用耗时 |

## Prometheus 配置

将以下内容添加到 `prometheus.yml`：

```yaml
scrape_configs:
  - job_name: 'qbittorrent-monitor'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 10s
```

## Grafana 仪表板

### 导入仪表板

1. 打开 Grafana (http://localhost:3000)
2. 导航到 **Dashboards** → **Import**
3. 上传 `grafana-dashboard.json` 文件
4. 选择 Prometheus 数据源

### 仪表板面板

- **系统概览**: 运行状态、处理总数、成功/失败数
- **处理趋势**: 按分类的速率图、成功率/失败率
- **性能指标**: 各项操作的 P95/P50/平均耗时
- **缓存与资源**: 缓存大小、命中率
- **分类统计**: 分类分布、分类方法、跳过原因

## 告警规则示例

```yaml
groups:
  - name: qbittorrent-monitor
    rules:
      - alert: MonitorDown
        expr: qbmonitor_monitor_running == 0
        for: 1m
        annotations:
          summary: "qBittorrent Monitor 已停止"
          
      - alert: QBDisconnected
        expr: qbmonitor_qbittorrent_connected == 0
        for: 2m
        annotations:
          summary: "qBittorrent 连接断开"
          
      - alert: HighFailureRate
        expr: |
          rate(qbmonitor_torrents_added_failed_total[5m]) /
          rate(qbmonitor_torrents_processed_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "种子添加失败率超过 10%"
```

## 自定义指标

在代码中使用指标模块：

```python
from qbittorrent_monitor import metrics

# 记录自定义事件
metrics.record_torrent_processed(category="custom")

# 使用计时器
with metrics.timed_api_call(endpoint="/custom"):
    # 你的代码
    pass

# 设置 gauge 值
metrics.set_cache_size("custom", 100)
```

## 故障排查

### 指标端点无法访问

1. 检查端口是否被占用：`lsof -i :9090`
2. 检查防火墙设置
3. 确认 `METRICS_ENABLED=true`

### 指标值为空

1. 检查指标收集是否启用
2. 查看应用日志确认指标是否正常记录
3. 使用 `curl http://localhost:9090/metrics` 直接访问

### Prometheus 抓取失败

1. 确认目标地址可访问
2. 检查 `prometheus.yml` 配置
3. 查看 Prometheus 的 Targets 页面
