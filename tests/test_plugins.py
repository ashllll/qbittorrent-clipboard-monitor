"""插件系统测试"""

import asyncio
import json
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from qbittorrent_monitor.plugins import (
    BasePlugin,
    NotifierPlugin,
    ClassifierPlugin,
    HandlerPlugin,
    PluginManager,
    PluginMetadata,
    PluginState,
    PluginType,
    HookRegistry,
    HookType,
    register_hook,
    invoke_hooks,
)
from qbittorrent_monitor.plugins.base import ClassificationResult, HandlerResult


# ==================== 测试插件类 ====================

class TestPlugin(BasePlugin):
    """测试用基础插件"""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="测试插件",
            author="Test",
            plugin_type=PluginType.CUSTOM
        )
    
    async def initialize(self) -> bool:
        return True
    
    async def shutdown(self) -> None:
        pass


class FailingPlugin(BasePlugin):
    """会失败的测试插件"""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="failing_plugin",
            version="1.0.0",
            plugin_type=PluginType.CUSTOM
        )
    
    async def initialize(self) -> bool:
        raise RuntimeError("初始化失败")
    
    async def shutdown(self) -> None:
        pass


class TestNotifier(NotifierPlugin):
    """测试通知插件"""
    
    def __init__(self):
        super().__init__()
        self.notifications = []
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test_notifier",
            version="1.0.0",
            plugin_type=PluginType.NOTIFIER,
            config_schema={
                "endpoint": {"type": "string", "required": True}
            }
        )
    
    async def notify(self, title: str, message: str, **kwargs) -> bool:
        self.notifications.append({"title": title, "message": message, **kwargs})
        return True


class TestClassifier(ClassifierPlugin):
    """测试分类器插件"""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test_classifier",
            version="1.0.0",
            plugin_type=PluginType.CLASSIFIER
        )
    
    async def classify(self, name: str, **kwargs) -> ClassificationResult:
        if "movie" in name.lower():
            return ClassificationResult("movies", 0.9, "test")
        return ClassificationResult("other", 0.5, "test")


class TestHandler(HandlerPlugin):
    """测试处理器插件"""
    
    def __init__(self):
        super().__init__()
        self.handled = []
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test_handler",
            version="1.0.0",
            plugin_type=PluginType.HANDLER
        )
    
    async def can_handle(self, content: str, **kwargs) -> bool:
        return content.startswith("test://")
    
    async def handle(self, content: str, **kwargs) -> HandlerResult:
        self.handled.append(content)
        return HandlerResult(success=True, message="处理成功", data={"content": content})


# ==================== 基础插件测试 ====================

class TestBasePlugin:
    """测试基础插件功能"""
    
    def test_plugin_metadata(self):
        """测试插件元数据"""
        plugin = TestPlugin()
        
        assert plugin.metadata.name == "test_plugin"
        assert plugin.metadata.version == "1.0.0"
        assert plugin.metadata.plugin_type == PluginType.CUSTOM
    
    def test_plugin_initial_state(self):
        """测试插件初始状态"""
        plugin = TestPlugin()
        
        assert plugin.state == PluginState.UNLOADED
        assert not plugin.is_enabled
        assert plugin.name == "test_plugin"
    
    def test_plugin_configure(self):
        """测试插件配置"""
        plugin = TestPlugin()
        
        errors = plugin.configure({"key": "value"})
        
        assert len(errors) == 0
        assert plugin.config["key"] == "value"
    
    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self):
        """测试插件生命周期"""
        plugin = TestPlugin()
        
        # 启用
        success = await plugin.enable()
        assert success
        assert plugin.state == PluginState.ENABLED
        assert plugin.is_enabled
        
        # 禁用
        success = await plugin.disable()
        assert success
        assert plugin.state == PluginState.DISABLED
        assert not plugin.is_enabled
    
    @pytest.mark.asyncio
    async def test_plugin_enable_failure(self):
        """测试插件启用失败"""
        plugin = FailingPlugin()
        
        success = await plugin.enable()
        
        assert not success
        assert plugin.state == PluginState.ERROR
    
    def test_plugin_get_info(self):
        """测试获取插件信息"""
        plugin = TestPlugin()
        
        info = plugin.get_info()
        
        assert info["name"] == "test_plugin"
        assert info["version"] == "1.0.0"
        assert info["type"] == "custom"
        assert not info["is_enabled"]


# ==================== 通知插件测试 ====================

class TestNotifierPlugin:
    """测试通知插件功能"""
    
    @pytest.mark.asyncio
    async def test_notify(self):
        """测试基础通知功能"""
        plugin = TestNotifier()
        await plugin.enable()
        
        success = await plugin.notify("测试标题", "测试消息")
        
        assert success
        assert len(plugin.notifications) == 1
        assert plugin.notifications[0]["title"] == "测试标题"
    
    @pytest.mark.asyncio
    async def test_notify_download_complete(self):
        """测试下载完成通知"""
        plugin = TestNotifier()
        await plugin.enable()
        
        success = await plugin.notify_download_complete(
            torrent_name="Test.Movie.2024",
            category="movies",
            save_path="/downloads/movies"
        )
        
        assert success
        assert len(plugin.notifications) == 1
        assert "Test.Movie.2024" in plugin.notifications[0]["title"]
    
    @pytest.mark.asyncio
    async def test_notify_error(self):
        """测试错误通知"""
        plugin = TestNotifier()
        await plugin.enable()
        
        success = await plugin.notify_error("出错了", {"code": 500})
        
        assert success
        assert "错误" in plugin.notifications[0]["title"]


# ==================== 分类器插件测试 ====================

class TestClassifierPlugin:
    """测试分类器插件功能"""
    
    @pytest.mark.asyncio
    async def test_classify(self):
        """测试分类功能"""
        plugin = TestClassifier()
        await plugin.enable()
        
        result = await plugin.classify("A Great Movie 2024")
        
        assert result.category == "movies"
        assert result.confidence == 0.9
        assert result.method == "test"
    
    @pytest.mark.asyncio
    async def test_classify_other(self):
        """测试其他分类"""
        plugin = TestClassifier()
        await plugin.enable()
        
        result = await plugin.classify("Some Random Content")
        
        assert result.category == "other"


# ==================== 处理器插件测试 ====================

class TestHandlerPlugin:
    """测试处理器插件功能"""
    
    @pytest.mark.asyncio
    async def test_can_handle(self):
        """测试处理能力检查"""
        plugin = TestHandler()
        await plugin.enable()
        
        assert await plugin.can_handle("test://something")
        assert not await plugin.can_handle("http://example.com")
    
    @pytest.mark.asyncio
    async def test_handle(self):
        """测试处理功能"""
        plugin = TestHandler()
        await plugin.enable()
        
        result = await plugin.handle("test://data")
        
        assert result.success
        assert "处理成功" in result.message
        assert result.data["content"] == "test://data"


# ==================== 插件元数据测试 ====================

class TestPluginMetadata:
    """测试插件元数据"""
    
    def test_validate_config_valid(self):
        """测试配置验证通过"""
        metadata = PluginMetadata(
            name="test",
            config_schema={
                "required_key": {"type": "string", "required": True},
                "optional_key": {"type": "integer", "required": False}
            }
        )
        
        errors = metadata.validate_config({
            "required_key": "value",
            "optional_key": 42
        })
        
        assert len(errors) == 0
    
    def test_validate_config_missing_required(self):
        """测试缺少必需配置"""
        metadata = PluginMetadata(
            name="test",
            config_schema={
                "required_key": {"type": "string", "required": True}
            }
        )
        
        errors = metadata.validate_config({})
        
        assert len(errors) == 1
        assert "required_key" in errors[0]
    
    def test_validate_config_wrong_type(self):
        """测试配置类型错误"""
        metadata = PluginMetadata(
            name="test",
            config_schema={
                "number_key": {"type": "integer", "required": True}
            }
        )
        
        errors = metadata.validate_config({"number_key": "not a number"})
        
        assert len(errors) == 1
        assert "integer" in errors[0]
    
    def test_validate_config_enum(self):
        """测试枚举配置验证"""
        metadata = PluginMetadata(
            name="test",
            config_schema={
                "level": {"type": "string", "enum": ["low", "medium", "high"]}
            }
        )
        
        errors_valid = metadata.validate_config({"level": "medium"})
        errors_invalid = metadata.validate_config({"level": "invalid"})
        
        assert len(errors_valid) == 0
        assert len(errors_invalid) == 1


# ==================== 钩子系统测试 ====================

class TestHookRegistry:
    """测试钩子系统"""
    
    def setup_method(self):
        """每个测试前重置钩子注册表"""
        registry = HookRegistry()
        registry.clear()
    
    @pytest.mark.asyncio
    async def test_register_and_invoke(self):
        """测试注册和调用钩子"""
        registry = HookRegistry()
        registry.clear()
        
        called = []
        
        @registry.register(HookType.PRE_DOWNLOAD)
        async def my_hook(data):
            called.append(data)
            return f"processed_{data}"
        
        results = await registry.invoke(HookType.PRE_DOWNLOAD, "test_data")
        
        assert len(called) == 1
        assert called[0] == "test_data"
        assert results[0] == "processed_test_data"
    
    @pytest.mark.asyncio
    async def test_hook_priority(self):
        """测试钩子优先级"""
        registry = HookRegistry()
        registry.clear()
        
        from qbittorrent_monitor.plugins.hooks import HookPriority
        
        order = []
        
        @registry.register(HookType.POST_DOWNLOAD, priority=HookPriority.LOW)
        async def low_priority(data):
            order.append("low")
        
        @registry.register(HookType.POST_DOWNLOAD, priority=HookPriority.HIGH)
        async def high_priority(data):
            order.append("high")
        
        @registry.register(HookType.POST_DOWNLOAD, priority=HookPriority.NORMAL)
        async def normal_priority(data):
            order.append("normal")
        
        await registry.invoke(HookType.POST_DOWNLOAD, "test")
        
        assert order == ["high", "normal", "low"]
    
    @pytest.mark.asyncio
    async def test_invoke_filter(self):
        """测试过滤钩子链"""
        registry = HookRegistry()
        registry.clear()
        
        @registry.register(HookType.PRE_CLASSIFY)
        async def add_prefix(name):
            return f"prefix_{name}"
        
        @registry.register(HookType.PRE_CLASSIFY)
        async def add_suffix(name):
            return f"{name}_suffix"
        
        result = await registry.invoke_filter(HookType.PRE_CLASSIFY, "test")
        
        assert result == "prefix_test_suffix"
    
    @pytest.mark.asyncio
    async def test_unregister(self):
        """测试注销钩子"""
        registry = HookRegistry()
        registry.clear()
        
        async def my_hook(data):
            return "called"
        
        registry.register(HookType.PRE_NOTIFY)(my_hook)
        
        # 注销前
        results_before = await registry.invoke(HookType.PRE_NOTIFY, "test")
        assert len(results_before) == 1
        
        # 注销
        count = registry.unregister(HookType.PRE_NOTIFY, my_hook)
        assert count == 1
        
        # 注销后
        results_after = await registry.invoke(HookType.PRE_NOTIFY, "test")
        assert len(results_after) == 0
    
    def test_get_stats(self):
        """测试获取统计信息"""
        registry = HookRegistry()
        registry.clear()
        
        @registry.register(HookType.PRE_DOWNLOAD)
        async def hook1(data): pass
        
        @registry.register(HookType.POST_DOWNLOAD)
        async def hook2(data): pass
        
        stats = registry.get_stats()
        
        assert stats["total"] == 2
        assert stats["pre_process"] == 0
        assert stats["pre_download"] == 1
        assert stats["post_download"] == 1


# ==================== 插件管理器测试 ====================

class TestPluginManager:
    """测试插件管理器"""
    
    @pytest.fixture
    async def manager(self, tmp_path):
        """创建测试用的插件管理器"""
        plugins_dir = tmp_path / "plugins"
        config_dir = tmp_path / "config"
        plugins_dir.mkdir()
        config_dir.mkdir()
        
        manager = PluginManager(
            plugins_dir=plugins_dir,
            config_dir=config_dir,
            auto_discover=False
        )
        
        yield manager
        
        # 清理
        await manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_add_and_get_plugin(self, manager):
        """测试添加和获取插件"""
        plugin = TestPlugin()
        manager._plugins[plugin.name] = plugin
        manager._states[plugin.name] = PluginState.LOADED
        
        retrieved = manager.get_plugin("test_plugin")
        
        assert retrieved == plugin
    
    @pytest.mark.asyncio
    async def test_get_plugins_by_type(self, manager):
        """测试按类型获取插件"""
        notifier = TestNotifier()
        classifier = TestClassifier()
        
        manager._plugins[notifier.name] = notifier
        manager._plugins[classifier.name] = classifier
        
        notifiers = manager.get_plugins_by_type(PluginType.NOTIFIER)
        classifiers = manager.get_plugins_by_type(PluginType.CLASSIFIER)
        
        assert len(notifiers) == 1
        assert len(classifiers) == 1
        assert notifiers[0].name == "test_notifier"
    
    @pytest.mark.asyncio
    async def test_enable_disable_plugin(self, manager):
        """测试启用和禁用插件"""
        plugin = TestPlugin()
        manager._plugins[plugin.name] = plugin
        manager._states[plugin.name] = PluginState.LOADED
        
        # 启用
        success = await manager.enable_plugin("test_plugin")
        assert success
        assert plugin.is_enabled
        
        # 禁用
        success = await manager.disable_plugin("test_plugin")
        assert success
        assert not plugin.is_enabled
    
    @pytest.mark.asyncio
    async def test_enable_nonexistent_plugin(self, manager):
        """测试启用不存在的插件"""
        success = await manager.enable_plugin("nonexistent")
        assert not success
    
    @pytest.mark.asyncio
    async def test_configure_plugin(self, manager):
        """测试配置插件"""
        plugin = TestNotifier()
        manager._plugins[plugin.name] = plugin
        
        errors = manager.configure_plugin("test_notifier", {
            "endpoint": "https://example.com/webhook"
        })
        
        assert len(errors) == 0
        assert plugin.config["endpoint"] == "https://example.com/webhook"
    
    @pytest.mark.asyncio
    async def test_notify_all(self, manager):
        """测试通知所有插件"""
        notifier1 = TestNotifier()
        notifier2 = TestNotifier()
        
        manager._plugins[notifier1.name] = notifier1
        manager._plugins[notifier2.name] = notifier2
        manager._states[notifier1.name] = PluginState.ENABLED
        manager._states[notifier2.name] = PluginState.ENABLED
        
        # 手动设置启用状态
        notifier1._state = PluginState.ENABLED
        notifier2._state = PluginState.ENABLED
        
        results = await manager.notify_all("测试", "消息")
        
        assert len(results) == 2
        assert all(results.values())
    
    @pytest.mark.asyncio
    async def test_get_stats(self, manager):
        """测试获取统计信息"""
        plugin = TestPlugin()
        manager._plugins[plugin.name] = plugin
        manager._states[plugin.name] = PluginState.LOADED
        
        stats = manager.get_stats()
        
        assert stats["total"] == 1
        assert stats["enabled"] == 0
        assert stats["disabled"] == 1


# ==================== 集成测试 ====================

class TestPluginIntegration:
    """插件系统集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流程"""
        # 创建插件管理器
        manager = PluginManager(auto_discover=False)
        
        try:
            # 创建并注册插件
            notifier = TestNotifier()
            classifier = TestClassifier()
            
            manager._plugins[notifier.name] = notifier
            manager._plugins[classifier.name] = classifier
            manager._states[notifier.name] = PluginState.LOADED
            manager._states[classifier.name] = PluginState.LOADED
            
            # 启用插件
            await manager.enable_plugin("test_notifier")
            await manager.enable_plugin("test_classifier")
            
            # 测试分类
            result = await classifier.classify("Action Movie 2024")
            assert result.category == "movies"
            
            # 测试通知
            await notifier.notify("分类完成", f"分类结果: {result.category}")
            assert len(notifier.notifications) == 1
            
        finally:
            await manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_hooks_with_plugins(self):
        """测试插件与钩子系统集成"""
        registry = HookRegistry()
        registry.clear()
        
        events = []
        
        @registry.register(HookType.PRE_DOWNLOAD)
        async def log_pre_download(url):
            events.append(("pre", url))
        
        @registry.register(HookType.POST_DOWNLOAD)
        async def log_post_download(result):
            events.append(("post", result))
        
        # 模拟下载流程
        await registry.invoke(HookType.PRE_DOWNLOAD, "magnet:?xt=urn:btih:test")
        await registry.invoke(HookType.POST_DOWNLOAD, {"success": True})
        
        assert len(events) == 2
        assert events[0] == ("pre", "magnet:?xt=urn:btih:test")
        assert events[1] == ("post", {"success": True})


# ==================== 异常处理测试 ====================

class TestPluginExceptions:
    """测试异常处理"""
    
    @pytest.mark.asyncio
    async def test_hook_error_handling(self):
        """测试钩子错误处理"""
        registry = HookRegistry()
        registry.clear()
        
        @registry.register(HookType.PRE_DOWNLOAD)
        async def failing_hook(data):
            raise RuntimeError("钩子错误")
        
        @registry.register(HookType.PRE_DOWNLOAD)
        async def success_hook(data):
            return "success"
        
        # stop_on_error=False 应该继续执行
        results = await registry.invoke(HookType.PRE_DOWNLOAD, "test", stop_on_error=False)
        
        # 失败的钩子不会返回结果
        assert len(results) == 1
        assert results[0] == "success"
    
    @pytest.mark.asyncio
    async def test_plugin_error_state(self):
        """测试插件错误状态"""
        plugin = FailingPlugin()
        
        result = await plugin.enable()
        
        assert not result
        assert plugin.state == PluginState.ERROR
        
        # 错误状态的插件不能再次启用
        result = await plugin.enable()
        assert not result


# ==================== 内置插件测试 ====================

class TestBuiltinPlugins:
    """测试内置插件"""
    
    @pytest.mark.asyncio
    async def test_webhook_notifier_config(self):
        """测试 Webhook 通知插件配置验证"""
        from qbittorrent_monitor.plugins.notifiers.webhook import WebhookNotifier
        
        plugin = WebhookNotifier()
        
        # 缺少必需配置
        errors = plugin.configure({})
        assert len(errors) == 1  # url 是必需的
        
        # 正确配置
        errors = plugin.configure({
            "url": "https://example.com/webhook",
            "timeout": 30
        })
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_dingtalk_notifier_config(self):
        """测试钉钉通知插件配置验证"""
        from qbittorrent_monitor.plugins.notifiers.dingtalk import DingTalkNotifier
        
        plugin = DingTalkNotifier()
        
        # 缺少必需配置
        errors = plugin.configure({})
        assert len(errors) == 1  # webhook_url 是必需的
        
        # 正确配置
        errors = plugin.configure({
            "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=test",
            "secret": "SECtest"
        })
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_local_ai_classifier_config(self):
        """测试本地 AI 分类器配置"""
        from qbittorrent_monitor.plugins.classifiers.local_ai import LocalAIClassifier
        
        plugin = LocalAIClassifier()
        
        # 所有配置都是可选的
        errors = plugin.configure({})
        assert len(errors) == 0
        
        # 带配置
        errors = plugin.configure({
            "base_url": "http://localhost:11434",
            "model": "llama2",
            "categories": ["movies", "tv", "anime"]
        })
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_rss_handler_config(self):
        """测试 RSS 处理器配置"""
        from qbittorrent_monitor.plugins.handlers.rss_feed import RSSFeedHandler
        
        plugin = RSSFeedHandler()
        
        # feeds 是必需的
        errors = plugin.configure({})
        assert len(errors) == 1
        
        # 正确配置
        errors = plugin.configure({
            "feeds": [
                {"url": "https://example.com/rss", "category": "movies"}
            ],
            "check_interval": 60
        })
        assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
