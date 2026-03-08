"""接口定义模块

定义核心抽象接口，支持依赖注入和测试 mock。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable, TypeVar, Generic
from contextlib import asynccontextmanager
import asyncio


# ============ 数据模型 ============

@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """分类结果 - 不可变数据类
    
    Attributes:
        category: 分类名称
        confidence: 置信度 0.0-1.0
        method: 分类方法 ("rule", "ai", "fallback")
        cached: 是否来自缓存
        timestamp: 分类时间戳
    """
    category: str
    confidence: float
    method: str
    cached: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self) -> None:
        # 验证置信度范围
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"置信度必须在 0.0-1.0 之间，当前: {self.confidence}"
            )


@dataclass(frozen=True, slots=True)
class MagnetProcessingContext:
    """磁力链接处理上下文
    
    封装处理过程中的所有相关信息。
    """
    magnet: str
    name: str
    magnet_hash: str
    category: str = ""
    status: str = "pending"
    error_message: str | None = None


@dataclass(slots=True)
class ProcessingStats:
    """处理统计信息"""
    total_processed: int = 0
    successful_adds: int = 0
    failed_adds: int = 0
    duplicates_skipped: int = 0
    invalid_magnets: int = 0
    start_time: datetime | None = None
    
    @property
    def uptime_seconds(self) -> float:
        """计算运行时间（秒）"""
        if self.start_time is None:
            return 0.0
        return (datetime.now() - self.start_time).total_seconds()


# ============ 协议接口 ============

@runtime_checkable
class IClassifier(Protocol):
    """内容分类器接口"""
    
    async def classify(
        self, 
        name: str, 
        use_cache: bool = True,
        timeout: float | None = None
    ) -> ClassificationResult:
        """对单个内容进行分类
        
        Args:
            name: 内容名称
            use_cache: 是否使用缓存
            timeout: 超时时间（秒）
            
        Returns:
            分类结果
        """
        ...
    
    async def classify_batch(
        self, 
        names: Sequence[str],
        use_cache: bool = True,
        timeout: float | None = None,
        max_concurrent: int = 5
    ) -> list[ClassificationResult]:
        """批量分类内容
        
        Args:
            names: 内容名称列表
            use_cache: 是否使用缓存
            timeout: 超时时间（秒）
            max_concurrent: 最大并发数
            
        Returns:
            分类结果列表
        """
        ...
    
    def get_cache_stats(self) -> dict[str, float]:
        """获取缓存统计信息
        
        Returns:
            包含 size, hits, misses, hit_rate 的字典
        """
        ...
    
    def clear_cache(self) -> None:
        """清空分类缓存"""
        ...


@runtime_checkable
class ITorrentClient(Protocol):
    """Torrent 客户端接口"""
    
    async def add_torrent(
        self,
        magnet: str,
        category: str | None = None,
        save_path: str | None = None
    ) -> bool:
        """添加磁力链接
        
        Args:
            magnet: 磁力链接
            category: 分类名称
            save_path: 保存路径
            
        Returns:
            是否添加成功
        """
        ...
    
    async def get_categories(self) -> dict[str, dict]:
        """获取所有分类
        
        Returns:
            分类信息字典
        """
        ...
    
    async def create_category(self, name: str, save_path: str) -> bool:
        """创建分类
        
        Args:
            name: 分类名称
            save_path: 保存路径
            
        Returns:
            是否创建成功
        """
        ...
    
    async def is_connected(self) -> bool:
        """检查连接状态
        
        Returns:
            是否已连接
        """
        ...
    
    async def get_version(self) -> str:
        """获取客户端版本
        
        Returns:
            版本字符串
        """
        ...


@runtime_checkable
class IClipboardProvider(Protocol):
    """剪贴板访问接口"""
    
    def get_content(self) -> str:
        """获取当前剪贴板内容
        
        Returns:
            剪贴板内容，空剪贴板返回空字符串
        """
        ...
    
    def set_content(self, content: str) -> None:
        """设置剪贴板内容
        
        Args:
            content: 要设置的内容
        """
        ...


@runtime_checkable
class IDatabase(Protocol):
    """数据持久化接口"""
    
    async def record_torrent(
        self,
        magnet_hash: str,
        name: str,
        category: str,
        status: str,
        error_message: str | None = None
    ) -> None:
        """记录种子处理结果
        
        Args:
            magnet_hash: 磁力链接 hash
            name: 种子名称
            category: 分类
            status: 处理状态 ("success", "failed", "duplicate", "invalid")
            error_message: 错误信息（如果有）
        """
        ...
    
    async def get_torrent_history(
        self,
        category: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[dict]:
        """查询历史记录
        
        Args:
            category: 按分类过滤
            status: 按状态过滤
            limit: 返回数量限制
            offset: 分页偏移
            
        Returns:
            记录字典列表
        """
        ...
    
    async def is_processed(self, magnet_hash: str) -> bool:
        """检查是否已处理过
        
        Args:
            magnet_hash: 磁力链接 hash
            
        Returns:
            是否已处理
        """
        ...
    
    async def get_stats(self) -> dict:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        ...


@runtime_checkable
class IMetricsCollector(Protocol):
    """指标收集接口"""
    
    def record_clipboard_change(self) -> None:
        """记录剪贴板变化"""
        ...
    
    def record_torrent_processed(self, category: str) -> None:
        """记录种子已处理"""
        ...
    
    def record_torrent_added_success(self, category: str) -> None:
        """记录种子添加成功"""
        ...
    
    def record_torrent_added_failed(
        self, 
        category: str, 
        reason: str
    ) -> None:
        """记录种子添加失败"""
        ...
    
    def record_duplicate_skipped(self, reason: str) -> None:
        """记录重复跳过"""
        ...
    
    def record_classification(self, method: str, category: str) -> None:
        """记录分类结果"""
        ...
    
    def record_invalid_magnet(self, reason: str) -> None:
        """记录无效磁力链接"""
        ...


# ============ 抽象基类 ============

T = TypeVar('T')


class Cache(ABC, Generic[T]):
    """缓存抽象基类"""
    
    @abstractmethod
    def get(self, key: str) -> T | None:
        """获取缓存值"""
        pass
    
    @abstractmethod
    def put(self, key: str, value: T) -> None:
        """设置缓存值"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """清空缓存"""
        pass
    
    @abstractmethod
    def get_stats(self) -> dict[str, float]:
        """获取统计信息"""
        pass


# ============ 默认实现 ============

class PyperclipProvider:
    """基于 pyperclip 的剪贴板提供器"""
    
    def __init__(self) -> None:
        import pyperclip
        self._pyperclip = pyperclip
    
    def get_content(self) -> str:
        try:
            content = self._pyperclip.paste()
            return content if content else ""
        except Exception:
            return ""
    
    def set_content(self, content: str) -> None:
        self._pyperclip.copy(content)


class NullMetricsCollector:
    """空指标收集器 - 用于禁用指标收集"""
    
    def record_clipboard_change(self) -> None: pass
    def record_torrent_processed(self, category: str) -> None: pass
    def record_torrent_added_success(self, category: str) -> None: pass
    def record_torrent_added_failed(
        self, 
        category: str, 
        reason: str
    ) -> None: pass
    def record_duplicate_skipped(self, reason: str) -> None: pass
    def record_classification(self, method: str, category: str) -> None: pass
    def record_invalid_magnet(self, reason: str) -> None: pass


class NullDatabase:
    """空数据库 - 用于禁用数据持久化"""
    
    async def record_torrent(
        self,
        magnet_hash: str,
        name: str,
        category: str,
        status: str,
        error_message: str | None = None
    ) -> None:
        pass
    
    async def get_torrent_history(
        self,
        category: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[dict]:
        return []
    
    async def is_processed(self, magnet_hash: str) -> bool:
        return False
    
    async def get_stats(self) -> dict:
        return {"enabled": False}
