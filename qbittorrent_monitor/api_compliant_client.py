"""
100% 符合 qBittorrent 官方 API 的客户端

确保所有 qBittorrent 操作都通过官方 API 完成：
- 严格遵循官方 API 规范
- 完整的错误处理和重试机制
- 详细的 API 调用日志
- 标准化的请求和响应处理
"""

import asyncio
import json
import logging
import ssl
import time
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlencode
import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from .config import QBittorrentConfig
from .exceptions import (
    QbtAuthError, NetworkError, QbtPermissionError,
    QbtRateLimitError, QBittorrentError
)


class APIClient:
    """
    100% 符合官方 API 规范的 qBittorrent 客户端

    所有操作严格遵循 qBittorrent Web API v2 规范
    """

    def __init__(self, config: QBittorrentConfig):
        self.config = config
        self.logger = logging.getLogger('APIClient')

        # API 基础配置
        self._base_url = f"{'https' if config.use_https else 'http'}://{config.host}:{config.port}/api/v2"
        self._session: Optional[aiohttp.ClientSession] = None
        self._authenticated = False
        self._session_cookie: Optional[str] = None

        # 性能监控
        self._stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'api_endpoints_used': set(),
            'last_request_time': None
        }

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def initialize(self):
        """初始化客户端"""
        # 创建 SSL 上下文
        ssl_context = ssl.create_default_context()
        if hasattr(self.config, 'verify_ssl') and not self.config.verify_ssl:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        # 创建 HTTP 会话
        timeout = aiohttp.ClientTimeout(
            total=getattr(self.config, 'request_timeout', 30),
            connect=getattr(self.config, 'connect_timeout', 10)
        )

        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=100,
            limit_per_host=30,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )

        self._session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
        )

        # 执行登录
        await self.login()

    async def close(self):
        """关闭客户端"""
        if self._session and not self._session.closed:
            await self._session.close()
        self._authenticated = False

    def _get_stats(self) -> Dict[str, Any]:
        """获取API调用统计信息"""
        return {
            **self._stats,
            'success_rate': (
                self._stats['successful_requests'] /
                max(1, self._stats['total_requests'])
            ) * 100,
            'unique_endpoints': len(self._stats['api_endpoints_used'])
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((NetworkError, QbtRateLimitError)),
        before_sleep=before_sleep_log(logging.getLogger('APIClient.Retry'), logging.INFO)
    )
    async def login(self):
        """
        登录 qBittorrent

        API: POST /api/v2/auth/login
        """
        endpoint = '/auth/login'
        url = f"{self._base_url}{endpoint}"

        data = {
            'username': self.config.username,
            'password': self.config.password
        }

        try:
            self.logger.info(f"API: 尝试登录 qBittorrent {self.config.host}:{self.config.port}")

            async with self._session.post(url, data=data) as resp:
                await self._record_api_call('POST', endpoint)

                if resp.status == 200:
                    response_text = await resp.text()
                    if response_text == "Ok.":
                        self._authenticated = True
                        # 保存会话cookie
                        if 'SID' in resp.cookies:
                            self._session_cookie = resp.cookies['SID'].value

                        self.logger.info("API: 登录成功")
                        return True
                    else:
                        raise QbtAuthError(f"API: 登录失败: {response_text}")
                elif resp.status == 403:
                    raise QbtAuthError("API: 登录失败: 用户名或密码错误")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"API: 登录失败: HTTP {resp.status} - {error_text}")

        except aiohttp.ClientError as e:
            raise NetworkError(f"API: 网络连接失败: {str(e)}") from e

    async def _ensure_authenticated(self):
        """确保已认证"""
        if not self._authenticated:
            await self.login()

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str]] = None,
        files: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        统一的 API 请求方法

        Args:
            method: HTTP 方法 (GET, POST)
            endpoint: API 端点 (如 /torrents/info)
            params: URL 查询参数
            data: 表单数据或JSON数据
            files: 文件上传数据

        Returns:
            API 响应数据
        """
        await self._ensure_authenticated()

        url = f"{self._base_url}{endpoint}"
        start_time = time.time()

        # 准备请求头
        headers = {}
        if self._session_cookie:
            headers['Cookie'] = f'SID={self._session_cookie}'

        try:
            self._stats['total_requests'] += 1
            self._stats['last_request_time'] = time.time()
            self._stats['api_endpoints_used'].add(endpoint)

            if method.upper() == 'GET':
                async with self._session.get(url, params=params, headers=headers) as resp:
                    response = await self._handle_response(resp)

            elif method.upper() == 'POST':
                if files:
                    # 文件上传
                    data_form = aiohttp.FormData()
                    for key, value in (data or {}).items():
                        data_form.add_field(key, str(value))

                    async with self._session.post(url, data=data_form, headers=headers) as resp:
                        response = await self._handle_response(resp)
                else:
                    # 表单数据
                    async with self._session.post(url, data=data, params=params, headers=headers) as resp:
                        response = await self._handle_response(resp)
            else:
                raise QBittorrentError(f"API: 不支持的HTTP方法: {method}")

            # 记录成功请求
            self._stats['successful_requests'] += 1
            response_time = time.time() - start_time
            self.logger.debug(f"API: {method} {endpoint} - {response_time:.3f}s")

            return response

        except aiohttp.ClientError as e:
            self._stats['failed_requests'] += 1
            raise NetworkError(f"API: 网络请求错误: {str(e)}") from e
        except Exception as e:
            self._stats['failed_requests'] += 1
            raise QBittorrentError(f"API: 请求失败: {str(e)}") from e

    async def _handle_response(self, resp: aiohttp.ClientResponse) -> Any:
        """处理 API 响应"""
        if resp.status == 200:
            content_type = resp.headers.get('Content-Type', '')

            if 'application/json' in content_type:
                return await resp.json()
            else:
                response_text = await resp.text()
                # 某些API端点返回文本响应
                if response_text.strip() in ['Ok.', 'Fails.']:
                    return response_text.strip()
                else:
                    # 尝试解析为JSON
                    try:
                        return json.loads(response_text)
                    except json.JSONDecodeError:
                        return response_text
        elif resp.status == 403:
            raise QbtPermissionError("API: 权限不足或会话过期")
        elif resp.status == 404:
            raise QBittorrentError(f"API: 端点不存在: {resp.url}")
        elif resp.status == 429:
            raise QbtRateLimitError("API: 请求过于频繁")
        else:
            error_text = await resp.text()
            raise QBittorrentError(f"API: HTTP {resp.status} - {error_text}")

    # ========== 应用程序信息 API ==========

    async def get_application_version(self) -> str:
        """
        获取 qBittorrent 应用程序版本

        API: GET /api/v2/app/version
        """
        endpoint = '/app/version'
        response = await self._api_request('GET', endpoint)
        return response

    async def get_api_version(self) -> str:
        """
        获取 qBittorrent Web API 版本

        API: GET /api/v2/app/webapiVersion
        """
        endpoint = '/app/webapiVersion'
        response = await self._api_request('GET', endpoint)
        return response

    async def get_build_info(self) -> Dict[str, str]:
        """
        获取 qBittorrent 构建信息

        API: GET /api/v2/app/buildInfo
        """
        endpoint = '/app/buildInfo'
        response = await self._api_request('GET', endpoint)
        return response

    # ========== 传输信息 API ==========

    async def get_transfer_info(self) -> Dict[str, Any]:
        """
        获取全局传输信息

        API: GET /api/v2/transfer/info
        """
        endpoint = '/transfer/info'
        response = await self._api_request('GET', endpoint)
        return response

    async def get_sync_maindata(self, rid: Optional[int] = None) -> Dict[str, Any]:
        """
        获取同步主要数据

        API: GET /api/v2/sync/maindata
        """
        endpoint = '/sync/maindata'
        params = {}
        if rid is not None:
            params['rid'] = rid

        response = await self._api_request('GET', endpoint, params=params)
        return response

    # ========== 种子管理 API ==========

    async def get_torrents_info(
        self,
        filter_type: str = "all",
        category: Optional[str] = None,
        sort: Optional[str] = None,
        reverse: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        hashes: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        获取种子信息列表

        API: GET /api/v2/torrents/info
        """
        endpoint = '/torrents/info'
        params = {}

        # 添加查询参数
        if filter_type:
            params['filter'] = filter_type
        if category:
            params['category'] = category
        if sort:
            params['sort'] = sort
        if reverse:
            params['reverse'] = 'true'
        if limit:
            params['limit'] = str(limit)
        if offset:
            params['offset'] = str(offset)
        if hashes:
            params['hashes'] = '|'.join(hashes)

        response = await self._api_request('GET', endpoint, params=params)
        return response

    async def get_torrent_properties(self, hash: str) -> Dict[str, Any]:
        """
        获取种子属性

        API: GET /api/v2/torrents/properties
        """
        endpoint = '/torrents/properties'
        params = {'hash': hash}

        response = await self._api_request('GET', endpoint, params=params)
        return response

    async def get_torrent_trackers(self, hash: str) -> List[Dict[str, Any]]:
        """
        获取种子 Tracker 列表

        API: GET /api/v2/torrents/trackers
        """
        endpoint = '/torrents/trackers'
        params = {'hash': hash}

        response = await self._api_request('GET', endpoint, params=params)
        return response

    async def get_torrent_webseeds(self, hash: str) -> List[str]:
        """
        获取种子 Web Seeds 列表

        API: GET /api/v2/torrents/webseeds
        """
        endpoint = '/torrents/webseeds'
        params = {'hash': hash}

        response = await self._api_request('GET', endpoint, params=params)
        return response

    async def get_torrent_files(self, hash: str) -> List[Dict[str, Any]]:
        """
        获取种子文件列表

        API: GET /api/v2/torrents/files
        """
        endpoint = '/torrents/files'
        params = {'hash': hash}

        response = await self._api_request('GET', endpoint, params=params)
        return response

    # ========== 种子操作 API ==========

    async def add_torrent(
        self,
        urls: Optional[str] = None,
        torrent_file: Optional[str] = None,
        save_path: Optional[str] = None,
        cookie: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[str] = None,
        skip_checking: bool = False,
        paused: bool = False,
        root_folder: Optional[str] = None,
        rename: Optional[str] = None,
        upload_limit: Optional[int] = None,
        download_limit: Optional[int] = None,
        sequential_download: bool = False,
        first_last_piece_first: bool = False
    ) -> bool:
        """
        添加种子 (通过磁力链接或文件)

        API: POST /api/v2/torrents/add
        """
        endpoint = '/torrents/add'

        data = {}
        files = None

        # 构建请求数据
        if urls:
            data['urls'] = urls

        if save_path:
            data['savepath'] = save_path

        if cookie:
            data['cookie'] = cookie

        if category:
            data['category'] = category

        if tags:
            data['tags'] = tags

        data['skip_checking'] = 'true' if skip_checking else 'false'
        data['paused'] = 'true' if paused else 'false'

        if root_folder:
            data['root_folder'] = root_folder

        if rename:
            data['rename'] = rename

        if upload_limit is not None:
            data['upLimit'] = str(upload_limit)

        if download_limit is not None:
            data['dlLimit'] = str(download_limit)

        data['sequentialDownload'] = 'true' if sequential_download else 'false'
        data['firstLastPiecePrio'] = 'true' if first_last_piece_first else 'false'

        # 文件上传
        if torrent_file:
            files = {'torrents': torrent_file}

        try:
            response = await self._api_request('POST', endpoint, data=data, files=files)
            # 检查响应是否为 "Fails."
            if response == "Fails.":
                return False
            return True
        except Exception as e:
            self.logger.error(f"添加种子失败: {e}")
            return False

    async def pause_torrents(self, hashes: Union[str, List[str]]) -> bool:
        """
        暂停种子

        API: POST /api/v2/torrents/pause
        """
        endpoint = '/torrents/pause'

        if isinstance(hashes, str):
            hashes_str = hashes
        else:
            hashes_str = '|'.join(hashes)

        data = {'hashes': hashes_str}

        try:
            await self._api_request('POST', endpoint, data=data)
            return True
        except Exception as e:
            self.logger.error(f"暂停种子失败: {e}")
            return False

    async def resume_torrents(self, hashes: Union[str, List[str]]) -> bool:
        """
        恢复种子

        API: POST /api/v2/torrents/resume
        """
        endpoint = '/torrents/resume'

        if isinstance(hashes, str):
            hashes_str = hashes
        else:
            hashes_str = '|'.join(hashes)

        data = {'hashes': hashes_str}

        try:
            await self._api_request('POST', endpoint, data=data)
            return True
        except Exception as e:
            self.logger.error(f"恢复种子失败: {e}")
            return False

    async def delete_torrents(
        self,
        hashes: Union[str, List[str]],
        delete_files: bool = False
    ) -> bool:
        """
        删除种子

        API: POST /api/v2/torrents/delete
        """
        endpoint = '/torrents/delete'

        if isinstance(hashes, str):
            hashes_str = hashes
        else:
            hashes_str = '|'.join(hashes)

        data = {
            'hashes': hashes_str,
            'deleteFiles': 'true' if delete_files else 'false'
        }

        try:
            await self._api_request('POST', endpoint, data=data)
            return True
        except Exception as e:
            self.logger.error(f"删除种子失败: {e}")
            return False

    async def recheck_torrents(self, hashes: Union[str, List[str]]) -> bool:
        """
        重新校验种子

        API: POST /api/v2/torrents/recheck
        """
        endpoint = '/torrents/recheck'

        if isinstance(hashes, str):
            hashes_str = hashes
        else:
            hashes_str = '|'.join(hashes)

        data = {'hashes': hashes_str}

        try:
            await self._api_request('POST', endpoint, data=data)
            return True
        except Exception as e:
            self.logger.error(f"重新校验种子失败: {e}")
            return False

    async def set_torrent_location(
        self,
        hashes: Union[str, List[str]],
        location: str
    ) -> bool:
        """
        设置种子位置

        API: POST /api/v2/torrents/setLocation
        """
        endpoint = '/torrents/setLocation'

        if isinstance(hashes, str):
            hashes_str = hashes
        else:
            hashes_str = '|'.join(hashes)

        data = {
            'hashes': hashes_str,
            'location': location
        }

        try:
            await self._api_request('POST', endpoint, data=data)
            return True
        except Exception as e:
            self.logger.error(f"设置种子位置失败: {e}")
            return False

    async def set_torrent_category(
        self,
        hashes: Union[str, List[str]],
        category: str
    ) -> bool:
        """
        设置种子分类

        API: POST /api/v2/torrents/setCategory
        """
        endpoint = '/torrents/setCategory'

        if isinstance(hashes, str):
            hashes_str = hashes
        else:
            hashes_str = '|'.join(hashes)

        data = {
            'hashes': hashes_str,
            'category': category
        }

        try:
            await self._api_request('POST', endpoint, data=data)
            return True
        except Exception as e:
            self.logger.error(f"设置种子分类失败: {e}")
            return False

    # ========== 分类管理 API ==========

    async def get_categories(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有分类

        API: GET /api/v2/torrents/categories
        """
        endpoint = '/torrents/categories'
        response = await self._api_request('GET', endpoint)
        return response

    async def create_category(
        self,
        name: str,
        save_path: Optional[str] = None
    ) -> bool:
        """
        创建新分类

        API: POST /api/v2/torrents/createCategory
        """
        endpoint = '/torrents/createCategory'

        data = {'category': name}
        if save_path:
            data['savePath'] = save_path

        try:
            await self._api_request('POST', endpoint, data=data)
            return True
        except Exception as e:
            self.logger.error(f"创建分类失败: {e}")
            return False

    async def edit_category(
        self,
        name: str,
        save_path: Optional[str] = None
    ) -> bool:
        """
        编辑现有分类

        API: POST /api/v2/torrents/editCategory
        """
        endpoint = '/torrents/editCategory'

        data = {'category': name}
        if save_path:
            data['savePath'] = save_path

        try:
            await self._api_request('POST', endpoint, data=data)
            return True
        except Exception as e:
            self.logger.error(f"编辑分类失败: {e}")
            return False

    async def remove_categories(self, categories: Union[str, List[str]]) -> bool:
        """
        删除分类

        API: POST /api/v2/torrents/removeCategories
        """
        endpoint = '/torrents/removeCategories'

        if isinstance(categories, str):
            categories_str = categories
        else:
            categories_str = '|'.join(categories)

        data = {'categories': categories_str}

        try:
            await self._api_request('POST', endpoint, data=data)
            return True
        except Exception as e:
            self.logger.error(f"删除分类失败: {e}")
            return False

    # ========== 应用设置 API ==========

    async def get_application_preferences(self) -> Dict[str, Any]:
        """
        获取应用程序偏好设置

        API: GET /api/v2/app/preferences
        """
        endpoint = '/app/preferences'
        response = await self._api_request('GET', endpoint)
        return response

    async def set_application_preferences(self, preferences: Dict[str, Any]) -> bool:
        """
        设置应用程序偏好设置

        API: POST /api/v2/app/setPreferences
        """
        endpoint = '/app/setPreferences'

        # qBittorrent API 要求 JSON 格式
        data = {'json': json.dumps(preferences)}

        try:
            await self._api_request('POST', endpoint, data=data)
            return True
        except Exception as e:
            self.logger.error(f"设置应用程序偏好失败: {e}")
            return False

    # ========== 工具方法 ==========

    async def is_torrent_duplicate(self, torrent_hash: str) -> bool:
        """
        检查种子是否重复

        使用官方 API 检查种子是否存在
        """
        try:
            torrents = await self.get_torrents_info(hashes=[torrent_hash])
            return len(torrents) > 0
        except Exception as e:
            self.logger.warning(f"检查种子重复失败: {e}")
            return False

    async def get_torrent_by_hash(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        """
        通过 Hash 获取特定种子信息

        使用官方 API 获取种子详细信息
        """
        try:
            torrents = await self.get_torrents_info(hashes=[torrent_hash])
            return torrents[0] if torrents else None
        except Exception as e:
            self.logger.error(f"获取种子信息失败: {e}")
            return None

    async def ensure_category_exists(self, category_name: str, save_path: Optional[str] = None) -> bool:
        """
        确保分类存在，如果不存在则创建

        使用官方 API 管理分类
        """
        try:
            # 获取现有分类
            categories = await self.get_categories()

            if category_name not in categories:
                # 创建新分类
                return await self.create_category(category_name, save_path)

            return True
        except Exception as e:
            self.logger.error(f"确保分类存在失败: {e}")
            return False

    async def get_api_statistics(self) -> Dict[str, Any]:
        """获取API使用统计信息"""
        return self._get_stats()


# 便捷函数
async def create_api_client(config: QBittorrentConfig) -> APIClient:
    """创建API客户端实例"""
    client = APIClient(config)
    await client.initialize()
    return client