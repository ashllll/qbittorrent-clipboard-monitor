# qBittorrent Clipboard Monitor 开发规范

本文档定义了项目的代码质量标准、编码规范和最佳实践。所有贡献者应遵循这些规范以确保代码质量的一致性。

## 目录

- [代码风格](#代码风格)
- [项目结构](#项目结构)
- [错误处理](#错误处理)
- [日志记录](#日志记录)
- [类型注解](#类型注解)
- [文档字符串](#文档字符串)
- [测试规范](#测试规范)
- [代码审查清单](#代码审查清单)

## 代码风格

### Python 版本

- 目标 Python 版本：**3.9+**
- 使用 `from __future__ import annotations` 支持延迟注解评估

### 格式化工具

项目使用以下工具进行代码格式化：

| 工具 | 用途 | 配置 |
|------|------|------|
| **Black** | 代码格式化 | 行长度 100，Python 3.9+ |
| **isort** | 导入排序 | Black 兼容模式 |
| **flake8** | 代码风格检查 | 最大行长度 100 |

### 格式化命令

```bash
# 格式化所有代码
black qbittorrent_monitor/ tests/

# 排序导入
isort qbittorrent_monitor/ tests/

# 运行所有检查
python scripts/code_quality_check.py
```

### 行长度

- 最大行长度：**100 字符**
- 对于过长的字符串，使用括号进行隐式连接

```python
# 推荐
message = (
    f"这是一个很长的错误消息，包含很多信息: "
    f"{error_code}, {error_message}"
)

# 不推荐
message = f"这是一个很长的错误消息，包含很多信息: {error_code}, {error_message}"
```

## 项目结构

### 目录组织

```
qbittorrent_monitor/
├── __init__.py              # 包入口
├── __version__.py           # 版本信息
├── config.py                # 配置管理
├── qb_client.py             # qBittorrent 客户端
├── classifier.py            # 内容分类器
├── monitor.py               # 剪贴板监控器
├── utils.py                 # 工具函数
├── exceptions.py            # 异常定义（向后兼容）
├── security.py              # 安全工具
├── logging_filters.py       # 日志过滤器
├── database.py              # 数据库管理
├── metrics.py               # 指标收集
├── metrics_server.py        # 指标服务器
├── logger.py                # 日志配置
└── common/                  # 通用工具模块
    ├── __init__.py
    ├── exceptions.py        # 统一异常体系
    ├── decorators.py        # 通用装饰器
    └── validators.py        # 统一验证器
```

### 导入排序

导入必须按以下顺序分组，每组之间空一行：

1. `__future__` 导入
2. 标准库导入
3. 第三方库导入
4. 本地应用/库导入

```python
"""模块文档字符串"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import aiohttp

from qbittorrent_monitor.common import safe_operation, ErrorCode
from .exceptions import QBMonitorError
```

## 错误处理

### 统一错误代码体系

项目使用统一的错误代码体系，格式为：`模块(2位) + 类别(2位) + 序号(2位)`

```python
from qbittorrent_monitor.common import (
    QBMonitorError,
    ConfigError,
    ErrorCode,
)

# 抛出带错误代码的异常
raise ConfigError(
    "配置文件不存在",
    error_code=ErrorCode.CONFIG_FILE_NOT_FOUND,
    context={"path": config_path},
)
```

### 使用 @safe_operation 装饰器

对于可能抛出异常的操作，使用装饰器统一处理：

```python
from qbittorrent_monitor.common import async_safe_operation, ErrorCode

@async_safe_operation(
    error_message="API调用失败",
    error_code=ErrorCode.QB_API_ERROR,
    reraise=True,
)
async def api_call():
    # 可能抛出异常的代码
    pass
```

### 异常处理最佳实践

```python
try:
    result = await some_operation()
except QBMonitorError as e:
    # 已知异常类型，直接记录
    logger.error(f"操作失败: {e}")
    raise
except Exception as e:
    # 未知异常，包装后抛出
    logger.exception("意外错误")
    raise QBMonitorError(
        "操作失败",
        error_code=ErrorCode.UNKNOWN_ERROR,
        cause=e,
    ) from e
```

## 日志记录

### 日志级别使用规范

| 级别 | 使用场景 | 示例 |
|------|----------|------|
| **DEBUG** | 详细的调试信息 | 函数调用、变量值 |
| **INFO** | 正常操作信息 | 服务启动、配置加载 |
| **WARNING** | 非致命问题 | 重试、降级操作 |
| **ERROR** | 可恢复的错误 | API调用失败 |
| **CRITICAL** | 致命错误 | 无法启动、数据损坏 |

### 日志格式

```python
# 包含上下文信息
logger.info(f"正在添加种子: magnet={log_magnet}, category={category}")

# 错误日志包含足够信息
logger.error(f"API调用失败: {endpoint} (status={status})")

# 使用 exc_info 记录异常详情
logger.exception("处理失败")
```

### 敏感信息过滤

永远不要记录敏感信息：

```python
from qbittorrent_monitor.logging_filters import sanitize_for_log

# 错误日志中使用安全的日志输出
logger.error(f"连接失败: {sanitize_for_log(error)}")
```

## 类型注解

### 基本规范

- 所有函数参数和返回值必须添加类型注解
- 使用 `typing` 模块的泛型类型
- 复杂类型使用类型别名

```python
from typing import Dict, List, Optional, Callable

# 类型别名
CategoryDict = Dict[str, List[str]]
HandlerFunc = Callable[[str, str], None]

def process_categories(
    categories: CategoryDict,
    handler: Optional[HandlerFunc] = None,
) -> List[str]:
    ...
```

### 可选参数

```python
from typing import Optional

# 参数可能有默认值
def connect(
    host: str = "localhost",
    port: int = 8080,
    timeout: Optional[float] = None,
) -> bool:
    ...
```

### 异步函数

```python
from typing import AsyncIterator

async def stream_data() -> AsyncIterator[bytes]:
    ...
```

## 文档字符串

### Google 风格文档字符串

```python
def add_torrent(
    self,
    magnet: str,
    category: Optional[str] = None,
) -> bool:
    """添加磁力链接到 qBittorrent
    
    验证磁力链接的有效性，并将其添加到 qBittorrent 下载队列。
    如果分类不存在，会自动创建分类。
    
    Args:
        magnet: 磁力链接字符串，格式为 magnet:?xt=urn:btih:...
        category: 分类名称，用于组织下载内容。如果为 None，
                 则使用默认分类。
    
    Returns:
        添加成功返回 True，失败返回 False。
    
    Raises:
        QBAuthError: 认证失败或会话过期
        QBConnectionError: 无法连接到 qBittorrent 服务器
        QBAPIError: API 调用返回错误状态码
    
    Example:
        >>> success = await client.add_torrent(
        ...     magnet="magnet:?xt=urn:btih:...",
        ...     category="movies",
        ... )
        >>> print(f"添加{'成功' if success else '失败'}")
    """
```

### 模块文档字符串

```python
"""配置管理模块

支持从 JSON 配置文件和环境变量加载配置，提供配置验证、热重载等功能。
环境变量优先级高于配置文件。

配置项说明：
    - qbittorrent: qBittorrent 连接配置
    - ai: AI 分类器配置
    - categories: 分类规则配置
    - check_interval: 剪贴板检查间隔（秒）
    - log_level: 日志级别

环境变量：
    QBIT_HOST: qBittorrent 服务器地址 (默认: localhost)
    QBIT_PORT: qBittorrent 服务器端口 (默认: 8080)
    # ... 更多环境变量

使用示例：
    >>> from qbittorrent_monitor.config import load_config
    >>> config = load_config()
    >>> print(config.qbittorrent.host)
    'localhost'
"""
```

## 测试规范

### 测试文件组织

```
tests/
├── conftest.py              # pytest 配置和 fixtures
├── test_config.py           # 配置模块测试
├── test_classifier.py       # 分类器测试
├── test_utils.py            # 工具函数测试
└── common/                  # common 模块测试
    ├── test_exceptions.py
    ├── test_decorators.py
    └── test_validators.py
```

### 测试类命名

```python
class TestConfig:
    """测试配置模块"""
    
    def test_load_default_config(self):
        """测试加载默认配置"""
        pass
    
    def test_config_validation(self):
        """测试配置验证"""
        pass


class TestQBClient:
    """测试 qBittorrent 客户端"""
    
    @pytest.mark.asyncio
    async def test_login_success(self):
        """测试登录成功"""
        pass
```

### 测试断言

```python
# 使用 pytest 的断言风格
def test_port_validation():
    assert validate_port(8080) == 8080
    
    with pytest.raises(ValidationError) as exc_info:
        validate_port(99999)
    
    assert "1-65535" in str(exc_info.value)
```

### 异步测试

```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result == expected
```

## 代码审查清单

在提交代码前，请检查以下事项：

### 基础检查

- [ ] 代码通过所有自动化测试
- [ ] 代码通过类型检查（mypy）
- [ ] 代码通过格式检查（Black、isort）
- [ ] 代码通过静态分析（flake8）
- [ ] 代码通过安全扫描（bandit）

### 代码质量

- [ ] 没有魔法数字，使用命名常量
- [ ] 没有重复代码，使用函数或类封装
- [ ] 错误处理完整，使用统一异常体系
- [ ] 日志记录适当，敏感信息已过滤

### 文档

- [ ] 模块包含文档字符串
- [ ] 公共函数包含文档字符串
- [ ] 复杂逻辑有注释说明
- [ ] 类型注解完整

### 测试

- [ ] 新功能有对应的单元测试
- [ ] 测试覆盖率达到要求（>80%）
- [ ] 边界条件已测试
- [ ] 错误路径已测试

## 自动化工具

### 代码质量检查脚本

```bash
# 运行所有检查
python scripts/code_quality_check.py

# 自动修复可修复的问题
python scripts/code_quality_check.py --fix

# 严格模式（警告视为错误）
python scripts/code_quality_check.py --strict

# 跳过测试
python scripts/code_quality_check.py --skip-tests
```

### Git 预提交钩子

建议在 `.pre-commit-config.yaml` 配置 pre-commit 钩子：

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.0.0
    hooks:
      - id: black
        language_version: python3.9

  - repo: https://github.com/PyCQA/isort
    rev: 5.13.0
    hooks:
      - id: isort

  - repo: https://github.com/PyCQA/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
```

## 参考资料

- [PEP 8 - Python 代码风格指南](https://peps.python.org/pep-0008/)
- [Google Python 风格指南](https://google.github.io/styleguide/pyguide.html)
- [Black 文档](https://black.readthedocs.io/)
- [mypy 文档](https://mypy.readthedocs.io/)
