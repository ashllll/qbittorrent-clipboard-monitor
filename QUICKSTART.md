# 快速启动指南

## 配置已更新

qBittorrent 服务器地址已设置为: **http://192.168.1.69:8085**

## 设置密码

需要更新配置文件中的密码：

```bash
# 编辑配置文件
nano ~/.config/qb-monitor/config.json
```

找到 `qbittorrent` 部分，修改 `password`：

```json
{
  "qbittorrent": {
    "host": "192.168.1.69",
    "port": 8085,
    "username": "admin",
    "password": "你的实际密码",
    "use_https": false
  }
}
```

## 启动程序

### 方式1: Web 管理界面（推荐）

```bash
python3 run.py --web --web-port 8888
```

然后访问: http://127.0.0.1:8888

### 方式2: 剪贴板监控模式

```bash
python3 run.py
```

## Web 界面功能

- 📊 仪表盘 - 查看统计信息
- 📋 历史记录 - 查看已处理的磁力链接
- 🏷️ 分类管理 - 管理分类规则
- ⚙️ 配置管理 - 修改配置
- 📝 实时日志 - 查看运行日志

## API 端点

```
GET  /api/stats      - 获取统计
GET  /api/categories - 获取分类
GET  /api/history    - 获取历史记录
GET  /api/config     - 获取配置
POST /api/torrents   - 手动添加磁力链接
```

## Prometheus 指标

```
http://localhost:9090/metrics
```

## 验证连接

```bash
# 测试 qBittorrent 连接
curl http://192.168.1.69:8085/api/v2/app/version
```

## 常见问题

1. **连接失败**: 检查密码是否正确，qBittorrent Web UI 是否启用
2. **端口占用**: 更换 `--web-port` 参数使用其他端口
3. **权限错误**: 确保 qBittorrent 允许远程连接

## 更多信息

- 完整文档: docs/
- API 文档: docs/api.md
- 部署指南: docs/deployment.md
