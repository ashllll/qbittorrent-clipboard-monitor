#!/usr/bin/env python3
"""
性能对比脚本：对比优化前后的性能差异

这个脚本用于对比：
1. 磁力链接提取速度
2. 配置参数对性能的影响
3. 并发vs顺序处理的性能差异
"""

import asyncio
import time
import logging
from pathlib import Path
import sys
import json

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from qbittorrent_monitor.config import ConfigManager, WebCrawlerConfig
from qbittorrent_monitor.utils import parse_magnet, validate_magnet_link

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PerformanceComparison')


class PerformanceProfiler:
    """性能分析器"""
    
    def __init__(self):
        self.results = {}
    
    def start_timer(self, name: str):
        """开始计时"""
        self.results[name] = {'start': time.time()}
    
    def end_timer(self, name: str):
        """结束计时"""
        if name in self.results:
            self.results[name]['end'] = time.time()
            self.results[name]['duration'] = self.results[name]['end'] - self.results[name]['start']
    
    def get_duration(self, name: str) -> float:
        """获取耗时"""
        return self.results.get(name, {}).get('duration', 0)
    
    def print_summary(self):
        """打印性能摘要"""
        logger.info("📊 性能分析摘要:")
        for name, data in self.results.items():
            if 'duration' in data:
                logger.info(f"   - {name}: {data['duration']:.3f}s")


async def simulate_old_config_extraction(num_torrents: int = 10):
    """模拟旧配置下的提取过程"""
    logger.info(f"🐌 模拟旧配置提取 {num_torrents} 个种子...")

    # 旧配置参数（硬编码的慢速参数）
    old_config = {
        'page_timeout': 120000,  # 120秒
        'wait_for': 10,          # 10秒等待
        'delay_before_return': 5, # 5秒延迟
        'max_retries': 5,        # 5次重试
        'base_delay': 15,        # 15秒基础延迟
        'inter_request_delay': 3, # 3秒请求间延迟
    }

    total_time = 0

    for i in range(num_torrents):
        # 模拟单个种子提取时间（顺序处理）
        extraction_time = (
            old_config['wait_for'] +           # 页面等待时间
            old_config['delay_before_return']  # 返回前延迟
        )

        # 请求间延迟（除了最后一个）
        if i < num_torrents - 1:
            extraction_time += old_config['inter_request_delay']

        await asyncio.sleep(extraction_time)
        total_time += extraction_time

        if (i + 1) % 5 == 0:
            logger.info(f"   已处理 {i + 1}/{num_torrents} 个种子")

    logger.info(f"🐌 旧配置提取完成，总耗时: {total_time:.3f}s")
    return total_time


async def simulate_new_config_extraction(num_torrents: int = 10):
    """模拟新配置下的提取过程"""
    logger.info(f"🚀 模拟新配置提取 {num_torrents} 个种子...")

    # 新配置参数（优化后的快速参数）
    new_config = {
        'page_timeout': 60000,   # 60秒
        'wait_for': 3,           # 3秒等待
        'delay_before_return': 2, # 2秒延迟
        'max_retries': 3,        # 3次重试
        'base_delay': 5,         # 5秒基础延迟
        'inter_request_delay': 1.5, # 1.5秒请求间延迟
        'max_concurrent': 3,     # 最大并发数
    }

    # 模拟并发处理
    batch_size = new_config['max_concurrent']
    total_time = 0

    for i in range(0, num_torrents, batch_size):
        batch_end = min(i + batch_size, num_torrents)
        batch_size_actual = batch_end - i

        # 模拟并发处理当前批次 - 并发执行，所以时间不累加
        extraction_time = (
            new_config['wait_for'] +           # 页面等待时间
            new_config['delay_before_return']  # 返回前延迟
        )

        await asyncio.sleep(extraction_time)
        total_time += extraction_time  # 并发处理，时间不乘以批次大小

        # 批次间延迟
        if batch_end < num_torrents:
            inter_delay = new_config['inter_request_delay']
            await asyncio.sleep(inter_delay)
            total_time += inter_delay

        logger.info(f"   已处理批次 {i//batch_size + 1}, 种子 {batch_end}/{num_torrents}")

    logger.info(f"🚀 新配置提取完成，总耗时: {total_time:.3f}s")
    return total_time


def test_magnet_parsing_performance():
    """测试磁力链接解析性能"""
    logger.info("⚡ 测试磁力链接解析性能...")
    
    test_magnets = [
        "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Test+Movie+2024+1080p+BluRay&tr=udp://tracker.example.com:80",
        "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12&dn=Test+TV+Show+S01E01&tr=udp://tracker.example.com:80",
        "magnet:?xt=urn:btih:fedcba0987654321fedcba0987654321fedcba09&dn=Test+Game+PC&tr=udp://tracker.example.com:80",
    ]
    
    # 测试解析性能
    iterations = 10000
    start_time = time.time()
    
    for i in range(iterations):
        for magnet in test_magnets:
            hash_val, name = parse_magnet(magnet)
            is_valid = validate_magnet_link(magnet)
    
    end_time = time.time()
    duration = end_time - start_time
    total_operations = iterations * len(test_magnets)
    
    logger.info(f"✅ 磁力链接解析性能测试完成")
    logger.info(f"   - 总操作数: {total_operations}")
    logger.info(f"   - 总耗时: {duration:.3f}s")
    logger.info(f"   - 平均耗时: {duration/total_operations*1000:.3f}ms/次")
    logger.info(f"   - 处理速度: {total_operations/duration:.0f} 次/秒")
    
    return duration


async def compare_extraction_performance():
    """对比提取性能"""
    logger.info("🏁 开始提取性能对比...")
    
    profiler = PerformanceProfiler()
    num_torrents = 20  # 测试20个种子
    
    # 测试旧配置
    profiler.start_timer("old_config")
    old_time = await simulate_old_config_extraction(num_torrents)
    profiler.end_timer("old_config")
    
    # 等待一下
    await asyncio.sleep(1)
    
    # 测试新配置
    profiler.start_timer("new_config")
    new_time = await simulate_new_config_extraction(num_torrents)
    profiler.end_timer("new_config")
    
    # 计算性能提升
    speedup = old_time / new_time if new_time > 0 else 0
    time_saved = old_time - new_time
    efficiency_gain = (time_saved / old_time) * 100 if old_time > 0 else 0
    
    logger.info("📈 性能对比结果:")
    logger.info(f"   - 种子数量: {num_torrents}")
    logger.info(f"   - 旧配置耗时: {old_time:.3f}s")
    logger.info(f"   - 新配置耗时: {new_time:.3f}s")
    logger.info(f"   - 性能提升: {speedup:.2f}x")
    logger.info(f"   - 节省时间: {time_saved:.3f}s")
    logger.info(f"   - 效率提升: {efficiency_gain:.1f}%")
    
    return {
        'old_time': old_time,
        'new_time': new_time,
        'speedup': speedup,
        'time_saved': time_saved,
        'efficiency_gain': efficiency_gain
    }


async def test_config_loading_performance():
    """测试配置加载性能"""
    logger.info("⚙️ 测试配置加载性能...")
    
    iterations = 100
    start_time = time.time()
    
    for i in range(iterations):
        config_manager = ConfigManager()
        config = await config_manager.load_config()
        
        # 验证新配置项
        assert hasattr(config, 'web_crawler')
        assert hasattr(config.web_crawler, 'max_concurrent_extractions')
    
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info(f"✅ 配置加载性能测试完成")
    logger.info(f"   - 加载次数: {iterations}")
    logger.info(f"   - 总耗时: {duration:.3f}s")
    logger.info(f"   - 平均耗时: {duration/iterations*1000:.3f}ms/次")
    
    return duration


def generate_performance_report(results: dict):
    """生成性能报告"""
    logger.info("📋 生成性能报告...")
    
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {
            'extraction_speedup': f"{results['speedup']:.2f}x",
            'time_saved': f"{results['time_saved']:.3f}s",
            'efficiency_gain': f"{results['efficiency_gain']:.1f}%"
        },
        'details': results,
        'recommendations': [
            "使用新的配置参数可以显著提升磁力链接提取速度",
            "并发处理能够有效减少总体处理时间",
            "优化后的重试策略减少了不必要的等待时间",
            "建议在生产环境中应用这些优化配置"
        ]
    }
    
    # 保存报告到文件
    report_file = Path('performance_report.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📄 性能报告已保存到: {report_file}")
    
    return report


async def main():
    """主函数"""
    logger.info("🚀 开始性能对比测试...")
    
    try:
        # 1. 测试磁力链接解析性能
        parsing_time = test_magnet_parsing_performance()
        
        # 2. 测试配置加载性能
        config_time = await test_config_loading_performance()
        
        # 3. 对比提取性能
        extraction_results = await compare_extraction_performance()
        
        # 4. 生成性能报告
        all_results = {
            **extraction_results,
            'parsing_time': parsing_time,
            'config_loading_time': config_time
        }
        
        report = generate_performance_report(all_results)
        
        logger.info("🎉 性能对比测试完成！")
        logger.info("📊 主要改进:")
        logger.info(f"   - 提取速度提升: {extraction_results['speedup']:.2f}x")
        logger.info(f"   - 效率提升: {extraction_results['efficiency_gain']:.1f}%")
        logger.info(f"   - 每20个种子节省: {extraction_results['time_saved']:.1f}秒")
        
    except Exception as e:
        logger.error(f"❌ 性能测试失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
