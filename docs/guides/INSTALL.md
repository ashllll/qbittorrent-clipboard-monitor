# 安装和配置指南

## 系统要求

- Python 3.8+
- qBittorrent (启用Web UI)
- DeepSeek API密钥 (可选，用于AI分类)

## 安装步骤

### 1. 克隆项目

```bash
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置文件设置

#### 复制配置模板

```bash
# Windows
copy qbittorrent_monitor\config.json.example qbittorrent_monitor\config.json

# Linux/macOS
cp qbittorrent_monitor/config.json.example qbittorrent_monitor/config.json
```

#### 编辑配置文件

打开 `qbittorrent_monitor/config.json` 并修改以下设置：

##### qBittorrent配置

```json
{
    "qbittorrent": {
        "host": "YOUR_QBITTORRENT_IP",
        "port": 8080,
        "username": "YOUR_USERNAME",
        "password": "YOUR_PASSWORD",
        "use_https": false,
        "verify_ssl": true
    }
}
```

- `host`: qBittorrent Web UI的IP地址
- `port`: qBittorrent Web UI的端口号
- `username`: qBittorrent Web UI用户名
- `password`: qBittorrent Web UI密码

##### DeepSeek AI配置 (可选)

**方式1: 使用环境变量 (推荐)**

```bash
# Windows
set DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Linux/macOS
export DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

**方式2: 直接在配置文件中设置**

```json
{
    "deepseek": {
        "api_key": "your_deepseek_api_key_here"
    }
}
```

> **注意**: 使用环境变量更安全，避免将API密钥提交到版本控制系统。

##### 路径映射配置

如果您使用Docker或NAS，可能需要配置路径映射：

```json
{
    "qbittorrent": {
        "path_mapping": [
            {
                "source_prefix": "/downloads",
                "target_prefix": "/your/actual/downloads/path",
                "description": "容器到主机的路径映射"
            }
        ]
    }
}
```

### 5. 启动程序

#### 使用启动脚本 (推荐)

```bash
# Windows PowerShell
.\start_monitor.ps1

# Windows CMD
start_monitor.bat

# Linux/macOS
./start_monitor.sh
```

#### 直接启动

```bash
python start.py
```

## 使用方法

1. 启动程序后，它会自动监控剪贴板
2. 复制磁力链接到剪贴板，程序会自动添加到qBittorrent并分类
3. 复制XXXClub等支持网站的搜索URL，程序会批量抓取种子
4. 使用 `Ctrl+C` 安全退出程序

## 故障排除

### 无法连接qBittorrent

1. 确认qBittorrent Web UI已启用
2. 检查IP地址和端口是否正确
3. 确认用户名和密码正确
4. 检查防火墙设置

### DeepSeek API错误

1. 确认API密钥有效
2. 检查网络连接
3. 确认API配额未用尽

### 文件名不保持原始名称

程序已包含文件名保持功能，如果仍有问题：

1. 检查qBittorrent版本 (建议4.4.0+)
2. 确认种子添加成功
3. 查看日志文件获取详细错误信息

## 支持的网站

- XXXClub搜索页面批量下载
- 所有磁力链接直接添加
- 更多网站支持持续开发中

## 高级配置

### 自定义分类规则

可以在配置文件中自定义分类规则：

```json
{
    "categories": {
        "your_category": {
            "savePath": "/downloads/your_category/",
            "keywords": ["keyword1", "keyword2"],
            "description": "自定义分类",
            "priority": 10,
            "rules": [
                {
                    "type": "regex",
                    "pattern": "your_regex_pattern",
                    "score": 5
                }
            ]
        }
    }
}
```

### 通知设置

可以启用/禁用控制台通知：

```json
{
    "notifications": {
        "enabled": true,
        "console": {
            "enabled": true,
            "colored": true,
            "show_details": true
        }
    }
}
```

## 开发和贡献

如果您想参与开发：

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request

## 许可证

MIT License - 详见 LICENSE 文件 