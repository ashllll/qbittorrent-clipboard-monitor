# Ruflo 集成规划

## 当前系统分析

### 现有 AI 分类流程
```
用户复制磁力链接 → ClipboardMonitor → ClipboardProcessor → AIClassifier → 分类结果 → 添加到 qBittorrent
```

### 现有组件
- `ai_classifier.py` - AI 分类器 (DeepSeek/OpenAI)
- `workflow_engine.py` - 工作流引擎
- `clipboard_actions.py` - 动作执行器

---

## Ruflo 集成方案

### 方案 1: 增强型 AI 分类器

使用 Ruflo 的多 Agent 协作进行深度内容分析:

```
原始流程:
torrent_name → AIClassifier → category

Ruflo 增强流程:
torrent_name → [Agent1: 提取关键词] → [Agent2: 分析类型] → [Agent3: 确定分类] → category
```

**优点:**
- 更准确的分类
- 可处理复杂命名
- 支持多语言

**实现方式:**
1. 安装 Ruflo: `npx ruflo@latest init`
2. 创建自定义 Agent 配置
3. 集成到 ai_classifier.py

---

### 方案 2: Swarm 批量处理

使用 Ruflo Swarm 并行处理多个下载任务:

```
场景: 用户复制多个磁力链接或批量 URL

Ruflo Swarm:
┌─ Agent 1: 解析链接
├─ Agent 2: 提取信息  
├─ Agent 3: 分类判断
├─ Agent 4: 决策保存路径
└─ Agent 5: 执行下载
```

**优点:**
- 并行处理提高效率
- 智能任务分配
- 错误自动恢复

---

### 方案 3: 自学习优化

利用 Ruflo 的学习能力优化分类:

1. **收集反馈** - 用户手动调整分类
2. **模式存储** - 成功分类模式存入 Memory
3. **智能路由** - 类似任务路由到最佳 Agent

---

## 集成步骤

### Step 1: 安装 Ruflo

```bash
# 安装 CLI
npm install -g claude-flow

# 或使用 npx
npx ruflo@latest init --wizard
```

### Step 2: 配置 Agent

创建 `ruflo-config.yaml`:

```yaml
agents:
  - name: classifier
    role: analyzer
    skills: [text-analysis, categorization]
    
  - name: researcher  
    role: information
    skills: [web-search, content-extraction]
    
swarm:
  topology: mesh
  maxAgents: 5
```

### Step 3: 集成到代码

修改 `ai_classifier.py`:

```python
import subprocess
import json

class RufloClassifier:
    """基于 Ruflo 的增强分类器"""
    
    def __init__(self, config):
        self.config = config
        self.ruflo_path = "npx ruflo@latest"
    
    async def classify(self, torrent_name: str, categories: Dict) -> str:
        # 调用 Ruflo Agent 进行分类
        result = subprocess.run(
            [self.ruflo_path, "run", "--agent", "classifier", 
             "--input", f"Classify: {torrent_name}"],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
```

---

## 推荐集成方案

### 渐进式集成 (推荐)

| 阶段 | 目标 | 改动 |
|------|------|------|
| 1 | 保持现有 | 熟悉 Ruflo CLI |
| 2 | 并行测试 | 新增 RufloClassifier 类 |
| 3 | A/B 测试 | 对比两种分类结果 |
| 4 | 智能切换 | 复杂任务用 Ruflo |
| 5 | 完全迁移 | 移除旧代码 |

---

## 风险与注意事项

1. **依赖外部服务** - Ruflo 需要网络连接
2. **延迟增加** - 多 Agent 协作比直接 API 慢
3. **成本考虑** - 多 Agent 调用成本更高
4. **兼容性** - 需要 Node.js 18+

---

## 下一步行动

1. ✅ 规划完成
2. ⏳ 用户确认集成方案
3. 📝 实现选定的集成方式
