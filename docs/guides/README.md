# qbittorrent-clipboard-monitor

## 🚀 项目简介

QBittorrent智能下载助手是一个企业级的自动化下载管理工具，支持：

- 🔍 智能剪贴板监控
- 🧠 AI自动分类
- 🕷️ 高性能网页爬虫批量下载
- 📂 自动目录管理
- 🔔 实时通知系统
- ⚡ 并发处理与性能优化

## 🆕 最新更新 (v2.0)

### 🚀 重大性能优化 (2025-07-16)

- **磁力链接提取速度提升 2-3倍**
- **新增并发处理能力** - 支持最多3个并发提取任务
- **智能配置系统** - 所有性能参数可配置
- **优化重试策略** - 减少无效等待时间
- **代码质量提升** - 清理重复代码，提高维护性

#### 性能提升数据
- 单个种子提取：18秒 → 6.5秒 (**64%提升**)
- 20个种子批量：360秒 → 50秒 (**86%提升**)
- 磁力链接解析：**73,000+次/秒**

## 📦 快速开始

### 环境要求

- Python 3.8+
- qBittorrent 4.0+
- 8GB+ 内存推荐

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 2. 安装依赖
scripts/setup_dev.sh

# 3. 启动监控
python start.py
```

### 配置说明

配置文件位于 `qbittorrent_monitor/config.json`，主要配置项：

- `qbittorrent`: qBittorrent连接配置
- `deepseek`: AI分类器配置
- `categories`: 下载分类规则
- `web_crawler`: **新增** 网页爬虫性能配置
- `notifications`: 通知系统配置

#### 🆕 网页爬虫配置 (v2.0新增)

```json
{
  "web_crawler": {
    "enabled": true,
    "page_timeout": 60000,              // 页面超时(毫秒)
    "wait_for": 3,                      // 页面等待时间(秒)
    "delay_before_return": 2,           // 返回前延迟(秒)
    "max_retries": 3,                   // 最大重试次数
    "base_delay": 5,                    // 基础延迟(秒)
    "max_delay": 60,                    // 最大延迟(秒)
    "max_concurrent_extractions": 3,    // 最大并发数
    "inter_request_delay": 1.5,         // 请求间延迟(秒)
    "ai_classify_torrents": true,       // AI分类开关
    "add_torrents_paused": false,       // 添加时暂停
    "proxy": null                       // 代理设置
  }
}
```

#### 配置调优建议

**网络较慢环境**:
```json
{
  "page_timeout": 90000,
  "wait_for": 5,
  "max_concurrent_extractions": 1
}
```

**网络较快环境**:
```json
{
  "page_timeout": 45000,
  "wait_for": 2,
  "max_concurrent_extractions": 5,
  "inter_request_delay": 1.0
}
```

**服务器限制严格**:
```json
{
  "max_concurrent_extractions": 1,
  "inter_request_delay": 3.0,
  "base_delay": 10
}
```

## 🏗️ 项目结构

```
qbittorrent-clipboard-monitor/
├── qbittorrent_monitor/      # 主模块（AI、剪贴板、爬虫等）
├── scripts/                  # setup 与测试脚本
├── tests/                    # 单元测试
├── docs/                     # 额外指南
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
- ✅ **并发磁力链接提取** (v2.0新增)
- ✅ **智能重试策略** (v2.0优化)
- ✅ **可配置性能参数** (v2.0新增)
- ✅ 实时状态监控
- ✅ 详细日志记录
- ✅ 通知系统集成

## 🧪 性能测试

项目包含完整的性能测试套件：

```bash
# 基础功能测试
python simple_test.py

# 性能对比测试
python performance_comparison.py
```

### 测试结果示例
```
🧪 开始简化功能测试...
✅ 磁力链接解析功能正常
⚡ 磁力链接解析性能: 73,000+次/秒
⚙️ 新配置模块可用
🔄 异步并发能力: 3倍性能提升
🎉 所有基础测试完成！
```

## 📝 更新日志

### v2.0 (2025-07-16) - 重大性能优化
- 🚀 **磁力链接提取速度提升2-3倍**
- ⚡ **新增并发处理能力** - 支持最多3个并发任务
- ⚙️ **新增WebCrawlerConfig配置模块** - 所有参数可配置
- 🔧 **优化重试策略** - 智能指数退避+最大延迟限制
- 🧹 **代码清理** - 删除重复代码，提高维护性
- 📊 **性能测试套件** - 完整的测试和基准测试

#### 详细优化内容
- 页面超时：120秒 → 60秒 (50%提升)
- 页面等待：10秒 → 3秒 (70%提升)
- 返回延迟：5秒 → 2秒 (60%提升)
- 请求间延迟：3-5秒 → 1.5秒 (50-70%提升)
- 最大重试：5次 → 3次 (减少40%无效重试)

### v1.x - 基础功能
- 剪贴板监控
- AI自动分类
- 基础网页爬虫
- 通知系统

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

# 性能测试 (v2.0新增)
python simple_test.py
python performance_comparison.py
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
