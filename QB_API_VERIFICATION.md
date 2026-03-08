# qBittorrent 官方 Web API 验证文档

## 验证结论

✅ **所有操作均使用 qBittorrent 官方 Web API (v2)**

## 使用的官方 API 列表

### 1. 认证 API
```
POST /api/v2/auth/login
```
- **用途**: 用户登录，获取 Session Cookie
- **官方文档**: https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)#authentication
- **代码位置**: `qb_client.py:253`

### 2. 应用信息 API
```
GET /api/v2/app/version
```
- **用途**: 获取 qBittorrent 版本号
- **官方文档**: https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)#general-information
- **代码位置**: `qb_client.py:324`

### 3. 种子管理 API
```
POST /api/v2/torrents/add
```
- **用途**: 添加磁力链接或种子文件
- **参数**:
  - `urls`: 磁力链接（URL 编码）
  - `category`: 分类名称（可选）
  - `savepath`: 保存路径（可选）
- **官方文档**: https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)#torrent-management
- **代码位置**: `qb_client.py:370`

```
GET /api/v2/torrents/categories
```
- **用途**: 获取所有分类列表
- **官方文档**: https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)#torrent-management
- **代码位置**: `qb_client.py:416`

```
POST /api/v2/torrents/createCategory
```
- **用途**: 创建新分类
- **参数**:
  - `category`: 分类名称
  - `savePath`: 保存路径
- **官方文档**: https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)#torrent-management
- **代码位置**: `qb_client.py:458`

## API 请求格式验证

### 基础 URL 构造
```python
def _get_full_url(self, endpoint: str) -> str:
    return f"{self.base_url}/api/v2{endpoint}"
```
✅ 符合官方 API 路径格式: `http://<host>:<port>/api/v2<endpoint>`

### 认证流程
```python
# 1. 发送登录请求
POST /api/v2/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin

# 2. 接收并存储 Session Cookie (SID)
Set-Cookie: SID=<session_id>; HttpOnly; path=/

# 3. 后续请求自动携带 Cookie
```
✅ 符合官方认证流程

### 添加磁力链接请求
```python
POST /api/v2/torrents/add
Content-Type: application/x-www-form-urlencoded

urls=magnet%3A%3Fxt%3Durn%3Abtih%3A...&category=movies&savepath=%2Fdownloads%2Fmovies
```
✅ 符合官方请求格式

## 验证方法

### 1. 查看源码中的 API 调用
```bash
grep -n "endpoint = " qbittorrent_monitor/qb_client.py
```

### 2. 测试 API 可用性
```bash
# 登录
curl -X POST http://192.168.1.69:8085/api/v2/auth/login \
  -d "username=admin" \
  -d "password=admin" \
  -c cookies.txt

# 获取版本
curl -b cookies.txt http://192.168.1.69:8085/api/v2/app/version

# 获取分类
curl -b cookies.txt http://192.168.1.69:8085/api/v2/torrents/categories
```

## 非官方操作检查

❌ **未发现任何非官方操作**:
- 未直接操作 qBittorrent 数据库
- 未修改 qBittorrent 配置文件
- 未使用第三方协议或接口
- 所有操作均通过 HTTP API 完成

## 官方 API 文档参考

- **完整 API 文档**: https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)
- **API 版本**: v2 (qBittorrent 4.1+)
- **基础路径**: `/api/v2`

## 代码文件

所有 API 调用封装在:
- **文件**: `qbittorrent_monitor/qb_client.py`
- **类**: `QBClient`
- **方法**:
  - `_login()` - 认证
  - `get_version()` - 获取版本
  - `add_torrent()` - 添加种子
  - `get_categories()` - 获取分类
  - `create_category()` - 创建分类
  - `ensure_categories()` - 确保分类存在（组合调用）
