# AGENTS.md - AI 编码代理指南

本文档为 AI 编码代理提供项目背景、架构和开发指南。阅读本文档前，请确保已了解项目是一个**简洁高效的 qBittorrent 剪贴板监控工具**。

---

## 项目概述

**qBittorrent Clipboard Monitor** 是一个自动监控剪贴板、检测磁力链接并添加到 qBittorrent 的 Python 工具。v3.0 版本经过精简重构，从 v2.5 的 22,883 行代码精简至约 800 行，专注于核心功能。

### 核心功能

- **剪贴板监控** - 实时检测剪贴板内容变化
- **磁力链接识别** - 自动提取磁力链接（`magnet:?xt=urn:btih:...`）
- **智能分类** - 支持规则匹配 + AI 自动分类（可选）
- **自动去重** - 避免重复添加相同种子
- **异步高性能** - 基于 asyncio 和 aiohttp

---

## 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 编程语言 | Python | 3.9+ |
| 包管理 | Poetry | - |
| HTTP 客户端 | aiohttp | ^3.11 |
| AI 客户端 | openai | ^1.76 |
| 剪贴板访问 | pyperclip | ^1.9 |
| 测试框架 | pytest | ^8.3 |
| 代码格式化 | Black | ^24.0 |
| 类型检查 | mypy | ^1.13 |

---

## 项目结构

```
qbittorrent-clipboard-monitor/
├── run.py                          # 入口脚本（命令行参数解析）
├── pyproject.toml                  # Poetry 配置、工具设置
├── Dockerfile                      # 多阶段构建镜像
├── docker-compose.yml              # Docker Compose 配置
├── config.example.json             # 配置文件示例
├── .env.example                    # 环境变量模板
│
├── qbittorrent_monitor/            # 核心包（约 800 行）
│   ├── __init__.py                 # 包入口，导出主要类
│   ├── __version__.py              # 版本信息（3.0.0）
│   ├── config.py                   # 配置管理（dataclass）
│   ├── qb_client.py                # qBittorrent 异步客户端
│   ├── classifier.py               # 内容分类器（规则 + AI）
│   ├── monitor.py                  # 剪贴板监控器
│   ├── utils.py                    # 工具函数
│   ├── exceptions.py               # 核心异常定义
│   └── logging_filters.py          # 敏感信息日志过滤器
│
└── tests/                          # 测试目录
    ├── conftest.py                 # pytest 配置和 fixtures
    ├── test_config.py              # 配置模块测试
    ├── test_classifier.py          # 分类器测试
    └── test_utils.py               # 工具函数测试
```

---

## 架构设计

### 数据流

```
剪贴板内容 → ClipboardMonitor → 磁力链接提取 → ContentClassifier → QBClient → qBittorrent
                                    ↓
                              规则匹配 / AI 分类
```

### 核心类

| 类名 | 文件 | 职责 |
|------|------|------|
| `Config` | `config.py` | 配置管理（JSON + 环境变量） |
| `QBClient` | `qb_client.py` | qBittorrent Web API 客户端 |
| `ContentClassifier` | `classifier.py` | 内容分类（规则优先，AI 备选） |
| `ClipboardMonitor` | `monitor.py` | 剪贴板监控主循环 |
| `SensitiveDataFilter` | `logging_filters.py` | 过滤日志中的敏感信息 |

### 异常体系

```
QBMonitorError (基类)
├── ConfigError          # 配置错误
├── QBClientError        # qBittorrent 客户端错误
│   ├── QBAuthError      # 认证错误
│   └── QBConnectionError # 连接错误
├── AIError              # AI 分类错误
└── ClassificationError  # 分类错误
```

---

## 构建和运行

### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖（开发模式）
pip install -e ".[dev]"
```

### 运行方式

**本地运行：**
```bash
# 基础运行
python run.py

# 指定配置文件
python run.py --config /path/to/config.json

# 调整检查间隔（秒）
python run.py --interval 0.5

# 调试模式
python run.py --log-level DEBUG
```

**Docker 运行：**
```bash
# 构建镜像
docker build -t qb-monitor .

# 运行容器
docker run -d \
  --name qb-monitor \
  -e QBIT_HOST=192.168.1.100 \
  -e QBIT_PORT=8080 \
  -e QBIT_USERNAME=admin \
  -e QBIT_PASSWORD=yourpassword \
  qb-monitor
```

**Docker Compose（推荐）：**
```bash
# 复制并编辑环境变量
cp .env.example .env
# 编辑 .env 文件

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## 测试

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行测试并生成覆盖率报告
pytest tests/ -v --cov=qbittorrent_monitor

# 运行测试并显示缺失的覆盖率
pytest tests/ -v --cov=qbittorrent_monitor --cov-report=term-missing

# 运行特定测试文件
pytest tests/test_config.py -v
```

### 测试配置

测试配置位于 `pyproject.toml`：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
asyncio_mode = "auto"
addopts = ["--cov=qbittorrent_monitor", "--cov-report=term-missing"]
```

### 测试 Fixtures

`conftest.py` 提供：
- `event_loop` - pytest-asyncio 事件循环
- `mock_config` - 模拟配置对象

---

## 代码风格指南

### 格式化

- 使用 **Black** 格式化代码
- 最大行长度：**100 字符**
- 目标 Python 版本：**3.9+**

```bash
# 格式化所有代码
black qbittorrent_monitor/ tests/
```

### 类型注解

- 所有函数参数和返回值必须添加类型注解
- 使用 `typing` 模块的类型提示

```python
def process_magnet(magnet: str, config: Config) -> Optional[str]:
    """处理磁力链接"""
    ...
```

### 文档字符串

- 使用 **Google 风格**文档字符串
- 所有公共函数、类和模块都需要文档字符串
- 使用**中文**编写注释和文档

```python
def add_torrent(self, magnet: str, category: str = "other") -> bool:
    """添加磁力链接到 qBittorrent
    
    Args:
        magnet: 磁力链接
        category: 分类名称
        
    Returns:
        是否添加成功
        
    Raises:
        QBClientError: 添加失败时抛出
    """
```

### 注释

- 使用**中文注释**
- 复杂逻辑需要详细注释
- 避免无意义的注释

---

## 配置系统

### 配置优先级

1. 环境变量（最高优先级）
2. 配置文件
3. 默认值

### 配置文件位置

- 默认：`~/.config/qb-monitor/config.json`
- 首次运行自动创建默认配置

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `QBIT_HOST` | qBittorrent 主机地址 | localhost |
| `QBIT_PORT` | qBittorrent 端口 | 8080 |
| `QBIT_USERNAME` | qBittorrent 用户名 | admin |
| `QBIT_PASSWORD` | qBittorrent 密码 | - |
| `QBIT_USE_HTTPS` | 使用 HTTPS | false |
| `AI_ENABLED` | 启用 AI 分类 | false |
| `AI_API_KEY` | AI API 密钥 | - |
| `AI_MODEL` | AI 模型 | deepseek-chat |
| `CHECK_INTERVAL` | 检查间隔（秒） | 1.0 |
| `LOG_LEVEL` | 日志级别 | INFO |

---

## 安全注意事项

### 敏感信息处理

- **永远不要**将密码或 API 密钥提交到 Git
- `.env` 和 `config.json` 已添加到 `.gitignore`
- 使用 `SensitiveDataFilter` 自动过滤日志中的敏感信息

### 日志过滤规则

自动过滤以下模式：
- API 密钥、密码、令牌
- 磁力链接完整 hash（保留前8位）
- 私钥、数据库连接字符串

---

## 发布流程

1. 更新 `__version__.py` 中的版本号
2. 更新 `CHANGELOG.md`
3. 创建 git tag
4. 推送到 GitHub

```bash
# 更新版本号并提交
git add .
git commit -m "chore(release): bump version to 3.1.0"

# 创建 tag
git tag -a v3.1.0 -m "Release version 3.1.0"

# 推送
git push origin main --tags
```

---

## 提交信息规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型说明：**

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响代码运行）
- `refactor`: 代码重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

---

## 开发约定

### 模块设计原则

1. **单一职责** - 每个模块只做一件事
2. **显式优于隐式** - 清晰的函数调用链
3. **少即是多** - 避免不必要的抽象层
4. **测试友好** - 易于单元测试的设计

### 异步编程

- 所有 IO 操作使用 `async/await`
- 使用 `aiohttp` 进行 HTTP 请求
- 注意处理 `asyncio.CancelledError`

### 错误处理

- 使用自定义异常类
- 在边界处捕获异常并记录日志
- 不要吞掉异常，除非有意为之

---

## 常见问题

### Docker 中剪贴板监控不工作

Docker 容器默认无法访问主机剪贴板。此工具主要用于：
- 本地开发/运行
- 主机网络模式的特殊配置

### AI 分类失败

AI 分类为可选功能。如果 AI 分类失败，会自动回退到规则分类或 "other" 分类。

---

## 相关文件

- `README.md` - 用户文档
- `CHANGELOG.md` - 更新日志
- `CONTRIBUTING.md` - 贡献指南
- `OPTIMIZATION_REPORT.md` - v3.0 优化报告
