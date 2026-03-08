# 安全审计报告

**项目名称**: qBittorrent Clipboard Monitor  
**审计日期**: 2026-03-08  
**审计版本**: 3.0.0  

## 执行摘要

本次安全审计对 qBittorrent Clipboard Monitor 项目进行了全面的安全评估，识别并修复了多个安全问题。所有已识别的中高危问题均已修复。

## 审计范围

审计覆盖了以下方面：
1. 敏感信息处理（密码、API密钥）
2. 日志中的敏感信息过滤
3. 输入验证（磁力链接解析）
4. 文件权限和路径遍历
5. 依赖安全扫描

## 发现的问题

### 1. 路径遍历漏洞 [高危] ✅ 已修复

**描述**: `CategoryConfig` 的 `save_path` 配置未验证路径遍历字符，可能导致攻击者通过配置访问系统任意文件。

**影响**: 攻击者可能通过构造特殊的 `save_path`（如 `../../../etc/passwd`）读取或写入系统敏感文件。

**修复措施**:
- 新增 `validate_save_path()` 函数，检查路径遍历模式
- 阻止包含 `..`、`~`、`$VAR` 等危险字符的路径
- 检查 Windows 保留名称（CON、PRN 等）
- 检查非法字符（`<`、`>`、`:`、`"`、`|`、`?`、`*`）

**文件修改**: `qbittorrent_monitor/security.py`, `qbittorrent_monitor/config.py`

---

### 2. 磁力链接验证不足 [中危] ✅ 已修复

**描述**: 磁力链接解析函数缺乏严格的输入验证，可能导致处理恶意构造的链接。

**影响**: 可能处理格式错误或恶意的磁力链接，存在 DoS 风险。

**修复措施**:
- 新增 `validate_magnet()` 函数，验证磁力链接格式
- 检查协议前缀（必须以 `magnet:?` 开头）
- 验证 btih hash 长度（32位 base32 或 40位 十六进制）
- 检查控制字符和非法字符
- 限制磁力链接最大长度（8192字符）防止 DoS
- 新增 `sanitize_magnet()` 函数清理输入

**文件修改**: `qbittorrent_monitor/security.py`, `qbittorrent_monitor/utils.py`, `qbittorrent_monitor/monitor.py`

---

### 3. 敏感信息泄露 [中危] ✅ 已修复

**描述**: 日志中可能包含密码、API密钥等敏感信息。

**影响**: 日志文件泄露可能导致凭证被盗用。

**修复措施**:
- 增强 `SensitiveDataFilter` 类，支持更多敏感模式
- 新增对 API 密钥（`sk-` 开头的密钥）的过滤
- 增强磁力链接 hash 过滤（支持32位和40位）
- 新增对配置文件中密码字段的过滤
- 新增 `RedactingFormatter` 格式化器
- 新增 `sanitize_for_log()` 辅助函数

**文件修改**: `qbittorrent_monitor/logging_filters.py`

---

### 4. 输入验证不足 [中危] ✅ 已修复

**描述**: 主机名、URL 等输入缺乏验证，可能存在命令注入风险。

**影响**: 可能通过恶意输入执行命令注入攻击。

**修复措施**:
- 新增 `validate_hostname()` 函数，检查命令注入字符
- 新增 `validate_url()` 函数，验证 URL 安全
  - 仅允许 HTTP/HTTPS 协议
  - 禁止 URL 中包含认证信息
  - 检查非法字符
- 新增 `sanitize_filename()` 函数清理文件名

**文件修改**: `qbittorrent_monitor/security.py`, `qbittorrent_monitor/config.py`

---

### 5. 缺少安全头部 [低危] ✅ 已修复

**描述**: HTTP 请求缺少安全头部，可能泄露应用程序信息。

**影响**: 攻击者可能根据应用程序版本信息进行针对性攻击。

**修复措施**:
- 新增 `get_secure_headers()` 函数生成安全头部
- 添加标准的 `User-Agent`、`Accept` 等头部
- 在 `QBClient` 中使用安全头部

**文件修改**: `qbittorrent_monitor/security.py`, `qbittorrent_monitor/qb_client.py`

---

### 6. 文件权限不安全 [低危] ✅ 已修复

**描述**: 配置文件创建时使用默认权限，可能被其他用户读取。

**影响**: 配置文件中的敏感信息可能被系统上的其他用户读取。

**修复措施**:
- 配置文件保存时设置权限为 `0o600`（仅用户可读写）
- 使用 `os.chmod()` 确保权限设置

**文件修改**: `qbittorrent_monitor/config.py`

---

### 7. 哈希算法安全性 [低危] ✅ 已修复

**描述**: 缓存使用 MD5 哈希算法，存在碰撞风险。

**影响**: MD5 已被证明存在碰撞漏洞，不建议用于安全相关场景。

**修复措施**:
- 将缓存哈希算法从 MD5 升级为 SHA256
- 保持向后兼容性

**文件修改**: `qbittorrent_monitor/monitor.py`

---

## 新增安全模块

### qbittorrent_monitor/security.py

新增安全工具模块，提供以下功能：

1. **磁力链接验证**:
   - `validate_magnet()` - 验证磁力链接有效性
   - `sanitize_magnet()` - 清理磁力链接
   - `extract_magnet_hash_safe()` - 安全提取 hash

2. **路径遍历防护**:
   - `validate_save_path()` - 验证保存路径安全
   - `sanitize_filename()` - 清理文件名

3. **URL 和主机名验证**:
   - `validate_url()` - 验证 URL 安全
   - `validate_hostname()` - 验证主机名安全

4. **敏感信息处理**:
   - `is_sensitive_field()` - 检测敏感字段
   - `mask_sensitive_value()` - 遮盖敏感值

5. **安全常量**:
   - `SAFE_TIMEOUTS` - 安全超时设置
   - `SAFE_LIMITS` - 安全限制

## 测试覆盖

新增 `tests/test_security.py`，包含 46 个安全测试用例：

- `TestMagnetValidation` - 磁力链接验证测试
- `TestPathTraversal` - 路径遍历防护测试
- `TestFilenameSanitization` - 文件名清理测试
- `TestUrlValidation` - URL 验证测试
- `TestHostnameValidation` - 主机名验证测试
- `TestSensitiveDataFilter` - 敏感数据过滤测试
- `TestSensitiveFieldDetection` - 敏感字段检测测试
- `TestSecureHeaders` - 安全头部测试
- `TestLoggingIntegration` - 日志集成测试
- `TestSecurityConstants` - 安全常量测试

## 安全文档

新增文档：

1. **SECURITY.md** - 项目安全策略文档
   - 支持的版本
   - 安全特性说明
   - 漏洞报告流程
   - 安全最佳实践
   - 依赖安全监控

2. **SECURITY_AUDIT_REPORT.md** - 本审计报告

3. **scripts/security_scan.py** - 依赖安全扫描脚本

## 修复验证

所有安全问题修复后，运行测试验证：

```bash
# 运行所有测试
python -m pytest tests/ -v

# 测试结果
============================= test results =============================
102 passed, 7 warnings in 0.39s
```

所有测试通过，修复有效。

## 建议

1. **定期安全审计**: 建议每季度进行一次安全审计
2. **依赖更新**: 定期运行 `scripts/security_scan.py` 检查依赖漏洞
3. **监控日志**: 定期检查日志文件是否有异常活动
4. **HTTPS 优先**: 生产环境应始终使用 HTTPS 连接 qBittorrent
5. **最小权限原则**: 以最小权限运行应用程序

## 结论

本次安全审计成功识别并修复了 7 个安全问题，新增 46 个安全测试用例，建立了完整的安全防护体系。项目现在具备了：

- ✅ 全面的输入验证
- ✅ 路径遍历防护
- ✅ 敏感信息过滤
- ✅ 安全日志记录
- ✅ 安全文档和流程

项目已达到生产环境的安全要求。

---

**审计人员**: Kimi Code CLI  
**审计完成日期**: 2026-03-08  
**下次审计建议日期**: 2026-06-08
