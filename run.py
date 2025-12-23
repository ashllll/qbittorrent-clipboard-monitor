#!/usr/bin/env python3
"""
qBittorrent剪贴板监控器 - 智能启动脚本

功能特性:
- 智能启动机制，自动检测和初始化环境
- 支持Web管理界面启动
- 内置RSS订阅管理
- 命令行诊断工具

使用方法:
    python run.py                     # 基础剪贴板监控
    python run.py --web              # 启动Web管理界面
    python run.py --web --port 8080  # 指定Web端口
    python run.py --status           # 检查环境状态
    python run.py --verify           # 验证依赖完整性
    python run.py --repair           # 修复依赖问题
    python run.py --skip-check       # 跳过启动检查
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入版本信息
from qbittorrent_monitor import __version__, PROJECT_DESCRIPTION

# 导入启动管理器
from qbittorrent_monitor.startup import (
    check_and_prepare, 
    get_startup_manager,
    StartupStatus
)


def print_status(status: StartupStatus) -> None:
    """打印启动状态"""
    print("=" * 60)
    print("环境状态检查")
    print("=" * 60)
    
    if status.is_first_run:
        print("[INFO] 首次运行，需要初始化环境")
    else:
        print("[OK] 环境已初始化")
    
    print(f"  Python 版本: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"  环境检查: {'通过' if status.environment_ok else '失败'}")
    print(f"  依赖检查: {'通过' if status.dependencies_ok else '失败'}")
    
    if status.missing_packages:
        print(f"  缺失依赖: {', '.join(status.missing_packages)}")
    
    if status.error_message:
        print(f"  错误信息: {status.error_message}")
    
    print("=" * 60)


def cmd_status() -> int:
    """检查环境状态命令"""
    manager = get_startup_manager()
    status = manager.check_and_prepare(auto_repair=False)
    print_status(status)
    
    if status.is_ready:
        print("[SUCCESS] 环境就绪，可以启动程序")
        return 0
    else:
        print("[WARNING] 环境未就绪，请运行 --repair 修复")
        return 1


def cmd_verify() -> int:
    """验证依赖完整性命令"""
    manager = get_startup_manager()
    deps_ok, missing = manager.verify_dependencies()
    
    print("=" * 60)
    print("依赖验证")
    print("=" * 60)
    
    if deps_ok:
        print("[SUCCESS] 所有依赖已安装且完整")
        return 0
    else:
        print(f"[WARNING] 发现 {len(missing)} 个缺失依赖:")
        for pkg in missing:
            print(f"  - {pkg}")
        print("\n运行 --repair 自动修复")
        return 1


def cmd_repair() -> int:
    """修复依赖命令"""
    print("=" * 60)
    print("依赖修复")
    print("=" * 60)
    
    manager = get_startup_manager()
    status = manager.check_and_prepare(auto_repair=True)
    
    if status.is_ready:
        print("[SUCCESS] 环境修复完成")
        return 0
    else:
        print(f"[ERROR] 修复失败: {status.error_message}")
        return 1


async def main():
    """主函数"""
    import argparse

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='qBittorrent剪贴板监控器')
    parser.add_argument('--web', action='store_true', help='启动Web管理界面')
    parser.add_argument('--port', type=int, default=8000, help='Web界面端口 (默认: 8000)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Web界面地址 (默认: 0.0.0.0)')
    
    # 诊断命令
    parser.add_argument('--status', action='store_true', help='检查环境状态')
    parser.add_argument('--verify', action='store_true', help='验证依赖完整性')
    parser.add_argument('--repair', action='store_true', help='修复依赖问题')
    
    # 启动选项
    parser.add_argument('--skip-check', action='store_true', help='跳过启动检查')
    parser.add_argument('--quiet', action='store_true', help='静默模式')
    
    args = parser.parse_args()

    # 处理诊断命令
    if args.status:
        return cmd_status()
    if args.verify:
        return cmd_verify()
    if args.repair:
        return cmd_repair()

    print("=" * 60)
    print(f"{PROJECT_DESCRIPTION} {__version__}")
    print("=" * 60)
    
    # 智能启动检查
    if not args.skip_check:
        print("[INFO] 正在检查环境...")
        status = check_and_prepare(auto_repair=not args.quiet)
        
        if not status.is_ready:
            print(f"\n[ERROR] 环境检查失败: {status.error_message}")
            if status.missing_packages:
                print(f"缺失依赖: {', '.join(status.missing_packages)}")
            print("\n请运行: python run.py --repair")
            return 1
        
        if status.is_first_run:
            print("[INFO] 首次运行，环境初始化完成")
        else:
            print("[INFO] 环境检查通过")
        
        print()

    try:
        # 延迟导入核心模块
        from qbittorrent_monitor.config import AppConfig, ConfigManager
        from qbittorrent_monitor.qbittorrent_client import QBittorrentClient
        from qbittorrent_monitor.clipboard_monitor import ClipboardMonitor

        print("[INFO] 核心模块导入成功")
        print()

        # 加载配置
        print("[INFO] 正在加载配置...")
        config_manager = ConfigManager()
        config = await config_manager.load_config()
        print("[SUCCESS] 配置加载完成")
        print()

        # 创建客户端
        print("[INFO] 正在连接qBittorrent...")
        qbt_client = QBittorrentClient(config.qbittorrent, app_config=config)

        # 使用异步上下文管理器
        async with qbt_client:
            version = await qbt_client.get_version()
            print(f"[SUCCESS] qBittorrent连接成功 (版本: {version})")
            print()

            # 创建监控器
            print("[INFO] 正在启动剪贴板监控器...")
            monitor = ClipboardMonitor(qbt_client, config)
            print("[SUCCESS] 剪贴板监控器已启动")
            print()

            # 初始化RSS管理器
            print("[INFO] 正在初始化RSS订阅管理器...")
            from qbittorrent_monitor.rss_manager import initialize_rss_manager
            rss_manager = await initialize_rss_manager(qbt_client, config)
            print("[SUCCESS] RSS订阅管理器已初始化")
            print()

            # 如果启用Web界面
            if args.web:
                print("[INFO] 正在启动Web管理界面...")
                try:
                    from qbittorrent_monitor.web_interface import start_web_interface
                    web_task = asyncio.create_task(
                        start_web_interface(config, qbt_client, args.host, args.port)
                    )
                    print(f"[SUCCESS] Web界面已启动: http://{args.host}:{args.port}")
                    print("=" * 60)
                    print("程序已启动！")
                    print("  - 剪贴板监控: 运行中")
                    print(f"  - Web界面: http://{args.host}:{args.port}")
                    print("  - 按 Ctrl+C 停止监控")
                    print("=" * 60)
                    print()

                    # 并行运行监控和Web服务
                    await asyncio.gather(monitor.start(), web_task)
                except ImportError as e:
                    print(f"[WARNING] Web界面模块未安装: {e}")
                    print("[TIP] 请安装: pip install fastapi uvicorn jinja2")
            else:
                print("=" * 60)
                print("[启动] 程序已启动！等待剪贴板内容...")
                print("[提示] 按 Ctrl+C 停止监控")
                print()
                print("[提示] 使用 --web 参数可以启动Web管理界面")
                print("[健康检查] http://localhost:8090/health")
                print("[监控指标] http://localhost:8091/metrics")
                print("=" * 60)
                print()

                # 启动监控
                await monitor.start()

    except KeyboardInterrupt:
        print("\n[INFO] 用户中断，程序退出")
    except Exception as e:
        print(f"\n[ERROR] 程序运行错误: {str(e)}")
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
    except Exception as e:
        print(f"\n[ERROR] 启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
