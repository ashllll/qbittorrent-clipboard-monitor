"""
增强的qBittorrent客户端模块

支持：
- 智能重试机制
- 增强的错误处理
- 多规则路径映射
- 更多API功能
"""

import asyncio
import json
import logging
import urllib.parse
from typing import Dict, List, Optional, Tuple, Any
import aiohttp
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from .config import QBittorrentConfig, CategoryConfig, PathMappingRule, AppConfig
from .exceptions import (
    QBittorrentError, NetworkError, QbtAuthError, 
    QbtRateLimitError, QbtPermissionError, TorrentParseError
)
from .utils import parse_magnet


class QBittorrentClient:
    """增强的异步qBittorrent API客户端"""
    
    def __init__(self, config: QBittorrentConfig, app_config: Optional[AppConfig] = None):
        self.config = config
        self.app_config = app_config
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger('QBittorrentClient')
        self._base_url = f"{'https' if config.use_https else 'http'}://{config.host}:{config.port}"
        self._authenticated = False
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            connector=aiohttp.TCPConnector(ssl=self.config.verify_ssl)
        )
        await self.login()
        return self
        
    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((NetworkError, QbtRateLimitError)),
        before_sleep=before_sleep_log(logging.getLogger('QBittorrent.Retry'), logging.INFO)
    )
    async def login(self):
        """登录qBittorrent"""
        url = f"{self._base_url}/api/v2/auth/login"
        data = {
            'username': self.config.username,
            'password': self.config.password
        }
        
        try:
            self.logger.info(f"尝试登录qBittorrent: {self.config.host}:{self.config.port}")
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    response_text = await resp.text()
                    if response_text == "Ok.":
                        self._authenticated = True
                        self.logger.info("成功登录qBittorrent")
                        return
                    else:
                        raise QbtAuthError(f"登录失败: {response_text}")
                elif resp.status == 403:
                    raise QbtAuthError("登录失败: 用户名或密码错误")
                elif resp.status == 429:
                    raise QbtRateLimitError("登录失败: API请求过于频繁")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"登录失败: HTTP {resp.status} - {error_text}")
                    
        except aiohttp.ClientError as e:
            raise NetworkError(f"网络连接失败: {str(e)}") from e
    
    async def get_version(self) -> str:
        """获取qBittorrent版本信息"""
        url = f"{self._base_url}/api/v2/app/version"
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    raise QBittorrentError(f"获取版本失败: HTTP {resp.status}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取版本失败: {str(e)}") from e
    
    async def get_existing_categories(self) -> Dict[str, Dict[str, Any]]:
        """获取现有的分类及其详细信息"""
        url = f"{self._base_url}/api/v2/torrents/categories"
        
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('Content-Type', '')
                    if 'application/json' not in content_type:
                        raise QBittorrentError(f"获取分类失败: 响应类型错误 ({content_type})")
                    
                    response_text = await resp.text()
                    if not response_text.strip():
                        self.logger.warning("qBittorrent返回空的分类列表")
                        return {}
                    
                    categories = json.loads(response_text)
                    self.logger.info(f"获取到 {len(categories)} 个现有分类")
                    return categories
                    
                elif resp.status == 403:
                    raise QbtPermissionError("获取分类失败: 权限不足")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"获取分类失败: HTTP {resp.status} - {error_text}")
                    
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取分类失败: {str(e)}") from e
        except json.JSONDecodeError as e:
            raise QBittorrentError(f"解析分类响应失败: {str(e)}") from e
    
    async def ensure_categories(self, categories: Dict[str, CategoryConfig]):
        """确保所有分类存在，动态更新分类路径"""
        try:
            existing_categories = await self.get_existing_categories()
            
            for name, config in categories.items():
                mapped_path = self._map_save_path(config.save_path, name)
                self.logger.info(f"处理分类: {name}, 映射路径: {mapped_path}")
                
                if name not in existing_categories:
                    self.logger.info(f"创建新分类: {name}")
                    await self._create_category(name, mapped_path)
                else:
                    # 动态更新分类路径
                    existing_path = existing_categories[name].get('savePath', '')
                    if existing_path != mapped_path:
                        self.logger.info(f"更新分类路径: {name} (当前路径: {existing_path} -> 新路径: {mapped_path})")
                        await self._update_category(name, mapped_path)
                    else:
                        self.logger.info(f"分类路径未变，跳过更新: {name} (路径: {existing_path})")
                        
        except Exception as e:
            self.logger.error(f"分类管理失败: {str(e)}")
            # 不再抛出异常，允许程序继续运行
            self.logger.warning("分类管理失败，但程序将继续运行")
    
    async def _create_category(self, name: str, save_path: str):
        """创建新分类"""
        url = f"{self._base_url}/api/v2/torrents/createCategory"
        data = {'category': name, 'savePath': save_path}
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.logger.info(f"创建分类成功: {name} -> {save_path}")
                elif resp.status == 409:
                    self.logger.warning(f"分类已存在: {name}")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"创建分类失败: {error_text}")
                    
        except aiohttp.ClientError as e:
            raise NetworkError(f"创建分类网络错误: {str(e)}") from e
    
    async def _update_category(self, name: str, save_path: str):
        """更新现有分类"""
        url = f"{self._base_url}/api/v2/torrents/editCategory"
        data = {'category': name, 'savePath': save_path}
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.logger.info(f"更新分类成功: {name} -> {save_path}")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"更新分类失败: {error_text}")
                    
        except aiohttp.ClientError as e:
            raise NetworkError(f"更新分类网络错误: {str(e)}") from e
    
    def _map_save_path(self, original_path: str, category_name: str = "") -> str:
        """增强的路径映射功能"""
        if not self.app_config:
            return original_path
        
        # 如果配置为直接使用NAS路径
        if self.app_config.use_nas_paths_directly or self.config.use_nas_paths_directly:
            return original_path
        
        # 优先使用新的路径映射规则
        if self.config.path_mapping:
            for mapping in self.config.path_mapping:
                if original_path.startswith(mapping.source_prefix):
                    mapped_path = original_path.replace(
                        mapping.source_prefix, 
                        mapping.target_prefix, 
                        1
                    )
                    self.logger.debug(
                        f"路径映射 ({mapping.description or 'N/A'}): "
                        f"{original_path} -> {mapped_path}"
                    )
                    return mapped_path
        
        # 回退到传统的全局路径映射
        for source, target in self.app_config.path_mapping.items():
            if original_path.startswith(source):
                mapped_path = original_path.replace(source, target, 1)
                self.logger.debug(f"全局路径映射: {original_path} -> {mapped_path}")
                return mapped_path
        
        # 没有匹配的规则，返回原始路径
        self.logger.debug(f"无路径映射规则匹配，使用原始路径: {original_path}")
        return original_path
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type((NetworkError, QbtRateLimitError)),
        before_sleep=before_sleep_log(logging.getLogger('QBittorrent.AddTorrent'), logging.INFO)
    )
    async def add_torrent(self, magnet_link: str, category: str, **kwargs) -> bool:
        """添加磁力链接，支持更多选项"""
        try:
            # 解析磁力链接，提供默认名称
            torrent_hash, torrent_name = parse_magnet(magnet_link)
            if not torrent_hash:
                raise TorrentParseError("无效的磁力链接格式")
            
            # 如果磁力链接没有dn参数，尝试从种子属性获取名称
            display_name = torrent_name or f"磁力链接_{torrent_hash[:8]}"
            self.logger.debug(f"原始磁力链接文件名: {torrent_name}")
            
            # 检查是否重复
            if await self._is_duplicate(torrent_hash):
                self.logger.info(f"跳过重复种子: {display_name}")
                return False
            
            # 验证分类存在
            existing_categories = await self.get_existing_categories()
            
            url = f"{self._base_url}/api/v2/torrents/add"
            data = {
                'urls': magnet_link,
                'autoTMM': 'false',  # 关闭自动种子管理
                **kwargs  # 支持额外参数
            }
            
            # 设置分类
            if category in existing_categories:
                data['category'] = category
                save_path = existing_categories[category]['savePath']
                self.logger.info(f"种子将添加到分类: {category} ({save_path})")
            else:
                self.logger.warning(f"分类不存在: {category}，将使用默认路径")
            
            # 首次尝试添加种子
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    response_text = await resp.text()
                    if response_text != "Fails.":
                        # 种子添加成功，获取实际的种子名称（但不强制重命名）
                        try:
                            # 等待短暂时间让qBittorrent处理种子
                            await asyncio.sleep(1)
                            torrent_info = await self.get_torrent_properties(torrent_hash)
                            if 'name' in torrent_info and torrent_info['name']:
                                actual_name = torrent_info['name']
                                self.logger.info(f"成功添加种子: {actual_name}")
                            else:
                                self.logger.info(f"成功添加种子: {display_name}")
                        except Exception as e:
                            self.logger.warning(f"获取种子属性失败但不影响添加: {str(e)}")
                            self.logger.info(f"成功添加种子: {display_name}")
                        
                        return True
                    else:
                        raise QBittorrentError("添加种子失败: qBittorrent返回Fails")
                elif resp.status == 403:
                    raise QbtPermissionError("添加种子失败: 权限不足")
                elif resp.status == 429:
                    raise QbtRateLimitError("添加种子失败: API请求过于频繁")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"添加种子失败: HTTP {resp.status} - {error_text}")
                    
        except TorrentParseError:
            raise
        except aiohttp.ClientError as e:
            raise NetworkError(f"添加种子网络错误: {str(e)}") from e
    
    async def _rename_torrent(self, torrent_hash: str, new_name: str) -> bool:
        """重命名种子以保持原始名称"""
        try:
            # 清理文件名中的非法字符
            import re
            new_name = re.sub(r'[\\/:*?"<>|]', '_', new_name)
            new_name = new_name.strip()
            
            # 使用正确的qBittorrent API端点
            url = f"{self._base_url}/api/v2/torrents/rename"
            data = {
                'hash': torrent_hash,
                'name': new_name
            }
            
            self.logger.info(f"🔄 尝试重命名种子: {torrent_hash[:8]} -> {new_name}")
            
            async with self.session.post(url, data=data) as resp:
                response_text = await resp.text()
                if resp.status == 200:
                    self.logger.info(f"✅ 种子重命名成功: {new_name}")
                    return True
                else:
                    self.logger.warning(f"⚠️ 种子重命名失败 (HTTP {resp.status}): {response_text}")
                    
                    # 尝试备用方法：使用setName端点
                    return await self._set_torrent_name_alternative(torrent_hash, new_name)
        except Exception as e:
            self.logger.warning(f"⚠️ 种子重命名异常: {str(e)}")
            # 尝试备用方法
            return await self._set_torrent_name_alternative(torrent_hash, new_name)

    async def _set_torrent_name_alternative(self, torrent_hash: str, new_name: str) -> bool:
        """备用重命名方法：使用setName端点"""
        try:
            url = f"{self._base_url}/api/v2/torrents/setName"
            data = {
                'hash': torrent_hash,
                'name': new_name
            }
            
            self.logger.info(f"🔄 使用备用方法重命名: {torrent_hash[:8]} -> {new_name}")
            
            async with self.session.post(url, data=data) as resp:
                response_text = await resp.text()
                if resp.status == 200:
                    self.logger.info(f"✅ 备用重命名成功: {new_name}")
                    return True
                else:
                    self.logger.warning(f"⚠️ 备用重命名也失败 (HTTP {resp.status}): {response_text}")
                    return False
        except Exception as e:
            self.logger.warning(f"⚠️ 备用重命名异常: {str(e)}")
            return False
    
    async def _is_duplicate(self, torrent_hash: str) -> bool:
        """检查种子是否已存在"""
        url = f"{self._base_url}/api/v2/torrents/info"
        params = {'hashes': torrent_hash}
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    torrents = await resp.json()
                    return len(torrents) > 0
                else:
                    self.logger.warning(f"检查重复失败: HTTP {resp.status}")
                    return False
        except aiohttp.ClientError as e:
            self.logger.warning(f"检查重复网络错误: {str(e)}")
            return False
    
    async def get_torrents(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取种子列表"""
        url = f"{self._base_url}/api/v2/torrents/info"
        params = {}
        if category:
            params['category'] = category
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"获取种子列表失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取种子列表网络错误: {str(e)}") from e
    
    async def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        """删除种子"""
        url = f"{self._base_url}/api/v2/torrents/delete"
        data = {
            'hashes': torrent_hash,
            'deleteFiles': 'true' if delete_files else 'false'
        }
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.logger.info(f"删除种子成功: {torrent_hash[:8]}")
                    return True
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"删除种子失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"删除种子网络错误: {str(e)}") from e
    
    async def pause_torrent(self, torrent_hash: str) -> bool:
        """暂停种子"""
        url = f"{self._base_url}/api/v2/torrents/pause"
        data = {'hashes': torrent_hash}
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.logger.info(f"暂停种子成功: {torrent_hash[:8]}")
                    return True
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"暂停种子失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"暂停种子网络错误: {str(e)}") from e
    
    async def resume_torrent(self, torrent_hash: str) -> bool:
        """恢复种子"""
        url = f"{self._base_url}/api/v2/torrents/resume"
        data = {'hashes': torrent_hash}
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.logger.info(f"恢复种子成功: {torrent_hash[:8]}")
                    return True
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"恢复种子失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"恢复种子网络错误: {str(e)}") from e
    
    async def get_torrent_properties(self, torrent_hash: str) -> Dict[str, Any]:
        """获取种子属性"""
        url = f"{self._base_url}/api/v2/torrents/properties"
        params = {'hash': torrent_hash}
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"获取种子属性失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取种子属性网络错误: {str(e)}") from e
    
    async def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        """获取种子文件列表"""
        url = f"{self._base_url}/api/v2/torrents/files"
        params = {'hash': torrent_hash}
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"获取种子文件失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取种子文件网络错误: {str(e)}") from e 