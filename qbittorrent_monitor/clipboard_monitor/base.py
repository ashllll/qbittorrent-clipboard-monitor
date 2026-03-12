"""剪贴板监控器的抽象基类和通用接口

此模块定义了剪贴板监控模块的抽象基类和协议，
用于确保各组件之间的接口一致性。
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable, Any, Protocol
from dataclasses import dataclass
import asyncio


@dataclass
class MonitorStats:
    """监控统计数据结构"""
    total_processed: int = 0
    successful_adds: int = 0
    failed_adds: int = 0
    duplicates_skipped: int = 0


class BaseClipboardMonitor(ABC):
    """剪贴板监控器抽象基类
    
    定义了所有剪贴板监控器必须实现的基本接口。
    """
    
    @abstractmethod
    async def start(self) -> None:
        """启动监控"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """停止监控"""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取监控状态
        
        Returns:
            包含监控器状态信息的字典
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """清理资源
        
        释放监控器使用的所有资源。
        """
        pass


class ActivityTrackerProtocol(Protocol):
    """活动跟踪器协议
    
    定义活动跟踪器必须实现的接口。
    """
    
    def record_activity(self, has_content: bool = False) -> None:
        """记录一次活动
        
        Args:
            has_content: 是否包含内容
        """
        ...
    
    async def get_level(self) -> int:
        """获取当前活动级别
        
        Returns:
            0-10 之间的整数，表示活动级别
        """
        ...


class BatchProcessorProtocol(Protocol):
    """批处理器协议
    
    定义批处理器必须实现的接口。
    """
    
    async def add_to_batch(self, item: Dict[str, Any]) -> None:
        """添加项目到批次
        
        Args:
            item: 要添加的项目
        """
        ...
    
    async def process_batch(self, items: List[Dict[str, Any]], batch_start_time: float) -> None:
        """处理批次
        
        Args:
            items: 批次中的项目列表
            batch_start_time: 批次开始时间
        """
        ...
    
    def get_stats(self) -> Dict[str, Any]:
        """获取批处理统计
        
        Returns:
            包含统计信息的字典
        """
        ...
