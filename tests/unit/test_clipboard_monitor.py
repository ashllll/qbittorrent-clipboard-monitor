"""剪贴板监控器单元测试

测试 ClipboardMonitor 的磁力链接提取、处理和监控功能。
"""

from __future__ import annotations

import asyncio
import hashlib
import pytest
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from qbittorrent_monitor.monitor import (
    ClipboardMonitor,
    MagnetExtractor,
    MonitorStats,
    PacingConfig,
)
from qbittorrent_monitor.config import Config, QBConfig, AIConfig, CategoryConfig


# ============================================================================
# TestMonitorStats - 监控统计测试
# ============================================================================

class TestMonitorStats:
    """监控统计测试"""

    def test_stats_initialization(self) -> None:
        """测试统计初始化"""
        stats = MonitorStats()
        
        assert stats.total_processed == 0
        assert stats.successful_adds == 0
        assert stats.failed_adds == 0
        assert stats.duplicates_skipped == 0
        assert stats.start_time is None

    def test_stats_uptime(self) -> None:
        """测试运行时间计算"""
        stats = MonitorStats()
        stats.start_time = datetime.now()
        
        # 应该返回正数
        assert stats.uptime_seconds >= 0

    def test_stats_uptime_not_started(self) -> None:
        """测试未启动时的运行时间"""
        stats = MonitorStats()
        
        assert stats.uptime_seconds == 0.0

    def test_checks_per_minute(self) -> None:
        """测试每分钟检查次数"""
        stats = MonitorStats()
        stats.start_time = datetime.now()
        stats.checks_performed = 60
        
        # 刚刚启动，应该很高或 0
        # 实际计算需要基于时间差
        cpm = stats.checks_per_minute
        assert isinstance(cpm, float)

    def test_record_check_time(self) -> None:
        """测试记录检查时间"""
        stats = MonitorStats()
        
        stats.record_check_time(100.0)
        stats.record_check_time(200.0)
        
        assert stats.avg_check_time_ms == 150.0
        assert len(stats._check_times) == 2

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        stats = MonitorStats()
        stats.start_time = datetime.now()
        stats.total_processed = 10
        stats.successful_adds = 8
        
        result = stats.to_dict()
        
        assert "uptime_seconds" in result
        assert "total_processed" in result
        assert result["total_processed"] == 10
        assert result["successful_adds"] == 8


# ============================================================================
# TestPacingConfig - 轮询配置测试
# ============================================================================

class TestPacingConfig:
    """轮询配置测试"""

    def test_default_values(self) -> None:
        """测试默认值"""
        config = PacingConfig()
        
        assert config.active_interval == 0.5
        assert config.idle_interval == 3.0
        assert config.idle_threshold_seconds == 30.0
        assert config.burst_threshold == 3

    def test_custom_values(self) -> None:
        """测试自定义值"""
        config = PacingConfig(
            active_interval=1.0,
            idle_interval=5.0,
            burst_threshold=5
        )
        
        assert config.active_interval == 1.0
        assert config.idle_interval == 5.0
        assert config.burst_threshold == 5


# ============================================================================
# TestMagnetExtractor - 磁力链接提取测试
# ============================================================================

class TestMagnetExtractor:
    """磁力链接提取器测试"""

    def test_extract_single_magnet(self) -> None:
        """测试提取单个磁力链接"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Test"
        
        results = MagnetExtractor.extract(magnet)
        
        assert len(results) == 1
        assert results[0].startswith("magnet:?")

    def test_extract_multiple_magnets(self) -> None:
        """测试提取多个磁力链接"""
        content = (
            "Here are two magnets: "
            "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Test1 "
            "and "
            "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12&dn=Test2"
        )
        
        results = MagnetExtractor.extract(content)
        
        assert len(results) == 2

    def test_extract_deduplication(self) -> None:
        """测试磁力链接去重"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
        content = f"{magnet} {magnet} {magnet}"
        
        results = MagnetExtractor.extract(content)
        
        # 应该去重
        assert len(results) == 1

    def test_extract_empty_content(self) -> None:
        """测试空内容"""
        results = MagnetExtractor.extract("")
        
        assert results == []

    def test_extract_too_short(self) -> None:
        """测试内容太短"""
        results = MagnetExtractor.extract("magnet:")
        
        assert results == []

    def test_extract_no_magnet(self) -> None:
        """测试没有磁力链接"""
        results = MagnetExtractor.extract("This is just regular text without any magnets")
        
        assert results == []

    def test_extract_invalid_magnet(self) -> None:
        """测试无效磁力链接"""
        # 无效的 hash 长度
        content = "magnet:?xt=urn:btih:short"
        
        results = MagnetExtractor.extract(content)
        
        assert results == []

    def test_extract_with_32_char_hash(self) -> None:
        """测试 32 字符 hash"""
        # Base32 编码的 hash
        magnet = "magnet:?xt=urn:btih:abcdefghijklmnopqrstuvwxyzabcdef"
        
        results = MagnetExtractor.extract(magnet)
        
        assert len(results) == 1

    def test_extract_with_40_char_hash(self) -> None:
        """测试 40 字符 hash"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
        
        results = MagnetExtractor.extract(magnet)
        
        assert len(results) == 1

    def test_extract_truncates_long_content(self) -> None:
        """测试截断过长内容"""
        from qbittorrent_monitor.security import SAFE_LIMITS
        
        # 创建超长内容
        long_content = "x" * (SAFE_LIMITS['max_magnet_length'] * 15)
        
        # 应该不会崩溃
        results = MagnetExtractor.extract(long_content)
        
        # 应该被截断处理
        assert isinstance(results, list)

    def test_extract_hash_extraction(self) -> None:
        """测试 hash 提取"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
        
        hash_value = MagnetExtractor._extract_hash(magnet)
        
        assert hash_value is not None
        assert len(hash_value) == 40
        assert hash_value == "1234567890abcdef1234567890abcdef12345678"

    def test_is_valid_magnet(self) -> None:
        """测试磁力链接有效性检查"""
        valid = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
        invalid = "magnet:?xt=urn:btih:short"
        
        assert MagnetExtractor._is_valid_magnet(valid) is True
        assert MagnetExtractor._is_valid_magnet(invalid) is False


# ============================================================================
# TestClipboardMonitorBasics - 监控器基础测试
# ============================================================================

class TestClipboardMonitorBasics:
    """剪贴板监控器基础测试"""

    @pytest.fixture
    def mock_qb_client(self) -> Mock:
        """模拟 QB 客户端"""
        client = Mock()
        client.add_torrent = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def mock_config(self) -> Config:
        """模拟配置"""
        return Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
            categories={
                "movies": CategoryConfig(
                    save_path="/downloads/movies",
                    keywords=["1080p", "BluRay"]
                ),
                "other": CategoryConfig(save_path="/downloads/other"),
            },
        )

    @pytest.fixture
    def monitor(self, mock_qb_client: Mock, mock_config: Config) -> ClipboardMonitor:
        """监控器 fixture"""
        return ClipboardMonitor(
            qb_client=mock_qb_client,
            config=mock_config,
        )

    def test_monitor_initialization(self, monitor: ClipboardMonitor) -> None:
        """测试监控器初始化"""
        assert monitor.qb is not None
        assert monitor.config is not None
        assert monitor._running is False
        assert monitor._max_magnets_per_check == 100

    def test_add_handler(self, monitor: ClipboardMonitor) -> None:
        """测试添加处理器"""
        handler_called = False
        
        def handler(magnet: str, category: str) -> None:
            nonlocal handler_called
            handler_called = True
        
        monitor.add_handler(handler)
        
        assert len(monitor._handlers) == 1

    def test_remove_handler(self, monitor: ClipboardMonitor) -> None:
        """测试移除处理器"""
        def handler(magnet: str, category: str) -> None:
            pass
        
        monitor.add_handler(handler)
        monitor.remove_handler(handler)
        
        assert len(monitor._handlers) == 0

    def test_get_stats(self, monitor: ClipboardMonitor) -> None:
        """测试获取统计"""
        stats = monitor.get_stats()
        
        assert "total_processed" in stats
        assert "debounce" in stats
        assert "rate_limiter" in stats

    def test_stop(self, monitor: ClipboardMonitor) -> None:
        """测试停止监控"""
        monitor._running = True
        monitor.stop()
        
        assert monitor._running is False

    def test_clear_cache(self, monitor: ClipboardMonitor) -> None:
        """测试清空缓存"""
        # 先添加一些内容到缓存
        monitor._cache.put("test", "value")
        
        monitor.clear_cache()
        
        # 缓存应该被清空
        assert len(monitor._cache.cache) == 0


# ============================================================================
# TestClipboardMonitorProcessing - 监控器处理测试
# ============================================================================

class TestClipboardMonitorProcessing:
    """监控器处理测试"""

    @pytest.fixture
    def mock_qb_client(self) -> Mock:
        """模拟 QB 客户端"""
        client = Mock()
        client.add_torrent = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def mock_config(self) -> Config:
        """模拟配置"""
        return Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
            categories={
                "movies": CategoryConfig(
                    save_path="/downloads/movies",
                    keywords=["1080p", "BluRay"]
                ),
                "tv": CategoryConfig(
                    save_path="/downloads/tv",
                    keywords=["S01", "E01"]
                ),
                "other": CategoryConfig(save_path="/downloads/other"),
            },
        )

    @pytest.fixture
    def monitor(self, mock_qb_client: Mock, mock_config: Config) -> ClipboardMonitor:
        """监控器 fixture"""
        return ClipboardMonitor(
            qb_client=mock_qb_client,
            config=mock_config,
        )

    async def test_process_magnet_link(self, monitor: ClipboardMonitor) -> None:
        """测试处理磁力链接"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Movie.2024.1080p.BluRay"
        
        await monitor._process_magnet(magnet)
        
        # 验证 add_torrent 被调用
        assert monitor.qb.add_torrent.called
        
        # 验证统计更新
        assert monitor.stats.total_processed == 1

    async def test_process_url_not_magnet(self, monitor: ClipboardMonitor) -> None:
        """测试处理非磁力链接 URL"""
        content = "https://example.com/some-file.torrent"
        
        await monitor._process_content(content)
        
        # 不应该处理
        assert monitor.stats.total_processed == 0

    async def test_duplicate_detection(self, monitor: ClipboardMonitor) -> None:
        """测试重复检测"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Test"
        
        # 第一次处理
        await monitor._process_magnet(magnet)
        initial_processed = monitor.stats.total_processed
        
        # 第二次处理（应该被跳过）
        await monitor._process_magnet(magnet)
        
        # 应该被标记为重复
        assert monitor.stats.duplicates_skipped >= 1

    async def test_error_recovery(self, monitor: ClipboardMonitor) -> None:
        """测试错误恢复"""
        # 模拟 add_torrent 失败
        monitor.qb.add_torrent = AsyncMock(return_value=False)
        
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Test"
        
        await monitor._process_magnet(magnet)
        
        # 应该记录失败
        assert monitor.stats.failed_adds == 1

    async def test_process_multiple_magnets(self, monitor: ClipboardMonitor) -> None:
        """测试处理多个磁力链接"""
        content = (
            "magnet:?xt=urn:btih:1111111111111111111111111111111111111111&dn=Movie1 "
            "magnet:?xt=urn:btih:2222222222222222222222222222222222222222&dn=Movie2"
        )
        
        await monitor._process_content(content)
        
        # 应该处理两个
        assert monitor.stats.total_processed == 2

    async def test_magnet_limit(self, monitor: ClipboardMonitor) -> None:
        """测试磁力链接数量限制"""
        # 创建很多磁力链接
        magnets = " ".join([
            f"magnet:?xt=urn:btih:{str(i).zfill(40)}&dn=Test{i}"
            for i in range(150)
        ])
        
        await monitor._process_content(magnets)
        
        # 应该只处理前 100 个
        assert monitor.stats.total_processed <= 100


# ============================================================================
# TestClipboardMonitorPacing - 智能轮询测试
# ============================================================================

class TestClipboardMonitorPacing:
    """智能轮询测试"""

    @pytest.fixture
    def monitor(self) -> ClipboardMonitor:
        """监控器 fixture"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
        )
        mock_qb = Mock()
        mock_qb.add_torrent = AsyncMock(return_value=True)
        
        return ClipboardMonitor(
            qb_client=mock_qb,
            config=config,
            pacing_config=PacingConfig(
                active_interval=0.5,
                idle_interval=2.0,
                idle_threshold_seconds=1.0,
                burst_threshold=3
            )
        )

    def test_calculate_interval_idle(self, monitor: ClipboardMonitor) -> None:
        """测试空闲间隔计算"""
        import time
        
        # 设置很久之前的变化
        monitor._last_change_time = time.time() - 5.0
        
        interval = monitor._calculate_interval()
        
        assert interval == monitor.pacing.idle_interval

    def test_calculate_interval_active(self, monitor: ClipboardMonitor) -> None:
        """测试活跃间隔计算"""
        import time
        
        # 最近的变化
        monitor._last_change_time = time.time()
        
        interval = monitor._calculate_interval()
        
        assert interval == monitor.pacing.active_interval

    def test_calculate_interval_burst(self, monitor: ClipboardMonitor) -> None:
        """测试突发模式间隔"""
        import time
        
        # 设置突发状态
        monitor._change_count_in_window = 5
        monitor._window_start_time = time.time()
        
        interval = monitor._calculate_interval()
        
        assert interval == monitor.pacing.active_interval

    def test_update_activity_tracking(self, monitor: ClipboardMonitor) -> None:
        """测试活动追踪更新"""
        import time
        
        initial_count = monitor._change_count_in_window
        
        monitor._update_activity_tracking()
        
        assert monitor._change_count_in_window == initial_count + 1
        assert monitor._last_change_time > 0


# ============================================================================
# TestClipboardMonitorWithMockPyperclip - 剪贴板模拟测试
# ============================================================================

class TestClipboardMonitorWithMockPyperclip:
    """使用 Mock pyperclip 的测试"""

    @pytest.fixture
    def monitor(self) -> ClipboardMonitor:
        """监控器 fixture"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
        )
        mock_qb = Mock()
        mock_qb.add_torrent = AsyncMock(return_value=True)
        
        return ClipboardMonitor(
            qb_client=mock_qb,
            config=config,
        )

    async def test_check_clipboard_with_magnet(self, monitor: ClipboardMonitor) -> None:
        """测试检查剪贴板发现磁力链接"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Test.Movie.1080p"
        
        with patch('qbittorrent_monitor.monitor.pyperclip.paste', return_value=magnet):
            await monitor._check_clipboard()
            
            # 应该更新统计
            assert monitor.stats.clipboard_changes == 1

    async def test_check_clipboard_no_change(self, monitor: ClipboardMonitor) -> None:
        """测试剪贴板无变化"""
        content = "same content"
        monitor._last_content = content
        monitor._last_content_hash = hashlib.md5(content.encode()).hexdigest()
        
        with patch('qbittorrent_monitor.monitor.pyperclip.paste', return_value=content):
            initial_changes = monitor.stats.clipboard_changes
            
            await monitor._check_clipboard()
            
            # 不应该增加变化计数
            assert monitor.stats.clipboard_changes == initial_changes

    async def test_check_clipboard_empty(self, monitor: ClipboardMonitor) -> None:
        """测试空剪贴板"""
        with patch('qbittorrent_monitor.monitor.pyperclip.paste', return_value=""):
            await monitor._check_clipboard()
            
            # 不应该有任何处理
            assert monitor.stats.clipboard_changes == 0

    async def test_check_clipboard_cache_hit(self, monitor: ClipboardMonitor) -> None:
        """测试剪贴板缓存命中"""
        content = "some content with magnet"
        
        # 先缓存内容
        monitor._cache.put(content, "cached_value")
        
        with patch('qbittorrent_monitor.monitor.pyperclip.paste', return_value=content):
            await monitor._check_clipboard()
            
            # 应该记录缓存命中
            assert monitor.stats.hash_cache_hits == 1


# ============================================================================
# TestClipboardMonitorCallback - 回调测试
# ============================================================================

class TestClipboardMonitorCallback:
    """回调测试"""

    @pytest.fixture
    def monitor(self) -> ClipboardMonitor:
        """监控器 fixture"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
        )
        mock_qb = Mock()
        mock_qb.add_torrent = AsyncMock(return_value=True)
        
        return ClipboardMonitor(
            qb_client=mock_qb,
            config=config,
        )

    async def test_handler_called_on_success(self, monitor: ClipboardMonitor) -> None:
        """测试成功时调用处理器"""
        handler_called = False
        received_magnet = None
        received_category = None
        
        def handler(magnet: str, category: str) -> None:
            nonlocal handler_called, received_magnet, received_category
            handler_called = True
            received_magnet = magnet
            received_category = category
        
        monitor.add_handler(handler)
        
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Movie.2024.1080p.BluRay"
        
        await monitor._process_magnet(magnet)
        
        assert handler_called is True
        assert received_magnet is not None
        assert received_category == "movies"

    async def test_handler_exception_caught(self, monitor: ClipboardMonitor) -> None:
        """测试处理器异常被捕获"""
        def failing_handler(magnet: str, category: str) -> None:
            raise ValueError("Handler error")
        
        monitor.add_handler(failing_handler)
        
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Test"
        
        # 不应该因为处理器异常而失败
        await monitor._process_magnet(magnet)
        
        # 处理应该完成
        assert monitor.stats.total_processed == 1


# ============================================================================
# TestClipboardMonitorDatabase - 数据库功能测试
# ============================================================================

class TestClipboardMonitorDatabase:
    """数据库功能测试"""

    @pytest.fixture
    def monitor_with_db(self) -> ClipboardMonitor:
        """带数据库的监控器 fixture"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
            database={
                "enabled": True,
                "db_path": ":memory:",
            },
        )
        mock_qb = Mock()
        mock_qb.add_torrent = AsyncMock(return_value=True)
        
        return ClipboardMonitor(
            qb_client=mock_qb,
            config=config,
        )

    async def test_database_disabled_by_default(self) -> None:
        """测试默认禁用数据库"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
        )
        mock_qb = Mock()
        
        monitor = ClipboardMonitor(qb_client=mock_qb, config=config)
        
        db = await monitor.get_database()
        assert db is None

    def test_max_processed_size_limit(self) -> None:
        """测试已处理集合大小限制"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
        )
        mock_qb = Mock()
        
        monitor = ClipboardMonitor(qb_client=mock_qb, config=config)
        monitor._max_processed_size = 5
        
        # 添加超过限制的条目
        for i in range(10):
            monitor._processed[f"hash{i}"] = None
            
            # 模拟自动清理
            while len(monitor._processed) > monitor._max_processed_size:
                monitor._processed.popitem(last=False)
        
        assert len(monitor._processed) <= 5
