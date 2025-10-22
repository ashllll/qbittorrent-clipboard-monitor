# qBittorrent 剪贴板监控器 API 文档

## 概述

qBittorrent 剪贴板监控器提供了完整的 REST API，支持监控、配置管理和性能分析功能。

## 目录

- [配置管理 API](config.md)
- [剪贴板监控 API](clipboard.md)
- [qBittorrent 客户端 API](qbittorrent.md)
- [AI 分类器 API](ai_classifier.md)
- [性能监控 API](performance.md)
- [日志管理 API](logging.md)
- [WebSocket 实时 API](websocket.md)

## 基础信息

- **基础URL**: `http://localhost:8080/api/v1`
- **认证**: 暂不需要（可配置）
- **数据格式**: JSON
- **字符编码**: UTF-8

## 通用响应格式

所有API响应都遵循统一的格式：

```json
{
  "status": "success|error",
  "data": {}, // 具体数据
  "message": "可选的错误消息",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 错误响应格式

```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "details": {}
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 常见错误代码

| 错误代码 | HTTP状态码 | 描述 |
|---------|-----------|------|
| `INVALID_REQUEST` | 400 | 请求参数无效 |
| `UNAUTHORIZED` | 401 | 认证失败 |
| `FORBIDDEN` | 403 | 权限不足 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `METHOD_NOT_ALLOWED` | 405 | HTTP方法不允许 |
| `RATE_LIMITED` | 429 | 请求频率超限 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 |
| `SERVICE_UNAVAILABLE` | 503 | 服务不可用 |

## 分页格式

列表接口支持分页，使用以下参数：

- `page`: 页码（从1开始）
- `limit`: 每页数量（默认20，最大100）
- `sort`: 排序字段
- `order`: 排序方向（asc/desc）

分页响应格式：

```json
{
  "status": "success",
  "data": {
    "items": [], // 数据项列表
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 100,
      "pages": 5,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

## 时间格式

所有时间字段使用 ISO 8601 格式：
- 请求时间：`2024-01-01T12:00:00Z`
- 响应时间：`2024-01-01T12:00:00.123Z`

## 限流规则

- **请求频率**: 每分钟最多 100 次请求
- **并发连接**: 每个IP最多 10 个并发连接
- **数据大小**: 单次请求最大 10MB

## 版本控制

API 版本通过 URL 路径中的版本号控制：
- v1: `/api/v1/...` (当前版本)
- v2: `/api/v2/...` (未来版本)

## 开发和测试

### 本地开发

```bash
# 启动开发服务器
python -m qbittorrent_monitor.main

# API文档会在 http://localhost:8080/docs 访问
```

### 使用 Postman

可以导入提供的 Postman 集合文件 `qbittorrent-monitor-api.postman_collection.json`。

### 使用 curl

```bash
# 获取当前状态
curl -X GET http://localhost:8080/api/v1/status

# 更新配置
curl -X PUT http://localhost:8080/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{"check_interval": 5.0}'
```

## SDK 和客户端库

### Python

```python
from qbittorrent_monitor.api import QBittorrentMonitorAPI

api = QBittorrentMonitorAPI("http://localhost:8080")
status = api.get_status()
```

### JavaScript

```javascript
import { QBittorrentMonitorAPI } from 'qbittorrent-monitor-js';

const api = new QBittorrentMonitorAPI('http://localhost:8080');
const status = await api.getStatus();
```

## 贡献

如果您想为 API 文档做贡献，请查看项目仓库中的 `docs/api/` 目录，并提交 Pull Request。