#!/usr/bin/env python3
"""
🚀 QBittorrent智能下载助手

功能特性：
- 🔍 自动监控剪贴板中的磁力链接和网页URL
- 🧠 AI智能分类（支持DeepSeek）
- 🕷️ 基于crawl4ai的网页爬虫批量下载
- 📂 自动分类到不同目录
- 🎯 支持XXXClub等种子网站

使用方法：
    python start.py            # 启动监控
    python start.py --help     # 查看帮助
"""

import asyncio
import sys
import signal
import logging
import time
import traceback
from pathlib import Path
from typing import Optional
import os
import subprocess

# 强制输出到控制台
os.environ['PYTHONUNBUFFERED'] = '1'

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def install_dependencies():
    """检查并安装依赖"""
    print_step(0, "∞", "正在检查和安装依赖库...")
    libs_dir = project_root / 'libs'
    requirements_path = project_root / 'requirements.txt'

    if not requirements_path.exists():
        print_error("错误: requirements.txt 文件未找到。")
        sys.exit(1)
        
    # 确保libs文件夹存在
    libs_dir.mkdir(exist_ok=True)

    try:
        # 检查是否所有包都已下载
        with open(requirements_path, 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        missing_packages = False
        for line in lines:
            try:
                # 解析包名
                pkg_name = line.split('==')[0].split('>=')[0].split('<=')[0].split('<')[0].split('>')[0].strip()
                # 这是一个简化的检查，可能不完全准确，但可以处理大部分情况
                if not any(pkg_name.lower() in f.lower() for f in os.listdir(libs_dir)):
                     missing_packages = True
                     break
            except Exception:
                # 如果解析失败，则假定需要下载
                missing_packages = True
                break
        
        if missing_packages:
            print_info("'libs' 文件夹中可能缺少依赖包，尝试从网络下载...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'download', '-r', str(requirements_path), '-d', str(libs_dir)])
            print_success("依赖包已下载到 'libs' 文件夹。")

        # 从libs文件夹离线安装
        print_info("正在从 'libs' 文件夹安装/验证依赖...")
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install',
            '--no-index',
            f'--find-links={str(libs_dir)}',
            '-r', str(requirements_path),
            '--break-system-packages'
        ])
        print_success("所有依赖已成功安装/验证。")
    except subprocess.CalledProcessError as e:
        print_error("依赖安装失败", e)
        print_info("请检查您的Python环境和pip设置。")
        sys.exit(1)
    except Exception as e:
        print_error("发生未知错误", e)
        sys.exit(1)

def print_with_flush(msg):
    """确保立即输出到控制台"""
    print(msg)
    sys.stdout.flush()

def print_step(step_num, total_steps, message):
    """显示步骤进度"""
    print_with_flush(f"[{step_num}/{total_steps}] {message}")

def print_error(message, error=None):
    """显示错误信息"""
    print_with_flush(f"❌ {message}")
    if error:
        print_with_flush(f"   错误详情: {str(error)}")

def print_success(message):
    """显示成功信息"""
    print_with_flush(f"✅ {message}")

def print_info(message):
    """显示信息"""
    print_with_flush(f"💡 {message}")

def print_separator(char="=", length=60):
    """显示分隔线"""
    print_with_flush(char * length)

# 在导入项目模块之前安装依赖
install_dependencies()

try:
    from qbittorrent_monitor.config import ConfigManager
    from qbittorrent_monitor.qbittorrent_client import QBittorrentClient
    from qbittorrent_monitor.clipboard_monitor import ClipboardMonitor
except ImportError as e:
    print_error("导入模块失败", e)
    print_info("请确保已安装所有依赖: pip install -r requirements.txt")
    sys.exit(1)


class QBittorrentDownloadHelper:
    """QBittorrent智能下载助手主程序"""
    
    def __init__(self):
        self.config_manager = None
        self.config = None
        self.qbt_client = None
        self.clipboard_monitor = None
        self.logger = None
        self.shutdown_event = asyncio.Event()
    
    async def start(self):
        """启动主程序"""
        try:
            await self._initialize()
            await self._run_monitor()
        except KeyboardInterrupt:
            print_with_flush("\n💡 收到键盘中断信号，正在优雅关闭...")
        except Exception as e:
            print_error("程序运行异常", e)
            print_with_flush("\n🔍 详细错误信息:")
            traceback.print_exc()
            if self.logger:
                self.logger.error(f"程序异常: {str(e)}", exc_info=True)
        finally:
            await self._cleanup()
    
    async def _initialize(self):
        """初始化程序"""
        print_separator()
        print_with_flush("🚀 QBittorrent智能下载助手启动中...")
        print_separator()
        
        total_steps = 6
        
        # 步骤1: 加载配置
        print_step(1, total_steps, "正在加载配置文件...")
        try:
            self.config_manager = ConfigManager()
            self.config = await self.config_manager.load_config()
            print_success("配置文件加载成功")
        except Exception as e:
            print_error("配置文件加载失败", e)
            raise
        
        # 步骤2: 设置日志
        print_step(2, total_steps, "正在配置日志系统...")
        try:
            logging.basicConfig(
                level=getattr(logging, self.config.log_level.upper()),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(self.config.log_file, encoding='utf-8'),
                    logging.StreamHandler()
                ]
            )
            self.logger = logging.getLogger('QBDownloadHelper')
            print_success("日志系统配置完成")
        except Exception as e:
            print_error("日志系统配置失败", e)
            raise
        
        # 步骤3: 显示配置信息
        print_step(3, total_steps, "显示当前配置...")
        self._show_startup_info()
        
        # 步骤4: 初始化qBittorrent客户端
        print_step(4, total_steps, "正在初始化qBittorrent客户端...")
        try:
            self.qbt_client = QBittorrentClient(
                self.config.qbittorrent,
                app_config=self.config
            )
            print_success("qBittorrent客户端初始化完成")
        except Exception as e:
            print_error("qBittorrent客户端初始化失败", e)
            raise
        
        # 步骤5: 测试连接
        print_step(5, total_steps, f"正在连接qBittorrent ({self.config.qbittorrent.host}:{self.config.qbittorrent.port})...")
        try:
            async with self.qbt_client as qbt:
                # 测试基本连接
                version = await qbt.get_version()
                print_success(f"qBittorrent连接成功 (版本: {version})")
                
                # 确保分类存在
                print_info("正在检查和创建分类...")
                await qbt.ensure_categories(self.config.categories)
                print_success("分类检查完成")
                
        except Exception as e:
            print_error("qBittorrent连接失败", e)
            print_info("请检查:")
            print_info("  - qBittorrent是否正在运行")
            print_info("  - Web UI是否已启用")
            print_info("  - 用户名和密码是否正确")
            print_info("  - 防火墙设置")
            raise
        
        # 步骤6: 初始化剪贴板监控器
        print_step(6, total_steps, "正在初始化剪贴板监控器...")
        try:
            self.clipboard_monitor = ClipboardMonitor(self.qbt_client, self.config)
            print_success("剪贴板监控器初始化完成")
        except Exception as e:
            print_error("剪贴板监控器初始化失败", e)
            raise
        
        # 设置信号处理
        self._setup_signal_handlers()
        
        print_separator()
        print_success("🎯 所有组件初始化完成！")
        print_separator()
    
    async def _run_monitor(self):
        """运行监控程序"""
        print_with_flush("\n🔍 开始监控剪贴板...")
        print_separator("─")
        print_info("支持的内容类型:")
        print_info("  📎 磁力链接 - 自动添加并智能分类")
        print_info("  🌐 网页URL - 批量爬取种子并下载")
        print_info("  🕷️ https://www.yinfans.me/等")
        print_separator("─")
        print_info("💡 提示:")
        print_info("  - 复制磁力链接或网页URL到剪贴板")
        print_info("  - 程序会自动检测并处理")
        print_info("  - 使用 Ctrl+C 安全退出")
        print_separator("─")
        print_with_flush("⏳ 等待剪贴板内容...")
        
        try:
            async with self.qbt_client as qbt:
                # 重新创建监控器实例（确保使用正确的客户端连接）
                self.clipboard_monitor = ClipboardMonitor(qbt, self.config)
                
                # 启动监控任务
                monitor_task = asyncio.create_task(self.clipboard_monitor.start())
                
                # 定期显示状态
                status_task = asyncio.create_task(self._status_reporter())
                
                # 等待关闭信号
                await self.shutdown_event.wait()
                
                print_with_flush("\n🛑 正在停止监控...")
                
                # 停止监控
                self.clipboard_monitor.stop()
                status_task.cancel()
                
                # 等待监控任务完成
                try:
                    await asyncio.wait_for(monitor_task, timeout=10.0)
                    print_success("监控任务已安全停止")
                except asyncio.TimeoutError:
                    print_with_flush("⚠️ 监控任务未能及时停止，正在强制结束...")
                    monitor_task.cancel()
                    
        except Exception as e:
            print_error("监控运行异常", e)
            raise
    
    async def _status_reporter(self):
        """定期显示状态报告"""
        try:
            last_report_time = time.time()
            while not self.shutdown_event.is_set():
                await asyncio.sleep(30)  # 每30秒检查一次
                
                if self.clipboard_monitor:
                    current_time = time.time()
                    if current_time - last_report_time >= 300:  # 每5分钟显示一次统计
                        status = self.clipboard_monitor.get_status()
                        stats = status['stats']
                        
                        print_separator("─", 40)
                        print_with_flush(f"📊 运行状态报告 ({time.strftime('%H:%M:%S')})")
                        print_with_flush(f"   总处理: {stats['total_processed']}")
                        print_with_flush(f"   成功添加: {stats['successful_adds']}")
                        print_with_flush(f"   失败: {stats['failed_adds']}")
                        print_with_flush(f"   重复跳过: {stats['duplicates_skipped']}")
                        print_with_flush(f"   URL爬取: {stats['url_crawls']}")
                        print_with_flush(f"   批量添加: {stats['batch_adds']}")
                        print_separator("─", 40)
                        print_with_flush("⏳ 继续等待剪贴板内容...")
                        
                        last_report_time = current_time
                        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print_error("状态报告异常", e)
    
    async def _cleanup(self):
        """清理资源"""
        print_with_flush("\n🧹 正在清理资源...")
        
        if self.config_manager:
            self.config_manager.stop_file_watcher()
            print_success("配置文件监控已停止")
        
        if self.logger:
            self.logger.info("程序已安全退出")
            print_success("日志已保存")
        
        print_separator()
        print_with_flush("👋 程序已退出，感谢使用QBittorrent智能下载助手！")
        print_separator()
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            print_with_flush(f"\n📡 收到信号 {signum}")
            asyncio.create_task(self._shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
    
    async def _shutdown(self):
        """优雅关闭"""
        self.shutdown_event.set()
    
    def _show_startup_info(self):
        """显示启动信息"""
        print_separator()
        print_with_flush("🎯 QBittorrent智能下载助手 v2.2.0")
        print_separator()
        print_with_flush(f"📡 qBittorrent: {self.config.qbittorrent.host}:{self.config.qbittorrent.port}")
        print_with_flush(f"👤 用户: {self.config.qbittorrent.username}")
        print_with_flush(f"🧠 AI分类: {'✅ 已启用 (DeepSeek)' if self.config.deepseek.api_key else '❌ 未配置'}")
        print_with_flush(f"🕷️ 网页爬虫: ✅ 已启用 (crawl4ai)")
        print_with_flush(f"📂 分类数量: {len(self.config.categories)} 个")
        print_with_flush(f"📋 检查间隔: {self.config.check_interval}秒")
        print_with_flush(f"📝 日志级别: {self.config.log_level}")
        print_with_flush(f"📄 日志文件: {self.config.log_file}")
        print_separator()


def show_help():
    """显示帮助信息"""
    help_text = """
🚀 QBittorrent智能下载助手

📋 功能说明:
  • 自动监控剪贴板中的磁力链接和网页URL
  • 智能分类下载内容（电影、电视剧、动漫等）
  • 支持AI分类（DeepSeek）和规则分类
  • 基于crawl4ai的专业网页爬虫
  • 支持XXXClub等种子网站批量下载

🎯 使用方法:
  python start.py              # 启动程序
  python start.py --help       # 显示此帮助

⚙️ 配置文件:
  qbittorrent_monitor/config.json

🔗 支持的内容:
  磁力链接: magnet:?xt=urn:btih:...
  网页URL:  https://xxxclub.to/torrents/search/...

📝 使用步骤:
  1. 确保qBittorrent已启动并开启Web UI
  2. 修改配置文件中的连接信息
  3. 运行此脚本开始监控
  4. 复制磁力链接或网页URL到剪贴板
  5. 程序会自动处理并分类下载

💡 提示:
  • Ctrl+C 安全退出程序
  • 程序运行时会显示实时统计信息
  • 支持热重载配置文件
"""
    print_with_flush(help_text)


async def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h', 'help']:
        show_help()
        return
    
    # 检查配置文件是否存在
    config_path = Path("qbittorrent_monitor/config.json")
    if not config_path.exists():
        print_error("配置文件不存在!")
        print_with_flush(f"📁 请确保存在文件: {config_path}")
        print_info("请检查项目结构或重新下载配置文件")
        return
    
    # 启动程序
    app = QBittorrentDownloadHelper()
    await app.start()


if __name__ == "__main__":
    try:
        print_with_flush("🔧 正在启动程序...")
        asyncio.run(main())
    except KeyboardInterrupt:
        print_with_flush("\n👋 程序已退出")
    except Exception as e:
        print_error("启动失败", e)
        print_with_flush("\n🔍 详细错误信息:")
        traceback.print_exc()
        sys.exit(1) 