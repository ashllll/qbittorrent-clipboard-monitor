"""
种子管理器

处理种子的增删改查操作，包括：
- 添加种子
- 删除种子
- 暂停/恢复种子
- 获取种子信息
- 去重检查
"""

import asyncio
import logging
import hashlib
from typing import Any, Dict, List, Optional
from ..utils import parse_magnet

logger = logging.getLogger(__name__)


class TorrentManager:
    """种子管理器"""

    def __init__(self, api_client):
        self.api_client = api_client
        self.logger = logging.getLogger('TorrentManager')

    async def add_torrent(self, magnet_link: str, category: str, **kwargs) -> bool:
        """添加种子"""
        try:
            # 验证磁力链接
            parsed = parse_magnet(magnet_link)
            if not parsed:
                self.logger.error(f"无效的磁力链接: {magnet_link[:50]}...")
                return False

            # 检查是否重复
            torrent_hash = parsed.get('xt', '').replace('urn:btih:', '')
            if await self._is_duplicate(torrent_hash):
                self.logger.info(f"种子已存在: {torrent_hash[:10]}...")
                return False

            # 准备请求数据
            data = {
                'urls': magnet_link,
                'category': category
            }
            data.update(kwargs)

            # 发送添加请求
            status, response = await self.api_client.post('torrents/add', data=data)

            if status == 200:
                self.logger.info(f"种子添加成功: {magnet_link[:50]}...")
                # 尝试重命名
                if 'name' in kwargs:
                    await asyncio.sleep(1)  # 等待种子创建
                    await self._rename_torrent(torrent_hash, kwargs['name'])
                return True
            else:
                self.logger.error(f"添加种子失败: {status} - {response}")
                return False

        except Exception as e:
            self.logger.error(f"添加种子时出错: {e}")
            return False

    async def _rename_torrent(self, torrent_hash: str, new_name: str) -> bool:
        """重命名种子"""
        try:
            data = {
                'hash': torrent_hash,
                'name': new_name
            }
            status, _ = await self.api_client.post('torrents/rename', data=data)
            return status == 200
        except Exception as e:
            self.logger.debug(f"重命名种子失败: {e}")
            return False

    async def _set_torrent_name_alternative(self, torrent_hash: str, new_name: str) -> bool:
        """使用替代方法重命名种子"""
        try:
            # 尝试不同的API端点
            data = {
                'hashes': torrent_hash,
                'name': new_name
            }
            status, _ = await self.api_client.post('torrents/rename', data=data)
            return status == 200
        except Exception as e:
            self.logger.debug(f"替代重命名失败: {e}")
            return False

    async def _is_duplicate(self, torrent_hash: str) -> bool:
        """检查种子是否已存在"""
        try:
            status, torrents = await self.api_client.get('torrents/info', params={'hashes': torrent_hash})
            if status == 200 and torrents:
                return True
            return False
        except Exception as e:
            self.logger.debug(f"检查重复种子失败: {e}")
            return False

    async def get_torrents(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取种子列表"""
        try:
            params = {}
            if category:
                params['category'] = category
            
            status, torrents = await self.api_client.get('torrents/info', params=params)
            if status == 200:
                return torrents if isinstance(torrents, list) else []
            return []
        except Exception as e:
            self.logger.error(f"获取种子列表失败: {e}")
            return []

    async def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        """删除种子"""
        try:
            data = {
                'hashes': torrent_hash,
                'deleteFiles': str(delete_files).lower()
            }
            status, _ = await self.api_client.post('torrents/delete', data=data)
            return status == 200
        except Exception as e:
            self.logger.error(f"删除种子失败: {e}")
            return False

    async def pause_torrent(self, torrent_hash: str) -> bool:
        """暂停种子"""
        try:
            data = {'hashes': torrent_hash}
            status, _ = await self.api_client.post('torrents/pause', data=data)
            return status == 200
        except Exception as e:
            self.logger.error(f"暂停种子失败: {e}")
            return False

    async def resume_torrent(self, torrent_hash: str) -> bool:
        """恢复种子"""
        try:
            data = {'hashes': torrent_hash}
            status, _ = await self.api_client.post('torrents/resume', data=data)
            return status == 200
        except Exception as e:
            self.logger.error(f"恢复种子失败: {e}")
            return False

    async def get_torrent_properties(self, torrent_hash: str) -> Dict[str, Any]:
        """获取种子属性"""
        try:
            status, properties = await self.api_client.get('torrents/properties', params={'hash': torrent_hash})
            if status == 200:
                return properties
            return {}
        except Exception as e:
            self.logger.error(f"获取种子属性失败: {e}")
            return {}

    async def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        """获取种子文件列表"""
        try:
            status, files = await self.api_client.get('torrents/files', params={'hash': torrent_hash})
            if status == 200:
                return files if isinstance(files, list) else []
            return []
        except Exception as e:
            self.logger.error(f"获取种子文件列表失败: {e}")
            return []
