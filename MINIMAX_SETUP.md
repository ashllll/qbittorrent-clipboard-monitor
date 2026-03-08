# Minimax AI 分类配置指南

## 简介

本项目已集成 Minimax AI 分类功能，使用 Anthropic API 兼容格式。

## 支持的模型

| 模型名称 | 上下文窗口 | 速度 | 说明 |
|---------|-----------|------|------|
| MiniMax-M2.5 | 204,800 | ~60 TPS | 顶尖性能与极致性价比 |
| MiniMax-M2.5-highspeed | 204,800 | ~100 TPS | M2.5 极速版 |
| MiniMax-M2.1 | 204,800 | ~60 TPS | 强大多语言编程能力 |
| MiniMax-M2.1-highspeed | 204,800 | ~100 TPS | M2.1 极速版 |
| MiniMax-M2 | 204,800 | - | 专为高效编码与 Agent 工作流而生 |

## 配置步骤

### 1. 获取 API 密钥

1. 访问 [MiniMax 开放平台](https://platform.minimaxi.com/)
2. 注册并登录账号
3. 在控制台获取 API 密钥

### 2. 修改配置文件

编辑 `~/.config/qb-monitor/config.json`：

```json
{
  "ai": {
    "enabled": true,
    "api_key": "your-minimax-api-key",
    "model": "MiniMax-M2.5",
    "base_url": "https://api.minimaxi.com/v1",
    "timeout": 30,
    "max_retries": 3
  }
}
```

### 3. 安装依赖

```bash
pip install anthropic
```

或使用 Poetry：

```bash
poetry install
```

### 4. 重启服务

```bash
pkill -f "run.py"
python3 run.py --web
```

## 环境变量配置

也可以通过环境变量配置：

```bash
export AI_ENABLED=true
export AI_API_KEY="your-minimax-api-key"
export AI_MODEL="MiniMax-M2.5"
export AI_BASE_URL="https://api.minimaxi.com/v1"
```

## 验证 AI 分类

在 Web 界面中查看日志，或查看剪贴板监控日志：

```
[INFO] AI 分类结果: movies (confidence=0.85, method=ai)
```

## 故障排除

### API 调用失败

1. 检查 API 密钥是否正确
2. 检查网络连接
3. 查看日志中的错误信息

### 分类不准确

1. 尝试使用更高性能的模型（如 MiniMax-M2.5）
2. 调整规则分类的关键词
3. 增加训练数据（通过反馈机制）

## 参考文档

- [MiniMax 官方文档](https://platform.minimaxi.com/docs/api-reference/text-anthropic-api)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
