"""
增强的剪贴板监控器模块

支持：
- 智能剪贴板监控
- 丰富的通知集成
- 错误恢复
- 历史记录
- 实时统计
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Dict, List
import pyperclip

from .config import AppConfig
from .qbittorrent_client import QBittorrentClient
from .ai_classifier import AIClassifier
from .utils import parse_magnet, validate_magnet_link, NotificationManager
from .exceptions import ClipboardError, TorrentParseError


class TorrentRecord:
    """种子处理记录"""
    
    def __init__(self, magnet_link: str, torrent_hash: str, torrent_name: str):
        self.magnet_link = magnet_link
        self.torrent_hash = torrent_hash
        self.torrent_name = torrent_name
        self.timestamp = datetime.now()
        self.category: Optional[str] = None
        self.status: str = "pending"  # pending, success, failed, duplicate
        self.error_message: Optional[str] = None
        self.classification_method: Optional[str] = None
        self.save_path: Optional[str] = None


class ClipboardMonitor:
    """增强的异步剪贴板监控器"""
    
    def __init__(self, qbt: QBittorrentClient, config: AppConfig):
        self.qbt = qbt
        self.config = config
        self.logger = logging.getLogger('ClipboardMonitor')
        self.last_clip = ""
        
        # 磁力链接正则模式
        self.magnet_pattern = re.compile(
            r"^magnet:\?xt=urn:btih:[0-9a-fA-F]{40,}.*",
            re.IGNORECASE
        )
        
        # XXXClub URL正则模式
        self.xxxclub_pattern = re.compile(
            r"https?://(?:www\.)?xxxclub\.to/torrents/search/.*",
            re.IGNORECASE
        )
        
        # 初始化AI分类器
        self.ai_classifier = AIClassifier(config.deepseek)
        
        # 初始化通知管理器
        self.notification_manager = NotificationManager(config.notifications.model_dump())
        
        # 处理历史记录
        self.history: List[TorrentRecord] = []
        self.max_history_size = 1000
        
        # 统计信息
        self.stats = {
            'total_processed': 0,
            'successful_adds': 0,
            'failed_adds': 0,
            'duplicates_skipped': 0,
            'ai_classifications': 0,
            'rule_classifications': 0,
            'url_crawls': 0,  # 新增：URL爬取统计
            'batch_adds': 0   # 新增：批量添加统计
        }
        
        # 监控状态
        self.is_running = False
        self.last_error_time: Optional[datetime] = None
        self.consecutive_errors = 0
        self.last_stats_report = datetime.now()
        
    async def start(self):
        """启动剪贴板监控循环"""
        self.is_running = True
        self.logger.info("开始监控剪贴板...")
        
        # 欢迎消息
        self._show_welcome_message()
        
        try:
            while self.is_running:
                await self._monitor_cycle()
                await asyncio.sleep(self.config.check_interval)
                
        except asyncio.CancelledError:
            self.logger.info("监控已取消")
            raise
        except Exception as e:
            self.logger.error(f"监控异常: {str(e)}")
            await self._handle_monitor_error(e)
            raise
        finally:
            self.is_running = False
            self.logger.info("剪贴板监控已停止")
            self._show_farewell_message()
    
    def stop(self):
        """停止监控"""
        self.is_running = False
    
    async def _monitor_cycle(self):
        """单次监控循环"""
        try:
            current_clip = pyperclip.paste()
            
            # 检查是否为新内容且为磁力链接
            if (current_clip != self.last_clip and 
                current_clip and 
                self.magnet_pattern.match(current_clip.strip())):
                
                self.last_clip = current_clip
                await self._process_magnet(current_clip.strip())
                
                # 重置错误计数
                self.consecutive_errors = 0
                self.last_error_time = None
            
            # 检查是否为XXXClub网页URL
            elif (current_clip != self.last_clip and 
                  current_clip and 
                  self.xxxclub_pattern.match(current_clip.strip())):
                
                self.last_clip = current_clip
                await self._process_url(current_clip.strip())
                
                # 重置错误计数
                self.consecutive_errors = 0
                self.last_error_time = None
                
            # 定期显示统计信息（每5分钟）
            now = datetime.now()
            if (now - self.last_stats_report).total_seconds() >= 300:  # 5分钟
                await self._periodic_stats_report()
                self.last_stats_report = now
                
        except Exception as e:
            self.consecutive_errors += 1
            self.last_error_time = datetime.now()
            
            if self.consecutive_errors <= 3:
                self.logger.warning(f"监控循环错误 ({self.consecutive_errors}/3): {str(e)}")
            else:
                self.logger.error(f"连续监控错误过多，可能需要重启: {str(e)}")
                await self._handle_monitor_error(e)
    
    async def _process_magnet(self, magnet_link: str):
        """处理磁力链接"""
        self.logger.info(f"🔍 发现新磁力链接: {magnet_link[:60]}...")
        
        # 验证磁力链接格式
        if not validate_magnet_link(magnet_link):
            self.logger.error("❌ 无效的磁力链接格式")
            return
        
        try:
            # 解析磁力链接
            torrent_hash, torrent_name = parse_magnet(magnet_link)
            if not torrent_hash:
                raise TorrentParseError("无法解析磁力链接哈希值")
            
            # 创建记录
            record = TorrentRecord(magnet_link, torrent_hash, torrent_name or "Unknown")
            self._add_to_history(record)
            
            self.stats['total_processed'] += 1
            
            self.logger.info(f"📁 处理种子: {record.torrent_name}")
            
            # 检查是否重复
            if await self._check_duplicate(record):
                return
            
            # AI分类
            category = await self._classify_torrent(record)
            record.category = category
            
            # 获取保存路径
            save_path = await self._get_save_path(category)
            record.save_path = save_path
            
            # 添加到qBittorrent
            success = await self._add_torrent_to_client(record)
            
            if success:
                record.status = "success"
                self.stats['successful_adds'] += 1
                await self.notification_manager.send_torrent_success(
                    record.torrent_name,
                    record.category,
                    record.save_path or "默认路径",
                    record.torrent_hash,
                    record.classification_method or "AI"
                )
                self.logger.info(f"✅ 成功添加种子: {record.torrent_name} -> {category}")
            else:
                record.status = "failed"
                self.stats['failed_adds'] += 1
                await self.notification_manager.send_torrent_failure(
                    record.torrent_name,
                    record.error_message or "添加失败",
                    record.torrent_hash,
                    record.category or ""
                )
                
        except Exception as e:
            self.logger.error(f"❌ 处理磁力链接失败: {str(e)}")
            if 'record' in locals():
                record.status = "failed"
                record.error_message = str(e)
                self.stats['failed_adds'] += 1
                await self.notification_manager.send_torrent_failure(
                    record.torrent_name,
                    str(e),
                    record.torrent_hash,
                    record.category or ""
                )
    
    async def _check_duplicate(self, record: TorrentRecord) -> bool:
        """检查种子是否重复"""
        try:
            if await self.qbt._is_duplicate(record.torrent_hash):
                record.status = "duplicate"
                self.stats['duplicates_skipped'] += 1
                
                await self.notification_manager.send_duplicate_notification(
                    record.torrent_name,
                    record.torrent_hash
                )
                
                self.logger.info(f"⚠️ 跳过重复种子: {record.torrent_name}")
                return True
                
        except Exception as e:
            self.logger.warning(f"检查重复失败: {str(e)}")
            
        return False
    
    async def _classify_torrent(self, record: TorrentRecord) -> str:
        """分类种子"""
        try:
            category = await self.ai_classifier.classify(
                record.torrent_name, 
                self.config.categories
            )
            
            # 统计分类方式
            if hasattr(self.ai_classifier, 'client') and self.ai_classifier.client:
                self.stats['ai_classifications'] += 1
                record.classification_method = "AI"
            else:
                self.stats['rule_classifications'] += 1
                record.classification_method = "规则"
            
            self.logger.info(f"🧠 分类结果: {record.torrent_name[:50]}... -> {category} ({record.classification_method})")
            return category
            
        except Exception as e:
            self.logger.error(f"❌ 分类失败: {str(e)}, 使用默认分类 'other'")
            self.stats['rule_classifications'] += 1
            record.classification_method = "默认"
            return "other"
    
    async def _get_save_path(self, category: str) -> str:
        """获取分类的保存路径"""
        try:
            existing_categories = await self.qbt.get_existing_categories()
            if category in existing_categories:
                return existing_categories[category].get('savePath', '默认路径')
            else:
                # 从配置中获取路径
                if category in self.config.categories:
                    return self.config.categories[category].save_path
                    
        except Exception as e:
            self.logger.warning(f"获取保存路径失败: {str(e)}")
            
        return "默认路径"
    
    async def _add_torrent_to_client(self, record: TorrentRecord) -> bool:
        """添加种子到qBittorrent客户端"""
        try:
            success = await self.qbt.add_torrent(
                record.magnet_link, 
                record.category or "other"
            )
            
            return success
            
        except Exception as e:
            record.error_message = str(e)
            self.logger.error(f"❌ 添加种子失败: {str(e)}")
            return False
    
    def _show_welcome_message(self):
        """显示欢迎消息"""
        if self.config.notifications.console.enabled:
            welcome_lines = [
                "🚀 qBittorrent增强剪贴板监控已启动!",
                f"📋 监控间隔: {self.config.check_interval}秒",
                f"🧠 AI分类器: {'已启用' if hasattr(self.ai_classifier, 'client') and self.ai_classifier.client else '使用规则引擎'}",
                f"🔔 通知系统: {'已启用' if self.config.notifications.enabled else '已禁用'}",
                "💡 支持的内容类型:",
                "   🔗 磁力链接 (magnet:) - 自动分类添加",
                "   🌐 XXXClub搜索URL - 批量抓取种子",
                "📝 使用方法:",
                "   复制磁力链接到剪贴板 → 自动添加单个种子",
                "   复制XXXClub搜索页面URL → 批量抓取并添加所有种子",
                "⏹️  按Ctrl+C停止监控"
            ]
            
            if self.notification_manager.use_colors:
                from colorama import Fore, Style
                print(f"\n{Fore.GREEN}{'='*70}")
                for line in welcome_lines:
                    print(f"{Fore.GREEN}{line}")
                print(f"{'='*70}{Style.RESET_ALL}\n")
            else:
                print(f"\n{'='*70}")
                for line in welcome_lines:
                    print(line)
                print(f"{'='*70}\n")
    
    def _show_farewell_message(self):
        """显示告别消息"""
        if self.config.notifications.console.enabled:
            # 显示最终统计
            if self.config.notifications.console.show_statistics:
                if self.notification_manager.use_colors:
                    from colorama import Fore, Style
                    print(f"\n{Fore.BLUE}📊 最终统计")
                    print(f"{Fore.BLUE}{'─'*40}")
                    print(f"{Fore.CYAN}总处理数: {Fore.WHITE}{self.stats.get('total_processed', 0)}")
                    print(f"{Fore.GREEN}成功添加: {Fore.WHITE}{self.stats.get('successful_adds', 0)}")
                    print(f"{Fore.RED}添加失败: {Fore.WHITE}{self.stats.get('failed_adds', 0)}")
                    print(f"{Fore.YELLOW}重复跳过: {Fore.WHITE}{self.stats.get('duplicates_skipped', 0)}")
                    print(f"{Fore.MAGENTA}URL爬取: {Fore.WHITE}{self.stats.get('url_crawls', 0)}")
                    print(f"{Fore.MAGENTA}批量添加: {Fore.WHITE}{self.stats.get('batch_adds', 0)}")
                    print(f"{Fore.BLUE}{'─'*40}{Style.RESET_ALL}")
                else:
                    print(f"\n📊 最终统计")
                    print(f"{'─'*40}")
                    print(f"总处理数: {self.stats.get('total_processed', 0)}")
                    print(f"成功添加: {self.stats.get('successful_adds', 0)}")
                    print(f"添加失败: {self.stats.get('failed_adds', 0)}")
                    print(f"重复跳过: {self.stats.get('duplicates_skipped', 0)}")
                    print(f"URL爬取: {self.stats.get('url_crawls', 0)}")
                    print(f"批量添加: {self.stats.get('batch_adds', 0)}")
                    print(f"{'─'*40}")
            
            farewell_lines = [
                "👋 qBittorrent剪贴板监控已停止",
                "感谢使用，再见!"
            ]
            
            if self.notification_manager.use_colors:
                from colorama import Fore, Style
                print(f"\n{Fore.BLUE}{'='*40}")
                for line in farewell_lines:
                    print(f"{Fore.BLUE}{line}")
                print(f"{'='*40}{Style.RESET_ALL}\n")
            else:
                print(f"\n{'='*40}")
                for line in farewell_lines:
                    print(line)
                print(f"{'='*40}\n")
    
    async def _periodic_stats_report(self):
        """定期统计报告"""
        if self.config.notifications.console.show_statistics:
            await self.notification_manager.send_statistics(self.stats)
    
    def _add_to_history(self, record: TorrentRecord):
        """添加记录到历史"""
        self.history.append(record)
        
        # 限制历史记录大小
        if len(self.history) > self.max_history_size:
            self.history = self.history[-self.max_history_size:]
    
    async def _handle_monitor_error(self, error: Exception):
        """处理监控错误"""
        self.logger.error(f"🚨 监控器遇到严重错误: {str(error)}")
        
        error_message = f"监控器错误: {type(error).__name__}: {str(error)}"
        await self.notification_manager.send_torrent_failure(
            "系统错误",
            error_message,
            "system_error",
            ""
        )
    
    def get_status(self) -> Dict:
        """获取监控状态"""
        recent_history = self.history[-10:] if self.history else []
        
        return {
            'is_running': self.is_running,
            'stats': self.stats.copy(),
            'last_error_time': self.last_error_time.isoformat() if self.last_error_time else None,
            'consecutive_errors': self.consecutive_errors,
            'history_count': len(self.history),
            'recent_records': [
                {
                    'torrent_name': r.torrent_name,
                    'category': r.category,
                    'status': r.status,
                    'timestamp': r.timestamp.isoformat(),
                    'error_message': r.error_message,
                    'classification_method': r.classification_method,
                    'save_path': r.save_path
                }
                for r in recent_history
            ]
        }
    
    def get_history(self, limit: int = 100) -> List[Dict]:
        """获取处理历史记录"""
        recent_records = self.history[-limit:] if limit > 0 else self.history
        
        return [
            {
                'torrent_hash': r.torrent_hash,
                'torrent_name': r.torrent_name,
                'category': r.category,
                'status': r.status,
                'timestamp': r.timestamp.isoformat(),
                'error_message': r.error_message,
                'classification_method': r.classification_method,
                'save_path': r.save_path
            }
            for r in recent_records
        ]
    
    def clear_history(self):
        """清空历史记录"""
        self.history.clear()
        self.logger.info("已清空历史记录")
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_processed': 0,
            'successful_adds': 0,
            'failed_adds': 0,
            'duplicates_skipped': 0,
            'ai_classifications': 0,
            'rule_classifications': 0,
            'url_crawls': 0,
            'batch_adds': 0
        }
        self.logger.info("已重置统计信息")
    
    async def _process_url(self, url: str):
        """处理网页URL（批量爬取种子）"""
        self.logger.info(f"🌐 检测到网页URL: {url}")
        
        try:
            # 导入web_crawler模块
            from .web_crawler import crawl_and_add_torrents
            
            # 通知开始批量处理
            if self.config.notifications.console.enabled:
                if self.notification_manager.use_colors:
                    from colorama import Fore, Style
                    print(f"\n{Fore.CYAN}🌐 检测到网页URL，开始批量抓取种子...")
                    print(f"{Fore.CYAN}📋 URL: {url}")
                    print(f"{Fore.CYAN}🔗 正在分析页面内容...{Style.RESET_ALL}")
                else:
                    print(f"\n🌐 检测到网页URL，开始批量抓取种子...")
                    print(f"📋 URL: {url}")
                    print(f"🔗 正在分析页面内容...")
            
            # 使用爬虫功能批量处理
            result = await crawl_and_add_torrents(
                url, 
                self.config, 
                self.qbt, 
                max_pages=1  # 默认只处理第一页，避免过多种子
            )
            
            if result['success']:
                # 更新统计信息
                stats = result['stats']['stats']
                self.stats['url_crawls'] += 1
                self.stats['total_processed'] += stats.get('torrents_found', 0)
                self.stats['successful_adds'] += stats.get('torrents_added', 0)
                self.stats['duplicates_skipped'] += stats.get('duplicates_skipped', 0)
                self.stats['failed_adds'] += stats.get('errors', 0)
                
                if stats.get('torrents_added', 0) > 0:
                    self.stats['batch_adds'] += 1
                
                # 显示批量处理结果
                if self.config.notifications.console.enabled:
                    if self.notification_manager.use_colors:
                        from colorama import Fore, Style
                        print(f"\n{Fore.GREEN}✅ 批量处理完成!")
                        print(f"{Fore.CYAN}📊 处理结果:")
                        print(f"   找到种子: {Fore.WHITE}{stats.get('torrents_found', 0)}")
                        print(f"   成功添加: {Fore.GREEN}{stats.get('torrents_added', 0)}")
                        print(f"   重复跳过: {Fore.YELLOW}{stats.get('duplicates_skipped', 0)}")
                        print(f"   失败数量: {Fore.RED}{stats.get('errors', 0)}")
                        print(f"{Fore.GREEN}{'─'*50}{Style.RESET_ALL}")
                    else:
                        print(f"\n✅ 批量处理完成!")
                        print(f"📊 处理结果:")
                        print(f"   找到种子: {stats.get('torrents_found', 0)}")
                        print(f"   成功添加: {stats.get('torrents_added', 0)}")
                        print(f"   重复跳过: {stats.get('duplicates_skipped', 0)}")
                        print(f"   失败数量: {stats.get('errors', 0)}")
                        print(f"{'─'*50}")
                
                self.logger.info(f"✅ 批量处理完成: {result['message']}")
            else:
                self.stats['failed_adds'] += 1
                self.logger.error(f"❌ 批量处理失败: {result['message']}")
                
                # 显示失败信息
                if self.config.notifications.console.enabled:
                    if self.notification_manager.use_colors:
                        from colorama import Fore, Style
                        print(f"\n{Fore.RED}❌ 批量处理失败!")
                        print(f"{Fore.CYAN}错误信息: {Fore.RED}{result['message']}")
                        print(f"{Fore.RED}{'─'*50}{Style.RESET_ALL}")
                    else:
                        print(f"\n❌ 批量处理失败!")
                        print(f"错误信息: {result['message']}")
                        print(f"{'─'*50}")
                
        except Exception as e:
            self.stats['failed_adds'] += 1
            self.logger.error(f"❌ 处理网页URL失败: {str(e)}")
            
            # 显示错误信息
            if self.config.notifications.console.enabled:
                if self.notification_manager.use_colors:
                    from colorama import Fore, Style
                    print(f"\n{Fore.RED}❌ 网页URL处理异常!")
                    print(f"{Fore.CYAN}错误详情: {Fore.RED}{str(e)}")
                    print(f"{Fore.RED}{'─'*50}{Style.RESET_ALL}")
                else:
                    print(f"\n❌ 网页URL处理异常!")
                    print(f"错误详情: {str(e)}")
                    print(f"{'─'*50}") 