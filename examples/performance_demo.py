#!/usr/bin/env python3
"""性能优化演示脚本

演示如何使用性能优化模块提升 qBittorrent Clipboard Monitor 的性能。

运行:
    python examples/performance_demo.py
"""

import asyncio
import time
from typing import Dict, Any, List

# 导入优化模块
from qbittorrent_monitor.performance import (
    BatchDatabaseWriter,
    TTLCache,
    ConcurrencyLimiter,
    AsyncIOOptimizer,
    TaskManager,
)


class MockDatabase:
    """模拟数据库用于演示"""
    
    def __init__(self):
        self._data: List[Dict] = []
        self._lock = asyncio.Lock()
        self._initialized = True
        self._connection = self
    
    async def initialize(self):
        pass
    
    async def executemany(self, sql, records):
        self._data.extend(records)
        return len(records)
    
    async def execute(self, sql, params=None):
        return self
    
    async def commit(self):
        pass
    
    async def fetchone(self):
        return [1]
    
    async def record_torrent(self, **kwargs):
        async with self._lock:
            self._data.append(kwargs)
        return kwargs


def generate_test_data(count: int) -> List[Dict[str, Any]]:
    """生成测试数据"""
    categories = ["movies", "tv", "anime", "music", "software"]
    return [
        {
            "magnet_hash": f"hash_{i:06d}",
            "name": f"Test Content {i}",
            "category": categories[i % len(categories)],
            "status": "success" if i % 10 != 0 else "failed",
        }
        for i in range(count)
    ]


async def demo_batch_writer():
    """演示批量数据库写入"""
    print("\n" + "=" * 60)
    print("演示: 批量数据库写入优化")
    print("=" * 60)
    
    db = MockDatabase()
    records = generate_test_data(1000)
    
    # 方式1: 传统单条写入
    print("\n[传统方式] 单条写入...")
    start = time.time()
    for record in records:
        await db.record_torrent(**record)
        # 模拟数据库IO延迟
        await asyncio.sleep(0.001)
    
    traditional_time = time.time() - start
    traditional_rate = len(records) / traditional_time
    print(f"  耗时: {traditional_time:.3f}s")
    print(f"  速率: {traditional_rate:.1f} ops/sec")
    
    # 重置数据库
    db = MockDatabase()
    
    # 方式2: 批量写入
    print("\n[优化方式] 批量写入...")
    writer = BatchDatabaseWriter(db, batch_size=100, flush_interval=0.05)
    await writer.start()
    
    start = time.time()
    await writer.queue_torrent_records(records)
    await writer.stop()
    
    batch_time = time.time() - start
    batch_rate = len(records) / batch_time
    print(f"  耗时: {batch_time:.3f}s")
    print(f"  速率: {batch_rate:.1f} ops/sec")
    
    # 统计
    speedup = traditional_time / batch_time
    print(f"\n✓ 性能提升: {speedup:.2f}x")
    print(f"✓ 写入批次数: {writer.get_stats()['batches_written']}")


async def demo_ttl_cache():
    """演示TTL缓存"""
    print("\n" + "=" * 60)
    print("演示: TTL缓存优化")
    print("=" * 60)
    
    cache = TTLCache[str](
        max_size=10000,
        default_ttl=3600,
        max_memory_mb=50,
    )
    cache.start()
    
    # 写入测试
    print("\n[写入测试] 写入10000条数据...")
    start = time.time()
    for i in range(10000):
        cache.set(f"key_{i}", f"value_{i}")
    write_time = time.time() - start
    print(f"  耗时: {write_time:.3f}s")
    print(f"  速率: {10000/write_time:.1f} ops/sec")
    
    # 读取测试（全部命中）
    print("\n[读取测试] 读取10000条数据（命中）...")
    start = time.time()
    for i in range(10000):
        _ = cache.get(f"key_{i}")
    read_time = time.time() - start
    print(f"  耗时: {read_time:.3f}s")
    print(f"  速率: {10000/read_time:.1f} ops/sec")
    
    # 统计
    stats = cache.get_stats()
    print(f"\n✓ 缓存命中率: {stats.hit_rate:.2%}")
    print(f"✓ 缓存大小: {stats.size}")
    print(f"✓ 内存使用: {stats.total_memory_bytes / 1024:.2f} KB")
    print(f"✓ 平均条目大小: {stats.avg_entry_size_bytes:.1f} bytes")
    
    cache.stop()


async def demo_concurrency_limiter():
    """演示并发限制器"""
    print("\n" + "=" * 60)
    print("演示: 并发限制器")
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
            return task_id
    
    print("\n[并发控制] 启动20个任务，限制5个并发...")
    start = time.time()
    tasks = [worker(i) for i in range(20)]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start
    
    print(f"  总耗时: {elapsed:.3f}s")
    print(f"  理论最小耗时: {20 * 0.1 / 5:.3f}s")
    print(f"  最大并发: {max_active}")
    
    assert max_active <= 5, "并发数不应超过限制"
    print("\n✓ 并发限制正常工作")
    
    # 演示 run 方法
    print("\n[批量处理] 使用 run 方法处理10个任务...")
    
    async def process_item(item: int) -> int:
        await asyncio.sleep(0.05)
        return item * 2
    
    start = time.time()
    results = await asyncio.gather(*[
        limiter.run(process_item, i) for i in range(10)
    ])
    elapsed = time.time() - start
    
    print(f"  结果: {results}")
    print(f"  耗时: {elapsed:.3f}s")
    print("✓ 批量处理完成")


async def demo_asyncio_optimizer():
    """演示AsyncIO优化器"""
    print("\n" + "=" * 60)
    print("演示: AsyncIO优化器")
    print("=" * 60)
    
    optimizer = AsyncIOOptimizer(max_workers=5)
    optimizer.initialize()
    
    # 演示1: 在线程池中执行阻塞函数
    print("\n[线程池] 并行执行阻塞任务...")
    
    def blocking_task(duration: float) -> str:
        """模拟阻塞任务"""
        time.sleep(duration)
        return f"completed after {duration}s"
    
    start = time.time()
    tasks = [
        optimizer.run_in_thread(blocking_task, 0.1)
        for _ in range(5)
    ]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start
    
    print(f"  5个阻塞任务（每个0.1s）并行执行")
    print(f"  结果: {results}")
    print(f"  耗时: {elapsed:.3f}s (串行需要0.5s)")
    print(f"  加速比: {0.5/elapsed:.2f}x")
    
    # 演示2: 任务管理
    print("\n[任务管理] 创建和管理异步任务...")
    
    manager = TaskManager()
    completed_tasks = []
    
    async def task_func(task_id: int):
        await asyncio.sleep(0.05)
        completed_tasks.append(task_id)
        return task_id
    
    # 创建10个任务
    for i in range(10):
        manager.create_task(
            task_func(i),
            name=f"task_{i}",
            on_complete=lambda t: None,
        )
    
    print(f"  创建任务数: 10")
    print(f"  活跃任务: {len(manager.get_active_tasks())}")
    
    # 等待完成
    await manager.wait_all()
    
    stats = manager.get_stats()
    print(f"  完成任务: {stats.completed}")
    print(f"  平均耗时: {stats.avg_duration_ms:.2f}ms")
    print("✓ 任务管理正常")
    
    optimizer.shutdown()


async def demo_integrated_optimization():
    """演示综合优化效果"""
    print("\n" + "=" * 60)
    print("演示: 综合优化效果")
    print("=" * 60)
    
    # 模拟实际场景：处理大量磁力链接
    total_records = 500
    records = generate_test_data(total_records)
    
    print(f"\n[场景] 处理 {total_records} 条磁力链接记录")
    
    # 初始化组件
    db = MockDatabase()
    writer = BatchDatabaseWriter(db, batch_size=50)
    await writer.start()
    
    cache = TTLCache[str](max_size=10000, default_ttl=1800)
    cache.start()
    
    limiter = ConcurrencyLimiter(max_concurrent=20)
    
    # 处理函数
    async def process_record(record: Dict) -> str:
        # 1. 检查分类缓存
        cache_key = f"cat:{record['category']}"
        if not cache.get(cache_key):
            cache.set(cache_key, record["category"])
        
        # 2. 写入数据库（批量）
        await writer.queue_torrent_record(
            magnet_hash=record["magnet_hash"],
            name=record["name"],
            category=record["category"],
            status=record["status"],
        )
        
        return record["magnet_hash"]
    
    # 开始处理
    print("\n[执行] 开始处理...")
    start = time.time()
    
    tasks = [limiter.run(process_record, r) for r in records]
    results = await asyncio.gather(*tasks)
    
    await writer.stop()
    
    elapsed = time.time() - start
    rate = total_records / elapsed
    
    # 统计
    print(f"\n[结果]")
    print(f"  处理总数: {len(results)}")
    print(f"  总耗时: {elapsed:.3f}s")
    print(f"  处理速率: {rate:.1f} ops/sec")
    
    cache_stats = cache.get_stats()
    writer_stats = writer.get_stats()
    
    print(f"\n[缓存统计]")
    print(f"  命中率: {cache_stats.hit_rate:.2%}")
    print(f"  缓存大小: {cache_stats.size}")
    
    print(f"\n[批量写入统计]")
    print(f"  写入批次数: {writer_stats['batches_written']}")
    print(f"  每批平均: {writer_stats['records_per_batch']:.1f} 条")
    print(f"  平均刷新时间: {writer_stats['avg_flush_time_ms']:.2f}ms")
    
    print("\n✓ 综合优化演示完成")
    
    cache.stop()


async def main():
    """主函数"""
    print("=" * 60)
    print("qBittorrent Clipboard Monitor - 性能优化演示")
    print("=" * 60)
    
    try:
        # 运行各个演示
        await demo_batch_writer()
        await demo_ttl_cache()
        await demo_concurrency_limiter()
        await demo_asyncio_optimizer()
        await demo_integrated_optimization()
        
        print("\n" + "=" * 60)
        print("所有演示完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 演示失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
