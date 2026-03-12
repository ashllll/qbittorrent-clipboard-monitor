"""测试配置

提供 pytest fixtures 和测试辅助工具。
"""

from __future__ import annotations

import asyncio
import json
import pytest
import pytest_asyncio
from pathlib import Path
from typing import Dict, Any, Generator, List
from unittest.mock import Mock, AsyncMock, MagicMock
from dataclasses import dataclass

# 配置相关导入
from qbittorrent_monitor.config import (
    Config,
    QBConfig,
    AIConfig,
    CategoryConfig,
    ConfigManager,
    get_default_categories,
)
from qbittorrent_monitor.config.ai import AIConfig as DeepSeekConfig
from qbittorrent_monitor.config.qb import QBConfig as QBittorrentConfig

# 弹性组件导入
from qbittorrent_monitor.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitStrategy,
    SlidingWindowCounter,
    TokenBucket,
    FixedWindowCounter,
)
from qbittorrent_monitor.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from qbittorrent_monitor.classifier import LRUCache, ClassificationResult


# ============================================================================
# 事件循环配置
# ============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """创建事件循环 - 会话级别"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# 配置相关 Fixtures
# ============================================================================

@pytest.fixture
def valid_config_data() -> Dict[str, Any]:
    """有效的配置数据字典"""
    return {
        "qbittorrent": {
            "host": "localhost",
            "port": 8080,
            "username": "admin",
            "password": "adminadmin",
            "use_https": False,
        },
        "ai": {
            "enabled": False,
            "api_key": "",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "timeout": 30,
            "max_retries": 3,
        },
        "categories": {
            "movies": {
                "save_path": "/downloads/movies",
                "keywords": ["1080p", "4K", "BluRay", "Movie"],
            },
            "tv": {
                "save_path": "/downloads/tv",
                "keywords": ["S01", "E01", "TV Series"],
            },
            "anime": {
                "save_path": "/downloads/anime",
                "keywords": ["Anime", "动画"],
            },
            "music": {
                "save_path": "/downloads/music",
                "keywords": ["FLAC", "MP3", "Music"],
            },
            "software": {
                "save_path": "/downloads/software",
                "keywords": ["Software", "Portable"],
            },
            "other": {
                "save_path": "/downloads/other",
                "keywords": [],
            },
        },
        "check_interval": 1.0,
        "log_level": "INFO",
        "database": {
            "enabled": False,
            "db_path": "./test.db",
            "auto_cleanup_days": 30,
            "export_format": "json",
        },
        "metrics": {
            "enabled": False,
            "host": "localhost",
            "port": 9090,
        },
        "plugins": {
            "enabled": False,
            "plugins_dir": None,
            "auto_enable": False,
            "auto_discover": True,
            "enabled_plugins": [],
            "disabled_plugins": [],
            "plugin_configs": {},
        },
    }


@pytest.fixture
def minimal_config_data() -> Dict[str, Any]:
    """最小配置数据字典"""
    return {
        "qbittorrent": {
            "host": "localhost",
            "port": 8080,
            "username": "admin",
            "password": "adminadmin",
        },
    }


@pytest.fixture
def invalid_config_data() -> Dict[str, Any]:
    """无效的配置数据字典"""
    return {
        "qbittorrent": {
            "host": "localhost",
            "port": 99999,  # 无效端口
            "username": "",
            "password": "",
        },
        "check_interval": -1.0,  # 无效间隔
    }


@pytest_asyncio.fixture
async def config_manager(tmp_path: Path) -> ConfigManager:
    """配置管理器 fixture - 使用临时目录"""
    config_path = tmp_path / "config.json"
    config = Config()
    config.save(config_path)
    
    manager = ConfigManager(
        config_path=config_path,
        auto_reload=False,
        reload_interval=1.0
    )
    return manager


@pytest.fixture
def mock_config() -> Config:
    """模拟配置 - 使用安全的路径"""
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
                keywords=["movie", "BluRay"]
            ),
            "tv": CategoryConfig(
                save_path="/downloads/tv",
                keywords=["S01", "E01", "TV"]
            ),
            "anime": CategoryConfig(
                save_path="/downloads/anime",
                keywords=["Anime"]
            ),
            "music": CategoryConfig(
                save_path="/downloads/music",
                keywords=["Music", "FLAC"]
            ),
            "software": CategoryConfig(
                save_path="/downloads/software",
                keywords=["Software"]
            ),
            "games": CategoryConfig(
                save_path="/downloads/games",
                keywords=["Game"]
            ),
            "books": CategoryConfig(
                save_path="/downloads/books",
                keywords=["PDF", "EPUB"]
            ),
            "other": CategoryConfig(save_path="/downloads/other"),
        },
        check_interval=0.1,
    )


# ============================================================================
# AI 配置 Fixtures
# ============================================================================

@pytest.fixture
def deepseek_config() -> DeepSeekConfig:
    """DeepSeek AI 配置"""
    return DeepSeekConfig(
        enabled=False,
        api_key="sk-test-key",
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        timeout=30,
        max_retries=3,
    )


@pytest.fixture
def enabled_ai_config() -> DeepSeekConfig:
    """启用的 AI 配置"""
    return DeepSeekConfig(
        enabled=True,
        api_key="sk-test-key-12345",
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        timeout=30,
        max_retries=3,
    )


# ============================================================================
# qBittorrent 配置 Fixtures
# ============================================================================

@pytest.fixture
def qbittorrent_config() -> QBittorrentConfig:
    """qBittorrent 配置"""
    return QBittorrentConfig(
        host="localhost",
        port=8080,
        username="admin",
        password="adminadmin",
        use_https=False,
    )


# ============================================================================
# Mock 客户端 Fixtures
# ============================================================================

@pytest.fixture
def mock_openai_client() -> Mock:
    """模拟 OpenAI 客户端"""
    client = Mock()
    
    # 创建模拟响应
    mock_response = Mock()
    mock_content = Mock()
    mock_content.text = "movies"
    mock_response.content = [mock_content]
    
    client.messages = Mock()
    client.messages.create = Mock(return_value=mock_response)
    
    return client


@pytest.fixture
def mock_openai_client_with_sequence() -> Mock:
    """模拟 OpenAI 客户端 - 支持序列响应"""
    client = Mock()
    client._responses: List[str] = []
    client._call_count = 0
    
    def create_side_effect(*args, **kwargs):
        mock_response = Mock()
        mock_content = Mock()
        
        if client._call_count < len(client._responses):
            mock_content.text = client._responses[client._call_count]
        else:
            mock_content.text = "other"
        
        client._call_count += 1
        mock_response.content = [mock_content]
        return mock_response
    
    client.messages = Mock()
    client.messages.create = Mock(side_effect=create_side_effect)
    
    return client


@pytest.fixture
def mock_aiohttp_session() -> AsyncMock:
    """模拟 aiohttp 会话"""
    session = AsyncMock()
    
    # 模拟 post 方法
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="Ok.")
    mock_response.json = AsyncMock(return_value={})
    
    session.post = AsyncMock(return_value=mock_response)
    session.get = AsyncMock(return_value=mock_response)
    session.close = AsyncMock()
    
    return session


@pytest.fixture
def mock_aiohttp_session_auth_failure() -> AsyncMock:
    """模拟认证失败的 aiohttp 会话"""
    session = AsyncMock()
    
    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.text = AsyncMock(return_value="Fails.")
    
    session.post = AsyncMock(return_value=mock_response)
    session.get = AsyncMock(return_value=mock_response)
    session.close = AsyncMock()
    
    return session


@pytest.fixture
def mock_qbittorrent_client() -> Mock:
    """模拟 qBittorrent 客户端"""
    client = Mock()
    client.add_torrent = AsyncMock(return_value=True)
    client.get_categories = AsyncMock(return_value={})
    client.create_category = AsyncMock(return_value=True)
    client.get_version = AsyncMock(return_value="v4.5.0")
    client._is_authenticated = True
    return client


# ============================================================================
# 弹性组件 Fixtures
# ============================================================================

@pytest.fixture
def rate_limiter() -> RateLimiter:
    """速率限制器 - 默认滑动窗口策略"""
    config = RateLimitConfig(
        max_requests=10,
        window_seconds=60.0,
        strategy=RateLimitStrategy.SLIDING_WINDOW
    )
    return RateLimiter(config)


@pytest.fixture
def token_bucket_limiter() -> RateLimiter:
    """令牌桶速率限制器"""
    config = RateLimitConfig(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        burst_size=5,
        refill_rate=1.0
    )
    return RateLimiter(config)


@pytest.fixture
def fixed_window_limiter() -> RateLimiter:
    """固定窗口速率限制器"""
    config = RateLimitConfig(
        max_requests=5,
        window_seconds=60.0,
        strategy=RateLimitStrategy.FIXED_WINDOW
    )
    return RateLimiter(config)


@pytest.fixture
def sliding_window_counter() -> SlidingWindowCounter:
    """滑动窗口计数器"""
    return SlidingWindowCounter(
        window_size=60.0,
        max_requests=10
    )


@pytest.fixture
def token_bucket() -> TokenBucket:
    """令牌桶"""
    return TokenBucket(
        capacity=5,
        refill_rate=1.0
    )


@pytest.fixture
def fixed_window_counter() -> FixedWindowCounter:
    """固定窗口计数器"""
    return FixedWindowCounter(
        window_size=60.0,
        max_requests=10
    )


@pytest.fixture
def circuit_breaker() -> CircuitBreaker:
    """熔断器 - 默认配置"""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=30.0,
        half_open_max_calls=2
    )
    return CircuitBreaker(config, name="test_breaker")


@pytest.fixture
def fast_circuit_breaker() -> CircuitBreaker:
    """快速熔断器 - 用于测试"""
    config = CircuitBreakerConfig(
        failure_threshold=2,
        success_threshold=1,
        timeout_seconds=0.1,  # 快速超时
        half_open_max_calls=1
    )
    return CircuitBreaker(config, name="fast_test_breaker")


# ============================================================================
# 分类器相关 Fixtures
# ============================================================================

@pytest.fixture
def lru_cache_fixture() -> LRUCache:
    """LRU 缓存"""
    return LRUCache(capacity=100)


@pytest.fixture
def sample_classification_results() -> Dict[str, ClassificationResult]:
    """示例分类结果"""
    return {
        "movie": ClassificationResult(
            category="movies",
            confidence=0.85,
            method="rule"
        ),
        "tv": ClassificationResult(
            category="tv",
            confidence=0.75,
            method="rule"
        ),
        "anime": ClassificationResult(
            category="anime",
            confidence=0.90,
            method="rule"
        ),
        "other": ClassificationResult(
            category="other",
            confidence=0.30,
            method="fallback"
        ),
    }


# ============================================================================
# 磁力链接 Fixtures
# ============================================================================

@pytest.fixture
def sample_magnet_links() -> Dict[str, str]:
    """示例磁力链接"""
    return {
        "movie": "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Movie.2024.1080p.BluRay.x264",
        "tv": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12&dn=TV.Show.S01E01.1080p.WEB-DL",
        "anime": "magnet:?xt=urn:btih:fedcba0987654321fedcba0987654321fedcba09&dn=Anime.Series.Episode.01",
        "software": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&dn=Software.v1.0.Portable",
        "minimal": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    }


# ============================================================================
# 测试数据目录 Fixtures
# ============================================================================

@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    """测试数据目录"""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def configs_dir(test_data_dir: Path) -> Path:
    """配置文件目录"""
    configs = test_data_dir / "configs"
    configs.mkdir(parents=True, exist_ok=True)
    return configs


@pytest.fixture
def ai_responses_dir(test_data_dir: Path) -> Path:
    """AI 响应目录"""
    responses = test_data_dir / "ai_responses"
    responses.mkdir(parents=True, exist_ok=True)
    return responses


# ============================================================================
# 环境变量 Fixtures
# ============================================================================

@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """清理环境变量"""
    env_vars = [
        "QBIT_HOST", "QBIT_PORT", "QBIT_USERNAME", "QBIT_PASSWORD", "QBIT_USE_HTTPS",
        "AI_ENABLED", "AI_API_KEY", "AI_MODEL", "AI_BASE_URL", "AI_TIMEOUT", "AI_MAX_RETRIES",
        "CHECK_INTERVAL", "LOG_LEVEL",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


# ============================================================================
# pytest 配置
# ============================================================================

def pytest_configure(config: pytest.Config) -> None:
    """pytest 配置钩子"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


# ============================================================================
# 异步测试配置
# ============================================================================

# pytest-asyncio 配置通过 pyproject.toml 中的 asyncio_mode = "auto" 设置
