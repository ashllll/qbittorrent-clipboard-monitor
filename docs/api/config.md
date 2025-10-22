# 配置管理 API

配置管理 API 提供了对应用配置的完整访问和管理功能。

## 基础端点

- **基础URL**: `/api/v1/config`

## 获取配置

```http
GET /api/v1/config
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "qbittorrent": {
      "host": "localhost",
      "port": 8080,
      "username": "admin",
      "use_https": false,
      "verify_ssl": true
    },
    "deepseek": {
      "api_key": "sk-xxx",
      "model": "deepseek-chat",
      "base_url": "https://api.deepseek.com"
    },
    "categories": {
      "电影": {
        "savePath": "/downloads/movies",
        "keywords": ["电影", "movie"],
        "description": "电影类内容"
      }
    },
    "check_interval": 1.0,
    "log_level": "INFO",
    "log_file": "qbittorrent_monitor.log"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 更新配置

```http
PUT /api/v1/config
```

### 请求体

```json
{
  "qbittorrent": {
    "host": "localhost",
    "port": 8080
  },
  "check_interval": 2.0
}
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "updated_fields": ["qbittorrent.host", "qbittorrent.port", "check_interval"],
    "config_version": "2024-01-01T12:00:00Z"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 重载配置

```http
POST /api/v1/config/reload
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "reloaded": true,
    "previous_version": "2024-01-01T10:00:00Z",
    "current_version": "2024-01-01T12:00:00Z"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 验证配置

```http
POST /api/v1/config/validate
```

### 请求体

```json
{
  "config": {
    "qbittorrent": {
      "host": "localhost",
      "port": 8080
    }
  }
}
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "valid": true,
    "errors": [],
    "warnings": [
      {
        "field": "log_level",
        "message": "建议设置为 WARNING 以减少日志噪音"
      }
    ]
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 获取配置模板

```http
GET /api/v1/config/templates
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "templates": [
      {
        "name": "default",
        "description": "默认配置模板",
        "config": {
          "qbittorrent": {
            "host": "localhost",
            "port": 8080
          }
        }
      },
      {
        "name": "production",
        "description": "生产环境配置",
        "config": {
          "log_level": "WARNING",
          "check_interval": 5.0
        }
      }
    ]
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 导出配置

```http
GET /api/v1/config/export
```

### 查询参数

- `format`: 导出格式（`json`, `yaml`, `toml`）

### 响应

直接返回配置文件内容，Content-Type 根据格式设置。

## 导入配置

```http
POST /api/v1/config/import
```

### 请求体

Content-Type: `multipart/form-data`

- `file`: 配置文件
- `format`: 文件格式（可选）
- `merge`: 是否与现有配置合并（`true`/`false`）

### 响应示例

```json
{
  "status": "success",
  "data": {
    "imported": true,
    "merged": false,
    "fields_imported": 15,
    "validation_errors": []
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 重置配置

```http
POST /api/v1/config/reset
```

### 请求体

```json
{
  "section": "qbittorrent" // 可选，重置特定部分
}
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "reset": true,
    "reset_sections": ["qbittorrent"],
    "backup_created": true
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 配置历史

```http
GET /api/v1/config/history
```

### 查询参数

- `limit`: 返回的历史记录数量（默认10）
- `page`: 页码（默认1）

### 响应示例

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "version": "2024-01-01T12:00:00Z",
        "changes": [
          {
            "field": "check_interval",
            "old_value": 1.0,
            "new_value": 2.0
          }
        ],
        "author": "system",
        "timestamp": "2024-01-01T12:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 10,
      "total": 25,
      "pages": 3
    }
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 配置备份

```http
POST /api/v1/config/backup
```

### 请求体

```json
{
  "name": "backup_20240101", // 可选，备份名称
  "description": "配置备份" // 可选，备份描述
}
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "backup_id": "backup_20240101",
    "filename": "backup_20240101_120000.json",
    "size": 2048,
    "created_at": "2024-01-01T12:00:00Z"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 恢复配置备份

```http
POST /api/v1/config/restore
```

### 请求体

```json
{
  "backup_id": "backup_20240101"
}
```

### 响应示例

```json
{
  "status": "success",
  "data": {
    "restored": true,
    "backup_id": "backup_20240101",
    "requires_restart": true
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 错误代码

| 错误代码 | 描述 |
|---------|------|
| `CONFIG_NOT_FOUND` | 配置文件不存在 |
| `CONFIG_INVALID` | 配置格式无效 |
| `CONFIG_VALIDATION_FAILED` | 配置验证失败 |
| `CONFIG_UPDATE_FAILED` | 配置更新失败 |
| `BACKUP_NOT_FOUND` | 备份文件不存在 |
| `BACKUP_RESTORE_FAILED` | 备份恢复失败 |
| `TEMPLATE_NOT_FOUND` | 配置模板不存在 |

## 使用示例

### Python SDK

```python
from qbittorrent_monitor.api import QBittorrentMonitorAPI

api = QBittorrentMonitorAPI("http://localhost:8080")

# 获取当前配置
config = api.get_config()

# 更新配置
api.update_config({
    "check_interval": 5.0,
    "log_level": "DEBUG"
})

# 重载配置
api.reload_config()
```

### JavaScript

```javascript
import { QBittorrentMonitorAPI } from 'qbittorrent-monitor-js';

const api = new QBittorrentMonitorAPI('http://localhost:8080');

// 获取配置
const config = await api.getConfig();

// 更新配置
await api.updateConfig({
    checkInterval: 5.0,
    logLevel: 'DEBUG'
});
```