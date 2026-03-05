"""测试配置"""

import pytest
from qbittorrent_monitor.config import Config, QBConfig, AIConfig, CategoryConfig


@pytest.fixture
def config():
    """创建测试配置"""
    return Config(
        qbittorrent=QBConfig(
            host="localhost",
            port=8080,
            username="admin",
            password="adminadmin",
        ),
        ai=AIConfig(
            enabled=False,
            api_key="",
        ),
    )


@pytest.fixture
def mock_categories():
    """模拟分类配置"""
    return {
        "movies": CategoryConfig(
            save_path="/downloads/movies",
            keywords=["Movie", "1080p"],
        ),
        "tv": CategoryConfig(
            save_path="/downloads/tv",
            keywords=["S01", "Series"],
        ),
    }
