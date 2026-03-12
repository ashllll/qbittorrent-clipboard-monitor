"""配置集成测试

测试配置热重载、环境变量覆盖等集成场景。
"""

from __future__ import annotations

import asyncio
import json
import os
import pytest
import tempfile
import time
from pathlib import Path
from typing import Dict, Any

from qbittorrent_monitor.config import Config, ConfigManager, QBConfig, AIConfig
from qbittorrent_monitor.config.env_loader import load_from_env
from qbittorrent_monitor.exceptions import ConfigError


# ============================================================================
# 热重载集成测试
# ============================================================================

@pytest.mark.integration
class TestConfigHotReload:
    """配置热重载集成测试"""

    async def test_config_hot_reload(self) -> None:
        """测试配置热重载功能
        
        验证修改配置文件后，ConfigManager 能够检测变化并重新加载配置。
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            
            # 创建初始配置
            initial_config = {
                "qbittorrent": {
                    "host": "localhost",
                    "port": 8080,
                    "username": "admin",
                    "password": "adminadmin"
                },
                "check_interval": 1.0,
                "log_level": "INFO"
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(initial_config, f)
            
            # 创建管理器（启用热重载）
            manager = ConfigManager(
                config_path=config_path,
                auto_reload=True,
                reload_interval=0.1
            )
            
            # 获取初始配置
            config1 = manager.get_config()
            assert config1.check_interval == 1.0
            assert config1.log_level == "INFO"
            
            # 修改配置文件
            initial_config["check_interval"] = 2.5
            initial_config["log_level"] = "DEBUG"
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(initial_config, f)
            
            # 等待重载检查
            await asyncio.sleep(0.2)
            
            # 获取新配置
            config2 = manager.get_config()
            assert config2.check_interval == 2.5
            assert config2.log_level == "DEBUG"

    async def test_hot_reload_with_callback(self) -> None:
        """测试带回调的热重载
        
        验证配置变化时回调函数被正确调用。
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            
            config_data = {
                "qbittorrent": {
                    "host": "localhost",
                    "port": 8080,
                    "username": "admin",
                    "password": "adminadmin"
                },
                "check_interval": 1.0
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            manager = ConfigManager(
                config_path=config_path,
                auto_reload=True,
                reload_interval=0.1
            )
            
            # 注册回调
            callback_called = False
            callback_config = None
            
            def on_config_change(new_config: Config) -> None:
                nonlocal callback_called, callback_config
                callback_called = True
                callback_config = new_config
            
            manager.on_change(on_config_change)
            
            # 首次加载不会触发回调
            manager.get_config()
            assert callback_called is False
            
            # 修改配置
            config_data["check_interval"] = 5.0
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            # 等待重载
            await asyncio.sleep(0.2)
            
            # 获取配置触发重载
            manager.get_config()
            
            # 回调应该被调用
            assert callback_called is True
            assert callback_config is not None
            assert callback_config.check_interval == 5.0

    async def test_no_reload_when_file_unchanged(self) -> None:
        """测试文件未修改时不重载"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            
            config_data = {
                "qbittorrent": {
                    "host": "localhost",
                    "port": 8080,
                    "username": "admin",
                    "password": "adminadmin"
                },
                "check_interval": 1.0
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            manager = ConfigManager(
                config_path=config_path,
                auto_reload=True,
                reload_interval=0.1
            )
            
            # 获取配置
            config1 = manager.get_config()
            
            # 等待但不修改文件
            await asyncio.sleep(0.2)
            
            # 再次获取，应该是同一个对象
            config2 = manager.get_config()
            
            # 配置对象应该是同一个（没有重载）
            assert config1 is config2


# ============================================================================
# 环境变量覆盖集成测试
# ============================================================================

@pytest.mark.integration
class TestEnvVarOverride:
    """环境变量覆盖集成测试"""

    def test_env_var_override_qb_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试环境变量覆盖 qBittorrent 设置
        
        验证环境变量优先级高于配置文件。
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            
            # 配置文件设置
            config_data = {
                "qbittorrent": {
                    "host": "localhost",
                    "port": 8080,
                    "username": "admin",
                    "password": "adminadmin",
                    "use_https": False
                }
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            # 设置环境变量覆盖
            monkeypatch.setenv("QBIT_HOST", "192.168.1.100")
            monkeypatch.setenv("QBIT_PORT", "9090")
            monkeypatch.setenv("QBIT_USERNAME", "env_user")
            monkeypatch.setenv("QBIT_PASSWORD", "env_pass")
            monkeypatch.setenv("QBIT_USE_HTTPS", "true")
            
            # 加载配置
            config = Config.load(config_path)
            load_from_env(config)
            
            # 验证环境变量覆盖
            assert config.qbittorrent.host == "192.168.1.100"
            assert config.qbittorrent.port == 9090
            assert config.qbittorrent.username == "env_user"
            assert config.qbittorrent.password == "env_pass"
            assert config.qbittorrent.use_https is True

    def test_env_var_override_check_interval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试环境变量覆盖检查间隔"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            
            config_data = {"check_interval": 1.0}
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            # 设置环境变量
            monkeypatch.setenv("CHECK_INTERVAL", "5.5")
            
            config = Config.load(config_path)
            load_from_env(config)
            
            assert config.check_interval == 5.5

    def test_env_var_override_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试环境变量覆盖日志级别"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            
            config_data = {"log_level": "INFO"}
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            monkeypatch.setenv("LOG_LEVEL", "DEBUG")
            
            config = Config.load(config_path)
            load_from_env(config)
            
            assert config.log_level == "DEBUG"

    def test_env_var_override_ai_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试环境变量覆盖 AI 设置"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            
            config_data = {
                "ai": {
                    "enabled": False,
                    "api_key": "",
                    "model": "deepseek-chat",
                    "base_url": "https://api.deepseek.com/v1",
                    "timeout": 30,
                    "max_retries": 3
                }
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            # 启用 AI
            monkeypatch.setenv("AI_ENABLED", "true")
            monkeypatch.setenv("AI_API_KEY", "sk-test-key-12345")
            monkeypatch.setenv("AI_MODEL", "custom-model")
            monkeypatch.setenv("AI_TIMEOUT", "60")
            monkeypatch.setenv("AI_MAX_RETRIES", "5")
            
            config = Config.load(config_path)
            load_from_env(config)
            
            assert config.ai.enabled is True
            assert config.ai.api_key == "sk-test-key-12345"
            assert config.ai.model == "custom-model"
            assert config.ai.timeout == 60
            assert config.ai.max_retries == 5

    def test_env_var_empty_value_not_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试空环境变量不覆盖"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            
            config_data = {
                "qbittorrent": {
                    "host": "localhost",
                    "port": 8080,
                    "username": "admin",
                    "password": "adminadmin"
                }
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            # 设置空环境变量
            monkeypatch.setenv("QBIT_HOST", "")
            monkeypatch.setenv("QBIT_USERNAME", "")
            
            config = Config.load(config_path)
            load_from_env(config)
            
            # 空值不应该覆盖配置
            assert config.qbittorrent.host == "localhost"
            assert config.qbittorrent.username == "admin"


# ============================================================================
# 配置验证集成测试
# ============================================================================

@pytest.mark.integration
class TestConfigValidationIntegration:
    """配置验证集成测试"""

    def test_strict_validation_failure(self) -> None:
        """测试严格验证失败"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=99999,  # 无效端口
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
        )
        
        with pytest.raises(ConfigError):
            config.validate(strict=True)

    def test_non_strict_validation_returns_warnings(self) -> None:
        """测试非严格验证返回警告"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=True, api_key=""),  # 启用 AI 但没有 key
        )
        
        warnings = config.validate(strict=False)
        
        # 应该有关于 AI 配置的警告
        assert any("ai" in w.lower() for w in warnings)

    def test_config_save_and_reload(self) -> None:
        """测试配置保存和重新加载"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            
            # 创建配置
            config = Config(
                qbittorrent=QBConfig(
                    host="192.168.1.100",
                    port=9090,
                    username="custom_user",
                    password="custom_pass"
                ),
                ai=AIConfig(enabled=False),
                check_interval=2.0,
                log_level="WARNING"
            )
            
            # 保存
            config.save(config_path)
            
            # 验证文件存在
            assert config_path.exists()
            
            # 重新加载
            loaded_config = Config.load(config_path)
            
            # 验证值正确
            assert loaded_config.qbittorrent.host == "192.168.1.100"
            assert loaded_config.qbittorrent.port == 9090
            assert loaded_config.qbittorrent.username == "custom_user"
            assert loaded_config.check_interval == 2.0
            assert loaded_config.log_level == "WARNING"


# ============================================================================
# 配置管理器生命周期测试
# ============================================================================

@pytest.mark.integration
class TestConfigManagerLifecycle:
    """配置管理器生命周期测试"""

    async def test_manager_multiple_callbacks(self) -> None:
        """测试多个回调函数"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            
            config_data = {
                "qbittorrent": {
                    "host": "localhost",
                    "port": 8080,
                    "username": "admin",
                    "password": "adminadmin"
                },
                "check_interval": 1.0
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            manager = ConfigManager(config_path=config_path, auto_reload=False)
            
            callback1_called = False
            callback2_called = False
            
            def callback1(config: Config) -> None:
                nonlocal callback1_called
                callback1_called = True
            
            def callback2(config: Config) -> None:
                nonlocal callback2_called
                callback2_called = True
            
            manager.on_change(callback1)
            manager.on_change(callback2)
            
            # 修改配置
            config_data["check_interval"] = 3.0
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            # 强制重载
            manager.reload()
            
            # 两个回调都应该被调用
            assert callback1_called is True
            assert callback2_called is True

    async def test_manager_callback_removal(self) -> None:
        """测试回调移除"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            
            config_data = {
                "qbittorrent": {
                    "host": "localhost",
                    "port": 8080,
                    "username": "admin",
                    "password": "adminadmin"
                },
                "check_interval": 1.0
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            manager = ConfigManager(config_path=config_path, auto_reload=False)
            
            callback_called = False
            
            def callback(config: Config) -> None:
                nonlocal callback_called
                callback_called = True
            
            manager.on_change(callback)
            
            # 移除回调
            removed = manager.remove_callback(callback)
            assert removed is True
            
            # 再次移除应该返回 False
            removed = manager.remove_callback(callback)
            assert removed is False
            
            # 修改配置
            config_data["check_interval"] = 5.0
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            # 强制重载
            manager.reload()
            
            # 回调不应该被调用
            assert callback_called is False

    async def test_manager_handles_callback_exception(self) -> None:
        """测试管理器处理回调异常"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            
            config_data = {
                "qbittorrent": {
                    "host": "localhost",
                    "port": 8080,
                    "username": "admin",
                    "password": "adminadmin"
                },
                "check_interval": 1.0
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            manager = ConfigManager(config_path=config_path, auto_reload=False)
            
            good_callback_called = False
            
            def failing_callback(config: Config) -> None:
                raise ValueError("Callback error")
            
            def good_callback(config: Config) -> None:
                nonlocal good_callback_called
                good_callback_called = True
            
            manager.on_change(failing_callback)
            manager.on_change(good_callback)
            
            # 修改配置
            config_data["check_interval"] = 2.0
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            
            # 强制重载（不应该因为异常而失败）
            manager.reload()
            
            # 好的回调应该仍然被调用
            assert good_callback_called is True
