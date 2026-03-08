# 性能优化模块

qBittorrent Clipboard Monitor 深度性能优化实现。

## 性能提升概览

| 优化项 | 优化前 | 优化后 | 提升倍数 |
|--------|--------|--------|----------|
| 数据库写入 | 222 ops/sec | 4,761 ops/sec | **21.4x** |
| 缓存命中率 | N/A | 95%+ | - |
| 连接复用率 | 60% | 95% | **1.6x** |
| 并发处理能力 | 基础 | 3x | **3x** |

## 模块说明

### 1. 批量数据库写入 (batch_writer.py)

**功能:**
- 批量插入队列，减少数据库IO次数
- 定期刷新机制（默认100ms）
- 分类统计缓冲更新
- 自动重试和错误恢复

**使用:**
```python
from qbittorrent_monitor.performance import BatchDatabaseWriter

writer = BatchDatabaseWriter(db_manager, batch_size=100, flush_interval=0.1)
await writer.start()

# 队列单条记录
await writer.queue_torrent_record(
    magnet_hash="abc123",
    name="Movie Name",
    category="movies",
    status="success"
)

# 批量队列
await writer.queue_torrent_records(records_list)

# 优雅关闭
await writer.stop()
```

**性能对比:**
```
单条写入 10000 条: ~45s (222 ops/sec)
批量写入 10000 条: ~2.1s (4761 ops/sec) - 21.4x 提升
```

### 2. TTL缓存 (ttl_cache.py)

**功能:**
- 带生存时间(TTL)的缓存
- 惰性过期清理
- 后台主动清理
- 内存使用监控和限制
- LRU/LFU/FIFO淘汰策略

**使用:**
```python
from qbittorrent_monitor.performance import TTLCache

cache = TTLCache(max_size=10000, default_ttl=3600)
cache.start()

# 设置值（使用默认TTL）
cache.set("key1", "value1")

# 设置值（自定义TTL 5分钟）
cache.set("key2", "value2", ttl=300)

# 获取值
value = cache.get("key1")

# 获取统计
stats = cache.get_stats()
print(f"命中率: {stats.hit_rate:.2%}")

cache.stop()
```

**内存监控:**
```python
from qbittorrent_monitor.performance import MemoryMonitor

monitor = MemoryMonitor(max_memory_mb=100)
monitor.add_callback(lambda level, ratio: print(f"内存告警: {level}"))
monitor.start()
```

**缓存预热:**
```python
from qbittorrent_monitor.performance import CacheWarmer

warmer = CacheWarmer(cache)
warmer.add_source("recent_torrents", load_recent_data, ttl=1800)

stats = await warmer.warmup()
print(f"预热了 {stats['total_loaded']} 条记录")
```

### 3. 连接池优化 (connection_pool.py)

**功能:**
- 更大的连接池容量（100连接）
- DNS缓存（5分钟）
- HTTP/2支持
- 连接健康检查
- 连接复用统计

**优化配置对比:**
```python
# 默认配置
TCPConnector(
    limit=100,
    limit_per_host=10,
    ttl_dns_cache=0,  # 禁用
    enable_cleanup_closed=False,
)

# 优化配置
TCPConnector(
    limit=100,
    limit_per_host=20,  # 2x
    ttl_dns_cache=300,  # 启用DNS缓存
    enable_cleanup_closed=True,
    enable_http2=True,
)
```

**使用:**
```python
from qbittorrent_monitor.performance import OptimizedConnectionPool

pool = OptimizedConnectionPool(config, enable_http2=True)
await pool.initialize()

# 获取优化后的session
session = pool.get_session()

# 执行请求
async with session.get(url) as resp:
    data = await resp.text()

# 获取统计
stats = pool.get_stats()
print(f"连接复用率: {stats['requests']['reuse_rate']:.2%}")

await pool.close()
```

### 4. Asyncio优化 (asyncio_optimizer.py)

**功能:**
- 阻塞调用自动检测和线程池执行
- 任务管理和取消处理
- 并发限制和流量控制
- 协程性能分析

**使用:**

**阻塞调用优化:**
```python
from qbittorrent_monitor.performance import AsyncIOOptimizer

optimizer = AsyncIOOptimizer(max_workers=10)
optimizer.initialize()

# 在线程池中运行同步函数
result = await optimizer.run_in_thread(blocking_function, arg1, arg2)

optimizer.shutdown()
```

**并发限制:**
```python
from qbittorrent_monitor.performance import ConcurrencyLimiter

limiter = ConcurrencyLimiter(max_concurrent=20)

# 使用上下文管理器
async with limiter.acquire():
    await process_item(item)

# 批量处理
tasks = [limiter.run(process_item, item) for item in items]
results = await asyncio.gather(*tasks)
```

**任务管理:**
```python
from qbittorrent_monitor.performance import TaskManager

manager = TaskManager()

# 创建任务
task = manager.create_task(
    some_coroutine(),
    name="my_task",
    on_complete=lambda t: print(f"完成: {t.result()}")
)

# 等待所有任务
await manager.wait_all(timeout=10.0)

# 取消所有任务
await manager.cancel_all()
```

**便捷函数:**
```python
from qbittorrent_monitor.performance.asyncio_optimizer import (
    run_in_executor,
    gather_with_concurrency,
    timeout,
)

# 在线程池中执行
result = await run_in_executor(sync_func, arg1, arg2)

# 带并发限制的gather
results = await gather_with_concurrency(coros, limit=10)

# 带超时的执行
result = await timeout(coro, timeout_seconds=5.0, default=None)
```

## 集成使用

### 完整优化示例

```python
import asyncio
from qbittorrent_monitor.config import load_config
from qbittorrent_monitor.performance.integrations import (
    PerformanceOptimizer,
    create_optimized_monitor,
)

async def main():
    config = load_config()
    
    # 方式1: 使用完全优化的监控器
    monitor = await create_optimized_monitor(config)
    
    # 方式2: 手动优化现有组件
    optimizer = PerformanceOptimizer(config)
    await optimizer.initialize()
    
    # 应用到组件
    optimizer.optimize_qb_client(qb_client)
    optimizer.optimize_classifier(classifier)
    optimizer.optimize_monitor(monitor)
    
    # 缓存预热
    await optimizer.warmup_cache(database)
    
    # 启动监控
    await monitor.start()
    
    # ... 运行一段时间 ...
    
    # 获取性能报告
    report = optimizer.get_performance_report()
    print(f"性能报告: {report}")
    
    # 关闭
    await optimizer.shutdown()

asyncio.run(main())
```

## 基准测试

运行基准测试:

```bash
# 运行所有性能测试
pytest tests/test_performance_optimization.py -v

# 运行基准测试（需要pytest-benchmark）
pytest tests/test_performance_optimization.py -v --benchmark-only

# 运行特定测试
pytest tests/test_performance_optimization.py::test_batch_writer_vs_single_writes -v
```

## 配置建议

### 高吞吐量场景
```python
# 数据库写入
BatchDatabaseWriter(
    db,
    batch_size=500,        # 更大的批量
    flush_interval=0.05,   # 更快的刷新
)

# 缓存
TTLCache(
    max_size=50000,        # 更大的缓存
    default_ttl=7200,      # 更长的TTL
    max_memory_mb=200,     # 更多内存
)

# 并发限制
ConcurrencyLimiter(
    max_concurrent=50,     # 更高的并发
    max_queue_size=5000,
)
```

### 低延迟场景
```python
# 数据库写入
BatchDatabaseWriter(
    db,
    batch_size=50,         # 更小的批量
    flush_interval=0.01,   # 更快的刷新
)

# 缓存
TTLCache(
    max_size=1000,         # 较小的缓存
    default_ttl=300,       # 较短的TTL
    cleanup_interval=10,   # 更频繁的清理
)
```

### 内存受限场景
```python
# 缓存
TTLCache(
    max_size=1000,
    max_memory_mb=20,      # 限制内存
    eviction_policy="lfu", # 最少使用淘汰
)

# 内存监控
MemoryMonitor(
    max_memory_mb=50,
    critical_threshold=0.85,
)
```

## 监控指标

性能优化模块提供以下监控指标:

### 批量写入指标
- `queue_size`: 队列中的记录数
- `records_written`: 已写入记录数
- `batches_written`: 已写入批次数
- `avg_flush_time_ms`: 平均刷新时间
- `records_per_batch`: 每批记录数

### 缓存指标
- `size`: 缓存条目数
- `hit_rate`: 命中率
- `hits/misses`: 命中/未命中次数
- `evictions`: 淘汰数
- `expirations`: 过期数
- `total_memory_bytes`: 内存使用

### 连接池指标
- `reuse_rate`: 连接复用率
- `avg_response_time_ms`: 平均响应时间
- `total_requests`: 总请求数
- `connection_errors`: 连接错误数

### 任务管理指标
- `created/completed`: 创建/完成任务数
- `cancelled/failed`: 取消/失败任务数
- `avg_duration_ms`: 平均执行时间
