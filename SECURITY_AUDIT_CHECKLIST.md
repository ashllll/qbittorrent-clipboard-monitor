# qBittorrent Clipboard Monitor 安全审计清单

本文档提供全面的安全审计清单，用于验证安全加固措施的有效性。

---

## 1. 输入验证审计

### 1.1 磁力链接验证

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 验证有效的40位十六进制hash | 输入标准磁力链接 | 通过验证 | ✅ |
| 验证有效的32位base32 hash | 输入base32格式链接 | 通过验证 | ✅ |
| 拒绝空字符串 | 输入空字符串 | 返回错误 | ✅ |
| 拒绝None值 | 输入None | 返回类型错误 | ✅ |
| 拒绝过短的链接 | 输入长度<50的链接 | 返回长度错误 | ✅ |
| 拒绝过长的链接 | 输入长度>4096的链接 | 返回长度错误 | ✅ |
| 拒绝非magnet协议 | 输入http链接 | 返回协议错误 | ✅ |
| 拒绝缺少xt参数 | 输入无xt参数的链接 | 返回参数错误 | ✅ |
| 拒绝非法hash长度 | 输入16位hash | 返回hash错误 | ✅ |
| 拒绝不支持的参数 | 添加非法参数 | 返回参数错误 | ✅ |
| 拒绝控制字符 | 插入\x00等控制字符 | 返回字符错误 | ✅ |
| 验证参数值长度限制 | 添加超长参数值 | 返回长度错误 | ✅ |
| 验证tracker数量限制 | 添加>20个tracker | 返回数量错误 | ✅ |

### 1.2 路径验证

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 验证有效路径 | 输入/downloads/movies | 通过验证 | ✅ |
| 拒绝空路径 | 输入空字符串 | 抛出异常 | ✅ |
| 拒绝None路径 | 输入None | 抛出异常 | ✅ |
| 拒绝路径遍历 ../ | 输入../../../etc/passwd | 抛出异常 | ✅ |
| 拒绝Windows遍历 \\..\\ | 输入..\\windows | 抛出异常 | ✅ |
| 拒绝非法字符 | 输入<>:"\|?* | 抛出异常 | ✅ |
| 拒绝Windows保留名 | 输入CON, PRN, AUX等 | 抛出异常 | ✅ |
| 验证深度限制 | 输入超过32层的路径 | 抛出异常 | ✅ |
| 验证安全路径检查 | 检查路径是否在根目录下 | 正确判断 | ✅ |

### 1.3 URL验证

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 验证HTTP URL | 输入http://example.com | 通过验证 | ✅ |
| 验证HTTPS URL | 输入https://example.com | 通过验证 | ✅ |
| 拒绝空URL | 输入空字符串 | 抛出异常 | ✅ |
| 拒绝JavaScript协议 | 输入javascript:alert(1) | 抛出异常 | ✅ |
| 拒绝Data URI | 输入data:text/html... | 抛出异常 | ✅ |
| 拒绝File协议 | 输入file:///etc/passwd | 抛出异常 | ✅ |
| 拒绝FTP协议 | 输入ftp://example.com | 抛出异常 | ✅ |
| 拒绝URL中的凭证 | 输入http://user:pass@... | 抛出异常 | ✅ |
| 拒绝私有IP（可选） | 输入192.168.x.x | 可选抛出异常 | ✅ |
| 强制HTTPS（可选） | 输入http链接 | 可选抛出异常 | ✅ |
| 验证URL长度限制 | 输入超长URL | 抛出异常 | ✅ |

### 1.4 主机名验证

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 验证有效主机名 | 输入example.com | 通过验证 | ✅ |
| 验证IPv4地址 | 输入192.168.1.1 | 通过验证 | ✅ |
| 拒绝命令注入 | 输入; rm -rf / | 抛出异常 | ✅ |
| 拒绝控制字符 | 输入\x00 | 抛出异常 | ✅ |
| 拒绝管道字符 | 输入\|cat | 抛出异常 | ✅ |
| 验证长度限制 | 输入超长主机名 | 抛出异常 | ✅ |

### 1.5 内容大小验证

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 验证正常内容 | 输入1KB文本 | 通过验证 | ✅ |
| 拒绝超大内容 | 输入>10MB内容 | 返回错误 | ✅ |
| 拒绝过多行数 | 输入>10000行 | 返回错误 | ✅ |
| 拒绝超长行 | 输入>10000字符的行 | 返回错误 | ✅ |

### 1.6 特殊字符过滤

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 过滤HTML标签 | 输入<script> | 标签被转义 | ✅ |
| 过滤双向字符 | 输入\u202E | 字符被移除 | ✅ |
| 检测XSS注入 | 输入<script>alert(1) | 检测到注入 | ✅ |
| 检测JS注入 | 输入javascript: | 检测到注入 | ✅ |
| 实体编码 | 输入< > " | 转换为实体 | ✅ |

---

## 2. 速率限制审计

### 2.1 滑动窗口算法

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 允许正常请求 | 发送3次/分钟 | 全部通过 | ✅ |
| 限制超额请求 | 发送10次/分钟（限5次） | 后5次被拒绝 | ✅ |
| 正确计算重试时间 | 触发限制后检查 | retry_after>0 | ✅ |
| 窗口滑过重置 | 等待窗口时间后重试 | 请求通过 | ✅ |

### 2.2 令牌桶算法

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 允许突发流量 | 发送10个请求（桶容量10） | 全部通过 | ✅ |
| 限制后续请求 | 继续发送请求 | 被拒绝 | ✅ |
| 令牌补充 | 等待后重试 | 部分通过 | ✅ |

### 2.3 固定窗口算法

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 允许窗口内请求 | 发送N次/窗口 | 前N次通过 | ✅ |
| 限制窗口外请求 | 超过N次 | 被拒绝 | ✅ |
| 新窗口重置 | 等待窗口时间 | 计数重置 | ✅ |

### 2.4 剪贴板专用限制器

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 磁力链接处理限制 | 快速处理100+磁力链接 | 触发限制 | ✅ |
| API调用限制 | 快速调用API | 触发限制 | ✅ |
| 分类请求限制 | 快速分类请求 | 触发限制 | ✅ |

---

## 3. 熔断器审计

### 3.1 状态转换

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 初始状态关闭 | 创建熔断器 | state=CLOSED | ✅ |
| 连续失败触发熔断 | 失败N次 | state=OPEN | ✅ |
| 超时后进入半开 | 等待超时时间 | state=HALF_OPEN | ✅ |
| 测试成功关闭熔断 | 半开状态成功M次 | state=CLOSED | ✅ |
| 测试失败重新打开 | 半开状态失败 | state=OPEN | ✅ |

### 3.2 快速失败

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 熔断时快速失败 | 熔断器打开时调用 | 抛出CircuitBreakerError | ✅ |
| 不执行被保护函数 | 熔断器打开时调用 | 函数不被调用 | ✅ |
| 返回重试时间 | 熔断时检查错误 | 包含retry_after | ✅ |

### 3.3 统计信息

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 记录失败次数 | 触发多次失败 | 失败计数正确 | ✅ |
| 记录成功次数 | 多次成功 | 成功计数正确 | ✅ |
| 记录熔断次数 | 多次熔断 | open_count正确 | ✅ |
| 记录连续失败 | 连续失败 | consecutive_failures正确 | ✅ |

---

## 4. 日志脱敏审计

### 4.1 敏感信息过滤

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 过滤API密钥 | 日志包含sk-xxx | 显示*** | ✅ |
| 过滤密码 | 日志包含password=xxx | 显示*** | ✅ |
| 过滤Bearer令牌 | 日志包含Bearer xxx | 显示*** | ✅ |
| 过滤磁力hash | 日志包含完整hash | 只显示前8位 | ✅ |
| 过滤JWT令牌 | 日志包含eyJ... | 签名部分隐藏 | ✅ |
| 过滤SSH密钥 | 日志包含ssh-rsa | 显示*** | ✅ |
| 过滤DB连接字符串 | 日志包含://user:pass@ | 密码显示*** | ✅ |
| 过滤Cookie | 日志包含session=xxx | 显示*** | ✅ |

### 4.2 字典脱敏

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 脱敏嵌套密码 | 嵌套字典中的password | 递归脱敏 | ✅ |
| 脱敏列表中的敏感字段 | 列表包含敏感字典 | 正确处理 | ✅ |
| 保留非敏感字段 | 普通字段 | 保持不变 | ✅ |
| 部分脱敏用户名 | username字段 | 部分隐藏 | ✅ |

### 4.3 安全字符串

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 安全存储值 | 创建SecureString | 值被存储 | ✅ |
| 脱敏表示 | 获取masked属性 | 显示*** | ✅ |
| 安全的repr | 打印对象 | 不显示值 | ✅ |
| 清理功能 | 调用clear() | 值被清除 | ✅ |

---

## 5. 资源监控审计

### 5.1 内存监控

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 获取内存使用 | 调用get_memory_usage | 返回MB数 | ✅ |
| 内存超限警告 | 模拟高内存 | 触发警告 | ✅ |
| 内存超限违规 | 超过max_memory | 触发违规 | ✅ |
| 记录峰值内存 | 运行一段时间 | peak_memory正确 | ✅ |

### 5.2 CPU监控

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 获取CPU使用率 | 调用get_cpu_percent | 返回百分比 | ✅ |
| CPU超限警告 | 模拟高CPU | 触发警告 | ✅ |
| CPU超限违规 | 超过max_cpu | 触发违规 | ✅ |

### 5.3 线程监控

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| 获取线程数 | 调用get_thread_count | 返回线程数 | ✅ |
| 线程超限违规 | 超过max_threads | 触发违规 | ✅ |

---

## 6. 安全头部审计

| 检查项 | 测试方法 | 预期结果 | 状态 |
|--------|----------|----------|------|
| X-Content-Type-Options | 检查返回头 | nosniff | ✅ |
| X-Frame-Options | 检查返回头 | DENY | ✅ |
| X-XSS-Protection | 检查返回头 | 1; mode=block | ✅ |
| Cache-Control | 检查返回头 | no-cache... | ✅ |

---

## 7. 自动化安全测试

### 7.1 运行安全测试

```bash
# 运行所有安全测试
pytest tests/test_security_enhanced.py -v

# 运行特定测试类
pytest tests/test_security_enhanced.py::TestMagnetValidation -v
pytest tests/test_security_enhanced.py::TestRateLimiter -v
pytest tests/test_security_enhanced.py::TestCircuitBreaker -v

# 运行带覆盖率的安全测试
pytest tests/test_security_enhanced.py --cov=qbittorrent_monitor --cov-report=term-missing
```

### 7.2 预期测试结果

```
tests/test_security_enhanced.py::TestMagnetValidation::test_valid_magnet_hex PASSED
tests/test_security_enhanced.py::TestMagnetValidation::test_valid_magnet_base32 PASSED
tests/test_security_enhanced.py::TestMagnetValidation::test_invalid_empty PASSED
... [其他测试] ...

=================== 50+ passed in X.XXs ===================
```

---

## 8. 手动安全测试步骤

### 8.1 输入验证测试

```python
from qbittorrent_monitor.security_enhanced import validate_magnet_strict

# 测试有效磁力链接
magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Test"
print(validate_magnet_strict(magnet))  # (True, None)

# 测试无效磁力链接
print(validate_magnet_strict("invalid"))  # (False, "...")
```

### 8.2 速率限制测试

```python
import asyncio
from qbittorrent_monitor.rate_limiter import RateLimiter, RateLimitConfig

async def test_rate_limit():
    limiter = RateLimiter(RateLimitConfig(max_requests=3))
    for i in range(5):
        allowed, status = await limiter.acquire("test")
        print(f"Request {i+1}: allowed={allowed}")

asyncio.run(test_rate_limit())
```

### 8.3 熔断器测试

```python
import asyncio
from qbittorrent_monitor.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

async def test_circuit_breaker():
    breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))
    
    async def fail():
        raise ValueError("Always fails")
    
    for i in range(5):
        try:
            await breaker.call(fail)
        except Exception as e:
            print(f"Call {i+1}: {type(e).__name__}")

asyncio.run(test_circuit_breaker())
```

---

## 9. 安全加固总结

### 已实施的安全措施

1. ✅ **输入验证增强**
   - 磁力链接参数白名单
   - 路径深度限制（32层）
   - 内容大小限制（10MB）
   - 特殊字符过滤

2. ✅ **速率限制**
   - 滑动窗口算法
   - 令牌桶算法
   - 固定窗口算法
   - 剪贴板专用限制器

3. ✅ **熔断机制**
   - 三态熔断器（CLOSED/OPEN/HALF_OPEN）
   - 自动恢复
   - 统计信息
   - 快速失败

4. ✅ **日志脱敏**
   - 增强敏感信息过滤器
   - 安全字符串存储
   - 配置脱敏
   - 审计日志

5. ✅ **资源监控**
   - 内存使用监控
   - CPU使用监控
   - 线程数监控
   - 违规检测

6. ✅ **安全头部**
   - X-Content-Type-Options
   - X-Frame-Options
   - X-XSS-Protection
   - Cache-Control

### 安全合规性

- ✅ OWASP输入验证指南
- ✅ OWASP日志安全指南
- ✅ OWASP DoS防护指南
- ✅ OWASP安全配置指南

### 后续建议

1. 定期更新依赖包以修复安全漏洞
2. 启用HTTPS以加密传输
3. 实施更细粒度的访问控制
4. 定期进行渗透测试
5. 监控安全公告并及时响应
