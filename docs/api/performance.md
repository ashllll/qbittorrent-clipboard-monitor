# 性能监控 API

性能监控 API 提供了系统性能指标收集、查询和分析功能。

## 基础端点

- **基础URL**: `/api/v1/performance`

## 获取当前性能统计

```http
GET /api/v1/performance/stats
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "cpu": {
      "percent": 45.2,
      "cores": 8,
      "frequency": 2400
    },
    "memory": {
      "total": 8589934592,
      "available": 4294967296,
      "used": 4294967296,
      "percent": 50.0,
      "cached": 1073741824
    },
    "disk": {
      "total": 107374182400,
      "free": 53687091200,
      "used": 53687091200,
      "percent": 50.0,
      "read_bytes": 1073741824,
      "write_bytes": 536870912
    },
    "network": {
      "bytes_sent": 1048576000,
      "bytes_recv": 2097152000,
      "packets_sent": 10000,
      "packets_recv": 15000
    },
    "processes": {
      "total": 150,
      "running": 145,
      "sleeping": 3,
      "zombie": 2
    },
    "connections": {
      "active": 25,
      "listening": 10,
      "established": 20
    },
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

## 获取性能历史数据

```http
GET /api/v1/performance/history
```

### 查询参数

- `minutes`: 时间范围（分钟），默认60分钟
- `interval`: 数据间隔（秒），默认60秒
- `metrics`: 指定指标，多个用逗号分隔，默认所有指标

### 响应示例

```json
{
  "status": "success",
  "data": {
    "metrics": [
      {
        "timestamp": "2024-01-01T12:00:00Z",
        "cpu_percent": 45.2,
        "memory_percent": 50.1,
        "disk_usage_percent": 60.5,
        "network_bytes_sent": 1048576000,
        "network_bytes_recv": 2097152000
      },
      {
        "timestamp": "2024-01-01T12:01:00Z",
        "cpu_percent": 43.8,
        "memory_percent": 49.9,
        "disk_usage_percent": 60.5,
        "network_bytes_sent": 1056969600,
        "network_bytes_recv": 2107648000
      }
    ],
    "summary": {
      "avg_cpu": 44.5,
      "max_cpu": 45.2,
      "min_cpu": 43.8,
      "avg_memory": 50.0,
      "max_memory": 50.1,
      "min_memory": 49.9
    }
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 获取指标摘要

```http
GET /api/v1/performance/summary
```

### 查询参数

- `period`: 时间周期（`1h`, `6h`, `24h`, `7d`），默认1h
- `metrics`: 指定指标，默认所有核心指标

### 响应示例

```json
{
  "status": "success",
  "data": {
    "period": "1h",
    "cpu": {
      "current": 45.2,
      "average": 44.8,
      "maximum": 67.1,
      "minimum": 12.3,
      "trend": "stable"
    },
    "memory": {
      "current": 50.0,
      "average": 49.5,
      "maximum": 78.2,
      "minimum": 23.1,
      "trend": "increasing"
    },
    "disk": {
      "current": 60.5,
      "average": 60.2,
      "maximum": 85.3,
      "minimum": 45.1,
      "trend": "stable"
    },
    "network": {
      "throughput_upload": 1048576,  // bytes/sec
      "throughput_download": 2097152,
      "total_upload": 1048576000,
      "total_download": 2097152000
    },
    "alerts": {
      "total": 3,
      "critical": 1,
      "warning": 2
    }
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 获取告警列表

```http
GET /api/v1/performance/alerts
```

### 查询参数

- `level`: 告警级别（`info`, `warning`, `critical`），可选
- `type`: 告警类型（`cpu`, `memory`, `disk`, `network`），可选
- `limit`: 返回数量，默认20
- `resolved`: 是否包含已解决告警（`true`/`false`）

### 响应示例

```json
{
  "status": "success",
  "data": {
    "alerts": [
      {
        "id": "alert_001",
        "type": "cpu",
        "level": "warning",
        "title": "CPU使用率过高",
        "message": "CPU使用率达到 85%，建议检查进程",
        "value": 85.2,
        "threshold": 80.0,
        "status": "active",
        "created_at": "2024-01-01T12:00:00Z",
        "updated_at": "2024-01-01T12:05:00Z",
        "resolved_at": null,
        "metadata": {
          "affected_processes": ["python", "qbittorrent"],
          "suggestion": "检查高CPU使用率进程"
        }
      },
      {
        "id": "alert_002",
        "type": "memory",
        "level": "critical",
        "title": "内存不足",
        "message": "可用内存低于 10%",
        "value": 95.8,
        "threshold": 90.0,
        "status": "resolved",
        "created_at": "2024-01-01T11:55:00Z",
        "updated_at": "2024-01-01T11:58:00Z",
        "resolved_at": "2024-01-01T11:58:00Z"
      }
    ],
    "summary": {
      "total": 2,
      "active": 1,
      "resolved": 1,
      "by_level": {
        "critical": 1,
        "warning": 1,
        "info": 0
      }
    }
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 添加自定义指标

```http
POST /api/v1/performance/metrics
```

### 请求体

```json
{
  "name": "custom_api_calls",
  "value": 150,
  "unit": "count",
  "category": "business",
  "tags": {
    "service": "api",
    "endpoint": "/api/v1/config"
  }
}
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "metric_id": "metric_001",
    "created_at": "2024-01-01T12:00:00Z"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 批量添加指标

```http
POST /api/v1/performance/metrics/batch
```

### 请求体

```json
{
  "metrics": [
    {
      "name": "api_response_time",
      "value": 150,
      "unit": "ms",
      "category": "performance"
    },
    {
      "name": "api_requests_count",
      "value": 25,
      "unit": "count",
      "category": "business"
    }
  ]
}
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "accepted": 2,
    "rejected": 0,
    "metric_ids": ["metric_002", "metric_003"]
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 设置告警规则

```http
POST /api/v1/performance/alerts/rules
```

### 请求体

```json
{
  "name": "high_cpu_usage",
  "metric": "cpu_percent",
  "operator": "greater_than",
  "threshold": 80.0,
  "level": "warning",
  "description": "CPU使用率过高",
  "enabled": true,
  "actions": ["log", "webhook"],
  "cooldown": 300 // 5分钟冷却期
}
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "rule_id": "rule_001",
    "created_at": "2024-01-01T12:00:00Z"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 获取告警规则

```http
GET /api/v1/performance/alerts/rules
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "rules": [
      {
        "id": "rule_001",
        "name": "high_cpu_usage",
        "metric": "cpu_percent",
        "operator": "greater_than",
        "threshold": 80.0,
        "level": "warning",
        "enabled": true,
        "created_at": "2024-01-01T12:00:00Z",
        "trigger_count": 5,
        "last_triggered": "2024-01-01T11:55:00Z"
      }
    ]
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 生成性能报告

```http
POST /api/v1/performance/reports
```

### 请求体

```json
{
  "type": "summary", // "summary", "detailed", "custom"
  "period": "24h",
  "format": "json", // "json", "pdf", "csv"
  "metrics": ["cpu", "memory", "disk"],
  "include_alerts": true,
  "include_recommendations": true
}
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "report_id": "report_001",
    "download_url": "/api/v1/performance/reports/report_001/download",
    "estimated_ready_time": "2024-01-01T12:02:00Z"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 获取系统信息

```http
GET /api/v1/performance/system
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "hostname": "monitor-server",
    "platform": "Linux",
    "platform_version": "5.15.0-52-generic",
    "architecture": "x86_64",
    "python_version": "3.9.7",
    "cpu_info": {
      "model": "Intel(R) Core(TM) i7-9700K CPU @ 3.60GHz",
      "cores": 8,
      "threads": 8,
      "frequency": 3600,
      "cache_size": 12288
    },
    "memory_info": {
      "total": 8589934592,
      "available": 4294967296,
      "swap_total": 4294967296,
      "swap_available": 4294967296
    },
    "disk_info": [
      {
        "device": "/dev/sda1",
        "mountpoint": "/",
        "total": 107374182400,
        "free": 53687091200,
        "filesystem": "ext4"
      }
    ],
    "network_info": [
      {
        "interface": "eth0",
        "ip_address": "192.168.1.100",
        "mac_address": "00:11:22:33:44:55",
        "is_up": true
      }
    ],
    "uptime": 86400,
    "load_average": [0.5, 0.3, 0.2]
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 解决告警

```http
POST /api/v1/performance/alerts/{alert_id}/resolve
```

### 请求体

```json
{
  "resolution": "Issue resolved by restarting service",
  "resolved_by": "admin"
}
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "resolved": true,
    "resolved_at": "2024-01-01T12:05:00Z"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 错误代码

| 错误代码 | 描述 |
|---------|------|
| `METRIC_NOT_FOUND` | 指标不存在 |
| `INVALID_METRIC_VALUE` | 无效的指标值 |
| `RULE_CREATION_FAILED` | 告警规则创建失败 |
| `RULE_NOT_FOUND` | 告警规则不存在 |
| `REPORT_GENERATION_FAILED` | 报告生成失败 |
| `SYSTEM_INFO_UNAVAILABLE` | 系统信息不可用 |

## 使用示例

### Python SDK

```python
from qbittorrent_monitor.api import QBittorrentMonitorAPI

api = QBittorrentMonitorAPI("http://localhost:8080")

# 获取当前性能统计
stats = api.get_performance_stats()

# 获取历史数据
history = api.get_performance_history(minutes=60)

# 添加自定义指标
api.add_metric("custom_requests", 100, unit="count")

# 设置告警规则
api.set_alert_rule("high_memory", "memory_percent", ">", 80, "warning")
```

### JavaScript

```javascript
import { QBittorrentMonitorAPI } from 'qbittorrent-monitor-js';

const api = new QBittorrentMonitorAPI('http://localhost:8080');

// 获取性能统计
const stats = await api.getPerformanceStats();

// 获取历史数据
const history = await api.getPerformanceHistory({ minutes: 60 });

// 添加指标
await api.addMetric({
  name: 'custom_requests',
  value: 100,
  unit: 'count'
});
```

## WebSocket 实时事件

连接到 `/ws/performance` 可以接收实时性能更新：

```javascript
const ws = new WebSocket('ws://localhost:8080/ws/performance');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.type) {
    case 'metric_update':
      updateMetricDisplay(data.metric);
      break;
    case 'alert_triggered':
      showAlert(data.alert);
      break;
  }
};
```

### 事件类型

- `metric_update`: 新的指标数据
- `alert_triggered`: 新的告警触发
- `alert_resolved`: 告警已解决
- `system_change`: 系统状态变化