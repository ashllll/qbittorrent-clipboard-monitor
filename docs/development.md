# 开发者文档

本文档面向项目开发者，介绍开发环境设置、测试、代码规范和贡献指南。

## 目录

- [开发环境设置](#开发环境设置)
- [项目结构](#项目结构)
- [代码规范](#代码规范)
- [测试](#测试)
- [调试技巧](#调试技巧)
- [性能优化](#性能优化)
- [贡献指南](#贡献指南)
- [发布流程](#发布流程)

---

## 开发环境设置

### 环境要求

- Python 3.9+
- Git
- (可选) Docker

### 1. 克隆仓库

```bash
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor
```

### 2. 创建虚拟环境

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows
```

### 3. 安装开发依赖

```bash
# 安装项目依赖
pip install -e .

# 安装开发依赖
pip install pytest pytest-asyncio pytest-cov black mypy
```

或使用 Poetry：

```bash
# 安装 Poetry
pip install poetry

# 安装所有依赖（包括开发依赖）
poetry install

# 激活 Poetry shell
poetry shell
```

### 4. 安装预提交钩子（可选）

```bash
# 安装 pre-commit
pip install pre-commit

# 安装钩子
pre-commit install
```

### 5. 配置 IDE

#### VS Code 配置

创建 `.vscode/settings.json`：

```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.analysis.typeCheckingMode": "basic",
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["--line-length", "100"],
    "editor.formatOnSave": true,
    "python.linting.enabled": true,
    "python.linting.mypyEnabled": true,
}
```

创建 `.vscode/launch.json`：

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Run Monitor",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/run.py",
            "console": "integratedTerminal",
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            }
        },
        {
            "name": "Debug Tests",
            "type": "python",
            "request": "launch",
            "module": "pytest",
            "args": ["-v", "tests/"],
            "console": "integratedTerminal"
        }
    ]
}
```

---

## 项目结构

```
qbittorrent-clipboard-monitor/
├── qbittorrent_monitor/      # 核心代码包
│   ├── __init__.py           # 包初始化，导出公共 API
│   ├── __version__.py        # 版本信息
│   ├── config.py             # 配置管理模块
│   ├── qb_client.py          # qBittorrent API 客户端
│   ├── classifier.py         # 内容分类器
│   ├── monitor.py            # 剪贴板监控器
│   ├── utils.py              # 工具函数
│   ├── exceptions.py         # 异常定义
│   └── logging_filters.py    # 日志过滤器
├── tests/                     # 测试目录
│   ├── conftest.py           # Pytest 配置和 fixtures
│   ├── test_config.py        # 配置模块测试
│   ├── test_classifier.py    # 分类器测试
│   └── test_utils.py         # 工具函数测试
├── docs/                      # 文档目录
│   ├── api.md                # API 文档
│   ├── deployment.md         # 部署指南
│   └── development.md        # 开发者文档
├── run.py                     # 主程序入口
├── config.example.json        # 配置文件示例
├── .env.example               # 环境变量示例
├── Dockerfile                 # Docker 构建文件
├── docker-compose.yml         # Docker Compose 配置
├── pyproject.toml             # 项目配置
├── README.md                  # 项目说明
├── CHANGELOG.md               # 更新日志
└── CONTRIBUTING.md            # 贡献指南
```

### 模块依赖关系

```
config.py
    ├── exceptions.py
    └── aiohttp (外部)

qb_client.py
    ├── config.py
    ├── exceptions.py
    └── aiohttp (外部)

classifier.py
    ├── config.py
    ├── exceptions.py
    └── openai (外部)

monitor.py
    ├── config.py
    ├── qb_client.py
    ├── classifier.py
    ├── utils.py
    └── pyperclip (外部)

logging_filters.py
    └── logging (标准库)
```

---

## 代码规范

### 代码风格

项目使用 **Black** 作为代码格式化工具：

```bash
# 格式化所有代码
black qbittorrent_monitor/ tests/

# 检查格式
black --check qbittorrent_monitor/ tests/
```

配置（`pyproject.toml`）：

```toml
[tool.black]
line-length = 100
target-version = ['py39']
```

### 类型注解

所有公共函数必须包含类型注解：

```python
def process_magnet(
    magnet: str,
    category: Optional[str] = None,
    save_path: Optional[str] = None
) -> bool:
    """处理磁力链接
    
    Args:
        magnet: 磁力链接
        category: 分类名称（可选）
        save_path: 保存路径（可选）
    
    Returns:
        是否处理成功
    """
    ...
```

### 文档字符串

使用 Google 风格的文档字符串：

```python
def classify_content(name: str, timeout: float = 30.0) -> ClassificationResult:
    """分类内容
    
    根据文件名或内容，使用规则匹配或 AI 自动分类。
    
    Args:
        name: 内容名称或文件名
        timeout: AI 分类超时时间（秒）
    
    Returns:
        ClassificationResult 包含分类结果和置信度
    
    Raises:
        AIError: AI 分类失败时抛出
        TimeoutError: 分类超时时抛出
    
    Example:
        >>> result = await classify_content("Movie.2024.1080p.BluRay")
        >>> print(result.category)
        'movies'
    """
    ...
```

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | 小写下划线 | `qb_client.py` |
| 类 | 大驼峰 | `ClipboardMonitor` |
| 函数 | 小写下划线 | `process_magnet` |
| 常量 | 大写下划线 | `MAX_RETRIES` |
| 私有 | 下划线前缀 | `_internal_method` |
| 变量 | 小写下划线 | `magnet_hash` |

### 导入规范

```python
# 1. 标准库
import asyncio
import logging
from typing import Optional, Dict, List

# 2. 第三方库
import aiohttp
import openai

# 3. 本地模块
from .config import Config
from .exceptions import QBClientError
```

---

## 测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行并显示详细信息
pytest -v

# 运行特定测试文件
pytest tests/test_config.py

# 运行特定测试函数
pytest tests/test_config.py::test_load_config

# 运行并生成覆盖率报告
pytest --cov=qbittorrent_monitor --cov-report=term-missing

# 生成 HTML 覆盖率报告
pytest --cov=qbittorrent_monitor --cov-report=html
```

### 测试结构

```python
# tests/test_example.py
import pytest
from qbittorrent_monitor.example import my_function


class TestMyFunction:
    """测试 my_function"""
    
    def test_success_case(self):
        """测试成功场景"""
        result = my_function("valid_input")
        assert result == "expected_output"
    
    def test_error_case(self):
        """测试错误场景"""
        with pytest.raises(ValueError) as exc_info:
            my_function("invalid_input")
        assert "error message" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_async_case(self):
        """测试异步函数"""
        result = await my_async_function()
        assert result is True
```

### Fixtures

```python
# tests/conftest.py
import pytest
from qbittorrent_monitor.config import Config, QBConfig


@pytest.fixture
def mock_config():
    """创建测试配置"""
    return Config(
        qbittorrent=QBConfig(
            host="localhost",
            port=8080,
            username="admin",
            password="admin"
        ),
        ai=AIConfig(enabled=False)
    )


@pytest.fixture
async def mock_qb_client(mock_config):
    """创建模拟的 qBittorrent 客户端"""
    client = QBClient(mock_config)
    # 设置模拟...
    yield client
    # 清理...
```

### Mock 技巧

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_with_mock():
    """使用 Mock 测试"""
    
    # Mock aiohttp 会话
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="Ok.")
    mock_session.post = MagicMock(return_value=mock_response)
    
    with patch('aiohttp.ClientSession', return_value=mock_session):
        client = QBClient(config)
        result = await client.login()
        assert result is True
```

### 测试覆盖率要求

- 核心模块覆盖率 >= 80%
- 关键路径覆盖率 100%
- 异常处理覆盖率 >= 70%

---

## 调试技巧

### 日志调试

```python
import logging

# 启用 DEBUG 日志
logging.basicConfig(level=logging.DEBUG)

# 或者使用命令行参数
python run.py --log-level DEBUG
```

### 断点调试

```python
# 使用 pdb
import pdb; pdb.set_trace()

# 或使用 ipdb（更友好）
import ipdb; ipdb.set_trace()
```

### 异步调试

```python
import asyncio

# 启用 asyncio 调试模式
asyncio.run(main(), debug=True)

# 或者设置环境变量
import os
os.environ['PYTHONASYNCIODEBUG'] = '1'
```

### 性能分析

```python
import cProfile
import pstats

# 运行分析器
profiler = cProfile.Profile()
profiler.enable()

# 运行代码
asyncio.run(main())

profiler.disable()

# 输出统计
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # 输出前 20 个
```

### 内存分析

```python
# 使用 memory_profiler
from memory_profiler import profile

@profile
def my_function():
    # 代码...
    pass
```

---

## 性能优化

### 性能测试

```python
import timeit

# 测试函数性能
def test_performance():
    result = timeit.timeit(
        'extract_magnets(text)',
        setup='from qbittorrent_monitor.monitor import MagnetExtractor; text = "..."',
        number=10000
    )
    print(f"平均耗时: {result / 10000 * 1000:.3f} ms")
```

### 性能监控

```python
from qbittorrent_monitor.monitor import ClipboardMonitor

# 获取性能统计
stats = monitor.get_stats()
print(f"""
性能统计:
- 总检查次数: {stats['checks_performed']}
- 平均检查耗时: {stats['avg_check_time_ms']:.3f} ms
- 每分钟检查: {stats['checks_per_minute']:.2f}
- 缓存命中: {stats['hash_cache_hits']}
""")
```

### 优化检查清单

- [ ] 使用预编译的正则表达式
- [ ] 避免在循环中创建临时对象
- [ ] 使用适当的数据结构（dict vs list）
- [ ] 合理使用缓存（LRU、剪贴板缓存）
- [ ] 异步 I/O 操作使用 `async`/`await`
- [ ] 限制并发数（使用 Semaphore）
- [ ] 日志级别生产环境使用 INFO 以上

---

## 贡献指南

### 提交 Issue

1. 搜索现有 Issue，避免重复
2. 使用清晰的标题
3. 提供详细描述：
   - 问题描述
   - 复现步骤
   - 期望结果
   - 实际结果
   - 环境信息（OS、Python 版本等）

### 提交 PR

1. **Fork 仓库**

```bash
git clone https://github.com/your-username/qbittorrent-clipboard-monitor.git
```

2. **创建分支**

```bash
git checkout -b feature/my-feature
# 或
git checkout -b fix/my-bugfix
```

3. **提交更改**

```bash
git add .
git commit -m "feat: add new feature"
```

提交信息规范：

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 Bug |
| `docs` | 文档更新 |
| `style` | 代码格式（不影响功能） |
| `refactor` | 重构 |
| `test` | 测试相关 |
| `chore` | 构建/工具更新 |

示例：

```
feat: add support for custom categories
fix: resolve connection timeout issue
docs: update API documentation
```

4. **推送到远程**

```bash
git push origin feature/my-feature
```

5. **创建 Pull Request**

- 填写清晰的标题和描述
- 关联相关 Issue
- 确保 CI 通过

### 代码审查标准

- [ ] 代码风格符合 Black 规范
- [ ] 包含适当的类型注解
- [ ] 包含文档字符串
- [ ] 包含单元测试
- [ ] 测试通过
- [ ] 无安全漏洞
- [ ] 性能影响评估

---

## 发布流程

### 版本号规范

使用语义化版本（SemVer）：`MAJOR.MINOR.PATCH`

- MAJOR：不兼容的 API 变更
- MINOR：向后兼容的功能添加
- PATCH：向后兼容的问题修复

### 发布步骤

1. **更新版本号**

```bash
# 更新 __version__.py
__version__ = "3.1.0"

# 更新 pyproject.toml
version = "3.1.0"
```

2. **更新 CHANGELOG.md**

```markdown
## [3.1.0] - 2025-03-08

### 新增
- 新功能 X
- 新功能 Y

### 修复
- 修复问题 Z
```

3. **创建 Git 标签**

```bash
git add .
git commit -m "chore: release v3.1.0"
git tag -a v3.1.0 -m "Release version 3.1.0"
git push origin main --tags
```

4. **创建 GitHub Release**

- 转到 GitHub Releases 页面
- 创建新 Release
- 选择标签 v3.1.0
- 填写发布说明
- 发布

### 自动发布（GitHub Actions）

创建 `.github/workflows/release.yml`：

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Build package
        run: |
          pip install build
          python -m build
      
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: dist/*
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## 故障排除

### 常见问题

#### 1. 导入错误

```bash
# 错误：ModuleNotFoundError: No module named 'qbittorrent_monitor'

# 解决：安装项目
cd qbittorrent-clipboard-monitor
pip install -e .
```

#### 2. 异步测试失败

```bash
# 错误：pytest-asyncio 配置问题

# 解决：确保安装了 pytest-asyncio
pip install pytest-asyncio

# 在 pyproject.toml 中配置
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

#### 3. 类型检查错误

```bash
# 运行 mypy 检查
mypy qbittorrent_monitor/

# 安装缺失的类型 stubs
mypy --install-types
```

### 获取帮助

- 查看 [GitHub Issues](https://github.com/ashllll/qbittorrent-clipboard-monitor/issues)
- 阅读 [API 文档](api.md)
- 查看 [部署指南](deployment.md)
