"""配置模块测试"""

import json
import tempfile
from pathlib import Path

import pytest

from qbittorrent_monitor.config import Config, QBConfig, AIConfig, CategoryConfig, load_config


class TestConfig:
    """测试配置类"""
    
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
        assert "ai" in data
        assert "categories" in data
    
    def test_config_from_dict(self):
        """测试从字典创建配置"""
        data = {
            "qbittorrent": {"host": "127.0.0.1", "port": 9090},
            "ai": {"enabled": True, "api_key": "test"},
            "categories": {},
            "check_interval": 2.0,
        }
        config = Config.from_dict(data)
        assert config.qbittorrent.host == "127.0.0.1"
        assert config.qbittorrent.port == 9090
        assert config.ai.enabled is True
    
    def test_config_save_load(self):
        """测试配置保存和加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config = Config(qbittorrent=QBConfig(host="test-host"))
            config.save(config_path)
            
            loaded = Config.load(config_path)
            assert loaded.qbittorrent.host == "test-host"


class TestQBConfig:
    """测试qBittorrent配置"""
    
    def test_default_values(self):
        """测试默认值"""
        qb = QBConfig()
        assert qb.host == "localhost"
        assert qb.port == 8080
        assert qb.use_https is False


class TestAIConfig:
    """测试AI配置"""
    
    def test_default_values(self):
        """测试默认值"""
        ai = AIConfig()
        assert ai.enabled is True
        assert ai.model == "deepseek-chat"
        assert ai.timeout == 30


class TestCategoryConfig:
    """测试分类配置"""
    
    def test_category_creation(self):
        """测试创建分类"""
        cat = CategoryConfig(save_path="/test", keywords=["a", "b"])
        assert cat.save_path == "/test"
        assert cat.keywords == ["a", "b"]
