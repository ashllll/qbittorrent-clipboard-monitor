# qBittorrent Clipboard Monitor 用户指南

## 概述

qBittorrent Clipboard Monitor 是一个企业级的自动化下载管理工具，主要用于监控剪贴板中的磁力链接和网页URL，自动将种子添加到qBittorrent客户端并进行智能分类。本指南将帮助用户安装、配置和使用该工具。

## 目录

- [系统要求](#系统要求)
- [安装指南](#安装指南)
- [配置说明](#配置说明)
- [使用方法](#使用方法)
- [高级功能](#高级功能)
- [故障排除](#故障排除)
- [常见问题](#常见问题)

## 系统要求

### 硬件要求

- CPU: 双核及以上
- 内存: 4GB及以上
- 硬盘空间: 至少1GB可用空间（用于日志和临时文件）

### 软件要求

- 操作系统: Windows 10+, macOS 10.14+, Linux (Ubuntu 18.04+, CentOS 7+)
- Python: 3.8+
- qBittorrent: 4.1+ (带Web API启用)
- Docker: 20.10+ (可选，用于容器化部署)

### 网络要求

- 稳定的互联网连接（用于AI分类和网页爬虫）
- 可访问DeepSeek API（如果使用AI分类功能）
- 可访问目标网站（如果使用网页爬虫功能）

## 安装指南

### 方法一：直接安装

1. **安装Python**

   - Windows: 从 [Python官网](https://www.python.org/downloads/) 下载并安装
   - macOS: 使用 Homebrew: `brew install python@3.9`
   - Linux: 使用包管理器: `sudo apt install python3 python3-pip` (Ubuntu/Debian)

2. **下载项目**

   ```bash
   git clone https://github.com/yourusername/qbittorrent-clipboard-monitor.git
   cd qbittorrent-clipboard-monitor
   ```

3. **安装依赖**

   ```bash
   pip install -r requirements.txt
   ```

4. **安装程序**

   ```bash
   pip install -e .
   ```

### 方法二：Docker安装

1. **安装Docker**

   - Windows: 下载并安装 [Docker Desktop](https://www.docker.com/products/docker-desktop)
   - macOS: 下载并安装 [Docker Desktop](https://www.docker.com/products/docker-desktop)
   - Linux: 按照 [官方指南](https://docs.docker.com/engine/install/) 安装

2. **下载项目**

   ```bash
   git clone https://github.com/yourusername/qbittorrent-clipboard-monitor.git
   cd qbittorrent-clipboard-monitor
   ```

3. **构建Docker镜像**

   ```bash
   docker build -t qbittorrent-clipboard-monitor .
   ```

4. **运行容器**

   ```bash
   docker run -d \
     --name qbittorrent-monitor \
     -v /path/to/config.json:/app/config.json \
     -v /path/to/logs:/app/logs \
     qbittorrent-clipboard-monitor
   ```

### 方法三：Docker Compose安装

1. **安装Docker和Docker Compose**

   见方法二

2. **下载项目**

   ```bash
   git clone https://github.com/yourusername/qbittorrent-clipboard-monitor.git
   cd qbittorrent-clipboard-monitor
   ```

3. **配置环境**

   复制并编辑 `docker-compose.yml` 文件，根据需要修改环境变量和卷映射。

4. **启动服务**

   ```bash
   docker-compose up -d
   ```

## 配置说明

### qBittorrent配置

1. **启用Web API**

   - 打开qBittorrent
   - 进入 "工具" -> "选项" -> "Web UI"
   - 勾选 "Web用户界面（远程控制）"
   - 设置用户名和密码
   - 记下端口号（默认8080）
   - 点击 "应用"

2. **测试连接**

   在浏览器中访问 `http://localhost:8080`，使用设置的用户名和密码登录。

### 程序配置

1. **创建配置文件**

   ```bash
   cp config.example.json config.json
   ```

2. **编辑配置文件**

   使用文本编辑器打开 `config.json`，根据需要修改配置：

   ```json
   {
     "qbittorrent": {
       "host": "localhost",
       "port": 8080,
       "username": "admin",
       "password": "password",
       "use_https": false,
       "verify_ssl": true,
       "use_nas_paths_directly": false,
       "path_mapping": [
         {
           "source_prefix": "/downloads",
           "target_prefix": "/mnt/nas/downloads",
           "description": "Docker容器到NAS的路径映射"
         }
       ]
     },
     "deepseek": {
       "api_key": "your_deepseek_api_key",
       "model": "deepseek-chat",
       "base_url": "https://api.deepseek.com",
       "timeout": 30,
       "max_retries": 3,
       "retry_delay": 1.0
     },
     "categories": {
       "tv": {
         "savePath": "/downloads/tv/",
         "keywords": ["tv", "show", "series"],
         "description": "电视剧、连续剧、剧集等",
         "priority": 10
       },
       "movies": {
         "savePath": "/downloads/movies/",
         "keywords": ["movie", "film", "cinema"],
         "description": "电影作品",
         "priority": 8
       },
       "adult": {
         "savePath": "/downloads/adult/",
         "keywords": ["adult", "xxx"],
         "description": "成人内容",
         "priority": 15
       },
       "anime": {
         "savePath": "/downloads/anime/",
         "keywords": ["anime", "animation"],
         "description": "日本动画、动漫",
         "priority": 12
       },
       "music": {
         "savePath": "/downloads/music/",
         "keywords": ["music", "audio"],
         "description": "音乐专辑、单曲",
         "priority": 6
       },
       "games": {
         "savePath": "/downloads/games/",
         "keywords": ["game", "pc"],
         "description": "电子游戏",
         "priority": 7
       },
       "software": {
         "savePath": "/downloads/software/",
         "keywords": ["software", "app"],
         "description": "应用程序、软件",
         "priority": 5
       },
       "other": {
         "savePath": "/downloads/other/",
         "keywords": [],
         "description": "其他内容",
         "priority": 1
       }
     },
     "check_interval": 2.0,
     "max_retries": 3,
     "retry_delay": 5.0,
     "notifications": {
       "enabled": true,
       "console": {
         "enabled": true,
         "colored": true,
         "show_details": true,
         "show_statistics": true
       }
     },
     "hot_reload": true,
     "log_level": "INFO",
     "log_file": "magnet_monitor.log"
   }
   ```

### 配置项说明

#### qBittorrent配置

- `host`: qBittorrent服务器地址
- `port`: qBittorrent Web API端口
- `username`: qBittorrent用户名
- `password`: qBittorrent密码
- `use_https`: 是否使用HTTPS
- `verify_ssl`: 是否验证SSL证书
- `use_nas_paths_directly`: 是否直接使用NAS路径
- `path_mapping`: 路径映射规则列表

#### DeepSeek配置

- `api_key`: DeepSeek API密钥
- `model`: 使用的模型名称
- `base_url`: API基础URL
- `timeout`: 请求超时时间（秒）
- `max_retries`: 最大重试次数
- `retry_delay`: 重试延迟（秒）

#### 分类配置

- `savePath`: 分类保存路径
- `keywords`: 分类关键词列表
- `description`: 分类描述
- `priority`: 分类优先级（数字越大优先级越高）
- `rules`: 增强规则列表（可选）
- `foreign_keywords`: 外语关键词列表（可选）

#### 其他配置

- `check_interval`: 剪贴板检查间隔（秒）
- `max_retries`: 最大重试次数
- `retry_delay`: 重试延迟（秒）
- `notifications`: 通知配置
- `hot_reload`: 是否启用配置热重载
- `log_level`: 日志级别（DEBUG, INFO, WARNING, ERROR）
- `log_file`: 日志文件路径

## 使用方法

### 命令行界面

程序提供了完整的命令行界面，可以通过以下方式使用：

```bash
# 显示帮助信息
qbittorrent-monitor --help

# 启动剪贴板监控
qbittorrent-monitor monitor

# 抓取网页并添加种子
qbittorrent-monitor crawl "https://www.xxxclub.to/torrents/search/test" --pages 2

# 显示版本信息
qbittorrent-monitor --version
```

### 监控剪贴板

1. **启动监控**

   ```bash
   qbittorrent-monitor monitor
   ```

2. **复制磁力链接**

   从任何来源复制磁力链接到剪贴板，程序会自动检测并添加到qBittorrent。

3. **复制网页URL**

   复制支持的网站URL（如XXXClub搜索页面），程序会自动抓取并添加种子。

### 网页爬虫

1. **抓取搜索页面**

   ```bash
   qbittorrent-monitor crawl "https://www.xxxclub.to/torrents/search/keyword" --pages 3
   ```

2. **指定最大页数**

   ```bash
   qbittorrent-monitor crawl "https://www.xxxclub.to/torrents/search/keyword" --pages 5
   ```

3. **使用配置文件**

   ```bash
   qbittorrent-monitor crawl "https://www.xxxclub.to/torrents/search/keyword" --config /path/to/config.json
   ```

### 查看状态和统计

1. **查看实时状态**

   程序运行时会显示实时状态和统计信息。

2. **查看历史记录**

   历史记录保存在日志文件中，可以通过以下方式查看：

   ```bash
   tail -f magnet_monitor.log
   ```

3. **查看统计信息**

   程序会定期显示统计信息，包括：
   - 总处理数
   - 成功添加数
   - 失败数
   - 重复跳过数
   - AI分类数
   - 规则分类数

## 高级功能

### AI分类

程序支持使用DeepSeek AI进行智能分类：

1. **配置AI分类**

   确保配置文件中的 `deepseek` 部分已正确设置API密钥。

2. **启用AI分类**

   程序会自动使用AI分类，如果AI分类失败，会回退到规则引擎。

3. **自定义分类规则**

   可以在分类配置中添加自定义规则：

   ```json
   "rules": [
     {
       "type": "regex",
       "pattern": "S\\d+E\\d+",
       "score": 5
     },
     {
       "type": "keyword",
       "keywords": ["Season", "Episode"],
       "score": 3
     },
     {
       "type": "exclude",
       "keywords": ["sample", "trailer"],
       "score": 10
     }
   ]
   ```

### 路径映射

如果使用Docker或需要将路径映射到NAS，可以配置路径映射：

```json
"path_mapping": [
  {
    "source_prefix": "/downloads",
    "target_prefix": "/mnt/nas/downloads",
    "description": "Docker容器到NAS的路径映射"
  }
]
```

### 通知系统

程序支持多种通知方式：

1. **控制台通知**

   默认启用，在控制台显示彩色通知。

2. **Webhook通知**

   配置webhook URL，程序会发送HTTP POST请求：

   ```json
   "notifications": {
     "enabled": true,
     "webhook_url": "https://your-webhook-url.com/endpoint"
   }
   ```

3. **Telegram通知**

   配置Telegram Bot API令牌和聊天ID：

   ```json
   "notifications": {
     "enabled": true,
     "services": ["telegram"],
     "api_token": "your_bot_token",
     "chat_id": "your_chat_id"
   }
   ```

### 配置热重载

程序支持配置文件热重载：

1. **启用热重载**

   确保配置文件中 `hot_reload` 设置为 `true`。

2. **修改配置**

   直接编辑配置文件并保存，程序会自动重新加载配置。

3. **查看重载日志**

   程序会在日志中记录配置重载事件。

### 性能优化

程序提供了多种性能优化选项：

1. **并发处理**

   可以配置网页爬虫的并发数：

   ```json
   "web_crawler": {
     "max_concurrent_extractions": 3,
     "inter_request_delay": 1.5
   }
   ```

2. **超时设置**

   可以配置各种超时时间：

   ```json
   "web_crawler": {
     "page_timeout": 60000,
     "wait_for": 3,
     "delay_before_return": 2
   }
   ```

3. **重试策略**

   可以配置重试策略：

   ```json
   "web_crawler": {
     "max_retries": 3,
     "base_delay": 5,
     "max_delay": 60
   }
   ```

## 故障排除

### 常见问题

#### Q: 程序无法连接到qBittorrent

A: 检查以下几点：
1. qBittorrent是否正在运行
2. Web API是否已启用
3. 主机、端口、用户名和密码是否正确
4. 防火墙是否阻止了连接

#### Q: AI分类不工作

A: 检查以下几点：
1. API密钥是否正确
2. 网络是否可以访问DeepSeek API
3. API配额是否已用完
4. 查看日志中的错误信息

#### Q: 网页爬虫无法抓取内容

A: 检查以下几点：
1. 网站是否可以正常访问
2. URL是否正确
3. 网站结构是否已更改
4. 是否需要登录或验证码

#### Q: 种子添加失败

A: 检查以下几点：
1. 磁力链接是否有效
2. qBittorrent是否有足够权限
3. 保存路径是否存在且可写
4. 磁盘空间是否足够

### 日志分析

程序会生成详细的日志，可以通过以下方式分析：

1. **查看日志文件**

   ```bash
   tail -f magnet_monitor.log
   ```

2. **过滤错误信息**

   ```bash
   grep "ERROR" magnet_monitor.log
   ```

3. **查看特定模块的日志**

   ```bash
   grep "ClipboardMonitor" magnet_monitor.log
   grep "WebCrawler" magnet_monitor.log
   ```

### 调试模式

启用调试模式可以获取更详细的日志：

1. **修改日志级别**

   在配置文件中设置：
   ```json
   "log_level": "DEBUG"
   ```

2. **重新启动程序**

   程序会输出更详细的调试信息。

3. **分析调试信息**

   查看日志中的调试信息，分析问题原因。

### 性能问题

如果程序运行缓慢，可以尝试以下优化：

1. **减少并发数**

   ```json
   "web_crawler": {
     "max_concurrent_extractions": 1
   }
   ```

2. **增加超时时间**

   ```json
   "web_crawler": {
     "page_timeout": 120000,
     "wait_for": 10
   }
   ```

3. **禁用AI分类**

   ```json
   "ai_classify_torrents": false
   ```

4. **增加检查间隔**

   ```json
   "check_interval": 5.0
   ```

## 常见问题

### 安装和配置

#### Q: 如何安装Python？

A: 
- Windows: 从 [Python官网](https://www.python.org/downloads/) 下载并安装
- macOS: 使用 Homebrew: `brew install python@3.9`
- Linux: 使用包管理器: `sudo apt install python3 python3-pip` (Ubuntu/Debian)

#### Q: 如何获取DeepSeek API密钥？

A: 
1. 访问 [DeepSeek官网](https://platform.deepseek.com/)
2. 注册账号并登录
3. 进入API管理页面
4. 创建新的API密钥
5. 将密钥复制到配置文件中

#### Q: 如何启用qBittorrent的Web API？

A: 
1. 打开qBittorrent
2. 进入 "工具" -> "选项" -> "Web UI"
3. 勾选 "Web用户界面（远程控制）"
4. 设置用户名和密码
5. 记下端口号（默认8080）
6. 点击 "应用"

### 使用和功能

#### Q: 程序支持哪些网站？

A: 目前主要支持XXXClub网站，但设计上是可扩展的，可以添加对其他网站的支持。

#### Q: 如何添加新的分类？

A: 在配置文件的 `categories` 部分添加新的分类配置：

```json
"new_category": {
  "savePath": "/downloads/new/",
  "keywords": ["keyword1", "keyword2"],
  "description": "新分类描述",
  "priority": 5
}
```

#### Q: 如何自定义分类规则？

A: 在分类配置中添加 `rules` 数组：

```json
"rules": [
  {
    "type": "regex",
    "pattern": "pattern",
    "score": 5
  },
  {
    "type": "keyword",
    "keywords": ["keyword1", "keyword2"],
    "score": 3
  }
]
```

#### Q: 如何禁用AI分类？

A: 在配置文件中设置：
```json
"ai_classify_torrents": false
```

#### Q: 如何设置路径映射？

A: 在配置文件的 `qbittorrent` 部分添加 `path_mapping` 数组：

```json
"path_mapping": [
  {
    "source_prefix": "/downloads",
    "target_prefix": "/mnt/nas/downloads",
    "description": "路径映射描述"
  }
]
```

### 故障排除

#### Q: 程序启动失败怎么办？

A: 
1. 检查Python版本是否满足要求
2. 检查依赖是否正确安装
3. 查看错误日志，分析具体原因
4. 尝试在调试模式下运行

#### Q: 磁力链接无法添加怎么办？

A: 
1. 检查磁力链接格式是否正确
2. 检查qBittorrent连接是否正常
3. 检查保存路径是否存在且可写
4. 查看日志中的错误信息

#### Q: 网页爬虫无法工作怎么办？

A: 
1. 检查网络连接是否正常
2. 检查URL是否正确
3. 检查网站是否需要登录或验证码
4. 尝试增加超时时间和重试次数

#### Q: AI分类不准确怎么办？

A: 
1. 检查API密钥是否正确
2. 检查网络是否可以访问DeepSeek API
3. 尝试优化分类关键词和规则
4. 查看AI分类的日志，分析分类结果

### 性能和优化

#### Q: 如何提高程序性能？

A: 
1. 调整并发数和超时设置
2. 优化分类规则，减少不必要的处理
3. 增加检查间隔，减少CPU使用率
4. 考虑使用更快的硬件或网络连接

#### Q: 如何减少资源使用？

A: 
1. 减少并发数
2. 增加检查间隔
3. 禁用不必要的功能（如AI分类）
4. 优化日志级别，减少日志输出

#### Q: 如何处理大量种子？

A: 
1. 增加并发数，提高处理速度
2. 使用更快的存储设备
3. 考虑分批处理，避免一次性处理过多种子
4. 监控系统资源使用情况，适时调整配置

### 高级功能

#### Q: 如何自定义通知？

A: 目前程序支持控制台、Webhook和Telegram通知。可以通过修改配置文件来自定义通知方式和内容。

#### Q: 如何扩展网站支持？

A: 程序设计上是可扩展的，可以通过以下方式添加新网站支持：
1. 在 `web_crawler.py` 中添加新的解析函数
2. 在 `utils.py` 中添加新的URL模式
3. 在配置中添加新网站的特定设置

#### Q: 如何备份数据？

A: 程序的主要数据是配置文件和日志文件，可以定期备份这些文件：
1. 配置文件：`config.json`
2. 日志文件：`magnet_monitor.log`
3. 历史记录：程序运行时生成的日志

#### Q: 如何更新程序？

A: 
1. 备份当前配置文件
2. 下载最新版本的程序
3. 安装新版本
4. 恢复配置文件
5. 测试新版本是否正常工作