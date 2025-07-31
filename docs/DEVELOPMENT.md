# qBittorrent Clipboard Monitor 开发指南

## 概述

本文档为开发者提供了关于 qBittorrent Clipboard Monitor 项目的开发指南，包括项目结构、代码规范、测试方法、贡献流程等信息。

## 目录

- [开发环境设置](#开发环境设置)
- [项目结构](#项目结构)
- [代码规范](#代码规范)
- [测试指南](#测试指南)
- [调试方法](#调试方法)
- [贡献流程](#贡献流程)
- [发布流程](#发布流程)
- [常见问题](#常见问题)

## 开发环境设置

### 系统要求

- Python 3.8+
- qBittorrent 4.1+ (带Web API启用)
- Docker (可选，用于容器化部署)

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/yourusername/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor
```

2. **创建虚拟环境**

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

3. **安装依赖**

```bash
pip install -r requirements.txt
```

4. **安装开发依赖**

```bash
pip install pytest pytest-asyncio pytest-cov black isort mypy
```

5. **配置qBittorrent**

确保qBittorrent的Web API已启用：
1. 打开qBittorrent
2. 进入 "工具" -> "选项" -> "Web UI"
3. 勾选 "Web用户界面（远程控制）"
4. 设置用户名和密码
5. 记下端口号（默认8080）

6. **创建配置文件**

```bash
cp config.example.json config.json
```

编辑 `config.json`，填入你的qBittorrent配置和DeepSeek API密钥（可选）。

### IDE 配置

#### VS Code

推荐安装以下扩展：
- Python
- Pylance
- Black Formatter
- isort
- Python Test Explorer

#### PyCharm

1. 打开项目
2. 配置Python解释器为创建的虚拟环境
3. 配置测试运行器为pytest

## 项目结构

```
qbittorrent-clipboard-monitor/
├── qbittorrent_monitor/          # 主模块
│   ├── __init__.py
│   ├── main.py                   # 主程序入口
│   ├── clipboard_monitor.py      # 剪贴板监控器
│   ├── qbittorrent_client.py     # qBittorrent API客户端
│   ├── ai_classifier.py          # AI分类器
│   ├── web_crawler.py           # 网页爬虫
│   ├── config.py                # 配置管理
│   ├── utils.py                 # 工具函数
│   └── exceptions.py            # 异常定义
├── tests/                        # 测试目录
│   ├── __init__.py
│   ├── pytest.ini
│   ├── test_config.py
│   ├── test_utils.py
│   ├── test_ai_classifier.py
│   ├── test_qbittorrent_client.py
│   └── test_clipboard_monitor.py
├── docs/                         # 文档目录
│   ├── API.md
│   ├── DEVELOPMENT.md
│   └── USER_GUIDE.md
├── src/                          # 源代码副本
├── libs/                         # 离线依赖包
├── requirements.txt             # 依赖列表
├── pyproject.toml              # 项目配置
├── Dockerfile                  # Docker配置
├── docker-compose.yml          # Docker Compose配置
└── README.md                   # 项目文档
```

## 代码规范

### Python 代码风格

项目遵循 PEP 8 代码风格，并使用以下工具进行格式化和检查：

- **Black**: 代码格式化
- **isort**: 导入排序
- **mypy**: 类型检查

### 格式化代码

```bash
black qbittorrent_monitor/
isort qbittorrent_monitor/
```

### 类型检查

```bash
mypy qbittorrent_monitor/
```

### 代码质量检查

```bash
flake8 qbittorrent_monitor/
```

### 文档字符串

所有公共函数、方法和类都应使用 Google 风格的文档字符串：

```python
def function_name(arg1: str, arg2: int) -> bool:
    """函数描述。

    Args:
        arg1: 参数1描述
        arg2: 参数2描述

    Returns:
        返回值描述

    Raises:
        ValueError: 异常描述
    """
    pass
```

### 异常处理

使用项目定义的异常类型，而不是内置异常：

```python
# 好的做法
from qbittorrent_monitor.exceptions import ConfigError

raise ConfigError("配置加载失败")

# 不好的做法
raise ValueError("配置加载失败")
```

### 日志记录

使用项目定义的日志记录器：

```python
import logging
from qbittorrent_monitor.utils import setup_logging

logger = logging.getLogger('ModuleName')

def some_function():
    logger.info("信息日志")
    logger.debug("调试日志")
    logger.error("错误日志")
```

## 测试指南

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_config.py

# 运行特定测试类
pytest tests/test_config.py::TestConfigManager

# 运行特定测试方法
pytest tests/test_config.py::TestConfigManager::test_load_config

# 生成覆盖率报告
pytest --cov=qbittorrent_monitor
```

### 测试标记

项目使用以下测试标记：
- `unit`: 单元测试
- `integration`: 集成测试
- `slow`: 慢速测试

```bash
# 只运行单元测试
pytest -m unit

# 跳过慢速测试
pytest -m "not slow"
```

### 编写测试

#### 单元测试示例

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from qbittorrent_monitor.config import ConfigManager

class TestConfigManager:
    def setup_method(self):
        """测试前设置"""
        # 创建临时配置文件
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.json"

    def teardown_method(self):
        """测试后清理"""
        # 清理临时文件
        if self.config_path.exists():
            self.config_path.unlink()
        os.rmdir(self.temp_dir)

    @pytest.mark.asyncio
    async def test_load_config(self):
        """测试加载配置"""
        # 创建测试配置
        test_config = {
            "qbittorrent": {
                "host": "localhost",
                "port": 8080,
                "username": "admin",
                "password": "password"
            }
        }
        
        # 写入测试配置文件
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(test_config, f)
        
        # 测试加载配置
        config_manager = ConfigManager(self.config_path)
        config = await config_manager.load_config()
        
        # 验证配置
        assert config.qbittorrent.host == "localhost"
        assert config.qbittorrent.port == 8080
```

#### 异步测试示例

```python
import pytest
from unittest.mock import AsyncMock
from qbittorrent_monitor.qbittorrent_client import QBittorrentClient

class TestQBittorrentClient:
    @pytest.mark.asyncio
    async def test_login_success(self):
        """测试登录成功"""
        # 创建客户端
        config = MagicMock()
        client = QBittorrentClient(config)
        
        # 模拟session和响应
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="Ok.")
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        # 设置客户端session
        client.session = mock_session
        
        # 测试登录
        await client.login()
        
        # 验证登录状态
        assert client._authenticated is True
```

### Mock 外部依赖

使用 `unittest.mock` 模拟外部依赖：

```python
from unittest.mock import patch, MagicMock

@patch('qbittorrent_monitor.ai_classifier.OpenAI')
async def test_ai_classification(mock_openai):
    # 模拟OpenAI客户端
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    
    # 模拟API响应
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content="tv"))]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
    
    # 测试分类
    classifier = AIClassifier(config)
    result = await classifier.classify("TV.Show.S01E01", categories)
    
    # 验证结果
    assert result == "tv"
```

## 调试方法

### 日志调试

1. **设置日志级别**

```python
from qbittorrent_monitor.utils import setup_logging

logger = setup_logging(level="DEBUG", log_file="debug.log")
```

2. **在代码中添加日志**

```python
logger.debug("调试信息: %s", variable)
logger.info("处理步骤: %s", step)
logger.warning("警告: %s", warning_message)
logger.error("错误: %s", error_message)
```

### 断点调试

#### VS Code

1. 创建 `.vscode/launch.json` 文件：

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal",
            "justMyCode": false
        },
        {
            "name": "Python: Module",
            "type": "python",
            "request": "launch",
            "module": "qbittorrent_monitor.main",
            "console": "integratedTerminal",
            "justMyCode": false
        }
    ]
}
```

2. 在代码中设置断点，然后按 F5 开始调试。

#### PyCharm

1. 在代码行号左侧点击设置断点
2. 右键点击文件，选择 "Debug 'filename'"

### 远程调试

对于在Docker容器或远程服务器上运行的代码，可以使用远程调试：

1. **安装调试依赖**

```bash
pip install debugpy
```

2. **修改代码以启用远程调试**

```python
import debugpy

# 启用远程调试
debugpy.listen(("0.0.0.0", 5678))
print("等待调试器连接...")
debugpy.wait_for_client()
```

3. **在VS Code中配置远程调试**

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Remote Attach",
            "type": "python",
            "request": "attach",
            "connect": {
                "host": "localhost",
                "port": 5678
            },
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}",
                    "remoteRoot": "/app"
                }
            ],
            "justMyCode": false
        }
    ]
}
```

### 性能分析

使用 `cProfile` 进行性能分析：

```python
import cProfile
import pstats

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # 运行要分析的代码
    await some_async_function()
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats(pstats.SortKey.TIME)
    stats.print_stats()
```

## 贡献流程

### Fork 和 Clone

1. **Fork 仓库**

在 GitHub 上 fork 项目仓库。

2. **Clone 你的 Fork**

```bash
git clone https://github.com/yourusername/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor
```

3. **添加上游仓库**

```bash
git remote add upstream https://github.com/originalusername/qbittorrent-clipboard-monitor.git
```

### 创建功能分支

```bash
# 创建新分支
git checkout -b feature/your-feature-name

# 或创建修复分支
git checkout -b fix/your-fix-name
```

### 开发和测试

1. **进行代码更改**

2. **运行测试**

```bash
pytest
```

3. **格式化代码**

```bash
black .
isort .
```

4. **检查代码质量**

```bash
flake8 .
mypy .
```

### 提交更改

1. **添加更改**

```bash
git add .
```

2. **提交更改**

```bash
git commit -m "feat: 添加新功能

- 功能描述1
- 功能描述2

Closes #123"
```

### 推送和创建 Pull Request

1. **推送到你的 Fork**

```bash
git push origin feature/your-feature-name
```

2. **创建 Pull Request**

在 GitHub 上创建从你的功能分支到上游仓库主分支的 Pull Request。

### Pull Request 审查

1. **确保 CI 测试通过**

2. **响应审查意见**

3. **根据需要进行更改**

4. **合并 Pull Request**

### 分支命名约定

- 功能分支: `feature/feature-name`
- 修复分支: `fix/issue-description`
- 文档分支: `docs/documentation-update`
- 测试分支: `test/test-improvement`

### 提交消息约定

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

类型（type）:
- `feat`: 新功能
- `fix`: 修复
- `docs`: 文档更改
- `style`: 代码格式（不影响代码运行的变动）
- `refactor`: 重构（既不是新增功能，也不是修改代码的变动）
- `test`: 增加测试
- `chore`: 构建过程或辅助工具的变动

示例：

```
feat(ai): 添加新的AI分类模型

- 添加DeepSeek分类器支持
- 改进分类准确性
- 添加相关测试

Closes #123
```

## 发布流程

### 版本号约定

项目使用 [Semantic Versioning](https://semver.org/) (语义化版本)：

- `MAJOR.MINOR.PATCH`
- `MAJOR`: 不兼容的 API 更改
- `MINOR`: 向后兼容的功能性新增
- `PATCH`: 向后兼容的问题修正

### 发布步骤

1. **更新版本号**

在 `pyproject.toml` 中更新版本号：

```toml
[project]
version = "1.0.0"
```

2. **更新变更日志**

在 `CHANGELOG.md` 中添加新版本条目：

```markdown
## [1.0.0] - 2023-01-01

### Added
- 新功能1
- 新功能2

### Changed
- 变更1

### Fixed
- 修复1
```

3. **创建发布分支**

```bash
git checkout -b release/v1.0.0
```

4. **提交更改**

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: 准备发布 v1.0.0"
```

5. **推送发布分支**

```bash
git push origin release/v1.0.0
```

6. **创建 Pull Request**

创建从发布分支到主分支的 Pull Request。

7. **合并发布分支**

合并 Pull Request 到主分支。

8. **创建标签**

```bash
git tag v1.0.0
git push origin v1.0.0
```

9. **构建和发布**

```bash
# 构建分发包
python -m build

# 发布到PyPI（需要权限）
twine upload dist/*
```

### 发布后任务

1. **创建 GitHub Release**

在 GitHub 上创建基于标签的 Release，添加发布说明。

2. **更新文档**

更新文档中的版本引用。

3. **发布公告**

在适当的地方发布公告（如讨论区、邮件列表等）。

## 常见问题

### 开发环境问题

#### Q: 如何解决依赖冲突？

A: 使用虚拟环境隔离项目依赖，并使用 `pip-tools` 固定依赖版本：

```bash
pip install pip-tools
pip-compile requirements.in > requirements.txt
```

#### Q: 如何处理异步代码调试？

A: 使用支持异步调试的IDE（如VS Code或PyCharm），或使用 `debugpy` 库进行远程调试。

### 测试问题

#### Q: 如何模拟外部API调用？

A: 使用 `unittest.mock` 模拟外部API：

```python
from unittest.mock import patch, AsyncMock

@patch('module.external_api_call')
async def test_function(mock_api):
    mock_api.return_value = AsyncMock(return_value={"result": "success"})
    
    # 测试代码
```

#### Q: 如何测试异步代码？

A: 使用 `pytest-asyncio` 插件，并使用 `@pytest.mark.asyncio` 标记异步测试：

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected
```

### 代码贡献问题

#### Q: 如何处理代码审查反馈？

A: 逐条处理审查意见，进行必要更改，并在评论中回应。如有疑问，可在评论中讨论。

#### Q: 如何处理合并冲突？

A: 在合并前，先同步上游仓库的最新更改：

```bash
git fetch upstream
git rebase upstream/main
```

解决冲突后，继续提交和推送。

### 发布问题

#### Q: 如何回滚有问题的发布？

A: 如果发现问题，可以创建修复分支，修复问题并发布新版本：

```bash
git checkout -b fix/issue
# 进行修复
git commit -m "fix: 修复问题"
git push origin fix/issue
```

然后创建 Pull Request 并发布新版本。

#### Q: 如何处理版本兼容性问题？

A: 在进行不兼容更改时，确保：
1. 更新主版本号
2. 在文档中明确说明不兼容更改
3. 提供迁移指南