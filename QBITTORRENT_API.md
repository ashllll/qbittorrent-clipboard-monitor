# qBittorrent Web API 使用说明

本项目所有 qBittorrent 操作均使用官方 Web API (v2)。

## 使用的官方 API 端点

### 认证
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v2/auth/login` | POST | 登录获取 Session Cookie |

### 应用信息
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v2/app/version` | GET | 获取 qBittorrent 版本 |

### 种子管理
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v2/torrents/add` | POST | 添加种子（磁力链接或文件） |
| `/api/v2/torrents/categories` | GET | 获取所有分类 |
| `/api/v2/torrents/createCategory` | POST | 创建新分类 |

## 官方文档参考

- qBittorrent Web API 文档: https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)
- API 基础路径: `http://<host>:<port>/api/v2`

## 请求格式

### 认证
```bash
POST /api/v2/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin
```

响应:
- `Ok.` - 登录成功
- `Fails.` - 登录失败

### 添加磁力链接
```bash
POST /api/v2/torrents/add
Content-Type: application/x-www-form-urlencoded

urls=magnet%3A%3Fxt%3Durn%3Abtih%3A...&category=movies&savepath=%2Fdownloads%2Fmovies
```

参数:
- `urls` - 磁力链接（URL 编码）
- `category` - 分类名称（可选）
- `savepath` - 保存路径（可选）

### 获取分类
```bash
GET /api/v2/torrents/categories
```

响应示例:
```json
{
  "movies": {
    "name": "movies",
    "savePath": "/downloads/movies"
  },
  "tv": {
    "name": "tv", 
    "savePath": "/downloads/tv"
  }
}
```

### 创建分类
```bash
POST /api/v2/torrents/createCategory
Content-Type: application/x-www-form-urlencoded

category=movies&savePath=%2Fdownloads%2Fmovies
```

## 实现代码位置

所有 API 调用封装在 `qbittorrent_monitor/qb_client.py`:

- `QBClient._login()` - 认证
- `QBClient.get_version()` - 获取版本
- `QBClient.add_torrent()` - 添加种子
- `QBClient.get_categories()` - 获取分类
- `QBClient.create_category()` - 创建分类
- `QBClient.ensure_categories()` - 确保分类存在

## 特点

✅ 100% 使用官方标准 API  
✅ 支持 API 错误处理和重试  
✅ 完整的日志记录  
✅ 性能指标监控  
✅ Cookie 会话管理  
