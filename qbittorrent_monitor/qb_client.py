"""qBittorrent客户端 - 简化版"""

import asyncio
import logging
from typing import Dict, Optional, Any

import aiohttp

from .config import Config
from .exceptions import QBClientError, QBAuthError, QBConnectionError

logger = logging.getLogger(__name__)


class QBClient:
    """简化的异步qBittorrent客户端"""
    
    def __init__(self, config: Config):
        self.config = config
        self.qb_config = config.qbittorrent
        self.base_url = f"{'https' if self.qb_config.use_https else 'http'}://{self.qb_config.host}:{self.qb_config.port}"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        await self._login()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _login(self) -> None:
        """登录获取cookie"""
        url = f"{self.base_url}/api/v2/auth/login"
        data = {"username": self.qb_config.username, "password": self.qb_config.password}
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    result = await resp.text()
                    if result == "Ok.":
                        logger.info("qBittorrent登录成功")
                    else:
                        raise QBAuthError(f"登录失败: {result}")
                else:
                    raise QBAuthError(f"登录失败，状态码: {resp.status}")
        except aiohttp.ClientError as e:
            raise QBConnectionError(f"连接失败: {e}")
    
    async def get_version(self) -> str:
        """获取版本"""
        url = f"{self.base_url}/api/v2/app/version"
        async with self.session.get(url) as resp:
            return await resp.text() if resp.status == 200 else "unknown"
    
    async def add_torrent(self, magnet: str, category: Optional[str] = None, save_path: Optional[str] = None) -> bool:
        """添加磁力链接"""
        url = f"{self.base_url}/api/v2/torrents/add"
        data: Dict[str, Any] = {"urls": magnet}
        if category:
            data["category"] = category
        if save_path:
            data["savepath"] = save_path
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    logger.info(f"添加成功: {magnet[:50]}...")
                    return True
                return False
        except Exception as e:
            logger.error(f"添加失败: {e}")
            return False
    
    async def get_categories(self) -> Dict[str, Any]:
        """获取分类"""
        url = f"{self.base_url}/api/v2/torrents/categories"
        try:
            async with self.session.get(url) as resp:
                return await resp.json() if resp.status == 200 else {}
        except Exception:
            return {}
    
    async def create_category(self, name: str, save_path: str) -> bool:
        """创建分类"""
        url = f"{self.base_url}/api/v2/torrents/createCategory"
        try:
            async with self.session.post(url, data={"category": name, "savePath": save_path}) as resp:
                return resp.status == 200
        except Exception:
            return False
    
    async def ensure_categories(self) -> None:
        """确保分类存在"""
        existing = await self.get_categories()
        for name, cat in self.config.categories.items():
            if name not in existing:
                await self.create_category(name, cat.save_path)
