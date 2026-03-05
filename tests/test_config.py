"""配置测试"""

import json
import tempfile
from pathlib import Path

import pytest

from qbittorrent_monitor.config import Config, QBConfig, AIConfig, CategoryConfig


class TestConfig:
    """配置测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = Config()
        assert config.qbittorrent.host == "localhost"
        assert config.qbittorrent.port == 8080
        assert config.check_interval == 1.0
        assert "movies" in config.categories
        assert "tv" in config.categories
    
    def test_config_to_dict(self):
        """测试配置转字典"""
        config = Config()
        data = config.to_dict()
        assert "qbittorrent" in data
        assert "categories" in data
        assert data["check_interval"] == 1.0
    
    def test_config_from_dict(self):
        """测试从字典加载"""
        data = {
            "qbittorrent": {"host": "192.168.1.1", "port": 9090},
            "ai": {"enabled": True, "api_key": "test"},
            "categories": {
                "test": {"save_path": "/test", "keywords": ["test"]}
            },
            "check_interval": 2.0,
            "log_level": "DEBUG",
        }
        config = Config.from_dict(data)
        assert config.qbittorrent.host == "192.168.1.1"
        assert config.qbittorrent.port == 9090
        assert config.ai.enabled is True
        assert config.check_interval == 2.0
    
    def test_config_save_load(self):
        """测试配置保存和加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            config = Config()
            config.qbittorrent.host = "test-host"
            config.save(path)
            
            loaded = Config.load(path)
            assert loaded.qbittorrent.host == "test-host"
