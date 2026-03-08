#!/usr/bin/env python3
"""
qBittorrent Clipboard Monitor v3.0 - 安全增强版

简洁、高效、易用且安全的磁力链接剪贴板监控工具。
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from qbittorrent_monitor import __version__, PROJECT_DESCRIPTION
from qbittorrent_monitor.config import load_config
from qbittorrent_monitor.qb_client import QBClient
from qbittorrent_monitor.monitor import ClipboardMonitor
from qbittorrent_monitor.logging_filters import (
    SensitiveDataFilter, 
    RedactingFormatter,
    install_global_filter
)
from qbittorrent_monitor.metrics import init_metrics
from qbittorrent_monitor.metrics_server import MetricsServer


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """设置日志，包含敏感信息过滤"""
    # 创建格式化器（自动遮盖敏感信息）
    formatter = RedactingFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    )
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有处理器
    root_logger.handlers = []
    
    # 添加敏感信息过滤器到根记录器
    sensitive_filter = SensitiveDataFilter()
    root_logger.addFilter(sensitive_filter)
    
    # 配置控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    root_logger.addHandler(console_handler)
    
    # 配置文件处理器（如果指定）
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        root_logger.addHandler(file_handler)


async def run_cli_mode(args):
    """运行 CLI 模式（传统剪贴板监控）"""
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
        logger.info(f"日志级别: {args.log_level}")
        
        # 初始化指标收集
        init_metrics(enabled=config.metrics.enabled)
        
        # 启动指标服务器（如果启用）
        metrics_server = None
        if config.metrics.enabled:
            metrics_server = MetricsServer(
                host=config.metrics.host,
                port=config.metrics.port,
                path=config.metrics.path,
                enabled=True,
            )
            await metrics_server.start()
            logger.info(f"Prometheus 指标服务器已启动: http://{config.metrics.host}:{config.metrics.port}{config.metrics.path}")
        
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
                # 安全地显示磁力链接
                from qbittorrent_monitor.utils import get_magnet_display_name
                magnet_display = get_magnet_display_name(magnet)
                logger.info(f"✓ 已添加到 [{category}]: {magnet_display}")
            
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


async def run_web_mode(args):
    """运行 Web 模式"""
    logger = logging.getLogger(__name__)
    
    print("=" * 50)
    print(f"{PROJECT_DESCRIPTION} - Web 模式")
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
        logger.info(f"Web 界面地址: http://{args.web_host}:{args.web_port}")
        
        # 导入 Web 模块
        from qbittorrent_monitor.web import run_web_server
        
        # 启动 Web 服务器
        await run_web_server(config, host=args.web_host, port=args.web_port)
        
    except ImportError as e:
        logger.error(f"启动 Web 模式失败: {e}")
        logger.error("请确保已安装 FastAPI 和 Uvicorn: pip install fastapi uvicorn")
        return 1
    except KeyboardInterrupt:
        print("\n用户中断，程序退出")
    except Exception as e:
        logger.error(f"程序错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


async def validate_config(args):
    """验证配置并测试连接"""
    from qbittorrent_monitor.config import load_config
    from qbittorrent_monitor.qb_client import QBClient
    from qbittorrent_monitor.exceptions import ConfigError
    
    print("=" * 50)
    print("🔍 配置验证")
    print("=" * 50)
    
    config_path = Path(args.config) if args.config else None
    config_file = config_path or Path.home() / ".config" / "qb-monitor" / "config.json"
    
    # 检查配置文件是否存在
    if not config_file.exists():
        print(f"\n❌ 配置文件不存在: {config_file}")
        print("\n💡 提示: 运行以下命令创建配置:")
        print(f"   python run.py --init")
        return 1
    
    try:
        # 加载配置
        print(f"\n📁 配置文件: {config_file}")
        config = load_config(config_path)
        print("✅ 配置加载成功")
        
        # 显示配置信息
        print(f"\n📋 配置信息:")
        print(f"   qBittorrent: {config.qbittorrent.host}:{config.qbittorrent.port}")
        print(f"   用户名: {config.qbittorrent.username}")
        print(f"   HTTPS: {'是' if config.qbittorrent.use_https else '否'}")
        print(f"   AI 分类: {'启用' if config.ai.enabled else '禁用'}")
        print(f"   检查间隔: {config.check_interval}s")
        print(f"   日志级别: {config.log_level}")
        
        # 测试 qBittorrent 连接
        print(f"\n🔌 测试 qBittorrent 连接...")
        try:
            async with QBClient(config) as qb:
                version = await qb.get_version()
                print(f"✅ 连接成功！qBittorrent 版本: {version}")
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            print("\n💡 排查建议:")
            print("   1. 确认 qBittorrent 已启动")
            print("   2. 确认 Web UI 已启用（选项 → Web UI）")
            print("   3. 检查用户名和密码")
            print("   4. 检查主机地址和端口")
            return 1
        
        print("\n" + "=" * 50)
        print("✅ 配置验证通过！可以正常运行")
        print("=" * 50)
        return 0
        
    except ConfigError as e:
        print(f"\n❌ 配置错误: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 验证失败: {e}")
        return 1


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="qBittorrent剪贴板监控器 - 安全增强版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py                    # 基础模式
  python run.py --config ~/.qb-monitor.json
  python run.py --interval 0.5     # 更快的检查间隔
  python run.py --log-file app.log # 记录到文件
  
配置工具:
  python run.py --init             # 运行交互式配置向导
  python run.py --validate         # 验证配置并测试连接
  
Web 模式:
  python run.py --web              # 启动 Web 界面 (默认端口 8080)
  python run.py --web --web-port 8888  # 指定 Web 端口
  python run.py --web --web-host 0.0.0.0  # 允许外部访问

安全特性:
  - 敏感信息自动过滤（密码、API密钥等）
  - 磁力链接验证和清理
  - 路径遍历防护
  - 速率限制和DoS防护
        """
    )
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument("--interval", "-i", type=float, help="检查间隔（秒）")
    parser.add_argument("--log-level", "-l", default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="日志级别 (默认: INFO)")
    parser.add_argument("--log-file", "-f", help="日志文件路径")
    parser.add_argument("--version", "-v", action="version", version=f"%(prog)s {__version__}")
    
    # 配置工具
    parser.add_argument("--init", action="store_true", 
                       help="运行交互式配置向导")
    parser.add_argument("--validate", action="store_true",
                       help="验证配置并测试连接")
    
    # Web 模式参数
    parser.add_argument("--web", action="store_true", help="启动 Web 管理界面")
    parser.add_argument("--web-host", default="127.0.0.1", help="Web 服务器绑定地址 (默认: 127.0.0.1)")
    parser.add_argument("--web-port", type=int, default=8080, help="Web 服务器端口 (默认: 8080)")
    
    args = parser.parse_args()
    
    # 运行配置向导
    if args.init:
        from qbittorrent_monitor.config.wizard import run_wizard
        run_wizard()
        return 0
    
    # 验证配置
    if args.validate:
        return await validate_config(args)
    
    # 设置日志
    setup_logging(args.log_level, args.log_file)
    
    # 根据模式运行
    if args.web:
        return await run_web_mode(args)
    else:
        return await run_cli_mode(args)


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n程序已退出")
        sys.exit(0)
