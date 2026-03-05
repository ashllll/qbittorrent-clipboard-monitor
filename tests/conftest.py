"""测试配置"""

import pytest
from qbittorrent_monitor.config import Config, QBConfig, AIConfig, CategoryConfig


@pytest.fixture
def mock_config():
    """测试配置"""
    return Config(
        qbittorrent=QBConfig(host="localhost", port=8080, username="admin", password="admin"),
        ai=AIConfig(enabled=False),
        check_interval=0.1,
    )


@pytest.fixture
def mock_config_with_ai():
    """带AI的配置"""
    return Config(
        qbittorrent=QBConfig(host="localhost", port=8080, username="admin", password="admin"),
        ai=AIConfig(enabled=True, api_key="test-key"),
        check_interval=0.1,
    )
