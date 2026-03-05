"""简化版qBittorrent客户端"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

import aiohttp

from .config import Config, CategoryConfig
from .exceptions import QBClientError, QBAuthError, QBConnectionError


logger = logging.getLogger(__name__)


class QBClient:
    """简化的异步qBittorrent客户端"""
    
    def __init__(self, config: Config):
        self.config = config
        self.qb_config = config.qbittorrent
        self.base_url = f"{'https' if self.qb_config.use_https else 'http'}://{self.qb_config.host}:{self.qb_config.port}"
        self.session: Optional[aiohttp.ClientSession] = None
        self._cookie: Optional[str] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        await self._login()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _login(self) -> None:
        """登录获取cookie"""
        url = f"{self.base_url}/api/v2/auth/login"
        data = {
            "username": self.qb_config.username,
            "password": self.qb_config.password,
        }
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    result = await resp.text()
                    if result == "Ok.":
                        self._cookie = resp.headers.get("Set-Cookie", "")
                        logger.info("qBittorrent登录成功")
                    else:
                        raise QBAuthError(f"登录失败: {result}")
                else:
                    raise QBAuthError(f"登录失败，状态码: {resp.status}")
        except aiohttp.ClientError as e:
            raise QBConnectionError(f"连接qBittorrent失败: {e}")
    
    async def get_version(self) -> str:
        """获取qBittorrent版本"""
        url = f"{self.base_url}/api/v2/app/version"
        async with self.session.get(url) as resp:
            if resp.status == 200:
                return await resp.text()
            return "unknown"
    
    async def add_torrent(
        self,
        magnet: str,
        category: Optional[str] = None,
        save_path: Optional[str] = None,
    ) -> bool:
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
                    result = await resp.text()
                    if "Ok" in result or result == "":
                        logger.info(f"添加种子成功: {magnet[:50]}...")
                        return True
                    else:
                        logger.warning(f"添加种子返回: {result}")
                        return False
                else:
                    text = await resp.text()
                    logger.error(f"添加种子失败: {resp.status} - {text}")
                    return False
        except Exception as e:
            logger.error(f"添加种子异常: {e}")
            return False
    
    async def get_categories(self) -> Dict[str, Any]:
        """获取分类列表"""
        url = f"{self.base_url}/api/v2/torrents/categories"
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {}
        except Exception as e:
            logger.error(f"获取分类失败: {e}")
            return {}
    
    async def create_category(self, name: str, save_path: str) -> bool:
        """创建分类"""
        url = f"{self.base_url}/api/v2/torrents/createCategory"
        data = {"category": name, "savePath": save_path}
        try:
            async with self.session.post(url, data=data) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"创建分类失败: {e}")
            return False
    
    async def ensure_categories(self) -> None:
        """确保配置中的分类都存在"""
        existing = await self.get_categories()
        for name, cat in self.config.categories.items():
            if name not in existing:
                await self.create_category(name, cat.save_path)
                logger.info(f"创建分类: {name} -> {cat.save_path}")


def parse_magnet(magnet: str) -> Optional[str]:
    """解析磁力链接，返回显示名称"""
    if not magnet.startswith("magnet:?"):
        return None
    
    # 提取dn参数（显示名称）
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(magnet)
        params = urllib.parse.parse_qs(parsed.query)
        if "dn" in params:
            return params["dn"][0]
    except Exception:
        pass
    return None
