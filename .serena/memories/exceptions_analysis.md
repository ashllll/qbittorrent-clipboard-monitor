# exceptions.py 模块分析

## 异常层次结构

### 基础异常类
- QBittorrentMonitorError: 项目基础异常类
  - 支持错误详情、重试时间
  - 所有其他异常的基类

### 配置相关异常
- ConfigError: 配置文件加载、验证相关异常

### qBittorrent相关异常
- QBittorrentError: qBittorrent操作异常基类
- NetworkError: 网络通信异常
- QbtAuthError: qBittorrent认证异常
- QbtRateLimitError: API限速异常（默认60秒重试）
- QbtPermissionError: qBittorrent权限异常

### AI相关异常
- AIError: AI功能异常基类
- AIApiError: AI API调用异常
- AICreditError: AI额度不足异常（默认1小时重试）
- AIRateLimitError: AI API限速异常（默认5分钟重试）

### 功能模块异常
- ClassificationError: 分类相关异常
- ClipboardError: 剪贴板访问异常
- TorrentParseError: 种子解析异常
- NotificationError: 通知发送异常
- CrawlerError: 网页爬虫异常
- ParseError: 网页解析异常（继承自CrawlerError）

## 设计特点
- 分层异常设计，便于精确错误处理
- 内置重试时间建议
- 支持错误详情附加
- 便于用户理解和调试