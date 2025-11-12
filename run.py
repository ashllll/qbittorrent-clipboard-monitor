#!/usr/bin/env python3
"""
qBittorrent剪贴板监控器 - 简化启动脚本
版本: v2.5.0

功能特性:
- 直接启动，跳过依赖安装（适用于已配置环境）
- 支持Web管理界面启动
- 内置RSS订阅管理
- 命令行参数配置

使用方法:
    python run.py                     # 基础剪贴板监控
    python run.py --web              # 启动Web管理界面
    python run.py --web --port 8080  # 指定Web端口

注意: 首次使用请运行 python scripts/environment_manager.py 进行环境配置
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def main():
    """主函数"""
    import argparse

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='qBittorrent剪贴板监控器')
    parser.add_argument('--web', action='store_true', help='启动Web管理界面')
    parser.add_argument('--port', type=int, default=8000, help='Web界面端口 (默认: 8000)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Web界面地址 (默认: 0.0.0.0)')
    args = parser.parse_args()

    print("=" * 60)
    print("🚀 qBittorrent剪贴板监控器 v2.5.0 - 简化启动")
    print("=" * 60)
    print("💡 提示: 首次使用请运行 python scripts/environment_manager.py")
    print()

    try:
        # 导入核心模块
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
                except ImportError:
                    print("[WARNING] Web界面模块未安装，跳过启动")
                    print("[TIP] 请安装: pip install fastapi uvicorn jinja2")
            else:
                print("=" * 60)
                print("🎯 程序已启动！等待剪贴板内容...")
                print("📋 按 Ctrl+C 停止监控")
                print()
                print("💡 提示: 使用 --web 参数可以启动Web管理界面")
                print("🏥 健康检查: http://localhost:8090/health")
                print("📊 监控指标: http://localhost:8091/metrics")
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
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已退出")
