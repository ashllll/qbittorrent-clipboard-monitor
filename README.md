# 🎯 qBittorrent智能下载助手

> 基于剪贴板监控的智能种子管理工具，支持AI分类和网页批量爬取

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![qBittorrent](https://img.shields.io/badge/qBittorrent-4.4.0+-green.svg)](https://www.qbittorrent.org/)

## ✨ 特性

- 🔍 **智能剪贴板监控** - 自动检测磁力链接和网页URL
- 🧠 **AI智能分类** - 使用DeepSeek API自动分类种子
- 🕷️ **网页批量爬取** - 支持XXXClub等网站批量下载
- 📁 **自动文件管理** - 智能分类到对应目录
- 🔄 **文件名保持** - 保持种子原始文件名
- ⚡ **异步高性能** - 基于asyncio的高效处理
- 🛡️ **错误重试机制** - 网络问题自动重试
- 🎨 **友好用户界面** - 彩色控制台输出和详细日志

## 🚀 快速开始

### 📋 系统要求

- Python 3.8+
- qBittorrent (启用Web UI)
- DeepSeek API密钥 (可选，用于AI分类)

### 🔧 安装

1. **克隆项目**
   ```bash
   git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
   cd qbittorrent-clipboard-monitor
   ```

2. **使用启动脚本 (推荐)**
   ```bash
   # Windows PowerShell
   .\start_monitor.ps1
   
   # Windows CMD
   start_monitor.bat
   
   # Linux/macOS
   ./start_monitor.sh
   ```

   启动脚本会自动：
   - 检查Python环境
   - 创建虚拟环境
   - 安装依赖包
   - 配置文件检查
   - 启动程序

3. **手动安装**
   ```bash
   # 创建虚拟环境
   python -m venv venv
   
   # 激活虚拟环境
   # Windows
   venv\Scripts\activate
   # Linux/macOS
   source venv/bin/activate
   
   # 安装依赖
   pip install -r requirements.txt
   ```

### ⚙️ 配置

1. **复制配置模板**
   ```bash
   cp qbittorrent_monitor/config.json.example qbittorrent_monitor/config.json
   ```

2. **编辑配置文件**
   ```json
   {
       "qbittorrent": {
           "host": "YOUR_QBITTORRENT_IP",
           "port": 8080,
           "username": "YOUR_USERNAME",
           "password": "YOUR_PASSWORD"
       },
       "deepseek": {
           "api_key": "YOUR_DEEPSEEK_API_KEY"
       }
   }
   ```

   > 💡 **推荐**: 使用环境变量设置API密钥更安全
   > ```bash
   > export DEEPSEEK_API_KEY=your_api_key_here
   > ```

3. **启动程序**
   ```bash
   python start.py
   ```

## 📖 使用方法

### 🔗 磁力链接下载
1. 复制磁力链接到剪贴板
2. 程序自动检测并添加到qBittorrent
3. AI自动分类到对应目录

### 🌐 网页批量下载
1. 复制XXXClub搜索页面URL到剪贴板
2. 程序自动爬取所有种子
3. 批量添加并分类

### 🎮 支持的分类

| 分类 | 描述 | 自动检测关键词 |
|------|------|----------------|
| 🎬 movies | 电影 | Movie, 1080p, 4K, BluRay |
| 📺 tv | 电视剧 | S01, Episode, Series |
| 🎌 anime | 动漫 | Anime, 动画 |
| 🔞 adult | 成人内容 | XXX, 18+, JAV |
| 🎵 music | 音乐 | Album, FLAC, MP3 |
| 🎮 games | 游戏 | Game, ISO, PC |
| 💻 software | 软件 | Software, App |
| 📦 other | 其他 | 默认分类 |

## 🛠️ 高级功能

### 🎨 自定义分类规则

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

### 🗂️ 路径映射配置

```json
{
    "qbittorrent": {
        "path_mapping": [
            {
                "source_prefix": "/downloads",
                "target_prefix": "/your/nas/downloads",
                "description": "NAS路径映射"
            }
        ]
    }
}
```

### 🔔 通知设置

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

## 🐛 故障排除

### qBittorrent连接问题
- ✅ 确认Web UI已启用
- ✅ 检查IP地址和端口
- ✅ 验证用户名密码
- ✅ 检查防火墙设置

### DeepSeek API问题
- ✅ 确认API密钥有效
- ✅ 检查网络连接
- ✅ 确认API配额

### 文件名问题
- ✅ 检查qBittorrent版本 (4.4.0+)
- ✅ 查看日志获取详细信息

详细故障排除指南：[INSTALL.md](INSTALL.md)

## 🌟 支持的网站

- ✅ XXXClub搜索页面批量下载
- ✅ 所有磁力链接直接添加
- 🔄 更多网站支持开发中...

## 📋 开发计划

- [ ] 🌐 Web管理界面
- [ ] 🤖 多AI模型支持
- [ ] 📱 移动端通知
- [ ] 🐳 Docker支持
- [ ] 🔌 插件系统
- [ ] 📊 下载统计

## 🤝 贡献

欢迎贡献代码！请查看 [贡献指南](INSTALL.md#开发和贡献)

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目基于 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

- [qBittorrent](https://www.qbittorrent.org/) - 优秀的BT客户端
- [DeepSeek](https://www.deepseek.com/) - 强大的AI服务
- [crawl4ai](https://github.com/unclecode/crawl4ai) - 网页爬虫框架

## 📞 支持

如有问题或建议，请：
- 📧 创建 [Issue](https://github.com/ashllll/qbittorrent-clipboard-monitor/issues)
- 💬 参与 [Discussions](https://github.com/ashllll/qbittorrent-clipboard-monitor/discussions)

---

⭐ 如果这个项目对您有帮助，请给一个星标！ 