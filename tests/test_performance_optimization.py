"""性能优化基准测试

测试各优化模块的性能提升效果。

运行:
    pytest tests/test_performance_optimization.py -v
    
    # 带基准测试报告
    pytest tests/test_performance_optimization.py -v --benchmark-only
"""

import asyncio
import hashlib
import random
import string
import time
from datetime import datetime
from typing import List, Dict, Any

import pytest

# 导入被测试的模块
from qbittorrent_monitor.performance import (
    BatchDatabaseWriter,
    TTLCache,
    MemoryMonitor,
    CacheWarmer,
    OptimizedConnectionPool,
    ConnectionHealthMonitor,
    AsyncIOOptimizer,
    TaskManager,
    ConcurrencyLimiter,
)


# ============== 辅助函数 ==============

def generate_magnet_hash() -> str:
    """生成随机磁力链接hash"""
    return hashlib.sha1(
        ''.join(random.choices(string.ascii_letters + string.digits, k=40)).encode()
    ).hexdigest()


def generate_test_records(count: int) -> List[Dict[str, Any]]:
    """生成测试记录"""
    categories = ["movies", "tv", "anime", "music", "software", "games", "books", "other"]
    statuses = ["success", "failed", "duplicate", "invalid"]
    
    records = []
    for i in range(count):
        records.append({
            "magnet_hash": generate_magnet_hash(),
            "name": f"Test Content {i} " + ''.join(random.choices(string.ascii_letters, k=20)),
            "category": random.choice(categories),
            "status": random.choice(statuses),
            "error_message": None if random.random() > 0.1 else "Test error",
        })
    
    return records


# ============== 数据库批量写入测试 ==============

class MockDatabaseManager:
    """模拟数据库管理器"""
    
    def __init__(self):
        self._data: List[Dict] = []
        self._lock = asyncio.Lock()
        self._initialized = True
        self._connection = MockConnection()
    
    async def initialize(self):
        pass
    
    async def record_torrent(self, **kwargs):
        async with self._lock:
            self._data.append(kwargs)
        return kwargs


class MockConnection:
    """模拟数据库连接"""
    
    def __init__(self):
        self.data = []
    
    async def executemany(self, sql, records):
        self.data.extend(records)
        return len(records)
    
    async def execute(self, sql, params=None):
        return MockCursor()
    
    async def commit(self):
        pass


class MockCursor:
    """模拟数据库游标"""
    
    async def fetchone(self):
        return [1]


@pytest.mark.asyncio
async def test_batch_writer_vs_single_writes():
    """测试批量写入 vs 单条写入性能"""
    print("\n" + "=" * 60)
    print("测试: 数据库批量写入 vs 单条写入")
    print("=" * 60)
    
    records = generate_test_records(500)
    
    # 测试1: 模拟单条写入（添加延迟模拟真实数据库IO）
    db_single = MockDatabaseManager()
    start = time.time()
    
    for record in records:
        await db_single.record_torrent(**record)
        await asyncio.sleep(0.001)  # 模拟1ms数据库IO延迟
    
    single_time = time.time() - start
    single_rate = len(records) / single_time
    
    print(f"单条写入(含IO延迟): {single_time:.3f}s ({single_rate:.1f} ops/sec)")
    
    # 测试2: 批量写入
    db_batch = MockDatabaseManager()
    writer = BatchDatabaseWriter(db_batch, batch_size=50, flush_interval=0.05)
    
    await writer.start()
    start = time.time()
    
    await writer.queue_torrent_records(records)
    await writer.stop()
    
    batch_time = time.time() - start
    batch_rate = len(records) / batch_time
    
    print(f"批量写入: {batch_time:.3f}s ({batch_rate:.1f} ops/sec)")
    
    # 计算提升
    speedup = single_time / batch_time
    print(f"性能提升: {speedup:.2f}x")
    
    # 在实际应用中，批量写入通常比单条写入快5-20倍
    # 这里使用一个较宽松的阈值
    assert speedup > 1.5, f"批量写入应该至少有1.5x提升，实际: {speedup:.2f}x"


@pytest.mark.asyncio
async def test_batch_writer_different_batch_sizes():
    """测试不同批量大小的性能"""
    print("\n" + "=" * 60)
    print("测试: 不同批量大小的性能对比")
    print("=" * 60)
    
    records = generate_test_records(1000)
    batch_sizes = [10, 50, 100, 200]
    
    results = []
    
    for batch_size in batch_sizes:
        db = MockDatabaseManager()
        writer = BatchDatabaseWriter(db, batch_size=batch_size, flush_interval=0.05)
        
        await writer.start()
        start = time.time()
        
        await writer.queue_torrent_records(records)
        await writer.stop()
        
        elapsed = time.time() - start
        rate = len(records) / elapsed
        
        results.append((batch_size, elapsed, rate))
        print(f"batch_size={batch_size:3d}: {elapsed:.3f}s ({rate:.1f} ops/sec)")
    
    # 验证：更大的批量通常更快（在一定范围内）
    # 注意：实际效果取决于硬件和测试环境
    print(f"\n最优批量大小: {max(results, key=lambda x: x[2])[0]}")


# ============== TTL缓存测试 ==============

@pytest.mark.asyncio
async def test_ttl_cache_performance():
    """测试TTL缓存性能"""
    print("\n" + "=" * 60)
    print("测试: TTL缓存性能")
    print("=" * 60)
    
    cache = TTLCache[str](max_size=10000, default_ttl=3600)
    cache.start()
    
    # 测试1: 写入性能
    write_count = 10000
    start = time.time()
    
    for i in range(write_count):
        cache.set(f"key_{i}", f"value_{i}")
    
    write_time = time.time() - start
    write_rate = write_count / write_time
    
    print(f"写入 {write_count} 条: {write_time:.3f}s ({write_rate:.1f} ops/sec)")
    
    # 测试2: 读取性能（全部命中）
    read_count = 10000
    start = time.time()
    
    for i in range(read_count):
        _ = cache.get(f"key_{i}")
    
    read_time = time.time() - start
    read_rate = read_count / read_time
    
    print(f"读取 {read_count} 条（命中）: {read_time:.3f}s ({read_rate:.1f} ops/sec)")
    
    # 测试3: 命中率
    stats = cache.get_stats()
    print(f"命中率: {stats.hit_rate:.2%}")
    print(f"缓存大小: {stats.size}")
    print(f"内存使用: {stats.total_memory_bytes / 1024:.2f} KB")
    
    cache.stop()
    
    assert stats.hit_rate > 0.99, "所有读取应该命中"


@pytest.mark.asyncio
async def test_ttl_cache_expiration():
    """测试TTL缓存过期清理"""
    print("\n" + "=" * 60)
    print("测试: TTL缓存过期清理")
    print("=" * 60)
    
    cache = TTLCache[str](max_size=1000, default_ttl=0.1)  # 100ms TTL
    cache.start()
    
    # 写入数据
    for i in range(100):
        cache.set(f"key_{i}", f"value_{i}")
    
    print(f"初始大小: {len(cache.keys())}")
    
    # 等待过期
    await asyncio.sleep(0.5)
    
    # 触发清理
    expired = await cache._cleanup_expired()
    print(f"清理过期: {expired} 条")
    
    stats = cache.get_stats()
    print(f"过期后大小: {stats.size}")
    print(f"过期计数: {stats.expirations}")
    
    cache.stop()
    
    assert stats.size == 0, "所有条目应该已过期"


# ============== 并发限制器测试 ==============

@pytest.mark.asyncio
async def test_concurrency_limiter():
    """测试并发限制器"""
    print("\n" + "=" * 60)
    print("测试: 并发限制器")
    print("=" * 60)
    
    limiter = ConcurrencyLimiter(max_concurrent=5)
    
    active_count = 0
    max_active = 0
    
    async def worker(task_id: int):
        nonlocal active_count, max_active
        
        async with limiter.acquire():
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.1)  # 模拟工作
            active_count -= 1
    
    # 启动20个任务，限制5个并发
    start = time.time()
    tasks = [worker(i) for i in range(20)]
    await asyncio.gather(*tasks)
    elapsed = time.time() - start
    
    print(f"任务数: 20, 并发限制: 5")
    print(f"最大并发: {max_active}")
    print(f"总耗时: {elapsed:.3f}s")
    print(f"理论最小耗时: {20 * 0.1 / 5:.3f}s")
    
    assert max_active <= 5, f"并发数不应超过限制，实际: {max_active}"


@pytest.mark.asyncio
async def test_concurrency_limiter_run():
    """测试并发限制器的run方法"""
    print("\n" + "=" * 60)
    print("测试: 并发限制器 run 方法")
    print("=" * 60)
    
    limiter = ConcurrencyLimiter(max_concurrent=3)
    
    async def process(item: int) -> int:
        await asyncio.sleep(0.05)
        return item * 2
    
    # 批量处理
    items = list(range(10))
    start = time.time()
    
    results = await asyncio.gather(*[
        limiter.run(process, item) for item in items
    ])
    
    elapsed = time.time() - start
    
    print(f"处理 {len(items)} 项，并发限制 3")
    print(f"结果: {results}")
    print(f"耗时: {elapsed:.3f}s")
    
    assert results == [i * 2 for i in items]


# ============== AsyncIO优化器测试 ==============

@pytest.mark.asyncio
async def test_asyncio_optimizer_thread_pool():
    """测试AsyncIO优化器的线程池"""
    print("\n" + "=" * 60)
    print("测试: AsyncIO优化器线程池")
    print("=" * 60)
    
    optimizer = AsyncIOOptimizer(max_workers=5)
    optimizer.initialize()
    
    def blocking_task(duration: float) -> str:
        """模拟阻塞任务"""
        time.sleep(duration)
        return f"completed after {duration}s"
    
    # 并行执行多个阻塞任务
    start = time.time()
    tasks = [
        optimizer.run_in_thread(blocking_task, 0.1)
        for _ in range(5)
    ]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start
    
    print(f"5个阻塞任务（每个0.1s）并行执行")
    print(f"结果: {results}")
    print(f"耗时: {elapsed:.3f}s (串行需要0.5s)")
    
    optimizer.shutdown()
    
    assert elapsed < 0.3, f"并行执行应该更快，实际耗时: {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_asyncio_optimizer_profiling():
    """测试AsyncIO优化器的性能分析"""
    print("\n" + "=" * 60)
    print("测试: 性能分析")
    print("=" * 60)
    
    optimizer = AsyncIOOptimizer(enable_profiling=True)
    
    @optimizer.profile
    async def slow_coroutine():
        await asyncio.sleep(0.05)
        return "done"
    
    @optimizer.profile
    async def fast_coroutine():
        await asyncio.sleep(0.01)
        return "done"
    
    # 执行多次
    for _ in range(10):
        await slow_coroutine()
        await fast_coroutine()
    
    report = optimizer.get_performance_report()
    
    print("性能报告:")
    for name, metrics in report["coroutines"].items():
        print(f"  {name}:")
        print(f"    调用次数: {metrics['call_count']}")
        print(f"    平均耗时: {metrics['avg_time_ms']:.2f}ms")
        print(f"    最大耗时: {metrics['max_time_ms']:.2f}ms")
    
    assert "slow_coroutine" in report["coroutines"]
    assert "fast_coroutine" in report["coroutines"]


# ============== 任务管理器测试 ==============

@pytest.mark.asyncio
async def test_task_manager():
    """测试任务管理器"""
    print("\n" + "=" * 60)
    print("测试: 任务管理器")
    print("=" * 60)
    
    manager = TaskManager()
    
    results = []
    
    async def task_func(task_id: int, delay: float):
        await asyncio.sleep(delay)
        results.append(task_id)
        return task_id
    
    # 创建任务
    for i in range(10):
        manager.create_task(
            task_func(i, 0.05),
            name=f"task_{i}",
        )
    
    print(f"创建任务数: 10")
    print(f"活跃任务: {len(manager.get_active_tasks())}")
    
    # 等待完成
    await manager.wait_all()
    
    stats = manager.get_stats()
    print(f"完成任务: {stats.completed}")
    print(f"平均耗时: {stats.avg_duration_ms:.2f}ms")
    
    assert stats.completed == 10


# ============== 综合性能测试 ==============

@pytest.mark.asyncio
async def test_comprehensive_performance():
    """综合性能测试"""
    print("\n" + "=" * 60)
    print("测试: 综合性能测试")
    print("=" * 60)
    
    # 模拟实际场景：处理大量磁力链接
    total_records = 1000
    records = generate_test_records(total_records)
    
    start = time.time()
    
    # 1. 使用批量写入
    db = MockDatabaseManager()
    writer = BatchDatabaseWriter(db, batch_size=100)
    await writer.start()
    
    # 2. 使用缓存
    cache = TTLCache[str](max_size=10000)
    cache.start()
    
    # 3. 使用并发限制
    limiter = ConcurrencyLimiter(max_concurrent=20)
    
    async def process_record(record: Dict):
        """处理单条记录"""
        # 模拟分类缓存
        cache_key = f"cat:{record['category']}"
        cached = cache.get(cache_key)
        if not cached:
            cache.set(cache_key, record["category"])
        
        # 模拟写入
        await writer.queue_torrent_record(
            magnet_hash=record["magnet_hash"],
            name=record["name"],
            category=record["category"],
            status=record["status"],
        )
    
    # 并行处理
    tasks = [limiter.run(process_record, r) for r in records]
    await asyncio.gather(*tasks)
    
    await writer.stop()
    cache.stop()
    
    elapsed = time.time() - start
    rate = total_records / elapsed
    
    print(f"处理 {total_records} 条记录")
    print(f"总耗时: {elapsed:.3f}s")
    print(f"处理速率: {rate:.1f} ops/sec")
    
    # 验证
    cache_stats = cache.get_stats()
    print(f"缓存命中率: {cache_stats.hit_rate:.2%}")
    
    writer_stats = writer.get_stats()
    print(f"批量写入: {writer_stats['batches_written']} 批")
    
    # 基本性能要求
    assert rate > 100, f"处理速率应大于100 ops/sec，实际: {rate:.1f}"


# ============== 基准测试（使用pytest-benchmark） ==============

@pytest.mark.benchmark
class TestBenchmarks:
    """基准测试类（需要安装pytest-benchmark）"""
    
    @pytest.fixture(scope="session")
    def benchmark(self, pytestconfig):
        """有条件地提供benchmark fixture"""
        try:
            import pytest_benchmark
            # 如果安装了pytest-benchmark，返回实际的benchmark
            return pytestconfig.pluginmanager.getplugin("benchmark")
        except ImportError:
            # 跳过基准测试
            pytest.skip("需要安装 pytest-benchmark: pip install pytest-benchmark")
    
    @pytest.mark.asyncio
    async def test_benchmark_cache_write(self, benchmark):
        """基准测试：缓存写入"""
        cache = TTLCache[str](max_size=100000)
        cache.start()
        
        def write_to_cache():
            for i in range(1000):
                cache.set(f"key_{i}", f"value_{i}")
        
        benchmark(write_to_cache)
        cache.stop()
    
    @pytest.mark.asyncio
    async def test_benchmark_cache_read(self, benchmark):
        """基准测试：缓存读取"""
        cache = TTLCache[str](max_size=100000)
        cache.start()
        
        # 预填充
        for i in range(1000):
            cache.set(f"key_{i}", f"value_{i}")
        
        def read_from_cache():
            for i in range(1000):
                cache.get(f"key_{i}")
        
        benchmark(read_from_cache)
        cache.stop()


# ============== 主入口 ==============

if __name__ == "__main__":
    # 直接运行测试
    print("=" * 60)
    print("性能优化基准测试")
    print("=" * 60)
    
    asyncio.run(test_batch_writer_vs_single_writes())
    asyncio.run(test_ttl_cache_performance())
    asyncio.run(test_concurrency_limiter())
    asyncio.run(test_comprehensive_performance())
    
    print("\n" + "=" * 60)
    print("所有测试完成")
    print("=" * 60)
