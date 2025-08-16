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
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set
import pyperclip
from concurrent.futures import ThreadPoolExecutor

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
        
        # 剪贴板状态管理
        self.last_clip = ""
        self.last_clip_hash = 0  # 用于快速比较
        self.clipboard_lock = asyncio.Lock()
        
        # 线程池用于同步操作
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="clipboard")
        
        # 磁力链接正则模式（编译一次，重复使用）
        self.magnet_pattern = re.compile(
            r"^magnet:\?xt=urn:btih:[0-9a-fA-F]{40,}.*",
            re.IGNORECASE
        )
        
        # XXXClub URL正则模式
        self.xxxclub_pattern = re.compile(
            r"https?://(?:www\.)?xxxclub\.to/torrents/search/.*",
            re.IGNORECASE
        )
        
        # 通用URL正则模式
        self.url_pattern = re.compile(
            r"https?://[^\s]+",
            re.IGNORECASE
        )
        
        # 初始化AI分类器
        self.ai_classifier = AIClassifier(config.deepseek)
        
        # 初始化通知管理器
        self.notification_manager = NotificationManager(config.notifications.model_dump())
        
        # 处理历史记录（使用deque提升性能）
        self.history: deque = deque(maxlen=1000)  # 自动限制大小
        
        # 重复检测缓存（LRU缓存，防止内存泄漏）
        self._duplicate_cache: Set[str] = set()
        self._cache_cleanup_time = datetime.now()
        self._max_cache_size = 10000
        
        # 动态轮询间隔
        self._base_interval = max(0.5, min(config.check_interval, 5.0))  # 限制在0.5-5秒
        self._current_interval = self._base_interval
        self._idle_count = 0
        self._max_interval = self._base_interval * 4  # 最大间隔
        
        # 统计信息
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
        
        # 监控状态
        self.is_running = False
        self.last_error_time: Optional[datetime] = None
        self.consecutive_errors = 0
        self.last_stats_report = datetime.now()
        
        # 性能监控
        self._process_times: deque = deque(maxlen=100)  # 保存最近100次处理时间
        
        # 清理状态标志
        self._is_cleaned_up = False
        self._cleanup_lock = asyncio.Lock()
        
    async def start(self):
        """启动剪贴板监控循环"""
        self.is_running = True
        self.logger.info("开始监控剪贴板...")
        
        # 欢迎消息
        self._show_welcome_message()
        
        try:
            while self.is_running:
                cycle_start = time.time()
                
                await self._monitor_cycle()
                
                # 记录处理时间
                cycle_time = time.time() - cycle_start
                self._process_times.append(cycle_time)
                
                # 更新性能指标
                self._update_performance_metrics(cycle_time)
                
                # 动态调整轮询间隔
                await asyncio.sleep(self._current_interval)
                
        except asyncio.CancelledError:
            self.logger.info("监控已取消")
            raise
        except Exception as e:
            self.logger.error(f"监控异常: {str(e)}")
            await self._handle_monitor_error(e)
            raise
        finally:
            self.is_running = False
            # 清理资源
            await self.cleanup()
            self.logger.info("剪贴板监控已停止")
            self._show_farewell_message()
    
    def stop(self):
        """停止监控"""
        self.is_running = False
    
    async def _monitor_cycle(self):
        """高性能单次监控循环"""
        try:
            # 异步获取剪贴板内容
            current_clip = await self._get_clipboard_async()
            self.stats['clipboard_reads'] += 1
            
            # 快速哈希比较，避免字符串比较开销
            current_hash = hash(current_clip) if current_clip else 0
            
            if current_hash == self.last_clip_hash:
                # 内容未变化，增加空闲计数
                self._idle_count += 1
                self._adjust_polling_interval()
                return
            
            # 内容发生变化，重置空闲计数
            self._idle_count = 0
            self._current_interval = self._base_interval
            
            if not current_clip or not current_clip.strip():
                self.last_clip = current_clip
                self.last_clip_hash = current_hash
                return
            
            content = current_clip.strip()
            
            # 检查是否为磁力链接
            if self.magnet_pattern.match(content):
                self.last_clip = current_clip
                self.last_clip_hash = current_hash
                await self._process_magnet(content)
                
            # 检查是否为网页URL
            elif (self.xxxclub_pattern.match(content) or 
                  self.url_pattern.match(content)):
                self.last_clip = current_clip
                self.last_clip_hash = current_hash
                await self._process_url(content)
            
            else:
                # 更新剪贴板状态但不处理
                self.last_clip = current_clip
                self.last_clip_hash = current_hash
            
            # 重置错误计数
            self.consecutive_errors = 0
            self.last_error_time = None
            
            # 定期清理缓存和报告统计
            await self._periodic_maintenance()
                
        except Exception as e:
            self.consecutive_errors += 1
            self.last_error_time = datetime.now()
            
            if self.consecutive_errors <= 3:
                self.logger.warning(f"监控循环错误 ({self.consecutive_errors}/3): {str(e)}")
            else:
                self.logger.error(f"连续监控错误过多，可能需要重启: {str(e)}")
                await self._handle_monitor_error(e)
    
    async def _process_magnet(self, magnet_link: str):
        """高性能处理磁力链接"""
        process_start = time.time()
        
        self.logger.info(f"🔍 发现新磁力链接: {magnet_link[:60]}...")
        
        # 验证磁力链接格式
        if not validate_magnet_link(magnet_link):
            self.logger.error("❌ 无效的磁力链接格式")
            self.stats['failed_adds'] += 1
            return
        
        try:
            # 解析磁力链接获取详细信息
            torrent_hash, torrent_name = parse_magnet(magnet_link)
            if not torrent_hash:
                raise TorrentParseError("无法解析磁力链接哈希值")
            
            # 检查是否重复（使用哈希值检查）
            if await self.qbt._is_duplicate(torrent_hash):
                self.logger.info(f"⚠️ 跳过重复种子: {torrent_hash[:8]}")
                self.stats['duplicates_skipped'] += 1
                return
            
            # 如果磁力链接没有dn参数（显示名），先添加种子再获取真实名称
            temp_added = False
            if not torrent_name:
                self.logger.info("📥 磁力链接缺少文件名，先添加种子以获取真实名称...")
                
                # 使用临时分类先添加种子
                temp_success = await self.qbt.add_torrent(magnet_link, "other")
                if not temp_success:
                    self.logger.error("❌ 添加种子失败")
                    self.stats['failed_adds'] += 1
                    return
                
                temp_added = True
                
                # 等待一段时间让qBittorrent处理种子
                await asyncio.sleep(2)
                
                # 获取种子的真实名称
                try:
                    torrent_info = await self.qbt.get_torrent_properties(torrent_hash)
                    if 'name' in torrent_info and torrent_info['name']:
                        torrent_name = torrent_info['name']
                        self.logger.info(f"📁 获取到真实文件名: {torrent_name}")
                    else:
                        torrent_name = f"未命名_{torrent_hash[:8]}"
                        self.logger.warning(f"⚠️ 无法获取真实文件名，使用: {torrent_name}")
                except Exception as e:
                    torrent_name = f"未命名_{torrent_hash[:8]}"
                    self.logger.warning(f"⚠️ 获取种子信息失败: {str(e)}，使用: {torrent_name}")
            
            # 创建记录
            record = TorrentRecord(magnet_link, torrent_hash, torrent_name)
            self._add_to_history(record)
            self.stats['total_processed'] += 1
            
            self.logger.info(f"📁 处理种子: {record.torrent_name}")
            
            # AI分类（使用真实的种子名称）
            try:
                category = await asyncio.wait_for(
                    self._classify_torrent(record), 
                    timeout=10.0
                )
                record.category = category
            except asyncio.TimeoutError:
                self.logger.warning("AI分类超时，使用默认分类")
                record.category = "other"
            except Exception as e:
                self.logger.warning(f"分类失败: {str(e)}，使用默认分类")
                record.category = "other"
            
            # 获取保存路径
            save_path = await self._get_save_path(record.category)
            record.save_path = save_path
            
            # 如果之前临时添加了种子，现在需要更新分类
            if temp_added:
                self.logger.info(f"🔄 更新种子分类: {record.category}")
                # 更新种子分类
                if record.category != "other":
                    try:
                        url = f"{self.qbt._base_url}/api/v2/torrents/setCategory"
                        data = {
                            'hashes': torrent_hash,
                            'category': record.category
                        }
                        async with self.qbt.session.post(url, data=data) as resp:
                            if resp.status == 200:
                                self.logger.info(f"✅ 种子分类已更新: {record.category}")
                            else:
                                self.logger.warning(f"⚠️ 更新分类失败: HTTP {resp.status}")
                    except Exception as e:
                        self.logger.warning(f"⚠️ 更新分类异常: {str(e)}")
                
                record.status = "success"
            else:
                # 正常添加种子（磁力链接有完整名称）
                success = await self._add_torrent_to_client(record)
                if not success:
                    return
            
            # 记录处理时间
            process_time = time.time() - process_start
            self.stats['performance_metrics']['total_process_time'] += process_time
            
            # 发送通知
            await self._send_success_notification(record)
            
            self.stats['successful_adds'] += 1
            self.logger.info(f"✅ 成功添加种子: {record.torrent_name} -> {record.category} ({process_time:.2f}s)")
            
        except Exception as e:
            process_time = time.time() - process_start
            self.logger.error(f"❌ 处理磁力链接失败: {str(e)} ({process_time:.2f}s)")
            self.stats['failed_adds'] += 1
            
            # 记录错误统计
            if 'errors' not in self.stats:
                self.stats['errors'] = 0
            self.stats['errors'] += 1
    
    async def _send_success_notification(self, record: TorrentRecord):
        """发送成功通知"""
        try:
            await self.notification_manager.send_torrent_success(
                record.torrent_name,
                record.category,
                record.save_path or "默认路径",
                record.torrent_hash,
                record.classification_method or "AI"
            )
        except Exception as e:
            self.logger.warning(f"发送通知失败: {str(e)}")
    
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
    

    
    async def _add_torrent_to_client(self, record: TorrentRecord) -> bool:
        """将种子添加到qBittorrent客户端"""
        try:
            # 准备要传递给客户端的额外参数
            torrent_params = {
                'paused': self.config.add_torrents_paused
            }
            # 只有在提供了明确的重命名时才添加rename参数
            if record.torrent_name:
                torrent_params['rename'] = record.torrent_name

            # 添加种子
            success = await self.qbt.add_torrent(
                record.magnet_link,
                record.category or "other",
                **torrent_params
            )
            
            if not success:
                # 如果初始添加不成功（例如，因为哈希已经存在），则返回False
                record.error_message = "添加到客户端失败"
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"添加种子到qBittorrent时出错: {str(e)}")
            record.error_message = f"客户端错误: {str(e)}"
            return False
    
    async def _get_clipboard_async(self) -> str:
        """异步获取剪贴板内容"""
        loop = asyncio.get_event_loop()
        try:
            # 使用线程池执行同步的剪贴板操作
            return await loop.run_in_executor(self._executor, pyperclip.paste)
        except Exception as e:
            self.logger.warning(f"剪贴板访问失败: {e}")
            return ""
    
    def _adjust_polling_interval(self):
        """动态调整轮询间隔"""
        if self._idle_count < 10:
            # 前10次空闲保持基础间隔
            self._current_interval = self._base_interval
        elif self._idle_count < 50:
            # 11-50次空闲，逐渐增加间隔
            self._current_interval = min(self._base_interval * 2, self._max_interval)
        else:
            # 50次以上空闲，使用最大间隔
            self._current_interval = self._max_interval
    
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
                "🚀 qBittorrent增强剪贴板监控已启动! (高性能版)",
                f"📋 基础监控间隔: {self._base_interval}秒 (动态调整: {self._base_interval}-{self._max_interval}秒)",
                f"🧠 AI分类器: {'已启用' if hasattr(self.ai_classifier, 'client') and self.ai_classifier.client else '使用规则引擎'}",
                f"🔔 通知系统: {'已启用' if self.config.notifications.enabled else '已禁用'}",
                f"⚡ 性能优化: 异步剪贴板访问、智能轮询、内存管理",
                "💡 支持的内容类型:",
                "   🔗 磁力链接 (magnet:) - 自动分类添加",
                "   🌐 网页URL (http/https) - 爬取页面内磁力链接",
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
                
                # 关闭线程池
                if hasattr(self, '_executor') and self._executor:
                    self.logger.info("🔍 [诊断] 关闭线程池...")
                    self._executor.shutdown(wait=True)
                    self.logger.info("✅ [诊断] 线程池已关闭")
                
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