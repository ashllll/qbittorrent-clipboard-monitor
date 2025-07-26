"""
主程序模块

支持：
- CLI界面
- 优雅关闭
- 信号处理
- 状态监控
"""

import asyncio
import signal
import sys
import logging
from pathlib import Path
from typing import Optional
import click

from .config import ConfigManager, AppConfig
from .qbittorrent_client import QBittorrentClient
from .clipboard_monitor import ClipboardMonitor
from .utils import setup_logging, get_config_path
from .exceptions import ConfigError, QBittorrentError


class QBittorrentMonitorApp:
    """主应用程序类"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config_manager: Optional[ConfigManager] = None
        self.config: Optional[AppConfig] = None
        self.qbt_client: Optional[QBittorrentClient] = None
        self.clipboard_monitor: Optional[ClipboardMonitor] = None
        self.logger: Optional[logging.Logger] = None
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """初始化应用程序"""
        # 加载配置
        self.config_manager = ConfigManager(self.config_path)
        self.config = await self.config_manager.load_config()
        
        # 配置日志
        self.logger = setup_logging(
            level=self.config.log_level,
            log_file=self.config.log_file
        )
        
        self.logger.info("=" * 60)
        self.logger.info("QBittorrent剪贴板监控工具启动")
        self.logger.info("=" * 60)
        
        # 注册配置重载回调
        self.config_manager.register_reload_callback(self._on_config_reload)
        
        self.logger.info("应用程序初始化完成")
    
    async def start(self):
        """启动应用程序"""
        try:
            await self.initialize()
            
            # 初始化qBittorrent客户端
            self.qbt_client = QBittorrentClient(
                self.config.qbittorrent,
                app_config=self.config
            )
            
            async with self.qbt_client as qbt:
                # 确保分类存在
                self.logger.info("检查并创建qBittorrent分类...")
                await qbt.ensure_categories(self.config.categories)
                
                # 初始化剪贴板监控器
                self.clipboard_monitor = ClipboardMonitor(qbt, self.config)
                
                # 设置信号处理
                self._setup_signal_handlers()
                
                self.logger.info("所有组件初始化完成，开始监控...")
                
                # 启动监控循环
                monitor_task = asyncio.create_task(self.clipboard_monitor.start())
                status_task = asyncio.create_task(self._status_reporter())
                
                # 等待关闭信号
                await self.shutdown_event.wait()
                
                self.logger.info("收到关闭信号，正在优雅关闭...")
                
                # 停止监控
                self.clipboard_monitor.stop()
                
                # 等待任务完成
                try:
                    await asyncio.wait_for(monitor_task, timeout=10.0)
                except asyncio.TimeoutError:
                    self.logger.warning("监控任务未能在超时时间内停止")
                    monitor_task.cancel()
                
                status_task.cancel()
                
                self.logger.info("应用程序已安全关闭")
                
        except ConfigError as e:
            if self.logger:
                self.logger.error(f"配置错误: {str(e)}")
            else:
                print(f"配置错误: {str(e)}")
            sys.exit(1)
            
        except QBittorrentError as e:
            if self.logger:
                self.logger.error(f"qBittorrent错误: {str(e)}")
            else:
                print(f"qBittorrent错误: {str(e)}")
            sys.exit(1)
            
        except KeyboardInterrupt:
            if self.logger:
                self.logger.info("收到键盘中断信号")
            else:
                print("收到键盘中断信号")
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"未处理的异常: {str(e)}", exc_info=True)
            else:
                print(f"未处理的异常: {str(e)}")
            sys.exit(1)
            
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """清理资源"""
        if self.config_manager:
            self.config_manager.stop_file_watcher()
        
        if self.logger:
            self.logger.info("资源清理完成")
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            self.logger.info(f"收到信号 {signum}")
            # 不要在信号处理函数中直接创建协程任务
            # 改为设置事件标志
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
    
    async def _shutdown(self):
        """优雅关闭"""
        self.shutdown_event.set()
    
    async def _status_reporter(self):
        """状态报告器"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(300)  # 每5分钟报告一次状态
                
                if self.clipboard_monitor:
                    status = self.clipboard_monitor.get_status()
                    self.logger.info(
                        f"状态报告 - "
                        f"已处理: {status['stats']['total_processed']}, "
                        f"成功: {status['stats']['successful_adds']}, "
                        f"失败: {status['stats']['failed_adds']}, "
                        f"重复: {status['stats']['duplicates_skipped']}"
                    )
                    
        except asyncio.CancelledError:
            pass
    
    async def _on_config_reload(self, old_config: AppConfig, new_config: AppConfig):
        """配置重载回调"""
        self.logger.info("检测到配置变更")
        self.config = new_config
        
        # 重新配置日志级别
        if old_config.log_level != new_config.log_level:
            self.logger.setLevel(getattr(logging, new_config.log_level.upper()))
            self.logger.info(f"日志级别已更新为: {new_config.log_level}")
        
        # 重新初始化AI分类器（如果配置变更）
        if (old_config.deepseek.dict() != new_config.deepseek.dict() and 
            self.clipboard_monitor):
            from .ai_classifier import AIClassifier
            self.clipboard_monitor.ai_classifier = AIClassifier(new_config.deepseek)
            self.logger.info("AI分类器已重新初始化")


# CLI命令
@click.group()
@click.version_option(version="2.1.0")
def cli():
    """QBittorrent剪贴板监控工具"""
    pass


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), 
              help='配置文件路径')
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              default='INFO', help='日志级别')
def start(config: Optional[str], log_level: str):
    """启动监控服务"""
    app = QBittorrentMonitorApp(config)
    
    try:
        asyncio.run(app.start())
    except KeyboardInterrupt:
        print("\n监控已停止")


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), 
              help='配置文件路径')
def validate_config(config: Optional[str]):
    """验证配置文件"""
    config_path = config or get_config_path()
    
    try:
        config_manager = ConfigManager(config_path)
        config_data = asyncio.run(config_manager.load_config())
        click.echo(f"✅ 配置文件验证通过: {config_path}")
        click.echo(f"   - qBittorrent: {config_data.qbittorrent.host}:{config_data.qbittorrent.port}")
        click.echo(f"   - 分类数量: {len(config_data.categories)}")
        click.echo(f"   - AI模型: {config_data.deepseek.model}")
        
    except Exception as e:
        click.echo(f"❌ 配置文件验证失败: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), 
              help='配置文件路径')
def test_connection(config: Optional[str]):
    """测试qBittorrent连接"""
    async def test():
        try:
            config_manager = ConfigManager(config)
            app_config = await config_manager.load_config()
            
            click.echo("正在测试qBittorrent连接...")
            qbt_client = QBittorrentClient(app_config.qbittorrent, app_config)
            async with qbt_client as qbt:
                version = await qbt.get_version()
                click.echo(f"✅ 连接成功！qBittorrent版本: {version}")
                
        except Exception as e:
            click.echo(f"❌ 连接失败: {str(e)}", err=True)
            sys.exit(1)
            
    asyncio.run(test())


@cli.command()
def create_config():
    """创建默认配置文件"""
    config_path = get_config_path()
    
    if config_path.exists():
        if not click.confirm(f"配置文件 {config_path} 已存在，是否覆盖？"):
            return
            
    try:
        config_manager = ConfigManager(config_path)
        config_manager._create_default_config()
        click.echo(f"✅ 默认配置文件已创建: {config_path}")
        click.echo("请编辑配置文件并设置：")
        click.echo("   - qBittorrent连接信息")
        click.echo("   - DeepSeek API密钥")
        click.echo("   - 下载路径映射")
        
    except Exception as e:
        click.echo(f"❌ 创建配置文件失败: {str(e)}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli() 