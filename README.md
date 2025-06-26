# qbittorrent-clipboard-monitor

## 🚀 项目简介

QBittorrent智能下载助手是一个企业级的自动化下载管理工具，支持：

- 🔍 智能剪贴板监控
- 🧠 AI自动分类
- 🕷️ 网页爬虫批量下载
- 📂 自动目录管理
- 🔔 实时通知系统

## 📦 快速开始

### 环境要求

- Python 3.8+
- qBittorrent 4.0+
- 8GB+ 内存推荐

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-username/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 2. 运行主程序（自动处理依赖）
python main.py

# 3. 启动监控
python main.py start
```

### 配置说明

配置文件位于 `configs/config.json`，主要配置项：

- `qbt`: qBittorrent连接配置
- `deepseek`: AI分类器配置  
- `categories`: 下载分类规则
- `notifications`: 通知系统配置

## 🏗️ 项目结构

```
qbittorrent-clipboard-monitor/
├── src/                    # 源代码
│   ├── qbittorrent_monitor/  # 主模块
│   └── start.py            # 启动脚本
├── tests/                  # 单元测试
├── libs/                   # 离线依赖
├── docs/                   # 文档
├── configs/                # 配置文件
├── logs/                   # 运行日志
├── requirements.txt        # 依赖列表
├── pyproject.toml         # 项目配置
└── main.py                # 主入口
```

## 📋 功能特性

### 核心功能
- ✅ 剪贴板自动监控
- ✅ 磁力链接智能识别
- ✅ AI自动分类下载
- ✅ 网页批量爬取
- ✅ 重复下载检测

### 高级功能
- ✅ 多线程并发处理
- ✅ 失败自动重试
- ✅ 实时状态监控
- ✅ 详细日志记录
- ✅ 通知系统集成

## 🔧 开发指南

### 代码规范
- 遵循PEP 8代码风格
- 使用类型提示
- 完整的docstring文档
- 单元测试覆盖率 ≥ 80%

### 质量检查
```bash
# 代码风格检查
python main.py --check-style

# 类型检查
python main.py --check-types

# 运行测试
python main.py --test
```

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

## 📞 支持

如有问题，请通过以下方式联系：

- 提交 [GitHub Issue](https://github.com/your-username/qbittorrent-clipboard-monitor/issues)
- 发送邮件至项目维护者

---

⭐ 如果这个项目对你有帮助，请给个Star支持一下！
