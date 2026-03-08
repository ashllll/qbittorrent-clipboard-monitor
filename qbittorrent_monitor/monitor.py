"""剪贴板监控器 - 安全增强版（使用 watchers 模块）

此版本使用 watchers 模块的组件重构，同时保持向后兼容。
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional, Set, Callable, Dict, List, OrderedDict as OrderedDictType
from datetime import datetime
from collections import OrderedDict
from dataclasses import dataclass, field

import pyperclip

from .config import Config
from .qb_client import QBClient
from .classifier import ContentClassifier
from .utils import parse_magnet, extract_magnet_hash, get_magnet_display_name
from .security import validate_magnet, sanitize_magnet, SAFE_LIMITS
from . import metrics as metrics_module
from .database import DatabaseManager, extract_magnet_hash as db_extract_magnet_hash

# 导入新的 watchers 模块
from .watchers import (
    DebounceFilter,
    RateLimiter,
    ClipboardWatcher,
    ClipboardCache,
)
from .watchers.clipboard_watcher import ClipboardEvent

# 导入 UI 组件（可选依赖）
try:
    from .cli_ui import (
        print_startup_info, 
        print_success, 
        print_warning, 
        SpinnerStatus,
        StyledOutput
    )
    CLI_UI_AVAILABLE = True
except ImportError:
    CLI_UI_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MonitorStats:
    """统计信息 - 增强版，添加性能监控"""
    total_processed: int = 0
    successful_adds: int = 0
    failed_adds: int = 0
    duplicates_skipped: int = 0
    invalid_magnets: int = 0
    start_time: Optional[datetime] = None
    
    # 性能监控统计
    checks_performed: int = 0
    clipboard_changes: int = 0
    hash_cache_hits: int = 0
    avg_check_time_ms: float = 0.0
    _check_times: List[float] = field(default_factory=list)
    
    @property
    def uptime_seconds(self) -> float:
        if self.start_time:
            return (datetime.now() - self.start_time).total_seconds()
        return 0.0
    
    @property
    def checks_per_minute(self) -> float:
        uptime = self.uptime_seconds
        if uptime > 0:
            return (self.checks_performed / uptime) * 60
        return 0.0
    
    def record_check_time(self, duration_ms: float) -> None:
        """记录单次检查耗时"""
        self._check_times.append(duration_ms)
        # 保持最近100次
        if len(self._check_times) > 100:
            self._check_times = self._check_times[-100:]
        self.avg_check_time_ms = sum(self._check_times) / len(self._check_times)
    
    def to_dict(self) -> Dict:
        """导出统计信息为字典"""
        return {
            "uptime_seconds": self.uptime_seconds,
            "total_processed": self.total_processed,
            "successful_adds": self.successful_adds,
            "failed_adds": self.failed_adds,
            "duplicates_skipped": self.duplicates_skipped,
            "invalid_magnets": self.invalid_magnets,
            "checks_performed": self.checks_performed,
            "clipboard_changes": self.clipboard_changes,
            "hash_cache_hits": self.hash_cache_hits,
            "checks_per_minute": round(self.checks_per_minute, 2),
            "avg_check_time_ms": round(self.avg_check_time_ms, 3),
        }


@dataclass
class PacingConfig:
    """智能轮询配置"""
    active_interval: float = 0.5
    idle_interval: float = 3.0
    idle_threshold_seconds: float = 30.0
    burst_window_seconds: float = 5.0
    burst_threshold: int = 3


# 保持旧的类名以兼容
ClipboardCache = ClipboardCache


class MagnetExtractor:
    """优化的磁力链接提取器 - 安全增强版"""
    
    # 预编译正则表达式 - 性能优化
    MAGNET_PATTERN = re.compile(
        r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{32,40}',
        re.IGNORECASE
    )
    BTIH_PATTERN = re.compile(r'btih:([a-fA-F0-9]{40}|[a-z2-7]{32})', re.IGNORECASE)
    
    MIN_MAGNET_LENGTH = 50
    MAX_MAGNET_LENGTH = SAFE_LIMITS['max_magnet_length']
    
    @classmethod
    def extract(cls, content: str) -> List[str]:
        """从内容中提取所有磁力链接 - 安全优化版本"""
        # 长度检查
        if not content or len(content) < cls.MIN_MAGNET_LENGTH:
            return []
        
        # 长度限制（防止DoS）
        if len(content) > cls.MAX_MAGNET_LENGTH * 10:
            logger.warning(f"剪贴板内容过长 ({len(content)} 字符)，可能被截断")
            content = content[:cls.MAX_MAGNET_LENGTH * 10]
        
        # 快速检查是否包含 magnet: 前缀
        if 'magnet:?' not in content:
            if content.startswith('magnet:?'):
                return cls._validate_and_return(content)
            return []
        
        # 使用预编译正则快速匹配
        magnets = cls.MAGNET_PATTERN.findall(content)
        
        # 去重并保持顺序，同时验证每个磁力链接
        seen = set()
        unique_magnets = []
        for m in magnets:
            m = sanitize_magnet(m)
            
            is_valid, error = validate_magnet(m)
            if not is_valid:
                logger.debug(f"跳过无效的磁力链接: {error}")
                continue
            
            magnet_hash = cls._extract_hash(m)
            if magnet_hash and magnet_hash not in seen:
                seen.add(magnet_hash)
                unique_magnets.append(m)
        
        return unique_magnets
    
    @classmethod
    def _validate_and_return(cls, content: str) -> List[str]:
        """验证并返回单个磁力链接"""
        content = sanitize_magnet(content)
        is_valid, error = validate_magnet(content)
        if is_valid:
            return [content]
        return []
    
    @classmethod
    def _is_valid_magnet(cls, content: str) -> bool:
        """快速验证磁力链接有效性"""
        return cls.BTIH_PATTERN.search(content) is not None
    
    @classmethod
    def _extract_hash(cls, magnet: str) -> Optional[str]:
        """提取磁力链接的 hash"""
        match = cls.BTIH_PATTERN.search(magnet)
        return match.group(1).lower() if match else None


class ClipboardMonitor:
    """剪贴板监控器 - 安全增强版（重构后）
    
    使用 watchers 模块的组件实现：
    - DebounceFilter: 防抖过滤器
    - RateLimiter: 速率限制器
    - ClipboardCache: 内容缓存
    """
    
    def __init__(
        self, 
        qb_client: QBClient, 
        config: Config, 
        classifier: Optional[ContentClassifier] = None,
        pacing_config: Optional[PacingConfig] = None,
        database: Optional[DatabaseManager] = None,
    ):
        self.qb = qb_client
        self.config = config
        self.classifier = classifier or ContentClassifier(config)
        self.pacing = pacing_config or PacingConfig()
        
        # 数据库管理器
        self._db: Optional[DatabaseManager] = None
        self._db_enabled = config.database.enabled if hasattr(config, 'database') else False
        self._db_path = config.database.db_path if hasattr(config, 'database') else None
        
        # 统计信息
        self.stats = MonitorStats()
        
        # 使用新的 watchers 组件
        self._cache = ClipboardCache()
        self._debounce_filter = DebounceFilter(debounce_seconds=2.0)
        self._rate_limiter = RateLimiter(max_per_second=10.0, burst_size=5)
        
        # 已处理缓存（LRU）
        self._processed: OrderedDictType[str, None] = OrderedDict()
        self._max_processed_size = 10000
        
        self._handlers: List[Callable[[str, str], None]] = []
        
        # 运行状态
        self._running = False
        self._last_content: str = ""
        self._last_content_hash: str = ""
        self._last_change_time: float = 0.0
        self._change_count_in_window: int = 0
        self._window_start_time: float = 0.0
        
        # 外部传入的数据库管理器
        self._external_db = database
        
        # 速率限制
        self._max_magnets_per_check = 100
    
    def add_handler(self, handler: Callable[[str, str], None]) -> None:
        """添加处理回调 - 保持向后兼容"""
        self._handlers.append(handler)
    
    def remove_handler(self, handler: Callable[[str, str], None]) -> None:
        """移除处理回调"""
        if handler in self._handlers:
            self._handlers.remove(handler)
    
    def get_stats(self) -> Dict:
        """获取性能统计 - 新增 API"""
        stats = self.stats.to_dict()
        # 添加 watchers 统计
        stats["debounce"] = self._debounce_filter.get_stats()
        stats["rate_limiter"] = self._rate_limiter.get_stats()
        stats["cache"] = self._cache.get_stats()
        return stats
    
    async def get_database(self) -> Optional[DatabaseManager]:
        """获取数据库管理器实例"""
        if not self._db_enabled:
            return None
        
        if self._external_db:
            return self._external_db
        
        if self._db is None:
            self._db = DatabaseManager(self._db_path)
            await self._db.initialize()
            
            await self._db.log_event(
                "info", 
                "剪贴板监控器启动",
                {"check_interval": self.config.check_interval}
            )
        
        return self._db
    
    async def query_history(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """查询历史记录"""
        db = await self.get_database()
        if not db:
            return []
        
        # 使用新的 Repository 接口
        from .repository import TorrentRepository
        repo = TorrentRepository(db._connection)
        records = await repo.find(
            category=category,
            status=status,
            limit=limit,
            offset=offset,
        )
        return [r.to_dict() for r in records]
    
    async def get_db_stats(self) -> Dict:
        """获取数据库统计信息"""
        db = await self.get_database()
        if not db:
            return {"enabled": False}
        
        from .repository import StatsRepository
        repo = StatsRepository(db._connection)
        stats = await repo.get_overall_stats()
        category_stats = await repo.get_category_stats()
        
        return {
            "enabled": True,
            "overall": stats,
            "categories": [s.to_dict() for s in category_stats],
        }
    
    async def export_data(
        self,
        output_path: str,
        format: Optional[str] = None,
    ) -> int:
        """导出数据"""
        db = await self.get_database()
        if not db:
            logger.warning("数据持久化未启用，无法导出")
            return 0
        
        fmt = format or self.config.database.export_format
        
        if fmt == "csv":
            return await db.export_to_csv(output_path)
        else:
            return await db.export_to_json(output_path)
    
    async def cleanup_old_data(self, days: Optional[int] = None, dry_run: bool = False) -> Dict:
        """清理旧数据"""
        db = await self.get_database()
        if not db:
            return {"enabled": False}
        
        cleanup_days = days or self.config.database.auto_cleanup_days
        if cleanup_days <= 0:
            return {"enabled": True, "message": "自动清理未启用"}
        
        return await db.cleanup_old_records(cleanup_days, dry_run)
    
    def clear_cache(self) -> None:
        """清空剪贴板缓存"""
        self._cache.clear()
        self._debounce_filter.clear()
        logger.info("剪贴板缓存已清空")
    
    async def start(self) -> None:
        """启动监控 - 优化版，支持智能轮询（UI 增强）"""
        # 初始化数据库（如果启用）
        if self._db_enabled and not self._external_db:
            try:
                if CLI_UI_AVAILABLE:
                    with SpinnerStatus("正在初始化数据库..."):
                        await self.get_database()
                    print_success("数据持久化已启用")
                else:
                    await self.get_database()
                    logger.info("数据持久化已启用")
            except Exception as e:
                if CLI_UI_AVAILABLE:
                    print_warning(f"数据库初始化失败: {e}")
                else:
                    logger.warning(f"数据库初始化失败: {e}")
                self._db_enabled = False
        
        self._running = True
        self.stats.start_time = datetime.now()
        self._window_start_time = datetime.now().timestamp()
        
        # 记录监控状态指标
        metrics_module.set_monitor_running(True)
        metrics_module.set_clipboard_check_interval(self.pacing.active_interval)
        
        # 使用新的 UI 显示启动信息
        if CLI_UI_AVAILABLE:
            config_info = {
                "host": f"{self.config.qbittorrent.host}:{self.config.qbittorrent.port}",
                "ai_enabled": self.config.ai.enabled if hasattr(self.config, 'ai') else False,
                "database_enabled": self._db_enabled,
                "database_path": self._db_path if self._db_enabled else None,
                "check_interval": self.pacing.active_interval,
                "metrics_enabled": self.config.metrics.enabled if hasattr(self.config, 'metrics') else False,
                "metrics_host": getattr(self.config.metrics, 'host', None) if hasattr(self.config, 'metrics') else None,
                "metrics_port": getattr(self.config.metrics, 'port', None) if hasattr(self.config, 'metrics') else None,
            }
            print_startup_info(config_info)
        else:
            # Fallback: 标准文本输出
            print("=" * 50)
            print("剪贴板监控已启动 (重构版)")
            print(f"活跃检查间隔: {self.pacing.active_interval}秒")
            print(f"空闲检查间隔: {self.pacing.idle_interval}秒")
            print(f"防抖窗口: {self._debounce_filter.debounce_seconds}秒")
            print(f"最大磁力链接长度: {SAFE_LIMITS['max_magnet_length']} 字符")
            print("按 Ctrl+C 停止")
            print("=" * 50)
        
        try:
            while self._running:
                check_start = datetime.now().timestamp()
                
                with metrics_module.timed_clipboard_check():
                    await self._check_clipboard()
                
                # 更新指标
                self._update_metrics()
                
                check_duration = (datetime.now().timestamp() - check_start) * 1000
                self.stats.record_check_time(check_duration)
                
                # 智能轮询间隔计算
                interval = self._calculate_interval()
                metrics_module.set_clipboard_check_interval(interval)
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.info("监控已取消")
        finally:
            self._running = False
            metrics_module.set_monitor_running(False)
            # 关闭数据库连接
            if self._db and not self._external_db:
                try:
                    await self._db.close()
                    self._db = None
                except Exception as e:
                    logger.warning(f"关闭数据库连接失败: {e}")
    
    def stop(self) -> None:
        """停止监控"""
        self._running = False
    
    def _calculate_interval(self) -> float:
        """计算智能轮询间隔"""
        now = datetime.now().timestamp()
        time_since_last_change = now - self._last_change_time
        
        # 如果在突发窗口内有多次变化，使用活跃间隔
        if self._change_count_in_window >= self.pacing.burst_threshold:
            return self.pacing.active_interval
        
        # 如果窗口过期，重置计数
        if now - self._window_start_time > self.pacing.burst_window_seconds:
            self._change_count_in_window = 0
            self._window_start_time = now
        
        # 根据空闲状态选择间隔
        if time_since_last_change > self.pacing.idle_threshold_seconds:
            return self.pacing.idle_interval
        
        return self.pacing.active_interval
    
    async def _check_clipboard(self) -> None:
        """检查剪贴板 - 使用 watchers 组件"""
        self.stats.checks_performed += 1
        
        try:
            # 异步读取剪贴板
            loop = asyncio.get_event_loop()
            current = await asyncio.wait_for(
                loop.run_in_executor(None, pyperclip.paste),
                timeout=0.5
            )
            
            if not current:
                return
            
            if current == self._last_content:
                return
            
            # 计算内容哈希
            import hashlib
            content_hash = hashlib.md5(current.encode('utf-8')).hexdigest()
            
            if content_hash == self._last_content_hash:
                self._last_content = current
                return
            
            # 更新状态
            self._last_content = current
            self._last_content_hash = content_hash
            self._update_activity_tracking()
            self.stats.clipboard_changes += 1
            
            metrics_module.record_clipboard_change()
            
            # 检查缓存
            cached_result = self._cache.get(current)
            if cached_result is not None:
                self.stats.hash_cache_hits += 1
                logger.debug("剪贴板内容命中缓存，跳过处理")
                return
            
            # 处理内容
            await self._process_content(current)
            
        except Exception as e:
            logger.error(f"检查剪贴板失败: {e}")
    
    def _update_activity_tracking(self) -> None:
        """更新活动追踪状态"""
        now = datetime.now().timestamp()
        
        self._last_change_time = now
        
        if now - self._window_start_time <= self.pacing.burst_window_seconds:
            self._change_count_in_window += 1
        else:
            self._change_count_in_window = 1
            self._window_start_time = now
    
    async def _process_content(self, content: str) -> None:
        """处理剪贴板内容"""
        # 使用优化的磁力链接提取
        magnets = MagnetExtractor.extract(content)
        
        if not magnets:
            # 缓存空结果
            self._cache.put(content, "")
            return
        
        # 速率限制检查
        if len(magnets) > self._max_magnets_per_check:
            logger.warning(
                f"检测到过多磁力链接 ({len(magnets)} > {self._max_magnets_per_check})，"
                f"可能存在滥用风险，仅处理前 {self._max_magnets_per_check} 个"
            )
            magnets = magnets[:self._max_magnets_per_check]
        
        # 缓存提取结果
        cache_key = ",".join(sorted((MagnetExtractor._extract_hash(m) or m) for m in magnets))
        self._cache.put(content, cache_key)
        
        logger.info(f"发现 {len(magnets)} 个磁力链接")
        
        for magnet in magnets:
            await self._process_magnet(magnet)
    
    async def _process_magnet(self, magnet: str) -> None:
        """处理单个磁力链接 - 使用 DebounceFilter"""
        self.stats.total_processed += 1
        
        # 首先解析名称
        name: str = parse_magnet(magnet) or magnet
        
        # 验证磁力链接
        is_valid, error = validate_magnet(magnet)
        if not is_valid:
            logger.warning(f"无效的磁力链接，跳过: {error}")
            self.stats.invalid_magnets += 1
            metrics_module.record_torrent_processed(category="invalid")
            metrics_module.record_torrent_added_failed(category="invalid", reason="validation")
            return
        
        # 提取 hash
        magnet_hash = extract_magnet_hash(magnet) or magnet
        
        # 防抖检查（使用新的 DebounceFilter）
        if self._debounce_filter.is_debounced(magnet_hash):
            logger.debug(f"磁力链接在防抖窗口内，跳过: {get_magnet_display_name(magnet)}")
            self.stats.duplicates_skipped += 1
            metrics_module.record_duplicate_skipped(reason="debounce")
            return
        
        # 分类
        with metrics_module.timed_classification():
            classification_result = await self.classifier.classify(name)
        category = classification_result.category
        cat_config = self.config.categories.get(category)
        
        # 已处理检查
        if magnet_hash in self._processed:
            self.stats.duplicates_skipped += 1
            metrics_module.record_duplicate_skipped(reason="duplicate")
            return
        
        # 记录分类指标
        metrics_module.record_classification(
            method=classification_result.method,
            category=category
        )
        
        # 安全地显示名称
        display_name = name[:50] + "..." if len(name) > 50 else name
        logger.info(f"分类: {display_name} -> {category}")
        
        # 记录处理的磁力链接
        metrics_module.record_torrent_processed(category=category)
        
        # 速率限制检查
        if not self._rate_limiter.try_acquire():
            logger.warning("处理速率超限，等待中...")
            await self._rate_limiter.acquire(timeout=5.0)
        
        # 添加到 qBittorrent
        with metrics_module.timed_torrent_add():
            success = await self.qb.add_torrent(
                magnet, 
                category=category, 
                save_path=cat_config.save_path if cat_config else None
            )
        
        # 确定状态
        if success:
            status = "success"
            self.stats.successful_adds += 1
            # 添加到已处理集合
            self._processed[magnet_hash] = None
            # 自动清理旧记录
            while len(self._processed) > self._max_processed_size:
                self._processed.popitem(last=False)
            metrics_module.record_torrent_added_success(category=category)
            
            # 使用新的 UI 显示成功信息
            if CLI_UI_AVAILABLE:
                StyledOutput.magnet_added(name, category, method=classification_result.method)
            
            # 触发回调
            for handler in self._handlers:
                try:
                    handler(magnet, category)
                except Exception as e:
                    logger.error(f"回调失败: {e}")
        else:
            status = "failed"
            self.stats.failed_adds += 1
            metrics_module.record_torrent_added_failed(category=category, reason="api")
            
            # 使用新的 UI 显示错误信息
            if CLI_UI_AVAILABLE:
                StyledOutput.error(f"添加失败: {display_name}")
        
        # 记录到数据库
        if self._db_enabled:
            try:
                db = await self.get_database()
                if db:
                    await db.record_torrent(
                        magnet_hash=magnet_hash,
                        name=name[:200],
                        category=category,
                        status=status,
                    )
            except Exception as e:
                logger.warning(f"记录到数据库失败: {e}")
    
    def _update_metrics(self) -> None:
        """更新 Prometheus 指标"""
        # 更新缓存大小
        metrics_module.set_cache_size("clipboard", len(self._cache))
        
        # 更新待处理队列大小
        metrics_module.set_pending_magnets(len(self._debounce_filter._pending))
        
        # 更新已处理集合大小
        metrics_module.set_processed_magnets_count(len(self._processed))
        
        # 更新分类器缓存统计
        if hasattr(self.classifier, 'cache') and self.classifier.cache:
            cache_stats = self.classifier.cache.get_stats()
            metrics_module.set_cache_size("classification", cache_stats.get("size", 0))
            metrics_module.set_cache_hit_rate("classification", cache_stats.get("hit_rate", 0.0))
    
    def _extract_hash(self, magnet: str) -> str:
        """向后兼容：提取磁力链接 hash"""
        return extract_magnet_hash(magnet) or magnet
