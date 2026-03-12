"""qBittorrent 客户端单元测试

测试 QBClient 的连接、认证和 API 调用功能。
"""

from __future__ import annotations

import asyncio
import pytest
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock

import aiohttp

from qbittorrent_monitor.qb_client import (
    QBClient,
    QBAPIError,
    APIErrorType,
    with_retry,
)
from qbittorrent_monitor.config import Config, QBConfig, AIConfig, CategoryConfig


# ============================================================================
# TestQBClientBasics - QBClient 基础测试
# ============================================================================

class TestQBClientBasics:
    """QBClient 基础测试"""

    @pytest.fixture
    def qb_config(self) -> Config:
        """QB 配置 fixture"""
        return Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin",
                use_https=False
            ),
            ai=AIConfig(enabled=False),
        )

    def test_client_initialization(self, qb_config: Config) -> None:
        """测试客户端初始化"""
        client = QBClient(qb_config)
        
        assert client.config == qb_config
        assert client.qb_config == qb_config.qbittorrent
        assert client.base_url == "http://localhost:8080"
        assert client._is_authenticated is False

    def test_client_https(self) -> None:
        """测试 HTTPS 配置"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin",
                use_https=True
            ),
            ai=AIConfig(enabled=False),
        )
        
        client = QBClient(config)
        
        assert client.base_url == "https://localhost:8080"

    def test_build_base_url(self, qb_config: Config) -> None:
        """测试构建基础 URL"""
        client = QBClient(qb_config)
        
        assert client._build_base_url() == "http://localhost:8080"

    def test_get_full_url(self, qb_config: Config) -> None:
        """测试获取完整 API URL"""
        client = QBClient(qb_config)
        
        url = client._get_full_url("/auth/login")
        
        assert url == "http://localhost:8080/api/v2/auth/login"


# ============================================================================
# TestQBClientAuthentication - 认证测试
# ============================================================================

class TestQBClientAuthentication:
    """认证测试"""

    @pytest.fixture
    def qb_config(self) -> Config:
        """QB 配置 fixture"""
        return Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin",
                use_https=False
            ),
            ai=AIConfig(enabled=False),
        )

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """模拟 aiohttp 会话"""
        session = AsyncMock()
        
        # 默认成功响应
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="Ok.")
        mock_response.json = AsyncMock(return_value={})
        
        session.post = AsyncMock(return_value=mock_response)
        session.get = AsyncMock(return_value=mock_response)
        session.close = AsyncMock()
        
        return session

    async def test_login_success(self, qb_config: Config, mock_session: AsyncMock) -> None:
        """测试登录成功"""
        client = QBClient(qb_config)
        
        with patch.object(client, '_create_session', return_value=mock_session):
            client.session = mock_session
            await client._login()
            
            assert client._is_authenticated is True

    async def test_login_failure_wrong_credentials(self, qb_config: Config) -> None:
        """测试登录失败 - 错误凭据"""
        client = QBClient(qb_config)
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="Fails.")
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        
        with patch.object(client, '_create_session', return_value=mock_session):
            client.session = mock_session
            
            from qbittorrent_monitor.exceptions import QBAuthError
            with pytest.raises(QBAuthError):
                await client._login()

    async def test_login_failure_unauthorized(self, qb_config: Config) -> None:
        """测试登录失败 - 未授权"""
        client = QBClient(qb_config)
        
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        
        with patch.object(client, '_create_session', return_value=mock_session):
            client.session = mock_session
            
            with pytest.raises(QBAPIError) as exc_info:
                await client._login()
            
            assert exc_info.value.error_type == APIErrorType.AUTH_ERROR

    async def test_login_connection_error(self, qb_config: Config) -> None:
        """测试登录连接错误"""
        client = QBClient(qb_config)
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(side_effect=aiohttp.ClientConnectorError(
            connection_key=Mock(),
            os_error=OSError("Connection refused")
        ))
        
        with patch.object(client, '_create_session', return_value=mock_session):
            client.session = mock_session
            
            from qbittorrent_monitor.exceptions import QBConnectionError
            with pytest.raises(QBConnectionError):
                await client._login()

    async def test_login_timeout(self, qb_config: Config) -> None:
        """测试登录超时"""
        client = QBClient(qb_config)
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(side_effect=asyncio.TimeoutError())
        
        with patch.object(client, '_create_session', return_value=mock_session):
            client.session = mock_session
            
            from qbittorrent_monitor.exceptions import QBConnectionError
            with pytest.raises(QBConnectionError):
                await client._login()

    async def test_context_manager(self, qb_config: Config, mock_session: AsyncMock) -> None:
        """测试上下文管理器"""
        client = QBClient(qb_config)
        
        with patch.object(client, '_create_session', return_value=mock_session):
            async with client as c:
                assert c._is_authenticated is True
            
            # 退出后应该关闭会话
            assert client.session is None
            assert client._is_authenticated is False

    async def test_ensure_authenticated(self, qb_config: Config, mock_session: AsyncMock) -> None:
        """测试确保认证"""
        client = QBClient(qb_config)
        
        with patch.object(client, '_create_session', return_value=mock_session):
            client.session = mock_session
            client._is_authenticated = False
            
            await client._ensure_authenticated()
            
            assert client._is_authenticated is True


# ============================================================================
# TestQBClientAPI - API 调用测试
# ============================================================================

class TestQBClientAPI:
    """API 调用测试"""

    @pytest.fixture
    def qb_config(self) -> Config:
        """QB 配置 fixture"""
        return Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin",
                use_https=False
            ),
            ai=AIConfig(enabled=False),
        )

    @pytest.fixture
    def authenticated_client(self, qb_config: Config) -> QBClient:
        """已认证的客户端"""
        client = QBClient(qb_config)
        client._is_authenticated = True
        return client

    async def test_get_version_success(self, authenticated_client: QBClient) -> None:
        """测试获取版本成功"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="v4.5.0")
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        authenticated_client.session = mock_session
        
        version = await authenticated_client.get_version()
        
        assert version == "v4.5.0"

    async def test_get_version_failure(self, authenticated_client: QBClient) -> None:
        """测试获取版本失败"""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=Exception("Network error"))
        authenticated_client.session = mock_session
        
        version = await authenticated_client.get_version()
        
        assert version == "unknown"

    async def test_add_torrent_success(self, authenticated_client: QBClient) -> None:
        """测试添加种子成功"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="Ok.")
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        authenticated_client.session = mock_session
        
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Test"
        success = await authenticated_client.add_torrent(magnet, category="movies")
        
        assert success is True

    async def test_add_torrent_with_save_path(self, authenticated_client: QBClient) -> None:
        """测试添加种子带保存路径"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="Ok.")
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        authenticated_client.session = mock_session
        
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
        success = await authenticated_client.add_torrent(
            magnet,
            category="movies",
            save_path="/custom/path"
        )
        
        assert success is True
        # 验证调用参数包含 save_path
        call_args = mock_session.post.call_args
        assert call_args is not None

    async def test_add_torrent_invalid_magnet(self, authenticated_client: QBClient) -> None:
        """测试添加无效磁力链接"""
        # 无效的磁力链接（太短 hash）
        magnet = "magnet:?xt=urn:btih:short"
        
        success = await authenticated_client.add_torrent(magnet, category="movies")
        
        assert success is False

    async def test_add_torrent_failure(self, authenticated_client: QBClient) -> None:
        """测试添加种子失败"""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        authenticated_client.session = mock_session
        
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
        success = await authenticated_client.add_torrent(magnet, category="movies")
        
        assert success is False

    async def test_get_categories_success(self, authenticated_client: QBClient) -> None:
        """测试获取分类成功"""
        categories_data = {
            "movies": {"savePath": "/downloads/movies"},
            "tv": {"savePath": "/downloads/tv"},
        }
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=categories_data)
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        authenticated_client.session = mock_session
        
        categories = await authenticated_client.get_categories()
        
        assert categories == categories_data
        assert "movies" in categories

    async def test_get_categories_failure(self, authenticated_client: QBClient) -> None:
        """测试获取分类失败"""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=Exception("Network error"))
        authenticated_client.session = mock_session
        
        categories = await authenticated_client.get_categories()
        
        assert categories == {}

    async def test_create_category_success(self, authenticated_client: QBClient) -> None:
        """测试创建分类成功"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="")
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        authenticated_client.session = mock_session
        
        success = await authenticated_client.create_category("new_cat", "/downloads/new")
        
        assert success is True

    async def test_create_category_failure(self, authenticated_client: QBClient) -> None:
        """测试创建分类失败"""
        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.text = AsyncMock(return_value="Forbidden")
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        authenticated_client.session = mock_session
        
        success = await authenticated_client.create_category("new_cat", "/downloads/new")
        
        assert success is False

    async def test_create_category_invalid_path(self, authenticated_client: QBClient) -> None:
        """测试创建分类无效路径"""
        # 尝试创建带有不安全路径的分类
        success = await authenticated_client.create_category("test", "../../../etc/passwd")
        
        assert success is False

    async def test_ensure_categories(self, authenticated_client: QBClient) -> None:
        """测试确保分类存在"""
        # 设置配置中的分类
        authenticated_client.config.categories = {
            "movies": CategoryConfig(save_path="/downloads/movies"),
            "tv": CategoryConfig(save_path="/downloads/tv"),
        }
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})  # 当前没有分类
        mock_response.text = AsyncMock(return_value="")
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.post = AsyncMock(return_value=mock_response)
        authenticated_client.session = mock_session
        authenticated_client._is_authenticated = True
        
        # 应该创建缺失的分类
        await authenticated_client.ensure_categories()
        
        # 验证调用了创建分类
        assert mock_session.post.called


# ============================================================================
# TestQBClientErrorHandling - 错误处理测试
# ============================================================================

class TestQBClientErrorHandling:
    """错误处理测试"""

    def test_handle_response_error_auth(self) -> None:
        """测试处理认证错误"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
        )
        client = QBClient(config)
        
        mock_response = Mock()
        mock_response.status = 401
        
        with pytest.raises(QBAPIError) as exc_info:
            client._handle_response_error(mock_response, "/test")
        
        assert exc_info.value.error_type == APIErrorType.AUTH_ERROR
        assert exc_info.value.status_code == 401

    def test_handle_response_error_not_found(self) -> None:
        """测试处理 404 错误"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
        )
        client = QBClient(config)
        
        mock_response = Mock()
        mock_response.status = 404
        
        with pytest.raises(QBAPIError) as exc_info:
            client._handle_response_error(mock_response, "/test")
        
        assert exc_info.value.error_type == APIErrorType.API_ERROR
        assert exc_info.value.status_code == 404

    def test_handle_response_error_server(self) -> None:
        """测试处理服务器错误"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
        )
        client = QBClient(config)
        
        mock_response = Mock()
        mock_response.status = 500
        
        with pytest.raises(QBAPIError) as exc_info:
            client._handle_response_error(mock_response, "/test")
        
        assert exc_info.value.error_type == APIErrorType.SERVER_ERROR

    def test_handle_response_error_ok(self) -> None:
        """测试处理成功响应"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
        )
        client = QBClient(config)
        
        mock_response = Mock()
        mock_response.status = 200
        
        # 200 状态码不应该抛出异常
        client._handle_response_error(mock_response, "/test")


# ============================================================================
# TestWithRetryDecorator - 重试装饰器测试
# ============================================================================

class TestWithRetryDecorator:
    """重试装饰器测试"""

    async def test_retry_success(self) -> None:
        """测试重试后成功"""
        call_count = 0
        
        @with_retry(max_retries=3, base_delay=0.01)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise aiohttp.ClientError("Temporary error")
            return "success"
        
        result = await flaky_function()
        
        assert result == "success"
        assert call_count == 3

    async def test_retry_exhausted(self) -> None:
        """测试重试耗尽"""
        @with_retry(max_retries=2, base_delay=0.01)
        async def always_fail():
            raise aiohttp.ClientError("Always fails")
        
        with pytest.raises(aiohttp.ClientError):
            await always_fail()

    async def test_no_retry_on_success(self) -> None:
        """测试成功时不重试"""
        call_count = 0
        
        @with_retry(max_retries=3, base_delay=0.01)
        async def always_succeed():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await always_succeed()
        
        assert result == "success"
        assert call_count == 1

    async def test_retry_with_custom_exceptions(self) -> None:
        """测试自定义异常重试"""
        call_count = 0
        
        @with_retry(max_retries=2, base_delay=0.01, retry_on=(ValueError,))
        async def raise_value_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry me")
            return "success"
        
        result = await raise_value_error()
        
        assert result == "success"
        assert call_count == 2

    async def test_no_retry_on_unexpected_exception(self) -> None:
        """测试不预期的异常不重试"""
        call_count = 0
        
        @with_retry(max_retries=3, base_delay=0.01, retry_on=(ValueError,))
        async def raise_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retried")
        
        with pytest.raises(TypeError):
            await raise_type_error()
        
        assert call_count == 1


# ============================================================================
# TestQBClientIntegration - 集成测试（轻量级）
# ============================================================================

class TestQBClientIntegration:
    """轻量级集成测试"""

    @pytest.fixture
    def full_config(self) -> Config:
        """完整配置"""
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
                    keywords=["1080p", "BluRay"]
                ),
                "tv": CategoryConfig(
                    save_path="/downloads/tv",
                    keywords=["S01", "E01"]
                ),
            },
        )

    def test_client_with_full_config(self, full_config: Config) -> None:
        """测试客户端使用完整配置"""
        client = QBClient(full_config)
        
        assert client.config == full_config
        assert len(client.config.categories) == 2
        assert "movies" in client.config.categories
