# 模块优化详细规划

## 当前状态
- Python 文件: 56
- 代码行数: 21,910
- 依赖关系已分析完成

---

## 优化方案 1: 清理 web_crawler.py 未使用的类

### 分析结果
- `ConfigurableSiteAdapter` 仅被引用 2 次 (在 web_crawler.py 内部)
- 这是安全的清理目标

### 执行步骤
1. 确认 `ConfigurableSiteAdapter` 未被外部使用
2. 标记为 deprecated 或删除

---

## 优化方案 2: 整合 retry.py 到 resilience.py

### 分析结果
- `retry.py` 仅被 `fallback.py` 使用 (1 个文件依赖)
- `resilience.py` 被 8 个文件使用
- 风险: 低

### 执行步骤
1. 将 `retry.py` 中的 `RetryConfig`, `RetryableError` 移到 `resilience.py`
2. 更新 `fallback.py` 的导入
3. 删除 `retry.py`

---

## 优化方案 3: 统一 circuit_breaker.py 的导入

### 分析结果
- `circuit_breaker.py` 被引用 32 次，但大部分是使用 `resilience.py` 中的类
- 实际直接使用 `circuit_breaker.py` 的是 `web_interface/app.py`

### 执行步骤
1. 保持 `resilience.py` 作为主要导入源
2. 在 `circuit_breaker.py` 中从 `resilience` 导入基础类
3. 不删除任何文件，只优化导入

---

## 优化方案 4: 拆分 clipboard_monitor.py

### 分析结果
- 包含 4 个类: ClipboardMonitor, ActivityTracker, SmartBatcher, OptimizedClipboardMonitor
- ActivityTracker 和 SmartBatcher 是独立功能

### 执行步骤
1. 将 ActivityTracker 移到新文件 `activity_tracker.py`
2. 将 SmartBatcher 移到新文件 `smart_batcher.py`
3. 在 clipboard_monitor.py 中导入这些类 (向后兼容)

---

## 执行顺序

1. ✅ 已完成: 清理空子模块
2. 🔄 下一步: 方案 1 (清理未使用类)
3. 📋 方案 2 (整合 retry)
4. 📋 方案 3 (统一导入)
5. 📋 方案 4 (拆分大文件)

---

## 风险评估

| 方案 | 风险 | 影响范围 |
|------|------|----------|
| 方案1 | 极低 | 仅内部类 |
| 方案2 | 低 | 1个导入 |
| 方案3 | 中 | 需测试 |
| 方案4 | 中高 | 多处导入 |

---

## 回滚计划

每个方案执行前创建 git tag:
- 优化前: `before-opt-YYYYMMDD`

如果出现问题:
```bash
git reset --hard before-opt-YYYYMMDD
```
