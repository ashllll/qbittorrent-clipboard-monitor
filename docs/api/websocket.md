# WebSocket 实时 API

WebSocket API 提供了实时数据推送功能，支持性能监控、告警通知和状态更新。

## 连接端点

### 主连接端点

```
ws://localhost:8080/ws
```

### 专用连接端点

```
ws://localhost:8080/ws/performance  // 性能监控
ws://localhost:8080/ws/alerts       // 告警通知
ws://localhost:8080/ws/status        // 状态更新
```

## 连接认证

```javascript
const ws = new WebSocket('ws://localhost:8080/ws', [], {
  headers: {
    'Authorization': 'Bearer your-api-key',
    'X-Client-ID': 'your-client-id'
  }
});
```

## 消息格式

所有 WebSocket 消息都使用统一格式：

```json
{
  "type": "message_type",
  "id": "unique_message_id",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {}, // 具体数据
  "meta": {} // 元数据
}
```

## 消息类型

### 1. 连接状态 (connection)

#### 连接确认

```json
{
  "type": "connection",
  "id": "conn_001",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "status": "connected",
    "client_id": "client_12345",
    "server_time": "2024-01-01T12:00:00Z"
  }
}
```

#### 连接错误

```json
{
  "type": "connection",
  "id": "conn_error_001",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "status": "error",
    "error_code": "AUTH_FAILED",
    "message": "认证失败"
  }
}
```

### 2. 性能更新 (performance)

#### 系统指标更新

```json
{
  "type": "performance",
  "id": "perf_001",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "cpu_percent": 45.2,
    "memory_percent": 67.8,
    "disk_usage_percent": 55.1,
    "network_io": {
      "bytes_sent": 1048576000,
      "bytes_recv": 2097152000
    },
    "process_count": 125
  }
}
```

#### 自定义指标更新

```json
{
  "type": "performance",
  "id": "perf_002",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "metric_name": "api_response_time",
    "value": 150,
    "unit": "ms",
    "category": "performance",
    "tags": {
      "endpoint": "/api/v1/config",
      "method": "GET"
    }
  }
}
```

### 3. 告警事件 (alert)

#### 告警触发

```json
{
  "type": "alert",
  "id": "alert_001",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "alert_id": "alert_12345",
    "type": "cpu",
    "level": "warning",
    "title": "CPU使用率过高",
    "message": "CPU使用率达到 85%，建议检查进程",
    "value": 85.2,
    "threshold": 80.0,
    "status": "active",
    "metadata": {
      "affected_processes": ["python", "qbittorrent"],
      "suggestion": "检查高CPU使用率进程"
    }
  }
}
```

#### 告警解决

```json
{
  "type": "alert",
  "id": "alert_002",
  "timestamp": "2024-01-01T12:05:00Z",
  "data": {
    "alert_id": "alert_12345",
    "type": "cpu",
    "level": "warning",
    "status": "resolved",
    "resolved_at": "2024-01-01T12:05:00Z",
    "resolution": "Issue resolved by restarting service",
    "resolved_by": "admin"
  }
}
```

### 4. 状态更新 (status)

#### 应用状态变化

```json
{
  "type": "status",
  "id": "status_001",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "component": "clipboard_monitor",
    "status": "running",
    "last_check": "2024-01-01T11:59:00Z",
    "details": {
      "processed_count": 25,
      "successful_adds": 23,
      "failed_adds": 2
    }
  }
}
```

#### qBittorrent 连接状态

```json
{
  "type": "status",
  "id": "status_002",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "component": "qbittorrent_client",
    "status": "connected",
    "connection_info": {
      "host": "localhost",
      "port": 8080,
      "version": "v4.5.0"
    },
    "last_activity": "2024-01-01T11:58:00Z"
  }
}
```

### 5. 配置更新 (config)

```json
{
  "type": "config",
  "id": "config_001",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "action": "updated",
    "fields": ["check_interval", "log_level"],
    "old_values": {
      "check_interval": 1.0,
      "log_level": "INFO"
    },
    "new_values": {
      "check_interval": 5.0,
      "log_level": "DEBUG"
    },
    "updated_by": "system"
  }
}
```

### 6. 系统事件 (system)

```json
{
  "type": "system",
  "id": "system_001",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "event": "service_restart",
    "service": "qbittorrent_monitor",
    "reason": "configuration_update",
    "previous_uptime": 86400,
    "new_pid": 12345
  }
}
```

## 客户端消息

客户端也可以向服务器发送消息：

### 订阅特定事件

```javascript
// 订阅 CPU 告警
ws.send(JSON.stringify({
  "type": "subscribe",
  "data": {
    "events": ["alert.cpu"],
    "filters": {
      "level": ["warning", "critical"]
    }
  }
}));
```

### 取消订阅

```javascript
ws.send(JSON.stringify({
  "type": "unsubscribe",
  "data": {
    "events": ["alert.cpu"]
  }
}));
```

### 请求特定数据

```javascript
// 请求当前性能数据
ws.send(JSON.stringify({
  "type": "request_data",
  "data": {
    "metrics": ["cpu_percent", "memory_percent"],
    "history_minutes": 10
  }
}));
```

### 心跳消息

```javascript
// 心跳保持连接
ws.send(JSON.stringify({
  "type": "ping"
}));
```

### 响应

```json
{
  "type": "pong",
  "id": "pong_001",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 错误处理

### 连接错误

```json
{
  "type": "error",
  "id": "error_001",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "code": "CONNECTION_FAILED",
    "message": "连接到服务器失败",
    "retry_after": 5000
  }
}
```

### 认证错误

```json
{
  "type": "error",
  "id": "error_002",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "code": "AUTHENTICATION_FAILED",
    "message": "API密钥无效"
  }
}
```

### 限流错误

```json
{
  "type": "error",
  "id": "error_003",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "消息频率超限",
    "retry_after": 60000
  }
}
```

## 使用示例

### JavaScript 客户端

```javascript
class WebSocketClient {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.eventHandlers = {};
  }

  connect() {
    try {
      this.ws = new WebSocket(this.url);
      this.setupEventHandlers();
    } catch (error) {
      console.error('WebSocket连接失败:', error);
      this.handleReconnect();
    }
  }

  setupEventHandlers() {
    this.ws.onopen = () => {
      console.log('WebSocket连接已建立');
      this.reconnectAttempts = 0;
      this.sendPing();
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('解析消息失败:', error);
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket连接已关闭');
      this.handleReconnect();
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket错误:', error);
    };
  }

  handleMessage(message) {
    const { type, data } = message;

    switch (type) {
      case 'performance':
        this.updatePerformanceDisplay(data);
        break;
      case 'alert':
        this.showAlert(data);
        break;
      case 'status':
        this.updateStatusDisplay(data);
        break;
      case 'pong':
        // 心跳响应
        break;
      default:
        console.log('未知消息类型:', type);
    }

    // 触发自定义事件处理器
    if (this.eventHandlers[type]) {
      this.eventHandlers[type](data);
    }
  }

  subscribe(events, filters = {}) {
    this.send({
      type: 'subscribe',
      data: { events, filters }
    });
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  sendPing() {
    this.send({ type: 'ping' });
    // 每30秒发送一次心跳
    setTimeout(() => this.sendPing(), 30000);
  }

  on(eventType, handler) {
    this.eventHandlers[eventType] = handler;
  }

  off(eventType) {
    delete this.eventHandlers[eventType];
  }

  updatePerformanceDisplay(data) {
    // 更新性能显示
    if (data.cpu_percent !== undefined) {
      document.getElementById('cpu-value').textContent = `${data.cpu_percent.toFixed(1)}%`;
    }
    if (data.memory_percent !== undefined) {
      document.getElementById('memory-value').textContent = `${data.memory_percent.toFixed(1)}%`;
    }
  }

  showAlert(alert) {
    // 显示告警
    const alertElement = document.createElement('div');
    alertElement.className = `alert alert-${alert.level}`;
    alertElement.textContent = alert.message;
    document.getElementById('alerts-container').appendChild(alertElement);

    // 5秒后自动移除
    setTimeout(() => alertElement.remove(), 5000);
  }

  updateStatusDisplay(data) {
    // 更新状态显示
    const statusElement = document.getElementById(`${data.component}-status`);
    if (statusElement) {
      statusElement.textContent = data.status;
      statusElement.className = `badge badge-${data.status}`;
    }
  }

  handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.pow(2, this.reconnectAttempts) * 1000; // 指数退避
      console.log(`尝试重新连接... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      setTimeout(() => this.connect(), delay);
    } else {
      console.error('达到最大重连次数');
    }
  }

  close() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// 使用示例
const client = new WebSocketClient('ws://localhost:8080/ws');

client.connect();

// 订阅事件
client.subscribe(['alert.cpu', 'alert.memory'], {
  level: ['warning', 'critical']
});

// 注册事件处理器
client.on('performance', (data) => {
  console.log('性能更新:', data);
});

client.on('alert', (alert) => {
  console.log('收到告警:', alert);
  // 可以在这里添加自定义告警处理逻辑
});
```

### Python 客户端

```python
import asyncio
import json
import websockets
from datetime import datetime

class WebSocketClient:
    def __init__(self, url):
        self.url = url
        self.websocket = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.event_handlers = {}

    async def connect(self):
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                self.websocket = await websockets.connect(self.url)
                await self.setup_handlers()
                break
            except Exception as e:
                print(f"连接失败: {e}")
                self.reconnect_attempts += 1
                if self.reconnect_attempts < self.max_reconnect_attempts:
                    await asyncio.sleep(2 ** self.reconnect_attempts)

    async def setup_handlers(self):
        async for message in self.websocket:
            try:
                data = json.loads(message)
                await self.handle_message(data)
            except Exception as e:
                print(f"处理消息失败: {e}")

    async def handle_message(self, message):
        message_type = message.get('type')
        message_data = message.get('data')

        if message_type == 'performance':
            await self.update_performance_display(message_data)
        elif message_type == 'alert':
            await self.show_alert(message_data)
        elif message_type == 'pong':
            pass  # 心跳响应
        else:
            print(f"未知消息类型: {message_type}")

        # 触发自定义事件处理器
        if message_type in self.event_handlers:
            await self.event_handlers[message_type](message_data)

    async def subscribe(self, events, filters=None):
        message = {
            "type": "subscribe",
            "data": {"events": events, "filters": filters or {}}
        }
        await self.send_message(message)

    async def send_message(self, message):
        if self.websocket:
            await self.websocket.send(json.dumps(message))

    async def send_ping(self):
        await self.send_message({"type": "ping"})
        # 每30秒发送心跳
        await asyncio.sleep(30)
        await self.send_ping()

    def on_event(self, event_type, handler):
        self.event_handlers[event_type] = handler

    def off_event(self, event_type):
        if event_type in self.event_handlers:
            del self.event_handlers[event_type]

    async def update_performance_display(self, data):
        # 更新性能显示逻辑
        if 'cpu_percent' in data:
            print(f"CPU: {data['cpu_percent']:.1f}%")
        if 'memory_percent' in data:
            print(f"内存: {data['memory_percent']:.1f}%")

    async def show_alert(self, alert):
        # 显示告警逻辑
        print(f"告警: {alert['title']} - {alert['message']}")

    async def close(self):
        if self.websocket:
            await self.websocket.close()

# 使用示例
async def main():
    client = WebSocketClient("ws://localhost:8080/ws")

    # 注册事件处理器
    client.on_event("performance", lambda data: print(f"性能更新: {data}"))
    client.on_event("alert", lambda alert: print(f"告警: {alert['title']}"))

    # 连接并订阅事件
    await client.connect()
    await client.subscribe(["alert.cpu", "alert.memory"])

    # 保持连接
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## 连接状态管理

| 状态 | 值 | 描述 |
|-----|-----|------|
| `CONNECTING` | 0 | 连接中 |
| `OPEN` | 1 | 连接已建立 |
| `CLOSING` | 2 | 连接关闭中 |
| `CLOSED` | 3 | 连接已关闭 |

## 最佳实践

### 1. 连接管理
- 实现自动重连机制
- 使用指数退避策略
- 设置最大重连次数

### 2. 心跳机制
- 定期发送心跳消息
- 监控心跳响应
- 设置超时检测

### 3. 错误处理
- 捕获并记录所有异常
- 实现优雅的错误恢复
- 提供用户友好的错误信息

### 4. 资源清理
- 连接关闭时清理资源
- 取消未完成的定时器
- 移除事件监听器

### 5. 性能优化
- 批量处理消息
- 使用对象池减少GC
- 避免频繁的DOM操作