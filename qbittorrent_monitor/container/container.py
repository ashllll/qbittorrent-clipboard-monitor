"""依赖注入容器

简易 DI 容器实现，支持单例、工厂和实例注册。
"""

from __future__ import annotations

import asyncio
import inspect
from typing import TypeVar, Type, Callable, Any, Dict, Optional, overload

T = TypeVar('T')


class Container:
    """依赖注入容器"""
    
    def __init__(self):
        self._registrations: Dict[Type, Callable[[], Any]] = {}
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable[..., Any]] = {}
    
    def register_instance(self, interface: Type[T], instance: T) -> None:
        """注册单例实例"""
        self._singletons[interface] = instance
    
    def register_factory(
        self,
        interface: Type[T],
        factory: Callable[..., T]
    ) -> None:
        """注册工厂函数"""
        self._factories[interface] = factory
    
    def register_singleton(
        self,
        interface: Type[T],
        factory: Callable[[], T]
    ) -> None:
        """注册延迟初始化的单例"""
        self._registrations[interface] = factory
    
    def resolve(self, interface: Type[T]) -> T:
        """解析依赖"""
        # 1. 检查已存在的单例
        if interface in self._singletons:
            return self._singletons[interface]
        
        # 2. 检查工厂
        if interface in self._factories:
            return self._factories[interface]()
        
        # 3. 延迟初始化单例
        if interface in self._registrations:
            instance = self._registrations[interface]()
            self._singletons[interface] = instance
            return instance
        
        raise KeyError(f"未注册的类型: {interface}")
    
    async def resolve_async(self, interface: Type[T]) -> T:
        """异步解析（用于需要初始化的依赖）"""
        if interface in self._singletons:
            return self._singletons[interface]
        
        if interface in self._factories:
            result = self._factories[interface]()
            if asyncio.iscoroutine(result):
                return await result
            return result
        
        raise KeyError(f"未注册的类型: {interface}")
    
    def has(self, interface: Type) -> bool:
        """检查是否注册了类型"""
        return (
            interface in self._singletons or
            interface in self._factories or
            interface in self._registrations
        )
    
    def build(self, cls: Type[T]) -> T:
        """自动构建类，解析构造函数依赖"""
        sig = inspect.signature(cls.__init__)
        params = list(sig.parameters.items())[1:]  # 跳过 self
        
        kwargs = {}
        for name, param in params:
            if param.annotation != inspect.Parameter.empty:
                try:
                    kwargs[name] = self.resolve(param.annotation)
                except KeyError:
                    if param.default != inspect.Parameter.empty:
                        kwargs[name] = param.default
                    else:
                        raise
            elif param.default != inspect.Parameter.empty:
                kwargs[name] = param.default
        
        return cls(**kwargs)
    
    def clear(self) -> None:
        """清空容器"""
        self._registrations.clear()
        self._singletons.clear()
        self._factories.clear()


# 全局容器实例
_container: Optional[Container] = None


def get_container() -> Container:
    """获取全局容器"""
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> Container:
    """重置容器（用于测试）"""
    global _container
    _container = Container()
    return _container
