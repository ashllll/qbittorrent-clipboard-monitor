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
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set

from .config import AppConfig
from .qbittorrent_client import QBittorrentClient
from .ai_classifier import AIClassifier
from .clipboard_poller import ClipboardPoller, PollerConfig
from .clipboard_processor import ClipboardContentProcessor
from .clipboard_actions import ClipboardActionExecutor
from .clipboard_models import TorrentRecord
from .notifications import NotificationManager
from .exceptions import ClipboardError
from .workflow_engine import initialize_workflow_engine, get_workflow_engine


class ClipboardMonitor:
    """高性能异步剪贴板监控器
    
    优化特性:
    - 异步剪贴板访问，避免阻塞事件循环
    - 智能轮询间隔调整，减少CPU使用
    - 内存管理优化，防止内存泄漏
    - 重复检测缓存，提升性能
    - 错误恢复机制，增强稳定性
    """
    
    def __init__(self, qbt: QBittorrentClient, config: AppConfig):
        self.qbt = qbt
        self.config = config
        self.logger = logging.getLogger('ClipboardMonitor')
        
        self.last_clip = ""

        # 提前初始化监控状态，确保异常时也可安全清理
        self.history: deque = deque(maxlen=1000)
        self._duplicate_cache: Set[str] = set()
        self._cache_cleanup_time = datetime.now()
        self._max_cache_size = 10000
        self.stats = {
            'total_processed': 0,
            'successful_adds': 0,
            'failed_adds': 0,
            'duplicates_skipped': 0,
            'ai_classifications': 0,
            'rule_classifications': 0,
            'url_crawls': 0,
            'batch_adds': 0,
            'clipboard_reads': 0,  # 新增：剪贴板读取次数
            'cache_hits': 0,       # 新增：缓存命中次数
            'performance_metrics': {
                'avg_process_time': 0.0,
                'max_process_time': 0.0,
                'total_process_time': 0.0
            }
        }
        self.is_running = False
        self.last_error_time: Optional[datetime] = None
        self.consecutive_errors = 0
        self.last_stats_report = datetime.now()
        self._process_times: deque = deque(maxlen=100)
        self._is_cleaned_up = False
        self._cleanup_lock = asyncio.Lock()

        # 初始化AI分类器 & 通知组件
        self.ai_classifier = AIClassifier(config.deepseek)
        self.notification_manager = NotificationManager(config.notifications.model_dump())
        self.content_processor = ClipboardContentProcessor()
        self.action_executor = ClipboardActionExecutor(
            self.qbt,
            self.config,
            self.ai_classifier,
            self.notification_manager,
            self.stats,
            self._add_to_history,
            logger=self.logger,
        )

        base_interval = max(0.5, min(config.check_interval, 5.0))
        poller_config = PollerConfig(base_interval=base_interval)
        self.poller = ClipboardPoller(poller_config, self._on_clipboard_change)
        self._pending_clip: Optional[str] = None
        self._clip_event = asyncio.Event()
        self._base_interval = poller_config.base_interval
        self._max_interval = poller_config.max_interval
        
    async def start(self):
        """启动剪贴板监控循环"""
        self.is_running = True
        self.logger.info("开始监控剪贴板...")

        # 初始化并启动工作流引擎
        try:
            self.workflow_engine = await initialize_workflow_engine(
                self.qbt,
                self.config,
                self.ai_classifier,
                self.notification_manager
            )
            self.logger.info("工作流引擎已启动")
        except Exception as e:
            self.logger.error(f"工作流引擎启动失败: {e}")
            self.workflow_engine = None

        # 欢迎消息
        self._show_welcome_message()

        poller_task = asyncio.create_task(self.poller.start())
        try:
            while self.is_running:
                await self._clip_event.wait()
                self._clip_event.clear()
                clip = self._pending_clip
                self._pending_clip = None
                if clip is None:
                    continue

                cycle_start = time.time()
                await self._process_clipboard_text(clip)

                cycle_time = time.time() - cycle_start
                self._process_times.append(cycle_time)
                self._update_performance_metrics(cycle_time)

        except asyncio.CancelledError:
            self.logger.info("监控已取消")
            raise
        except Exception as e:
            self.logger.error(f"监控异常: {str(e)}")
            await self._handle_monitor_error(e)
            raise
        finally:
            self.is_running = False
            self.poller.stop()
            poller_task.cancel()
            try:
                await poller_task
            except asyncio.CancelledError:
                pass
            await self.cleanup()
            self.logger.info("剪贴板监控已停止")
            self._show_farewell_message()
    
    def stop(self):
        """停止监控"""
        self.is_running = False
        self.poller.stop()
        self._clip_event.set()

    def _on_clipboard_change(self, text: str):
        """处理剪贴板变更回调"""
        if not self.is_running:
            return
        self.stats['clipboard_reads'] = self.poller.clipboard_reads
        self._pending_clip = text or ""
        self._clip_event.set()
    
    async def _process_clipboard_text(self, current_clip: str):
        try:
            task = self.content_processor.process(current_clip)
            self.last_clip = current_clip or ""

            handled = False
            if task.kind == "magnet":
                await self.action_executor.handle_magnet(task.content)
                handled = True
            elif task.kind == "url":
                await self.action_executor.handle_url(task.content)
                handled = True

            # 重置错误计数
            self.consecutive_errors = 0
            self.last_error_time = None
            
            # 定期清理缓存和报告统计
            if handled:
                await self._periodic_maintenance()
                
        except Exception as e:
            self.consecutive_errors += 1
            self.last_error_time = datetime.now()
            
            if self.consecutive_errors <= 3:
                self.logger.warning(f"监控循环错误 ({self.consecutive_errors}/3): {str(e)}")
            else:
                self.logger.error(f"连续监控错误过多，可能需要重启: {str(e)}")
                await self._handle_monitor_error(e)
    
    def _update_performance_metrics(self, cycle_time: float):
        """更新性能指标"""
        # 更新性能指标
        if self._process_times:
            avg_time = sum(self._process_times) / len(self._process_times)
            self.stats['performance_metrics']['avg_process_time'] = round(avg_time, 4)
            self.stats['performance_metrics']['total_process_time'] += cycle_time
        
        # 记录最大处理时间
        if cycle_time > self.stats['performance_metrics']['max_process_time']:
            self.stats['performance_metrics']['max_process_time'] = round(cycle_time, 4)
    
    async def _periodic_maintenance(self):
        """定期维护任务"""
        now = datetime.now()
        
        # 每5分钟显示统计信息
        if (now - self.last_stats_report).total_seconds() >= 300:
            await self._periodic_stats_report()
            self.last_stats_report = now
        
        # 每小时清理重复检测缓存
        if (now - self._cache_cleanup_time).total_seconds() >= 3600:
            self._cleanup_duplicate_cache()
            self._cache_cleanup_time = now
    
    def _cleanup_duplicate_cache(self):
        """清理过期的重复检测缓存"""
        # 如果缓存过大，清理一半
        if len(self._duplicate_cache) > self._max_cache_size:
            # 转换为列表并保留后一半
            cache_list = list(self._duplicate_cache)
            self._duplicate_cache = set(cache_list[len(cache_list)//2:])
            self.logger.debug(f"清理了 {len(cache_list)//2} 个缓存项")
    
    def _show_welcome_message(self):
        """显示欢迎消息"""
        if self.config.notifications.console.enabled:
            welcome_lines = [
                "qBittorrent增强剪贴板监控已启动! (高性能版 v2.3.0)",
                f"基础监控间隔: {self._base_interval}秒 (动态调整: {self._base_interval}-{self._max_interval}秒)",
                f"AI分类器: {'已启用' if hasattr(self.ai_classifier, 'client') and self.ai_classifier.client else '使用规则引擎'}",
                f"通知系统: {'已启用' if self.config.notifications.enabled else '已禁用'}",
                f"性能优化: 异步剪贴板访问、智能轮询、内存管理",
                "支持的内容类型:",
                "   磁力链接 (magnet:) - 自动分类添加",
                "   网页URL (http/https) - 爬取页面内磁力链接",
                "   XXXClub搜索URL - 批量抓取种子",
                "使用方法:",
                "   复制磁力链接到剪贴板 → 自动添加单个种子",
                "   复制XXXClub搜索页面URL → 批量抓取并添加所有种子",
                "按Ctrl+C停止监控"
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
    
    async def _classify_torrent_async(self, torrent_name: str) -> str:
        """异步分类种子"""
        if self.ai_classifier:
            try:
                return await self.ai_classifier.classify(torrent_name, self.config.categories)
            except Exception as e:
                self.logger.warning(f"AI分类失败: {str(e)}")
                return self._classify_by_rules(torrent_name)
        else:
            return self._classify_by_rules(torrent_name)
    
    def _classify_by_rules(self, torrent_name: str) -> str:
        """基于规则的分类"""
        # 简单的规则分类逻辑
        name_lower = torrent_name.lower()
        
        if any(keyword in name_lower for keyword in ['movie', 'film', '电影']):
            return 'movies'
        elif any(keyword in name_lower for keyword in ['tv', 'series', '电视']):
            return 'tv'
        elif any(keyword in name_lower for keyword in ['music', '音乐']):
            return 'music'
        elif any(keyword in name_lower for keyword in ['game', '游戏']):
            return 'games'
        else:
            return 'other'
    
    async def _add_torrent_with_retry(self, magnet_link: str, category: str, save_path: str, max_retries: int = 3) -> bool:
        """带重试机制的种子添加"""
        for attempt in range(max_retries):
            try:
                success = await self._add_torrent_to_qb(magnet_link, category, save_path)
                if success:
                    return True
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    self.logger.warning(f"添加失败，{wait_time}秒后重试 (尝试 {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"添加异常: {str(e)}，{wait_time}秒后重试 (尝试 {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"添加失败，已达最大重试次数: {str(e)}")
        
        return False
    
    async def _add_torrent_to_qb(self, magnet_link: str, category: str, save_path: str) -> bool:
        """添加种子到qBittorrent"""
        try:
            return await self.qbt.add_torrent(magnet_link, category)
        except Exception as e:
            self.logger.error(f"添加种子到qBittorrent失败: {str(e)}")
            return False
    
    async def _process_single_torrent_from_web(self, torrent_info, url: str, semaphore: asyncio.Semaphore) -> bool:
        """处理从网页提取的单个种子"""
        async with semaphore:
            try:
                # 检查磁力链接重复
                if await self._check_duplicate_by_hash(torrent_info.get('hash', '')):
                    self.logger.info(f"跳过重复的种子: {torrent_info.get('name', 'Unknown')}")
                    return False
                
                # 创建种子记录
                record = TorrentRecord(
                    magnet_link=torrent_info.get('magnet_link', ''),
                    torrent_hash=torrent_info.get('hash', ''),
                    torrent_name=torrent_info.get('name', 'Unknown')
                )
                
                # 分类
                record.category = await self._classify_torrent_async(torrent_info.get('name', ''))
                
                # 获取保存路径
                save_path = await self._get_save_path(record.category)
                
                # 添加到qBittorrent
                success = await self._add_torrent_with_retry(
                    torrent_info.get('magnet_link', ''), 
                    record.category, 
                    save_path
                )
                
                if success:
                    record.status = "success"
                    self.stats['successful_adds'] += 1
                    self.logger.info(f"  ✅ {torrent_info.get('name', 'Unknown')} -> {record.category}")
                else:
                    record.status = "failed"
                    self.stats['failed_adds'] += 1
                    self.logger.error(f"  ❌ 添加失败: {torrent_info.get('name', 'Unknown')}")
                
                # 添加到历史记录
                self._add_to_history(record)
                return success
                
            except Exception as e:
                self.logger.error(f"处理种子时发生错误 {torrent_info.get('name', 'Unknown')}: {str(e)}")
                self.stats['failed_adds'] += 1
                return False
    
    async def _check_duplicate_by_hash(self, torrent_hash: str) -> bool:
        """通过哈希检查重复"""
        if not torrent_hash:
            return False
        
        try:
            return await self.qbt._is_duplicate(torrent_hash)
        except Exception as e:
            self.logger.warning(f"检查重复失败: {str(e)}")
            return False
    
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
    
    def _add_to_history(self, record: TorrentRecord):
        """添加到历史记录"""
        try:
            self.history.append(record)
        except Exception as e:
            self.logger.warning(f"添加历史记录失败: {str(e)}")
    
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
    
    async def _periodic_stats_report(self):
        """定期统计报告"""
        if self.config.notifications.console.show_statistics:
            await self.notification_manager.send_statistics(self.stats)
    

    
    async def cleanup(self):
        """清理资源"""
        async with self._cleanup_lock:
            if self._is_cleaned_up:
                return
            
            self.logger.info("开始清理ClipboardMonitor资源...")
            self.logger.info("🔍 [诊断] ClipboardMonitor开始清理流程...")
            
            try:
                # 停止监控
                self._running = False
                self.logger.info("🔍 [诊断] 监控状态已设置为停止")

                # 停止工作流引擎
                if hasattr(self, 'workflow_engine') and self.workflow_engine:
                    self.logger.info("🔍 [诊断] 停止工作流引擎...")
                    await self.workflow_engine.stop()
                    self.logger.info("✅ [诊断] 工作流引擎已停止")

                # 清理Web爬虫（如果存在）
                if hasattr(self, 'web_crawler') and self.web_crawler:
                    self.logger.info("🔍 [诊断] 清理Web爬虫资源...")
                    await self.web_crawler.cleanup()
                    self.logger.info("✅ [诊断] Web爬虫资源已清理")
                
                # 清理AI分类器
                if hasattr(self, 'ai_classifier') and hasattr(self.ai_classifier, 'cleanup'):
                    self.logger.info("🔍 [诊断] 清理AI分类器资源...")
                    await self.ai_classifier.cleanup()
                    self.logger.info("✅ [诊断] AI分类器资源已清理")
                
                # 清理QBittorrent客户端（重要！这可能是遗漏的部分）
                if hasattr(self, 'qbt') and self.qbt:
                    self.logger.info("🔍 [诊断] 清理QBittorrent客户端资源...")
                    await self.qbt.cleanup()
                    self.logger.info("✅ [诊断] QBittorrent客户端资源已清理")
                
                # 清理缓存
                if hasattr(self, '_duplicate_cache'):
                    self._duplicate_cache.clear()
                    self.logger.info("✅ [诊断] 重复检测缓存已清理")
                
                # 清理历史记录
                if hasattr(self, 'history'):
                    self.history.clear()
                    self.logger.info("✅ [诊断] 历史记录已清理")
                
                # 等待短暂时间确保所有异步操作完成
                self.logger.info("⏳ [诊断] 等待所有异步操作完成...")
                await asyncio.sleep(0.5)
                
                self._is_cleaned_up = True
                self.logger.info("✅ [诊断] ClipboardMonitor资源清理完成")
                
            except Exception as e:
                self.logger.error(f"❌ [诊断] 清理ClipboardMonitor资源时出错: {str(e)}")
    
    def __del__(self):
        """析构函数，确保资源被清理"""
        if not self._is_cleaned_up:
            try:
                # 同步清理关键资源
                if hasattr(self, '_executor') and self._executor:
                    self._executor.shutdown(wait=False)
                
                if hasattr(self, '_duplicate_cache'):
                    self._duplicate_cache.clear()
                    
                if hasattr(self, 'history'):
                    self.history.clear()
                    
            except Exception:
                pass  # 忽略析构时的异常
    
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
        history_snapshot = list(self.history)
        recent_history = history_snapshot[-10:] if history_snapshot else []

        # 获取工作流引擎状态
        workflow_stats = {}
        if hasattr(self, 'workflow_engine') and self.workflow_engine:
            workflow_stats = self.workflow_engine.get_stats()

        return {
            'is_running': self.is_running,
            'stats': self.stats.copy(),
            'workflow_stats': workflow_stats,
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
        history_snapshot = list(self.history)
        recent_records = history_snapshot[-limit:] if limit > 0 else history_snapshot
        
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
        """高性能处理网页URL（批量爬取种子）"""
        process_start = time.time()
        
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
            
            # 使用爬虫功能批量处理（添加超时控制）
            try:
                result = await asyncio.wait_for(
                    crawl_and_add_torrents(
                        url, 
                        self.config, 
                        self.qbt, 
                        max_pages=1  # 默认只处理第一页，避免过多种子
                    ),
                    timeout=60.0  # 60秒超时
                )
            except asyncio.TimeoutError:
                raise Exception("网页处理超时（60秒）")
            
            # 记录处理时间
            process_time = time.time() - process_start
            self.stats['performance_metrics']['total_process_time'] += process_time
            
            if result['success']:
                # 更新统计信息
                stats = result['stats']['stats']
                self.stats['url_crawls'] += 1
                self.stats['total_processed'] += stats.get('torrents_found', 0)
                self.stats['successful_adds'] += stats.get('torrents_added', 0)
                self.stats['duplicates_skipped'] += stats.get('duplicates_skipped', 0)
                self.stats['failed_adds'] += stats.get('failed_adds', 0)
                
                if stats.get('torrents_added', 0) > 0:
                    self.stats['batch_adds'] += 1
                
                # 显示批量处理结果
                if self.config.notifications.console.enabled:
                    if self.notification_manager.use_colors:
                        from colorama import Fore, Style
                        print(f"\n{Fore.GREEN}✅ 批量处理完成! ({process_time:.2f}s)")
                        print(f"{Fore.CYAN}📊 处理结果:")
                        print(f"   找到种子: {Fore.WHITE}{stats.get('torrents_found', 0)}")
                        print(f"   成功添加: {Fore.GREEN}{stats.get('torrents_added', 0)}")
                        print(f"   重复跳过: {Fore.YELLOW}{stats.get('duplicates_skipped', 0)}")
                        print(f"   失败数量: {Fore.RED}{stats.get('errors', 0)}")
                        print(f"{Fore.GREEN}{'─'*50}{Style.RESET_ALL}")
                    else:
                        print(f"\n✅ 批量处理完成! ({process_time:.2f}s)")
                        print(f"📊 处理结果:")
                        print(f"   找到种子: {stats.get('torrents_found', 0)}")
                        print(f"   成功添加: {stats.get('torrents_added', 0)}")
                        print(f"   重复跳过: {stats.get('duplicates_skipped', 0)}")
                        print(f"   失败数量: {stats.get('errors', 0)}")
                        print(f"{'─'*50}")
                
                self.logger.info(f"✅ 批量处理完成: {result['message']} ({process_time:.2f}s)")
            else:
                self.stats['failed_adds'] += 1
                self.logger.error(f"❌ 批量处理失败: {result['message']} ({process_time:.2f}s)")
                
                # 显示失败信息
                if self.config.notifications.console.enabled:
                    if self.notification_manager.use_colors:
                        from colorama import Fore, Style
                        print(f"\n{Fore.RED}❌ 批量处理失败! ({process_time:.2f}s)")
                        print(f"{Fore.CYAN}错误信息: {Fore.RED}{result['message']}")
                        print(f"{Fore.RED}{'─'*50}{Style.RESET_ALL}")
                    else:
                        print(f"\n❌ 批量处理失败! ({process_time:.2f}s)")
                        print(f"错误信息: {result['message']}")
                        print(f"{'─'*50}")
                
        except Exception as e:
            process_time = time.time() - process_start
            self.stats['failed_adds'] += 1
            self.logger.error(f"❌ 处理网页URL失败: {str(e)} ({process_time:.2f}s)")
            
            # 记录错误统计
            if 'errors' not in self.stats:
                self.stats['errors'] = 0
            self.stats['errors'] += 1
            
            # 显示错误信息
            if self.config.notifications.console.enabled:
                if self.notification_manager.use_colors:
                    from colorama import Fore, Style
                    print(f"\n{Fore.RED}❌ 网页URL处理异常! ({process_time:.2f}s)")
                    print(f"{Fore.CYAN}错误详情: {Fore.RED}{str(e)}")
                    print(f"{Fore.RED}{'─'*50}{Style.RESET_ALL}")
                else:
                    print(f"\n❌ 网页URL处理异常! ({process_time:.2f}s)")
                    print(f"错误详情: {str(e)}")
                    print(f"{'─'*50}")


# ============================================================================
# 优化后的剪贴板监控器 - 支持智能自适应监控和批处理
# ============================================================================

class ActivityTracker:
    """
    智能活动跟踪器 - 优化指导文档建议

    根据剪贴板活动模式智能调整监控策略
    """

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.activity_history: deque = deque(maxlen=window_size)
        self.last_activity_time = time.time()
        self.total_activities = 0
        self.current_level = 0  # 0-10 活动级别

    def record_activity(self, has_content: bool = False):
        """记录一次活动"""
        current_time = time.time()
        is_active = has_content or self._is_recently_active(current_time)

        self.activity_history.append({
            'timestamp': current_time,
            'active': is_active
        })

        if is_active:
            self.last_activity_time = current_time
            self.total_activities += 1

        # 计算当前活动级别
        self._calculate_activity_level()

    def _is_recently_active(self, current_time: float, threshold: float = 5.0) -> bool:
        """检查最近是否活跃"""
        return (current_time - self.last_activity_time) < threshold

    def _calculate_activity_level(self):
        """计算当前活动级别 (0-10)"""
        if not self.activity_history:
            self.current_level = 0
            return

        # 计算最近1分钟的活动率
        current_time = time.time()
        recent_window = 60  # 1分钟
        active_count = 0
        total_count = 0

        for entry in reversed(self.activity_history):
            if current_time - entry['timestamp'] > recent_window:
                break
            total_count += 1
            if entry['active']:
                active_count += 1

        # 计算活动级别
        if total_count == 0:
            self.current_level = 0
        else:
            activity_rate = active_count / total_count
            self.current_level = min(10, int(activity_rate * 10))

    async def get_level(self) -> int:
        """获取当前活动级别 (0-10)"""
        return self.current_level

    def get_stats(self) -> Dict:
        """获取活动统计"""
        return {
            'total_activities': self.total_activities,
            'current_level': self.current_level,
            'window_size': len(self.activity_history),
            'is_active': self._is_recently_active(time.time())
        }


class SmartBatcher:
    """
    智能批处理器 - 优化指导文档建议

    根据内容类型和系统负载智能调整批处理策略
    """

    def __init__(self, max_size: int = 10, timeout: float = 0.5):
        self.max_size = max_size
        self.timeout = timeout
        self.batch_queue = asyncio.Queue(maxsize=100)
        self.processor: Optional[any] = None  # 类型会在运行时设置
        self.stats = {
            'batches_processed': 0,
            'items_processed': 0,
            'avg_batch_size': 0.0,
            'queue_pressure': 0.0
        }

    def set_processor(self, processor):
        """设置批处理器"""
        self.processor = processor

    async def add_to_batch(self, item: Dict):
        """添加项目到批次"""
        try:
            # 非阻塞式添加
            self.batch_queue.put_nowait(item)
        except asyncio.QueueFull:
            # 队列满时，立即处理当前批次
            self.logger.warning("批次队列已满，立即处理当前批次")
            await self._process_batch()

        # 动态调整批次大小
        await self._adjust_batch_size()

    async def _process_batch(self):
        """处理当前批次"""
        if self.processor is None:
            self.logger.error("批处理器未设置")
            return

        items = []
        batch_start_time = time.time()

        # 收集批次项目
        try:
            # 立即获取第一个项目
            first_item = await asyncio.wait_for(self.batch_queue.get(), timeout=0.1)
            items.append(first_item)

            # 尝试获取更多项目 (直到达到批次大小或超时)
            while len(items) < self.max_size:
                try:
                    item = await asyncio.wait_for(
                        self.batch_queue.get(),
                        timeout=self.timeout
                    )
                    items.append(item)
                except asyncio.TimeoutError:
                    break

        except Exception as e:
            self.logger.error(f"收集批次项目时出错: {str(e)}")
            return

        if not items:
            return

        # 记录统计
        self.stats['batches_processed'] += 1
        self.stats['items_processed'] += len(items)

        # 计算平均批次大小
        total_items = self.stats['items_processed']
        total_batches = self.stats['batches_processed']
        self.stats['avg_batch_size'] = total_items / total_batches

        # 处理批次
        try:
            await self.processor.process_batch(items, batch_start_time)
            self.logger.debug(
                f"批次处理完成: {len(items)} 个项目 "
                f"(用时: {time.time() - batch_start_time:.3f}s)"
            )
        except Exception as e:
            self.logger.error(f"批次处理失败: {str(e)}")

    async def _adjust_batch_size(self):
        """动态调整批次大小"""
        current_size = self.batch_queue.qsize()
        queue_pressure = current_size / self.batch_queue.maxsize

        # 记录队列压力
        self.stats['queue_pressure'] = queue_pressure

        # 根据队列压力调整批次大小
        if queue_pressure > 0.8:
            # 高压力：增加批次大小以提高吞吐量
            self.max_size = min(20, self.max_size + 1)
        elif queue_pressure < 0.2:
            # 低压力：减少批次大小以提高响应速度
            self.max_size = max(5, self.max_size - 1)

    def get_stats(self) -> Dict:
        """获取批处理统计"""
        return {
            **self.stats,
            'current_queue_size': self.batch_queue.qsize(),
            'current_batch_size': self.max_size,
            'timeout': self.timeout
        }


class OptimizedClipboardMonitor(ClipboardMonitor):
    """
    优化版剪贴板监控器 - 继承自原监控器

    新增功能:
    1. 智能自适应监控 (ActivityTracker)
    2. 智能批处理 (SmartBatcher)
    3. 动态性能调优
    4. 高级统计
    """

    def __init__(self, qbt: QBittorrentClient, config: AppConfig):
        super().__init__(qbt, config)
        self.logger = logging.getLogger('OptimizedClipboardMonitor')

        # 初始化智能活动跟踪器
        self.activity_tracker = ActivityTracker(window_size=100)

        # 初始化智能批处理器
        self.smart_batcher = SmartBatcher(
            max_size=getattr(config, 'batch_size', 10),
            timeout=getattr(config, 'batch_timeout', 0.5)
        )
        self.smart_batcher.set_processor(self)

        # 高级性能统计
        self.advanced_stats = {
            'activity_levels': deque(maxlen=100),
            'batch_sizes': deque(maxlen=100),
            'processing_latency': deque(maxlen=100),
            'adaptive_adjustments': 0,
            'cpu_saved_percent': 0.0
        }

    async def _on_clipboard_change_optimized(self, text: str):
        """优化的剪贴板变化处理"""
        # 记录活动
        has_content = bool(text and text.strip())
        self.activity_tracker.record_activity(has_content)

        # 动态调整轮询间隔
        await self._adjust_monitoring_interval()

        # 智能批处理
        if has_content:
            content_item = {
                'text': text,
                'timestamp': time.time(),
                'source': 'clipboard'
            }
            await self.smart_batcher.add_to_batch(content_item)

    async def _adjust_monitoring_interval(self):
        """根据活动级别动态调整监控间隔"""
        activity_level = await self.activity_tracker.get_level()

        # 计算目标间隔
        if activity_level >= 8:
            # 高活跃度：使用最小间隔
            target_interval = self._max_interval * 0.1
        elif activity_level >= 5:
            # 中等活跃度：使用基础间隔
            target_interval = self._base_interval
        elif activity_level >= 2:
            # 低活跃度：增加间隔
            target_interval = self._base_interval * 2
        else:
            # 无活跃：使用最大间隔
            target_interval = self._max_interval

        # 平滑调整间隔
        if hasattr(self.poller, 'current_interval'):
            current = self.poller.current_interval
            # 使用指数移动平均进行平滑调整
            smooth_factor = 0.1
            new_interval = current * (1 - smooth_factor) + target_interval * smooth_factor

            # 限制在合理范围内
            new_interval = max(
                self.poller.config.min_interval,
                min(new_interval, self.poller.config.max_interval)
            )

            if abs(new_interval - current) > 0.01:  # 只有变化显著时才调整
                self.poller.current_interval = new_interval
                self.advanced_stats['adaptive_adjustments'] += 1

        # 记录活动级别
        self.advanced_stats['activity_levels'].append(activity_level)

    async def process_batch(self, items: List[Dict], batch_start_time: float):
        """处理批次内容"""
        if not items:
            return

        start_time = batch_start_time or time.time()
        results = {
            'total': len(items),
            'successful': 0,
            'failed': 0,
            'duplicates': 0
        }

        # 并发处理批次中的所有项目
        tasks = []
        for item in items:
            task = asyncio.create_task(self._process_single_item(item))
            tasks.append(task)

        # 等待所有任务完成
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        for result in batch_results:
            if isinstance(result, Exception):
                results['failed'] += 1
                self.logger.error(f"批次项目处理失败: {str(result)}")
            elif result == 'duplicate':
                results['duplicates'] += 1
            elif result == 'success':
                results['successful'] += 1

        # 更新统计
        batch_size = len(items)
        self.advanced_stats['batch_sizes'].append(batch_size)
        self.advanced_stats['processing_latency'].append(time.time() - start_time)

        self.logger.info(
            f"批次处理完成: {results['successful']}/{results['total']} 成功, "
            f"{results['duplicates']} 重复, {results['failed']} 失败 "
            f"(用时: {time.time() - start_time:.3f}s)"
        )

        # 计算CPU节省
        await self._calculate_cpu_savings()

    async def _process_single_item(self, item: Dict) -> str:
        """处理单个项目"""
        try:
            text = item.get('text', '')
            if not text:
                return 'failed'

            # 调用原有的处理逻辑
            await self._on_clipboard_change(text)
            return 'success'
        except Exception as e:
            self.logger.error(f"处理项目时出错: {str(e)}")
            return 'failed'

    async def _calculate_cpu_savings(self):
        """计算CPU使用节省"""
        # 基于自适应间隔计算CPU节省
        if self.advanced_stats['activity_levels']:
            recent_levels = list(self.advanced_stats['activity_levels'])[-10:]
            avg_level = sum(recent_levels) / len(recent_levels)

            # 估算CPU节省百分比
            if avg_level < 3:
                # 低活跃度：节省更多CPU
                cpu_saved = 70
            elif avg_level < 6:
                # 中等活跃度：节省一些CPU
                cpu_saved = 40
            else:
                # 高活跃度：节省少量CPU
                cpu_saved = 10

            # 平滑更新
            current_saved = self.advanced_stats['cpu_saved_percent']
            self.advanced_stats['cpu_saved_percent'] = current_saved * 0.9 + cpu_saved * 0.1

    def get_advanced_stats(self) -> Dict:
        """获取高级统计信息"""
        stats = self.advanced_stats.copy()

        # 计算平均值
        if self.advanced_stats['activity_levels']:
            stats['avg_activity_level'] = sum(self.advanced_stats['activity_levels']) / len(
                self.advanced_stats['activity_levels']
            )
        else:
            stats['avg_activity_level'] = 0

        if self.advanced_stats['batch_sizes']:
            stats['avg_batch_size'] = sum(self.advanced_stats['batch_sizes']) / len(
                self.advanced_stats['batch_sizes']
            )
        else:
            stats['avg_batch_size'] = 0

        if self.advanced_stats['processing_latency']:
            stats['avg_processing_latency'] = sum(
                self.advanced_stats['processing_latency']
            ) / len(self.advanced_stats['processing_latency'])
        else:
            stats['avg_processing_latency'] = 0

        # 添加智能批处理器统计
        stats['smart_batcher'] = self.smart_batcher.get_stats()

        # 添加活动跟踪器统计
        stats['activity_tracker'] = self.activity_tracker.get_stats()

        return stats

    async def start(self):
        """启动优化版监控器"""
        self.logger.info("🚀 启动优化版剪贴板监控器 (智能自适应 + 批处理)")

        # 记录启动时间
        self.start_time = time.time()

        # 覆盖原有的变化处理方法
        original_on_change = self._on_clipboard_change
        self._on_clipboard_change = self._on_clipboard_change_optimized

        try:
            # 启动父类监控
            await super().start()
        finally:
            # 恢复原有方法
            self._on_clipboard_change = original_on_change
