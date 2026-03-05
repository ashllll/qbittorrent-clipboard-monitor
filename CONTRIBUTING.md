# 贡献指南

感谢您对 qBittorrent Clipboard Monitor 项目的关注！我们欢迎所有形式的贡献。

## 行为准则

请保持友善和尊重，我们致力于提供一个开放和友好的环境。

## 如何贡献

### 报告问题

如果您发现了 bug 或有功能建议：

1. 先搜索 [Issues](https://github.com/ashllll/qbittorrent-clipboard-monitor/issues) 是否已存在
2. 如果没有，创建一个新的 Issue
3. 提供尽可能详细的信息：
   - 问题描述
   - 复现步骤
   - 预期行为
   - 实际行为
   - 系统环境（OS、Python 版本等）
   - 相关日志（注意删除敏感信息）

### 提交代码

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/ashllll/qbittorrent-clipboard-monitor.git
cd qbittorrent-clipboard-monitor

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v
```

## 代码规范

### Python 代码风格

- 遵循 [PEP 8](https://pep8.org/) 规范
- 使用 [Black](https://github.com/psf/black) 格式化代码
- 最大行长度：100 字符
- 使用 4 空格缩进

```bash
# 格式化代码
black qbittorrent_monitor/ tests/
```

### 类型注解

- 所有函数参数和返回值都应添加类型注解
- 使用 `typing` 模块的类型提示

```python
def process_magnet(magnet: str, config: Config) -> Optional[str]:
    """处理磁力链接"""
    ...
```

### 文档字符串

- 使用 Google 风格的文档字符串
- 所有公共函数、类和模块都需要文档字符串

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

- 使用中文注释和文档字符串
- 复杂逻辑需要详细注释
- 避免无意义的注释

## 测试

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行测试并生成覆盖率报告
pytest tests/ -v --cov=qbittorrent_monitor

# 运行特定测试文件
pytest tests/test_config.py -v
```

### 编写测试

- 测试文件命名：`test_<module>.py`
- 测试类命名：`Test<ClassName>`
- 测试方法命名：`test_<description>`

```python
def test_parse_magnet_valid():
    """测试解析有效的磁力链接"""
    magnet = "magnet:?xt=urn:btih:ABC123&dn=test"
    result = parse_magnet(magnet)
    assert result == "test"
```

## 提交信息规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <subject>

<body>

<footer>
```

类型说明：

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响代码运行）
- `refactor`: 代码重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

示例：

```
feat(config): 添加环境变量支持

支持从环境变量加载配置，覆盖配置文件中的设置。
支持的变量：
- QBIT_HOST
- QBIT_PORT
- QBIT_USERNAME
- QBIT_PASSWORD
- AI_API_KEY

Closes #123
```

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

## 安全

如果您发现了安全漏洞，请不要在公开 Issue 中披露。

请通过以下方式私下报告：
- 邮件：[your-email@example.com]

## 许可证

通过贡献代码，您同意您的贡献将在 MIT 许可证下发布。
