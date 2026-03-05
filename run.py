#!/usr/bin/env python3
"""
qBittorrent Clipboard Monitor v3.0 - 精简版

简洁、高效、易用的磁力链接剪贴板监控工具。
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from qbittorrent_monitor import __version__, PROJECT_DESCRIPTION
from qbittorrent_monitor.config import load_config
from qbittorrent_monitor.qb_client import QBClient
from qbittorrent_monitor.monitor import ClipboardMonitor


def setup_logging(level: str = "INFO") -> None:
    """设置日志"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="qBittorrent剪贴板监控器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py                    # 基础模式
  python run.py --config ~/.qb-monitor.json
  python run.py --interval 0.5     # 更快的检查间隔
        """
    )
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument("--interval", "-i", type=float, help="检查间隔（秒）")
    parser.add_argument("--log-level", "-l", default="INFO", help="日志级别")
    parser.add_argument("--version", "-v", action="version", version=f"%(prog)s {__version__}")
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    print("=" * 50)
    print(f"{PROJECT_DESCRIPTION}")
    print(f"版本: {__version__}")
    print("=" * 50)
    
    try:
        # 加载配置
        config_path = Path(args.config) if args.config else None
        config = load_config(config_path)
        
        # 覆盖命令行参数
        if args.interval:
            config.check_interval = args.interval
        
        logger.info(f"配置加载完成")
        logger.info(f"qBittorrent: {config.qbittorrent.host}:{config.qbittorrent.port}")
        
        # 创建客户端并启动
        async with QBClient(config) as qb:
            version = await qb.get_version()
            logger.info(f"qBittorrent连接成功 (版本: {version})")
            
            # 确保分类存在
            await qb.ensure_categories()
            
            # 创建并启动监控器
            monitor = ClipboardMonitor(qb, config)
            
            # 注册统计回调
            def on_added(magnet: str, category: str):
                logger.info(f"✓ 已添加到 [{category}]")
            
            monitor.add_handler(on_added)
            
            # 启动监控
            await monitor.start()
            
    except KeyboardInterrupt:
        print("\n用户中断，程序退出")
    except Exception as e:
        logger.error(f"程序错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n程序已退出")
        sys.exit(0)
