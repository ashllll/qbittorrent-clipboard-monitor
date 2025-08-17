# QBittorrent 剪贴板监控与自动分类下载器

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.1.0-orange.svg)](pyproject.toml)
[![Stars](https://img.shields.io/github/stars/your-username/qbittorrent-clipboard-monitor?style=social)](https://github.com/your-username/qbittorrent-clipboard-monitor)

🚀 **智能磁力链接监控与自动分类下载工具**

## ✨ 核心功能

- 🔍 **智能监控**: 实时监控剪贴板中的磁力链接和种子URL
- 🧠 **AI分类**: 支持DeepSeek等AI模型进行内容智能分类
- 🕷️ **网页爬虫**: 基于crawl4ai的高效网页内容抓取
- 📂 **自动分类**: 根据内容类型自动分类到不同下载目录
- 🎯 **多站点支持**: 支持主流种子网站
- 🔔 **通知系统**: 支持多种通知方式（Apprise）

## 🚀 快速开始

```bash
# 克隆项目
git clone https://github.com/your-username/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 安装依赖
pip install -r requirements.txt

# 启动程序
python start.py
```

## 📈 项目更新记录

### v2.1.0 (2025-08-17) - 最新版本
**重大更新与优化**
- ✅ **新增**: DeepSeek AI分类支持，提高分类准确性
- ⚡ **优化**: 网页爬虫性能显著提升，处理速度提高2-3倍
- 🐛 **修复**: 资源泄漏问题，内存使用更稳定
- 🔧 **改进**: 异常处理机制，提高系统稳定性
- 📦 **清理**: 移除不必要的临时文件和测试脚本

### v2.0.0 (2025-07-15)
**架构重构**
- 🏗️ 重构核心架构，模块化设计
- 🌐 添加Web管理界面（FastAPI）
- 📊 新增性能监控模块
- 🔄 改进配置管理系统

### v1.5.0 (2025-06-01)
**功能增强**
- 🎯 多站点支持扩展
- 🔔 通知系统集成
- 📝 完善日志系统
- 🧪 增加单元测试覆盖率

### v1.0.0 (2025-05-01) - 首个正式版本
**基础功能实现**
- 🔍 剪贴板监控功能
- 📂 自动分类下载
- ⚙️ 基础配置管理
- 📚 初始文档

## 🏗️ 项目结构

```
qbittorrent-clipboard-monitor/
├── qbittorrent_monitor/    # 核心代码
│   ├── ai_classifier.py    # AI分类器
│   ├── clipboard_monitor.py # 剪贴板监控
│   ├── web_crawler.py      # 网页爬虫
│   └── qbittorrent_client.py # qBittorrent客户端
├── config/                 # 配置文件
├── docs/                   # 项目文档
├── test/                   # 测试代码
└── start.py               # 启动入口
```

## ⚙️ 配置示例

```yaml
# config/config.yaml
qbittorrent:
  host: "localhost"
  port: 8080
  username: "admin"
  password: "your_password"

ai:
  provider: "deepseek"
  api_key: "your_api_key"
  model: "deepseek-chat"

monitoring:
  interval: 2
  categories:
    - name: "电影"
      path: "/downloads/movies"
      keywords: ["电影", "movie", "film"]
```

## 🧪 测试

```bash
# 运行所有测试
pytest

# 生成覆盖率报告
pytest --cov=qbittorrent_monitor --cov-report=html
```

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)

## 🙏 致谢

- [qBittorrent](https://www.qbittorrent.org/) - 优秀的BitTorrent客户端
- [crawl4ai](https://github.com/unclecode/crawl4ai) - 强大的网页爬虫框架
- [DeepSeek](https://www.deepseek.com/) - AI分类服务提供商

---

**⭐ 如果这个项目对您有帮助，请给个Star支持一下！**