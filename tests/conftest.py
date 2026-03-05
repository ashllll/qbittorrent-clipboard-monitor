"""测试配置"""

import pytest
import asyncio


@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """模拟配置"""
    from qbittorrent_monitor.config import Config, QBConfig, AIConfig, CategoryConfig
    
    return Config(
        qbittorrent=QBConfig(host="localhost", port=8080, username="admin", password="admin"),
        ai=AIConfig(enabled=False),
        categories={
            "movies": CategoryConfig(save_path="/downloads/movies", keywords=["movie", "BluRay"]),
            "tv": CategoryConfig(save_path="/downloads/tv", keywords=["S01", "E01", "TV"]),
            "other": CategoryConfig(save_path="/downloads/other"),
        },
        check_interval=0.1,
    )
