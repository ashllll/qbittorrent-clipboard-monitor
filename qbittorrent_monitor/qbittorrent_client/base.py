"""qBittorrent客户端抽象基类和协议定义

此模块定义了qBittorrent客户端的抽象基类和协议，
用于确保各组件之间的接口一致性。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol


class QBittorrentClientProtocol(Protocol):
    """qBittorrent客户端协议
    
    定义qBittorrent客户端必须实现的接口。
    """
    
    async def login(self) -> None:
        """登录到qBittorrent服务器"""
        ...
    
    async def add_torrent(self, magnet_link: str, category: str, **kwargs) -> bool:
        """添加种子
        
        Args:
            magnet_link: 磁力链接
            category: 分类名称
            **kwargs: 其他参数
        
        Returns:
            是否添加成功
        """
        ...
    
    async def get_torrents(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取种子列表
        
        Args:
            category: 分类名称过滤（可选）
        
        Returns:
            种子列表
        """
        ...
    
    async def cleanup(self) -> None:
        """清理资源"""
        ...


class ConnectionPoolProtocol(Protocol):
    """连接池协议
    
    定义连接池必须实现的接口。
    """
    
    async def initialize(self) -> None:
        """初始化连接池"""
        ...
    
    async def get_session(self) -> Any:
        """获取会话
        
        Returns:
            会话对象
        """
        ...
    
    async def close_all(self) -> None:
        """关闭所有连接"""
        ...


class CacheManagerProtocol(Protocol):
    """缓存管理器协议
    
    定义缓存管理器必须实现的接口。
    """
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值
        
        Args:
            key: 缓存键
        
        Returns:
            缓存值，如果不存在返回 None
        """
        ...
    
    def set(self, key: str, value: Any) -> None:
        """设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
        """
        ...
    
    def clear(self) -> None:
        """清空缓存"""
        ...


class BaseQBittorrentClient(ABC):
    """qBittorrent客户端抽象基类"""
    
    @abstractmethod
    async def login(self) -> None:
        """登录到qBittorrent服务器"""
        pass
    
    @abstractmethod
    async def add_torrent(
        self,
        magnet_link: str,
        category: Optional[str] = None,
        **kwargs
    ) -> bool:
        """添加种子"""
        pass
    
    @abstractmethod
    async def get_torrents(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取种子列表"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """清理资源"""
        pass
