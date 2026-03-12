# 配置文档中心

> **文档版本**: v2.5.0  
> **更新日期**: 2026-03-12  
> **适用版本**: qBittorrent剪贴板监控器 v2.5.0+

本文档中心提供 qBittorrent剪贴板监控器 的完整配置文档和工具。

---

## 目录结构

```
docs/config/
├── README.md                          # 本文档
├── CONFIGURATION_REFERENCE.md         # 配置参考手册
├── ENVIRONMENT_VARIABLES.md           # 环境变量配置指南
├── schema/
│   └── config.schema.json             # JSON Schema (IDE自动补全)
├── guides/
│   └── MULTI_ENVIRONMENT.md           # 多环境配置指南
├── examples/                          # 配置示例
│   ├── config.development.json        # 开发环境配置
│   ├── config.production.json         # 生产环境配置
│   └── config.docker.json             # Docker环境配置
└── generated/                         # 自动生成的文档
    ├── CONFIG_REFERENCE_AUTO.md       # 自动生成的配置参考
    └── ENV_MAPPING_AUTO.md            # 自动生成的环境变量映射
```

---

## 快速开始

### 1. 生成默认配置

```bash
# 首次运行会自动生成默认配置
python run.py

# 或使用配置模板
python scripts/config/validate_config.py --template development --output config.json
```

### 2. 验证配置

```bash
# 验证配置文件
python scripts/config/validate_config.py --config config.json

# 验证并应用环境变量
python scripts/config/validate_config.py --config config.json --env-file .env
```

### 3. 使用IDE编辑配置

配置文件夹下包含 `schema/config.schema.json`，支持IDE自动补全和验证：

- **VS Code**: 安装 "JSON" 扩展，自动识别schema
- **PyCharm**: 内置JSON Schema支持
- **Vim/Neovim**: 安装 `coc-json` 或 `nvim-lspconfig`

---

## 配置文档

### 主要文档

| 文档 | 说明 | 适用场景 |
|------|------|----------|
| [CONFIGURATION_REFERENCE.md](./CONFIGURATION_REFERENCE.md) | 完整的配置项参考 | 查找配置项说明 |
| [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md) | 环境变量配置指南 | Docker/K8s部署 |
| [guides/MULTI_ENVIRONMENT.md](./guides/MULTI_ENVIRONMENT.md) | 多环境配置指南 | 开发/测试/生产切换 |

### 配置示例

| 示例文件 | 环境 | 特点 |
|----------|------|------|
| [config.development.json](./examples/config.development.json) | 开发 | 详细日志、热加载、快速重试 |
| [config.production.json](./examples/config.production.json) | 生产 | 性能优化、安全检查、通知开启 |
| [config.docker.json](./examples/config.docker.json) | Docker | 环境变量优先、容器优化 |

---

## 配置工具

### validate_config.py - 配置验证工具

```bash
# 验证配置
python scripts/config/validate_config.py

# 生成模板
python scripts/config/validate_config.py --template development --output config.json

# 使用环境变量验证
python scripts/config/validate_config.py --env-file .env.production
```

**功能特性:**
- ✅ JSON/YAML/TOML格式验证
- ✅ 配置项类型检查
- ✅ 安全警告（弱密码、明文存储）
- ✅ 性能建议
- ✅ 生成修复建议

### generate_docs.py - 文档生成工具

```bash
# 生成所有文档
python scripts/config/generate_docs.py --output docs/config/generated/

# 仅生成JSON Schema
python scripts/config/generate_docs.py --format json-schema

# 仅生成Markdown
python scripts/config/generate_docs.py --format markdown
```

**功能特性:**
- ✅ 从Pydantic模型自动生成JSON Schema
- ✅ 生成Markdown配置文档
- ✅ 生成环境变量映射表
- ✅ 生成配置示例

---

## 配置最佳实践

### 1. 敏感信息保护

```bash
# ❌ 不要这样做
# config.json
{
  "qbittorrent": {
    "password": "my_real_password"
  }
}

# ✅ 使用环境变量
# config.json
{
  "qbittorrent": {
    "password": "${QBT_PASSWORD}"
  }
}

# .env (添加到 .gitignore)
QBT_PASSWORD=my_real_password
```

### 2. 多环境管理

```bash
# 创建环境特定配置
cp config.json config.development.json
cp config.json config.production.json

# 使用环境变量切换
export CONFIG_ENV=production
python run.py --config config.${CONFIG_ENV}.json
```

### 3. 配置验证CI/CD

```yaml
# .github/workflows/validate-config.yml
name: Validate Config
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install pydantic
      - name: Validate configs
        run: |
          python scripts/config/validate_config.py --config config.development.json
          python scripts/config/validate_config.py --config config.production.json
```

### 4. IDE集成

**VS Code配置 (`.vscode/settings.json`):**

```json
{
  "json.schemas": [
    {
      "fileMatch": ["config*.json"],
      "url": "./docs/config/schema/config.schema.json"
    }
  ]
}
```

**PyCharm配置:**

1. 打开 Settings → Languages & Frameworks → Schemas and DTDs → JSON Schema Mappings
2. 添加新的Schema映射：
   - Schema file: `docs/config/schema/config.schema.json`
   - File path pattern: `config*.json`

---

## 常见问题

### Q: 配置热加载不生效?

**A:** 检查以下几点:
1. 确认 `hot_reload` 设置为 `true`
2. 检查日志中是否有文件监控错误
3. 某些环境（如Docker）可能不支持热加载
4. 手动重启: `python run.py --reload`

### Q: 环境变量如何覆盖配置?

**A:** 优先级: `环境变量 > 配置文件 > 默认值`

```bash
# 环境变量会覆盖配置文件中同名配置
export QBT_HOST=192.168.1.100
export DEEPSEEK_API_KEY=sk-xxx
```

### Q: 如何添加新的分类?

**A:** 在 `categories` 配置节中添加：

```json
{
  "categories": {
    "my_category": {
      "savePath": "/downloads/my_category/",
      "keywords": ["keyword1", "keyword2"],
      "description": "我的自定义分类",
      "priority": 10
    }
  }
}
```

### Q: JSON Schema如何生效?

**A:** 
1. 确保IDE安装了JSON Schema支持插件
2. 配置文件命名为 `config.json` 或 `config.*.json`
3. 重启IDE或重新加载窗口

---

## 相关资源

- [项目README](../../README.md)
- [部署指南](../DEPLOYMENT_GUIDE.md)
- [故障排除](../TROUBLESHOOTING.md)
- [Python Pydantic文档](https://docs.pydantic.dev/)
- [JSON Schema规范](https://json-schema.org/)

---

## 更新日志

### v2.5.0 (2026-03-12)

- ✨ 新增完整配置文档化方案
- ✨ 新增JSON Schema支持IDE自动补全
- ✨ 新增配置验证工具
- ✨ 新增文档自动生成工具
- ✨ 新增多环境配置示例
- 📚 新增环境变量完整映射表
