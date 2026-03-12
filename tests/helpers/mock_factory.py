"""Mock 工厂 - 创建各种模拟对象

提供统一的接口创建测试中使用的 Mock 对象。
"""

from __future__ import annotations

import json
from typing import Dict, List, Any, Optional, Callable
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from dataclasses import dataclass

import aiohttp


@dataclass
class MockAIResponse:
    """模拟 AI 响应"""
    category: str
    confidence: float = 0.85


class MockFactory:
    """Mock 工厂类
    
    提供静态方法创建各种测试用的 Mock 对象。
    
    Example:
        >>> from tests.helpers import MockFactory
        >>> mock_client = MockFactory.create_mock_openai_client(["movies", "tv"])
        >>> mock_session = MockFactory.create_mock_aiohttp_response(200, {"success": True})
    """

    @staticmethod
    def create_mock_openai_client(responses: List[str]) -> Mock:
        """创建模拟 OpenAI 客户端
        
        Args:
            responses: AI 响应分类列表，每次调用返回下一个响应
            
        Returns:
            配置好的 Mock 对象
            
        Example:
            >>> client = MockFactory.create_mock_openai_client(["movies", "tv", "anime"])
            >>> # 第一次调用返回 "movies"，第二次返回 "tv"，依此类推
        """
        client = Mock()
        client._responses = responses
        client._call_count = 0
        
        def create_side_effect(*args, **kwargs):
            """创建响应的副作用函数"""
            mock_response = Mock()
            mock_content = Mock()
            
            if client._call_count < len(client._responses):
                mock_content.text = client._responses[client._call_count]
            else:
                mock_content.text = "other"
            
            client._call_count += 1
            mock_response.content = [mock_content]
            return mock_response
        
        # 设置 messages.create 为 Mock
        messages_mock = Mock()
        messages_mock.create = Mock(side_effect=create_side_effect)
        client.messages = messages_mock
        
        return client

    @staticmethod
    def create_mock_openai_client_with_error(error: Exception) -> Mock:
        """创建会抛出异常的模拟 OpenAI 客户端
        
        Args:
            error: 要抛出的异常
            
        Returns:
            配置好的 Mock 对象
        """
        client = Mock()
        messages_mock = Mock()
        messages_mock.create = Mock(side_effect=error)
        client.messages = messages_mock
        return client

    @staticmethod
    def create_mock_aiohttp_response(
        status: int = 200,
        json_data: Optional[Dict[str, Any]] = None,
        text: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncMock:
        """创建模拟 aiohttp 响应对象
        
        Args:
            status: HTTP 状态码
            json_data: JSON 响应数据
            text: 文本响应内容
            headers: 响应头
            
        Returns:
            配置好的 AsyncMock 对象
            
        Example:
            >>> mock_resp = MockFactory.create_mock_aiohttp_response(
            ...     200, {"version": "v4.5.0"}
            ... )
        """
        response = AsyncMock()
        response.status = status
        response.headers = headers or {}
        
        # 设置 json() 方法
        if json_data is not None:
            response.json = AsyncMock(return_value=json_data)
        else:
            response.json = AsyncMock(return_value={})
        
        # 设置 text() 方法
        response.text = AsyncMock(return_value=text or json.dumps(json_data or {}))
        
        # 设置 read() 方法
        response.read = AsyncMock(return_value=text.encode() if text else b"")
        
        return response

    @staticmethod
    def create_mock_aiohttp_session(
        responses: Optional[Dict[str, Any]] = None,
        default_status: int = 200,
    ) -> AsyncMock:
        """创建模拟 aiohttp ClientSession
        
        Args:
            responses: URL 到响应的映射字典
            default_status: 默认状态码
            
        Returns:
            配置好的 AsyncMock 对象
            
        Example:
            >>> responses = {
            ...     "/auth/login": {"status": 200, "text": "Ok."},
            ...     "/app/version": {"status": 200, "text": "v4.5.0"},
            ... }
            >>> session = MockFactory.create_mock_aiohttp_session(responses)
        """
        session = AsyncMock()
        responses = responses or {}
        
        async def mock_get(url: str, **kwargs) -> AsyncMock:
            """模拟 GET 请求"""
            # 从 URL 中提取路径
            path = url.split("/api/v2")[-1] if "/api/v2" in url else url
            
            response_data = responses.get(path, {})
            status = response_data.get("status", default_status)
            json_data = response_data.get("json")
            text = response_data.get("text", "")
            
            return MockFactory.create_mock_aiohttp_response(status, json_data, text)
        
        async def mock_post(url: str, **kwargs) -> AsyncMock:
            """模拟 POST 请求"""
            path = url.split("/api/v2")[-1] if "/api/v2" in url else url
            
            response_data = responses.get(path, {})
            status = response_data.get("status", default_status)
            json_data = response_data.get("json")
            text = response_data.get("text", "")
            
            return MockFactory.create_mock_aiohttp_response(status, json_data, text)
        
        session.get = mock_get
        session.post = mock_post
        session.close = AsyncMock()
        
        # 支持 async with 语法
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        
        return session

    @staticmethod
    def create_mock_qbittorrent_client(
        categories: Optional[Dict[str, Any]] = None,
        version: str = "v4.5.0",
        login_success: bool = True,
        add_torrent_success: bool = True,
    ) -> Mock:
        """创建模拟 qBittorrent 客户端
        
        Args:
            categories: 分类字典
            version: qBittorrent 版本
            login_success: 登录是否成功
            add_torrent_success: 添加种子是否成功
            
        Returns:
            配置好的 Mock 对象
            
        Example:
            >>> categories = {
            ...     "movies": {"savePath": "/downloads/movies"},
            ...     "tv": {"savePath": "/downloads/tv"},
            ... }
            >>> client = MockFactory.create_mock_qbittorrent_client(categories)
        """
        client = Mock()
        
        # 设置属性
        client._is_authenticated = login_success
        
        # 设置异步方法
        client._login = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        
        client.login = AsyncMock(return_value=login_success)
        client.get_version = AsyncMock(return_value=version)
        client.get_categories = AsyncMock(return_value=categories or {})
        client.add_torrent = AsyncMock(return_value=add_torrent_success)
        client.create_category = AsyncMock(return_value=True)
        client.ensure_categories = AsyncMock()
        
        return client

    @staticmethod
    def create_mock_classifier(
        classifications: Optional[Dict[str, str]] = None,
        default_category: str = "other",
    ) -> Mock:
        """创建模拟分类器
        
        Args:
            classifications: 名称到分类的映射
            default_category: 默认分类
            
        Returns:
            配置好的 Mock 对象
        """
        from qbittorrent_monitor.classifier import ClassificationResult
        
        classifier = Mock()
        classifications = classifications or {}
        
        async def mock_classify(name: str, **kwargs) -> ClassificationResult:
            """模拟分类"""
            for key, category in classifications.items():
                if key.lower() in name.lower():
                    return ClassificationResult(
                        category=category,
                        confidence=0.85,
                        method="mock"
                    )
            
            return ClassificationResult(
                category=default_category,
                confidence=0.30,
                method="fallback"
            )
        
        classifier.classify = mock_classify
        classifier.classify_batch = AsyncMock(return_value=[])
        classifier.get_cache_stats = Mock(return_value={
            "size": 0,
            "capacity": 1000,
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0,
        })
        classifier.clear_cache = Mock()
        
        return classifier

    @staticmethod
    def create_mock_database_manager() -> Mock:
        """创建模拟数据库管理器
        
        Returns:
            配置好的 Mock 对象
        """
        db = Mock()
        
        db.initialize = AsyncMock()
        db.close = AsyncMock()
        db.record_torrent = AsyncMock()
        db.get_torrent_by_hash = AsyncMock(return_value=None)
        db.get_recent_torrents = AsyncMock(return_value=[])
        db.export_to_json = AsyncMock(return_value=0)
        db.export_to_csv = AsyncMock(return_value=0)
        db.cleanup_old_records = AsyncMock(return_value={"deleted": 0})
        db.log_event = AsyncMock()
        
        return db

    @staticmethod
    def create_mock_clipboard(content: str = "") -> Mock:
        """创建模拟剪贴板
        
        Args:
            content: 剪贴板内容
            
        Returns:
            配置好的 Mock 对象
        """
        clipboard = Mock()
        clipboard._content = content
        clipboard.paste = Mock(return_value=content)
        clipboard.copy = Mock()
        return clipboard

    @staticmethod
    def create_mock_config_manager(
        config_data: Optional[Dict[str, Any]] = None,
    ) -> Mock:
        """创建模拟配置管理器
        
        Args:
            config_data: 配置数据
            
        Returns:
            配置好的 Mock 对象
        """
        from qbittorrent_monitor.config import Config, QBConfig, AIConfig, CategoryConfig
        
        manager = Mock()
        
        if config_data:
            config = Config.from_dict(config_data)
        else:
            config = Config(
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
                },
            )
        
        manager.get_config = Mock(return_value=config)
        manager.reload = Mock(return_value=config)
        manager.on_change = Mock()
        manager.remove_callback = Mock(return_value=True)
        
        return manager

    @staticmethod
    def create_patch(
        target: str,
        return_value: Any = None,
        side_effect: Optional[Callable] = None,
    ) -> Any:
        """创建 patch 装饰器
        
        Args:
            target: 要 patch 的目标路径
            return_value: 返回值
            side_effect: 副作用函数
            
        Returns:
            patch 对象
            
        Example:
            >>> with MockFactory.create_patch("module.function", return_value=42):
            ...     result = module.function()
        """
        return patch(target, return_value=return_value, side_effect=side_effect)


class AsyncTestHelper:
    """异步测试辅助类"""

    @staticmethod
    async def run_coroutine(coro):
        """运行协程并返回结果"""
        return await coro

    @staticmethod
    def run_sync(coro):
        """同步运行异步协程"""
        return asyncio.get_event_loop().run_until_complete(coro)

    @staticmethod
    async def wait_for_condition(
        condition: Callable[[], bool],
        timeout: float = 5.0,
        interval: float = 0.1,
    ) -> bool:
        """等待条件满足
        
        Args:
            condition: 条件函数
            timeout: 超时时间
            interval: 检查间隔
            
        Returns:
            条件是否在超时前满足
        """
        import asyncio
        
        elapsed = 0.0
        while elapsed < timeout:
            if condition():
                return True
            await asyncio.sleep(interval)
            elapsed += interval
        
        return False
