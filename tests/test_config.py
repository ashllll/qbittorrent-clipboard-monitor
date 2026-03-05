"""配置模块测试"""

import json
import tempfile
from pathlib import Path

import pytest

from qbittorrent_monitor.config import Config, QBConfig, AIConfig, CategoryConfig


class TestConfig:
    """配置类测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = Config()
        assert config.qbittorrent.host == "localhost"
        assert config.qbittorrent.port == 8080
        assert config.check_interval == 1.0
        assert "movies" in config.categories
        assert "tv" in config.categories
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = Config(
            qbittorrent=QBConfig(host="192.168.1.100", port=9090),
            check_interval=2.0,
        )
        assert config.qbittorrent.host == "192.168.1.100"
        assert config.qbittorrent.port == 9090
        assert config.check_interval == 2.0
    
    def test_config_to_dict(self):
        """测试配置转字典"""
        config = Config()
        data = config.to_dict()
        assert "qbittorrent" in data
        assert "ai" in data
        assert "categories" in data
        assert data["check_interval"] == 1.0
    
    def test_config_from_dict(self):
        """测试从字典创建配置"""
        data = {
            "qbittorrent": {"host": "10.0.0.1", "port": 1234},
            "ai": {"enabled": True, "api_key": "test-key"},
            "categories": {},
            "check_interval": 0.5,
            "log_level": "DEBUG",
        }
        config = Config.from_dict(data)
        assert config.qbittorrent.host == "10.0.0.1"
        assert config.ai.enabled is True
        assert config.check_interval == 0.5


class TestConfigPersistence:
    """配置持久化测试"""
    
    def test_save_and_load(self):
        """测试保存和加载配置"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            
            # 创建并保存配置
            config = Config(
                qbittorrent=QBConfig(host="test-host"),
                check_interval=3.0,
            )
            config.save(config_path)
            
            # 验证文件存在
            assert config_path.exists()
            
            # 加载配置
            loaded = Config.load(config_path)
            assert loaded.qbittorrent.host == "test-host"
            assert loaded.check_interval == 3.0
    
    def test_load_nonexistent_creates_default(self):
        """测试加载不存在的配置会创建默认配置"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent" / "config.json"
            
            config = Config.load(config_path)
            assert config.qbittorrent.host == "localhost"
            assert config_path.exists()  # 应该自动创建
