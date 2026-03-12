# 配置参考手册

> **文档版本**: v2.5.0  
> **更新日期**: 2026-03-12  
> **适用版本**: qBittorrent剪贴板监控器 v2.5.0+

本文档提供 qBittorrent剪贴板监控器 的完整配置参考，包含所有配置项的详细说明。

---

## 目录

- [配置概述](#配置概述)
- [配置结构](#配置结构)
- [配置项详解](#配置项详解)
  - [qbittorrent](#qbittorrent)
  - [deepseek](#deepseek)
  - [categories](#categories)
  - [web_crawler](#web_crawler)
  - [notifications](#notifications)
  - [全局配置](#全局配置)
- [环境变量映射](#环境变量映射)
- [配置验证](#配置验证)
- [故障排除](#故障排除)

---

## 配置概述

### 配置文件位置

| 环境 | 路径 |
|------|------|
| 开发环境 | `./qbittorrent_monitor/config.json` |
| 生产环境 | `/app/config.json` (Docker) 或指定路径 |
| 自定义 | 通过 `--config` 参数指定 |

### 支持的格式

- **JSON** (`.json`) - 推荐，性能最佳
- **YAML** (`.yaml`, `.yml`) - 适合手工编辑
- **TOML** (`.toml`) - 类型安全

### 配置加载优先级

```
命令行参数 > 环境变量 > 配置文件 > 默认值
```

---

## 配置结构

```json
{
  "qbittorrent": {...},      // qBittorrent连接配置 [必需]
  "deepseek": {...},         // AI配置 [必需]
  "categories": {...},       // 分类配置 [必需]
  "web_crawler": {...},      // 爬虫配置 [可选]
  "notifications": {...},    // 通知配置 [可选]
  "check_interval": 2.0,     // 检查间隔 [可选]
  ...
}
```

---

## 配置项详解

### qbittorrent

qBittorrent连接配置。

| 配置项 | 类型 | 必填 | 默认值 | 说明 | 示例 |
|--------|------|------|--------|------|------|
| `host` | string | ✅ | `192.168.1.40` | qBittorrent主机地址 | `"localhost"`, `"192.168.1.40"` |
| `port` | integer | ✅ | `8989` | Web UI端口 (1-65535) | `8080`, `8989` |
| `username` | string | ✅ | `admin` | 登录用户名 | `"admin"` |
| `password` | string | ✅ | `password` | 登录密码（明文） | `"your_password"` |
| `hashed_password` | string | ❌ | `null` | 哈希密码（更安全） | `"$2b$12$..."` |
| `use_https` | boolean | ❌ | `false` | 使用HTTPS连接 | `true` / `false` |
| `verify_ssl` | boolean | ❌ | `true` | 验证SSL证书 | `true` / `false` |
| `use_nas_paths_directly` | boolean | ❌ | `false` | 直接使用NAS路径 | `true` / `false` |
| `path_mapping` | array | ❌ | `[]` | 路径映射规则 | 见下方示例 |

**path_mapping 结构:**

```json
{
  "path_mapping": [
    {
      "source_prefix": "/downloads",
      "target_prefix": "/vol1/downloads",
      "description": "本地到NAS的路径映射"
    }
  ]
}
```

**安全建议:**
- 生产环境使用 `hashed_password` 替代明文 `password`
- 使用 HTTPS 并启用 `verify_ssl`
- 限制 qBittorrent Web UI 的网络访问

---

### deepseek

DeepSeek AI配置，用于智能分类。

| 配置项 | 类型 | 必填 | 默认值 | 说明 | 示例 |
|--------|------|------|--------|------|------|
| `api_key` | string | ❌ | `""` | DeepSeek API密钥 | `"sk-..."` |
| `model` | string | ❌ | `deepseek-chat` | AI模型名称 | `"deepseek-chat"` |
| `base_url` | string | ❌ | `https://api.deepseek.com` | API基础URL | `"https://api.deepseek.com"` |
| `timeout` | integer | ❌ | `30` | 请求超时(秒) (1-300) | `30` |
| `max_retries` | integer | ❌ | `3` | 最大重试次数 (0-10) | `3` |
| `retry_delay` | number | ❌ | `1.0` | 重试延迟(秒) (0-60) | `1.0` |
| `few_shot_examples` | array | ❌ | `null` | Few-shot示例 | 见下方示例 |
| `prompt_template` | string | ❌ | 内置模板 | 分类提示词模板 | 见下方示例 |

**few_shot_examples 结构:**

```json
{
  "few_shot_examples": [
    {
      "torrent_name": "Game.of.Thrones.S08E06.1080p.WEB.H264-MEMENTO",
      "category": "tv"
    },
    {
      "torrent_name": "Avengers.Endgame.2019.1080p.BluRay.x264-SPARKS",
      "category": "movies"
    }
  ]
}
```

**支持的模型:**
- `deepseek-chat` - DeepSeek聊天模型（推荐）
- `deepseek-coder` - DeepSeek代码模型
- `gpt-3.5-turbo` - OpenAI GPT-3.5
- `gpt-4` - OpenAI GPT-4

---

### categories

下载分类配置，键为分类名称，值为分类配置。

| 配置项 | 类型 | 必填 | 默认值 | 说明 | 示例 |
|--------|------|------|--------|------|------|
| `savePath` | string | ✅ | - | 下载保存路径 | `"/downloads/movies/"` |
| `keywords` | array | ❌ | `[]` | 分类关键词列表 | `["电影", "Movie"]` |
| `description` | string | ❌ | `""` | 分类描述 | `"电影作品"` |
| `priority` | integer | ❌ | `0` | 优先级 (0-100) | `8` |
| `foreign_keywords` | array | ❌ | `null` | 外站关键词 | `["Brazzers"]` |
| `rules` | array | ❌ | `null` | 分类规则 | 见下方示例 |

**预定义分类:**

| 分类名 | 说明 | 推荐优先级 |
|--------|------|-----------|
| `movies` | 电影作品 | 8 |
| `tv` | 电视剧、连续剧 | 10 |
| `anime` | 日本动画、动漫 | 12 |
| `music` | 音乐专辑、单曲 | 6 |
| `games` | 电子游戏 | 7 |
| `software` | 应用程序、软件 | 5 |
| `adult` | 成人内容 | 15 |
| `other` | 其他内容 | 1 |

**rules 结构:**

```json
{
  "rules": [
    {
      "type": "regex",
      "pattern": "S\\d+E\\d+",
      "score": 5
    },
    {
      "type": "keyword",
      "keywords": ["Season", "Episode"],
      "score": 3
    }
  ]
}
```

**规则类型:**
- `regex` - 正则表达式匹配
- `keyword` - 关键词匹配

---

### web_crawler

网页爬虫配置，用于从URL提取磁力链接。

| 配置项 | 类型 | 必填 | 默认值 | 说明 | 范围 |
|--------|------|------|--------|------|------|
| `enabled` | boolean | ❌ | `true` | 启用爬虫 | - |
| `page_timeout` | integer | ❌ | `60000` | 页面超时(毫秒) | 1000-300000 |
| `wait_for` | integer | ❌ | `3` | 页面加载等待(秒) | 0-60 |
| `delay_before_return` | integer | ❌ | `2` | 返回前等待(秒) | 0-30 |
| `max_retries` | integer | ❌ | `3` | 最大重试次数 | 0-10 |
| `base_delay` | integer | ❌ | `5` | 基础延迟(秒) | 0-300 |
| `max_delay` | integer | ❌ | `60` | 最大延迟(秒) | 0-600 |
| `max_concurrent_extractions` | integer | ❌ | `3` | 最大并发提取数 | 1-20 |
| `inter_request_delay` | number | ❌ | `1.5` | 请求间延迟(秒) | 0-60 |
| `ai_classify_torrents` | boolean | ❌ | `true` | AI分类种子 | - |
| `add_torrents_paused` | boolean | ❌ | `false` | 暂停添加种子 | - |
| `proxy` | string | ❌ | `null` | 代理地址 | URL格式 |

**性能建议:**
- 低配服务器: `max_concurrent_extractions=1`, `page_timeout=30000`
- 标准配置: `max_concurrent_extractions=3`, `page_timeout=60000`
- 高性能服务器: `max_concurrent_extractions=5`, `page_timeout=120000`

---

### notifications

通知配置。

#### 主配置

| 配置项 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `enabled` | boolean | ❌ | `false` | 启用通知 |
| `services` | array | ❌ | `[]` | 通知服务列表 |
| `webhook_url` | string | ❌ | `null` | Webhook URL |
| `api_token` | string | ❌ | `null` | API令牌 |
| `chat_id` | string | ❌ | `null` | 聊天ID |
| `email_config` | object | ❌ | `null` | 邮件配置 |

#### console 子配置

| 配置项 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `enabled` | boolean | ❌ | `true` | 启用控制台通知 |
| `colored` | boolean | ❌ | `true` | 彩色输出 |
| `show_details` | boolean | ❌ | `true` | 显示详情 |
| `show_statistics` | boolean | ❌ | `true` | 显示统计 |

**支持的通知服务:**
- `telegram` - Telegram Bot
- `discord` - Discord Webhook
- `email` - SMTP邮件
- `webhook` - 自定义Webhook
- `apprise` - Apprise统一通知

**email_config 结构:**

```json
{
  "email_config": {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "your_email@gmail.com",
    "password": "your_app_password",
    "use_tls": true,
    "to_addresses": ["recipient@example.com"]
  }
}
```

---

### 全局配置

| 配置项 | 类型 | 必填 | 默认值 | 说明 | 范围 |
|--------|------|------|--------|------|------|
| `check_interval` | number | ❌ | `2.0` | 剪贴板检查间隔(秒) | 0.1-60 |
| `max_retries` | integer | ❌ | `3` | 最大重试次数 | 0-10 |
| `retry_delay` | number | ❌ | `5.0` | 重试延迟(秒) | 0-60 |
| `hot_reload` | boolean | ❌ | `true` | 配置热加载 | - |
| `log_level` | string | ❌ | `"INFO"` | 日志级别 | DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `log_file` | string/null | ❌ | `"magnet_monitor.log"` | 日志文件路径 | 文件路径或null |
| `add_torrents_paused` | boolean | ❌ | `false` | 暂停添加种子 | - |
| `ai_classify_torrents` | boolean | ❌ | `true` | AI分类种子 | - |
| `proxy` | string/null | ❌ | `null` | 代理地址 | URL格式 |
| `path_mapping` | object | ❌ | `{}` | 路径映射(向后兼容) | - |
| `use_nas_paths_directly` | boolean | ❌ | `false` | 直接使用NAS路径 | - |

**日志级别说明:**
- `DEBUG` - 调试信息（开发使用）
- `INFO` - 一般信息（推荐）
- `WARNING` - 警告信息
- `ERROR` - 错误信息
- `CRITICAL` - 严重错误

---

## 环境变量映射

### 优先级

```
环境变量 > 配置文件 > 默认值
```

### 完整映射表

| 环境变量 | 配置路径 | 说明 | 示例 |
|----------|----------|------|------|
| `QBT_HOST` | `qbittorrent.host` | qBittorrent主机 | `localhost` |
| `QBT_PORT` | `qbittorrent.port` | qBittorrent端口 | `8080` |
| `QBT_USERNAME` | `qbittorrent.username` | 登录用户名 | `admin` |
| `QBT_PASSWORD` | `qbittorrent.password` | 登录密码 | `password` |
| `QBT_USE_HTTPS` | `qbittorrent.use_https` | 使用HTTPS | `false` |
| `QBT_VERIFY_SSL` | `qbittorrent.verify_ssl` | 验证SSL | `true` |
| `DEEPSEEK_API_KEY` | `deepseek.api_key` | DeepSeek API密钥 | `sk-...` |
| `DEEPSEEK_BASE_URL` | `deepseek.base_url` | API基础URL | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | `deepseek.model` | AI模型 | `deepseek-chat` |
| `LOG_LEVEL` | `log_level` | 日志级别 | `INFO` |
| `LOG_FILE` | `log_file` | 日志文件 | `app.log` |
| `CHECK_INTERVAL` | `check_interval` | 检查间隔 | `2.0` |
| `HOT_RELOAD` | `hot_reload` | 热加载 | `true` |
| `PROXY` | `proxy` | 代理地址 | `http://127.0.0.1:7890` |

**Docker环境特殊变量:**

| 环境变量 | 说明 | 示例 |
|----------|------|------|
| `CONFIG_PATH` | 配置文件路径 | `/app/config.json` |
| `CONFIG_FORMAT` | 配置文件格式 | `json` / `yaml` |

---

## 配置验证

### 使用配置验证脚本

```bash
# 验证默认路径的配置文件
python scripts/config/validate_config.py

# 验证指定路径的配置文件
python scripts/config/validate_config.py --config /path/to/config.json

# 生成配置模板
python scripts/config/validate_config.py --template development
python scripts/config/validate_config.py --template production
python scripts/config/validate_config.py --template testing
```

### 常见验证错误

| 错误信息 | 原因 | 解决方案 |
|----------|------|----------|
| `缺少必需的配置节: qbittorrent` | qbittorrent配置节缺失 | 添加qbittorrent配置 |
| `主机地址不能为空` | qbittorrent.host为空 | 填写正确的主机地址 |
| `端口号必须在1-65535之间` | 端口号无效 | 修改端口号 |
| `分类 xxx 的保存路径与其他分类重复` | 保存路径重复 | 确保各分类路径唯一 |
| `API基础URL必须以http://或https://开头` | URL格式错误 | 修正URL格式 |

---

## 故障排除

### 配置不生效

1. 检查配置文件路径是否正确
2. 确认配置文件格式为有效的JSON/YAML/TOML
3. 查看日志确认配置加载情况
4. 检查环境变量是否覆盖了配置

### 热加载不工作

1. 确认 `hot_reload` 设置为 `true`
2. 检查文件系统监控是否可用
3. 查看日志中的文件监控事件
4. 考虑手动重启服务

### 敏感信息泄露

1. 使用 `hashed_password` 替代明文密码
2. 将API密钥移至环境变量
3. 配置文件设置正确的文件权限 (`chmod 600`)
4. 避免将配置文件提交到版本控制

---

## 相关文档

- [快速开始指南](./guides/QUICKSTART.md)
- [多环境配置指南](./guides/MULTI_ENVIRONMENT.md)
- [JSON Schema](./schema/config.schema.json)
- [环境变量说明](./ENVIRONMENT_VARIABLES.md)
