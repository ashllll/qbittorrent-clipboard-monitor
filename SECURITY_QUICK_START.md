# 安全加固快速入门

本文档提供安全加固功能的快速参考。

## 新模块一览

| 模块 | 功能 | 文件大小 |
|------|------|----------|
| `security_enhanced.py` | 输入验证和清理 | 27KB |
| `rate_limiter.py` | DoS防护和速率限制 | 20KB |
| `circuit_breaker.py` | 故障保护和熔断 | 17KB |
| `logging_enhanced.py` | 日志脱敏和审计 | 19KB |
| `resource_monitor.py` | 资源监控 | 19KB |

## 快速使用

### 1. 磁力链接验证

```python
from qbittorrent_monitor.security_enhanced import validate_magnet_strict

is_valid, error = validate_magnet_strict(magnet_link)
if not is_valid:
    raise ValueError(f"Invalid magnet: {error}")
```

### 2. 速率限制

```python
from qbittorrent_monitor.rate_limiter import clipboard_rate_limiter

allowed, status = await clipboard_rate_limiter.check_magnet(magnet_hash)
if not allowed:
    raise RateLimitError(f"Retry after {status.retry_after}s")
```

### 3. 熔断器保护

```python
from qbittorrent_monitor.circuit_breaker import get_qb_circuit_breaker

breaker = await get_qb_circuit_breaker()
result = await breaker.call(qb_api_call, magnet_link)
```

### 4. 安全日志

```python
from qbittorrent_monitor.logging_enhanced import setup_secure_logging

logger, audit_logger = setup_secure_logging(
    level="INFO",
    log_file="/var/log/qb-monitor/app.log"
)
```

### 5. 资源监控

```python
from qbittorrent_monitor.resource_monitor import start_global_monitor_async

await start_global_monitor_async()
```

## 安全测试

```bash
# 运行所有安全测试
pytest tests/test_security_enhanced.py -v

# 生成覆盖率报告
pytest tests/test_security_enhanced.py --cov=qbittorrent_monitor --cov-report=html
```

## 配置选项

### 速率限制配置

```python
from qbittorrent_monitor.rate_limiter import RateLimitConfig, RateLimitStrategy

config = RateLimitConfig(
    max_requests=100,
    window_seconds=60.0,
    strategy=RateLimitStrategy.SLIDING_WINDOW
)
```

### 熔断器配置

```python
from qbittorrent_monitor.circuit_breaker import CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=5,
    success_threshold=3,
    timeout_seconds=60.0
)
```

### 资源限制

```python
from qbittorrent_monitor.resource_monitor import ResourceThresholds

thresholds = ResourceThresholds(
    max_memory_mb=512,
    max_cpu_percent=80,
    max_threads=100
)
```

## 安全常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `MAX_MAGNET_LENGTH` | 4096 | 磁力链接最大长度 |
| `MAX_MAGNET_PARAMS` | 50 | 最大参数数量 |
| `MAX_PATH_DEPTH` | 32 | 最大目录深度 |
| `MAX_URL_LENGTH` | 2048 | URL最大长度 |
| `MAX_CLIPBOARD_SIZE` | 10MB | 剪贴板内容最大大小 |

## 文档索引

- [安全审计清单](./SECURITY_AUDIT_CHECKLIST.md) - 完整的安全检查清单
- [安全加固报告](./SECURITY_HARDENING_REPORT.md) - 详细的加固报告
- [测试文件](./tests/test_security_enhanced.py) - 81个安全测试用例

## 合规性

- ✅ OWASP 输入验证指南
- ✅ OWASP 日志安全指南
- ✅ OWASP DoS 防护指南
- ✅ OWASP 安全配置指南
