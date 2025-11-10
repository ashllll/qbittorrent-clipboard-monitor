"""
资源管理模块

提供统一的异步资源管理，包括上下文管理器、连接池、信号量等
"""

import asyncio
import logging
import time
import weakref
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Callable, Awaitable, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


@dataclass
class ResourceInfo:
    """资源信息"""
    resource_id: str
    resource_type: str
    created_at: datetime
    last_used: datetime
    usage_count: int = 0
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResourceTracker:
    """
    资源跟踪器

    跟踪所有资源的创建、使用和释放
    """

    def __init__(self):
        self._resources: Dict[str, ResourceInfo] = {}
        self._resource_refs: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._cleanup_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._total_resources = 0
        self._active_resources = 0

    async def register_resource(
        self,
        resource_id: str,
        resource_type: str,
        resource: Any,
        size_bytes: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """注册资源"""
        async with self._lock:
            info = ResourceInfo(
                resource_id=resource_id,
                resource_type=resource_type,
                created_at=datetime.now(),
                last_used=datetime.now(),
                usage_count=0,
                size_bytes=size_bytes,
                metadata=metadata or {}
            )

            self._resources[resource_id] = info
            self._resource_refs[resource_id] = weakref.ref(
                resource, lambda ref: asyncio.create_task(self._cleanup_resource(resource_id))
            )
            self._total_resources += 1
            self._active_resources += 1

            logger.debug(f"资源已注册: {resource_id} (类型: {resource_type})")

    async def unregister_resource(self, resource_id: str) -> None:
        """注销资源"""
        async with self._lock:
            if resource_id in self._resources:
                del self._resources[resource_id]
            if resource_id in self._resource_refs:
                del self._resource_refs[resource_id]

            self._active_resources = max(0, self._active_resources - 1)
            logger.debug(f"资源已注销: {resource_id}")

    async def update_usage(self, resource_id: str) -> None:
        """更新资源使用情况"""
        async with self._lock:
            if resource_id in self._resources:
                info = self._resources[resource_id]
                info.last_used = datetime.now()
                info.usage_count += 1

    async def get_resource_info(self, resource_id: str) -> Optional[ResourceInfo]:
        """获取资源信息"""
        async with self._lock:
            return self._resources.get(resource_id)

    async def get_all_resources(self) -> List[ResourceInfo]:
        """获取所有资源信息"""
        async with self._lock:
            return list(self._resources.values())

    async def cleanup_resource(self, resource_id: str) -> None:
        """清理资源（由弱引用回调调用）"""
        logger.warning(f"资源 {resource_id} 已被垃圾回收，但可能没有正确清理")

        # 执行清理回调
        for callback in self._cleanup_callbacks[resource_id]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"清理回调执行失败: {str(e)}")

        # 注销资源
        await self.unregister_resource(resource_id)

    def add_cleanup_callback(self, resource_id: str, callback: Callable) -> None:
        """添加清理回调"""
        self._cleanup_callbacks[resource_id].append(callback)

    def get_stats(self) -> Dict[str, Any]:
        """获取资源统计"""
        return {
            "total_resources": self._total_resources,
            "active_resources": self._active_resources,
            "resource_types": defaultdict(int),
            "oldest_resource_age": 0,
            "total_memory_bytes": 0
        }

    async def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        async with self._lock:
            now = datetime.now()
            resource_stats = self.get_stats()

            # 统计资源类型
            for info in self._resources.values():
                resource_stats["resource_types"][info.resource_type] += 1

            # 计算最老资源年龄
            if self._resources:
                oldest_time = min(info.created_at for info in self._resources.values())
                resource_stats["oldest_resource_age"] = (now - oldest_time).total_seconds()

            # 计算总内存使用
            resource_stats["total_memory_bytes"] = sum(
                info.size_bytes for info in self._resources.values()
            )

            # 检查资源泄漏
            leaks = []
            for info in self._resources.values():
                age = (now - info.created_at).total_seconds()
                idle_time = (now - info.last_used).total_seconds()

                # 资源创建超过1小时且1小时未使用，可能泄漏
                if age > 3600 and idle_time > 3600:
                    leaks.append({
                        "resource_id": info.resource_id,
                        "resource_type": info.resource_type,
                        "age_seconds": age,
                        "idle_seconds": idle_time
                    })

            resource_stats["potential_leaks"] = leaks
            resource_stats["leak_count"] = len(leaks)

            return resource_stats


# 全局资源跟踪器
_global_tracker = ResourceTracker()


class BaseAsyncResource(ABC):
    """
    基础异步资源类

    所有需要管理的资源都应该继承此类
    """

    def __init__(self, resource_id: Optional[str] = None):
        self.resource_id = resource_id or f"{self.__class__.__name__}_{id(self)}"
        self._created_at = datetime.now()
        self._last_used = datetime.now()
        self._usage_count = 0
        self._is_closed = False
        self._cleanup_tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()

    @abstractmethod
    async def _do_close(self) -> None:
        """执行实际的资源关闭逻辑"""
        pass

    async def close(self) -> None:
        """关闭资源"""
        async with self._lock:
            if self._is_closed:
                return

            try:
                await self._do_close()
                self._is_closed = True

                # 取消清理任务
                for task in self._cleanup_tasks:
                    if not task.done():
                        task.cancel()

                # 通知资源跟踪器
                asyncio.create_task(_global_tracker.unregister_resource(self.resource_id))

                logger.debug(f"资源已关闭: {self.resource_id}")

            except Exception as e:
                logger.error(f"关闭资源失败 {self.resource_id}: {str(e)}")
                raise

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await _global_tracker.update_usage(self.resource_id)
        self._last_used = datetime.now()
        self._usage_count += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()
        return False

    async def ensure_open(self) -> None:
        """确保资源处于打开状态"""
        if self._is_closed:
            raise RuntimeError(f"资源已关闭: {self.resource_id}")

    def get_info(self) -> ResourceInfo:
        """获取资源信息"""
        return ResourceInfo(
            resource_id=self.resource_id,
            resource_type=self.__class__.__name__,
            created_at=self._created_at,
            last_used=self._last_used,
            usage_count=self._usage_count
        )


class AsyncResourcePool(BaseAsyncResource):
    """
    异步资源池

    管理一组可重用的资源
    """

    def __init__(
        self,
        create_func: Callable[[], Awaitable[Any]],
        max_size: int = 10,
        min_size: int = 2,
        acquire_timeout: float = 30.0,
        idle_timeout: float = 300.0,
        resource_type: str = "generic"
    ):
        super().__init__(f"pool_{resource_type}_{id(self)}")
        self.create_func = create_func
        self.max_size = max_size
        self.min_size = min_size
        self.acquire_timeout = acquire_timeout
        self.idle_timeout = idle_timeout
        self.resource_type = resource_type

        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._used: Set[Any] = set()
        self._created_count = 0
        self._acquired_count = 0
        self._released_count = 0
        self._error_count = 0
        self._cleanup_task: Optional[asyncio.Task] = None

    async def _initialize_pool(self) -> None:
        """初始化连接池"""
        for _ in range(self.min_size):
            try:
                resource = await self.create_func()
                await self._pool.put(resource)
            except Exception as e:
                logger.error(f"初始化资源池失败: {str(e)}")
                raise

        # 启动清理任务
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def acquire(self) -> Any:
        """获取资源"""
        await self.ensure_open()

        try:
            # 尝试从池中获取资源
            timeout = min(self.acquire_timeout, 30.0)  # 最大30秒超时
            resource = await asyncio.wait_for(self._pool.get(), timeout=timeout)

            # 如果资源失效，递归获取新资源
            if not await self._is_resource_valid(resource):
                await self._destroy_resource(resource)
                return await self.acquire()

            self._used.add(resource)
            self._acquired_count += 1

            # 记录资源跟踪
            await _global_tracker.update_usage(self.resource_id)

            logger.debug(f"从资源池获取资源: {self.resource_id}")
            return resource

        except asyncio.TimeoutError:
            self._error_count += 1
            raise RuntimeError(f"资源池获取超时 ({self.acquire_timeout}s)")

    async def release(self, resource: Any) -> None:
        """释放资源"""
        if resource not in self._used:
            logger.warning(f"尝试释放未使用的资源: {resource}")
            return

        self._used.remove(resource)
        self._released_count += 1

        # 检查资源是否有效
        if not await self._is_resource_valid(resource):
            await self._destroy_resource(resource)
            return

        # 放回池中
        try:
            if not self._pool.full():
                await self._pool.put(resource)
            else:
                # 池已满，销毁资源
                await self._destroy_resource(resource)
        except Exception as e:
            logger.error(f"释放资源失败: {str(e)}")
            await self._destroy_resource(resource)

    async def _is_resource_valid(self, resource: Any) -> bool:
        """检查资源是否有效"""
        try:
            if hasattr(resource, 'ping'):
                return await resource.ping()
            if hasattr(resource, 'is_alive'):
                return resource.is_alive()
            if hasattr(resource, '_closed'):
                return not resource._closed
            return True
        except:
            return False

    async def _destroy_resource(self, resource: Any) -> None:
        """销毁资源"""
        try:
            if hasattr(resource, 'close'):
                await resource.close()
        except Exception as e:
            logger.error(f"销毁资源失败: {str(e)}")

    async def _cleanup_loop(self) -> None:
        """清理循环"""
        while not self._is_closed:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次

                # 清理过期的未使用资源
                while not self._pool.empty():
                    try:
                        resource = self._pool.get_nowait()
                        # 这里可以添加过期检查逻辑
                        # 如果过期，销毁资源
                        # 否则放回池中
                    except asyncio.QueueEmpty:
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"资源池清理循环错误: {str(e)}")

    async def _do_close(self) -> None:
        """关闭资源池"""
        # 停止清理任务
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # 关闭所有资源
        while not self._pool.empty():
            try:
                resource = self._pool.get_nowait()
                await self._destroy_resource(resource)
            except asyncio.QueueEmpty:
                break

        # 关闭正在使用的资源
        for resource in list(self._used):
            await self._destroy_resource(resource)

        logger.info(f"资源池已关闭: {self.resource_id}")

    def get_stats(self) -> Dict[str, Any]:
        """获取资源池统计"""
        return {
            "pool_size": self._pool.qsize(),
            "max_size": self.max_size,
            "used_size": len(self._used),
            "created_count": self._created_count,
            "acquired_count": self._acquired_count,
            "released_count": self._released_count,
            "error_count": self._error_count,
            "hit_rate": self._released_count / max(1, self._acquired_count)
        }


class ResourceContext:
    """
    资源上下文管理器

    提供更灵活的资源管理，支持动态资源创建和清理
    """

    def __init__(self):
        self._resources: List[Any] = []
        self._cleanup_callbacks: List[Callable] = []
        self._lock = asyncio.Lock()
        self._is_closed = False

    async def add_resource(self, resource: Any, cleanup: Optional[Callable] = None) -> None:
        """添加资源"""
        async with self._lock:
            if self._is_closed:
                raise RuntimeError("资源上下文已关闭")

            self._resources.append(resource)
            if cleanup:
                self._cleanup_callbacks.append(cleanup)

    async def cleanup(self) -> None:
        """清理所有资源"""
        async with self._lock:
            if self._is_closed:
                return

            # 倒序清理（后添加的先清理）
            for resource, cleanup in zip(reversed(self._resources), reversed(self._cleanup_callbacks)):
                try:
                    if cleanup:
                        if asyncio.iscoroutinefunction(cleanup):
                            await cleanup(resource)
                        else:
                            cleanup(resource)
                except Exception as e:
                    logger.error(f"资源清理失败: {str(e)}")

            self._resources.clear()
            self._cleanup_callbacks.clear()
            self._is_closed = True

    async def __aenter__(self):
        """进入上下文"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        await self.cleanup()
        return False


@asynccontextmanager
async def managed_resource(
    create_func: Callable[[], Awaitable[Any]],
    resource_id: Optional[str] = None,
    pool: Optional[AsyncResourcePool] = None
):
    """
    资源管理上下文管理器

    Args:
        create_func: 资源创建函数
        resource_id: 资源ID
        pool: 资源池（可选）

    Yields:
        创建的资源
    """
    resource = None
    is_from_pool = False

    try:
        if pool:
            # 从资源池获取
            resource = await pool.acquire()
            is_from_pool = True
            resource_id = resource_id or f"pooled_resource_{id(resource)}"
        else:
            # 直接创建
            resource = await create_func()
            resource_id = resource_id or f"direct_resource_{id(resource)}"

        # 注册到资源跟踪器
        await _global_tracker.register_resource(
            resource_id,
            "direct" if not pool else "pooled",
            resource
        )

        yield resource

    finally:
        # 清理资源
        try:
            if resource:
                # 更新使用情况
                await _global_tracker.update_usage(resource_id)

                if is_from_pool and pool:
                    await pool.release(resource)
                else:
                    if hasattr(resource, 'close'):
                        if asyncio.iscoroutinefunction(resource.close):
                            await resource.close()
                        else:
                            resource.close()

        except Exception as e:
            logger.error(f"资源清理失败: {str(e)}")


# 全局资源管理工具
def get_global_tracker() -> ResourceTracker:
    """获取全局资源跟踪器"""
    return _global_tracker


async def get_resource_health_report() -> Dict[str, Any]:
    """获取全局资源健康报告"""
    return await _global_tracker.get_health_report()
