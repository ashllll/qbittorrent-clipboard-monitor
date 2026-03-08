#!/usr/bin/env python3
"""
qBittorrent Clipboard Monitor - 模块入口点

支持通过 `python -m qbittorrent_monitor` 直接运行模块。

示例:
    python -m qbittorrent_monitor
    python -m qbittorrent_monitor --config /path/to/config.json
    python -m qbittorrent_monitor --interval 0.5 --log-level DEBUG

退出码:
    0 - 正常退出
    1 - 运行时错误
    2 - 命令行参数错误
    130 - 用户中断 (Ctrl+C)
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import NoReturn, Optional

# 导入项目主模块
from qbittorrent_monitor import __version__, PROJECT_DESCRIPTION
from qbittorrent_monitor.config import load_config
from qbittorrent_monitor.qb_client import QBClient
from qbittorrent_monitor.monitor import ClipboardMonitor
from qbittorrent_monitor.logging_filters import (
    SensitiveDataFilter,
    RedactingFormatter,
)

# 配置日志记录器
logger = logging.getLogger(__name__)

# 全局标志用于优雅退出
_shutdown_requested = False


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """配置日志系统，包含敏感信息过滤。"""
    formatter = RedactingFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.handlers = []

    sensitive_filter = SensitiveDataFilter()
    root_logger.addFilter(sensitive_filter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    root_logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        root_logger.addHandler(file_handler)


def signal_handler(signum: int, frame) -> None:
    """处理系统信号，实现优雅退出。"""
    global _shutdown_requested
    sig_name = signal.Signals(signum).name
    logger.info(f"收到信号 {sig_name} ({signum})，正在优雅退出...")
    _shutdown_requested = True


def setup_signal_handlers() -> None:
    """设置信号处理器。"""
    # 注册 SIGINT (Ctrl+C) 和 SIGTERM 处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Windows 平台也支持 SIGBREAK
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, signal_handler)


async def async_main() -> int:
    """
    异步主函数。
    
    Returns:
        退出码: 0=成功, 1=错误, 2=参数错误
    """
    import argparse

    parser = argparse.ArgumentParser(
        description=f"{PROJECT_DESCRIPTION} - v{__version__}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python -m qbittorrent_monitor                    # 使用默认配置运行
  python -m qbittorrent_monitor -c config.json     # 指定配置文件
  python -m qbittorrent_monitor -i 0.5             # 设置检查间隔为0.5秒
  python -m qbittorrent_monitor -l DEBUG           # 设置日志级别为DEBUG
  python -m qbittorrent_monitor -f app.log         # 输出日志到文件

环境变量:
  QBIT_HOST          qBittorrent 主机地址
  QBIT_PORT          qBittorrent 端口
  QBIT_USERNAME      qBittorrent 用户名
  QBIT_PASSWORD      qBittorrent 密码
  QBIT_USE_HTTPS     是否使用 HTTPS
  AI_ENABLED         是否启用 AI 分类
  AI_API_KEY         AI API 密钥
  CHECK_INTERVAL     检查间隔（秒）
  LOG_LEVEL          日志级别
        """
    )
    parser.add_argument(
        "--config", "-c",
        help="配置文件路径 (JSON 格式)"
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        help="剪贴板检查间隔（秒），覆盖配置文件中的设置"
    )
    parser.add_argument(
        "--log-level", "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="日志级别 (默认: INFO)"
    )
    parser.add_argument(
        "--log-file", "-f",
        help="日志文件路径"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    try:
        args = parser.parse_args()
    except SystemExit as e:
        # 参数解析错误时返回退出码 2
        return 2 if e.code != 0 else 0

    # 设置日志
    setup_logging(args.log_level, args.log_file)

    # 打印启动信息
    print("=" * 50)
    print(f"{PROJECT_DESCRIPTION}")
    print(f"版本: {__version__}")
    print(f"模块入口: python -m qbittorrent_monitor")
    print("=" * 50)

    # 设置信号处理器
    setup_signal_handlers()

    try:
        # 加载配置
        config_path = Path(args.config) if args.config else None
        config = load_config(config_path)

        # 覆盖命令行参数
        if args.interval:
            config.check_interval = args.interval

        logger.info("配置加载完成")
        logger.info(f"qBittorrent: {config.qbittorrent.host}:{config.qbittorrent.port}")
        logger.info(f"日志级别: {args.log_level}")

        # 创建客户端并启动
        async with QBClient(config) as qb:
            version = await qb.get_version()
            logger.info(f"qBittorrent 连接成功 (版本: {version})")

            # 确保分类存在
            await qb.ensure_categories()

            # 创建并启动监控器
            monitor = ClipboardMonitor(qb, config)

            # 注册统计回调
            def on_added(magnet: str, category: str) -> None:
                from qbittorrent_monitor.utils import get_magnet_display_name
                magnet_display = get_magnet_display_name(magnet)
                logger.info(f"✓ 已添加到 [{category}]: {magnet_display}")

            monitor.add_handler(on_added)

            # 启动监控
            logger.info("开始监控剪贴板...")
            await monitor.start()

    except KeyboardInterrupt:
        logger.info("用户中断程序")
        return 130
    except asyncio.CancelledError:
        logger.info("任务已取消")
        return 0
    except Exception as e:
        logger.error(f"程序运行时错误: {e}")
        if args.log_level == "DEBUG":
            import traceback
            traceback.print_exc()
        return 1

    return 0


def main() -> NoReturn:
    """
    程序入口点。
    
    处理同步入口，运行异步主函数，并返回适当的退出码。
    """
    try:
        # 运行异步主函数
        exit_code = asyncio.run(async_main())
    except KeyboardInterrupt:
        # 处理主循环外的 KeyboardInterrupt
        print("\n程序已退出")
        exit_code = 130
    except Exception as e:
        # 处理意外错误
        print(f"严重错误: {e}", file=sys.stderr)
        exit_code = 1

    # 使用适当的退出码退出
    sys.exit(exit_code)


# 当模块作为脚本运行时执行
if __name__ == "__main__":
    main()
