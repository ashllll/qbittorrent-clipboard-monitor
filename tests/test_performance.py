"""性能基准测试"""
import time
import statistics
import asyncio
from typing import Dict, List, Callable
from collections import deque


class PerformanceBenchmark:
    """性能基准测试框架"""
    
    def __init__(self):
        self.results: Dict[str, List[float]] = {}
    
    def benchmark(self, name: str, iterations: int = 1000):
        """装饰器：测量函数执行时间"""
        def decorator(func: Callable):
            def wrapper(*args, **kwargs):
                times = []
                for _ in range(iterations):
                    start = time.perf_counter()
                    result = func(*args, **kwargs)
                    end = time.perf_counter()
                    times.append((end - start) * 1000)  # ms
                
                self.results[name] = times
                return result
            return wrapper
        return decorator
    
    def report(self) -> str:
        """生成测试报告"""
        lines = ["\n" + "=" * 70, "性能测试报告".center(70), "=" * 70]
        
        for name, times in self.results.items():
            avg = statistics.mean(times)
            median = statistics.median(times)
            std = statistics.stdev(times) if len(times) > 1 else 0
            min_t = min(times)
            max_t = max(times)
            
            lines.append(f"\n{name}:")
            lines.append(f"  平均:     {avg:.3f}ms")
            lines.append(f"  中位数:   {median:.3f}ms")
            lines.append(f"  标准差:   {std:.3f}ms")
            lines.append(f"  最小:     {min_t:.3f}ms")
            lines.append(f"  最大:     {max_t:.3f}ms")
            lines.append(f"  吞吐量:   {1000/avg:.0f} ops/s")
        
        lines.append("=" * 70)
        return "\n".join(lines)


def run_hash_benchmark():
    """哈希算法性能测试"""
    bench = PerformanceBenchmark()
    
    test_string = "magnet:?xt=urn:btih:1234567890abcdef" * 10
    
    @bench.benchmark("MD5 Hash", iterations=10000)
    def test_md5():
        import hashlib
        return hashlib.md5(test_string.encode()).hexdigest()
    
    @bench.benchmark("xxHash64", iterations=10000)
    def test_xxhash():
        try:
            import xxhash
            return xxhash.xxh64(test_string.encode()).hexdigest()
        except ImportError:
            return "N/A"
    
    test_md5()
    test_xxhash()
    print(bench.report())


def run_matcher_benchmark():
    """关键词匹配性能测试"""
    bench = PerformanceBenchmark()
    
    # 构建测试关键词
    keywords = {
        "movies": ["1080p", "720p", "BluRay", "WEB-DL", "HDR", "UHD"] * 20,
        "tv": ["S01", "S02", "E01", "E02", "Season", "Episode"] * 20,
        "anime": ["BD", "OVA", "SP", "字幕组", "第"] * 20,
    }
    
    test_names = [
        "Movie.Name.2024.1080p.BluRay.x264",
        "TV.Show.S01E02.720p.WEB-DL",
        "Anime.Title.BD.第01话.字幕组",
        "Music.Album.2024.FLAC",
        "Software.v1.0.Portable",
    ]
    
    @bench.benchmark("Regex Match", iterations=1000)
    def test_regex():
        import re
        patterns = {
            cat: re.compile('|'.join(re.escape(k) for k in words), re.I)
            for cat, words in keywords.items()
        }
        results = []
        for name in test_names:
            for cat, pattern in patterns.items():
                if pattern.search(name):
                    results.append(cat)
        return results
    
    @bench.benchmark("Aho-Corasick", iterations=1000)
    def test_ac():
        try:
            import ahocorasick
            A = ahocorasick.Automaton()
            for cat, words in keywords.items():
                for word in words:
                    A.add_word(word.lower(), (cat, word))
            A.make_automaton()
            
            results = []
            for name in test_names:
                for _, (cat, _) in A.iter(name.lower()):
                    results.append(cat)
            return results
        except ImportError:
            return "N/A"
    
    @bench.benchmark("Trie Match", iterations=1000)
    def test_trie():
        from qbittorrent_monitor.optimized_matcher import TrieMatcher
        matcher = TrieMatcher()
        for cat, words in keywords.items():
            for word in words:
                matcher.add_pattern(word, cat)
        
        results = []
        for name in test_names:
            matches = matcher.find_matches(name)
            if matches:
                results.append(max(matches.items(), key=lambda x: len(x[1]))[0])
        return results
    
    test_regex()
    test_ac()
    test_trie()
    print(bench.report())


def run_cache_benchmark():
    """缓存性能测试"""
    bench = PerformanceBenchmark()
    
    @bench.benchmark("Simple Dict Cache", iterations=5000)
    def test_simple_cache():
        cache = {}
        for i in range(100):
            cache[f"key_{i}"] = f"value_{i}"
        for i in range(100):
            _ = cache.get(f"key_{i}")
        return cache
    
    @bench.benchmark("Tiered Cache", iterations=5000)
    def test_tiered_cache():
        from qbittorrent_monitor.optimized_cache import TieredCache
        cache = TieredCache(l1_size=20, l2_size=80)
        for i in range(100):
            cache.put(f"key_{i}", f"value_{i}")
        for i in range(100):
            _ = cache.get(f"key_{i}")
        return cache
    
    test_simple_cache()
    test_tiered_cache()
    print(bench.report())


async def run_async_benchmark():
    """异步操作性能测试"""
    print("\n" + "=" * 70)
    print("异步操作性能测试".center(70))
    print("=" * 70)
    
    # 测试剪贴板读取
    from qbittorrent_monitor.async_clipboard import AsyncClipboardReader
    
    reader = AsyncClipboardReader(poll_interval=0.1)
    
    start = time.perf_counter()
    reader.start()
    
    # 模拟读取
    count = 0
    async for content in reader.changes():
        count += 1
        if count >= 10:
            break
    
    elapsed = time.perf_counter() - start
    reader.stop()
    
    print(f"\n剪贴板读取测试:")
    print(f"  读取次数: {count}")
    print(f"  总时间:   {elapsed:.3f}s")
    print(f"  平均延迟: {elapsed/count*1000:.3f}ms")
    
    # 测试批量数据库写入
    from qbittorrent_monitor.optimized_database import BatchDatabaseWriter, BatchRecord
    import tempfile
    import os
    
    db_path = os.path.join(tempfile.gettempdir(), "test_benchmark.db")
    
    writer = BatchDatabaseWriter(db_path, batch_size=100, flush_interval=1.0)
    await writer.start()
    
    start = time.perf_counter()
    
    # 写入测试数据
    for i in range(500):
        await writer.write(BatchRecord(
            magnet_hash=f"hash_{i}",
            name=f"Test Name {i}",
            category="movies" if i % 2 == 0 else "tv",
            status="success"
        ))
    
    await writer.stop()
    elapsed = time.perf_counter() - start
    
    print(f"\n批量数据库写入测试:")
    print(f"  写入记录: 500")
    print(f"  总时间:   {elapsed:.3f}s")
    print(f"  吞吐量:   {500/elapsed:.0f} records/s")
    
    # 清理
    try:
        os.remove(db_path)
    except:
        pass
    
    print("=" * 70)


def run_all_benchmarks():
    """运行所有基准测试"""
    print("\n开始性能基准测试...")
    
    print("\n【哈希算法测试】")
    run_hash_benchmark()
    
    print("\n【关键词匹配测试】")
    run_matcher_benchmark()
    
    print("\n【缓存性能测试】")
    run_cache_benchmark()
    
    print("\n【异步操作测试】")
    asyncio.run(run_async_benchmark())


if __name__ == "__main__":
    run_all_benchmarks()
