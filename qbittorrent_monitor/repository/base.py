"""Repository 模式基础定义

提供数据访问的抽象接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Dict, Any
from dataclasses import dataclass

from ..exceptions import QBMonitorError


class RepositoryError(QBMonitorError):
    """仓库错误"""
    pass


class RecordNotFoundError(RepositoryError):
    """记录不存在"""
    pass


class DuplicateRecordError(RepositoryError):
    """重复记录"""
    pass


@dataclass
class QueryOptions:
    """查询选项"""
    limit: int = 100
    offset: int = 0
    order_by: Optional[str] = None
    order_desc: bool = True


T = TypeVar('T')


class Repository(Generic[T], ABC):
    """Repository 抽象基类"""
    
    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[T]:
        """根据ID获取实体"""
        pass
    
    @abstractmethod
    async def create(self, entity: T) -> T:
        """创建实体"""
        pass
    
    @abstractmethod
    async def update(self, entity: T) -> T:
        """更新实体"""
        pass
    
    @abstractmethod
    async def delete(self, id: int) -> bool:
        """删除实体"""
        pass
    
    @abstractmethod
    async def list(self, options: QueryOptions) -> List[T]:
        """列出实体"""
        pass
