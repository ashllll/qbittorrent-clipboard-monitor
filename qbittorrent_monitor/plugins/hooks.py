"""钩子系统

提供插件间通信和事件处理机制。
"""

import asyncio
import logging
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Awaitable, Union
from functools import wraps

logger = logging.getLogger(__name__)

# 钩子回调类型
HookCallback = Callable[..., Awaitable[Any]]


class HookType(Enum):
    """钩子类型枚举
    
    定义系统中可用的钩子点。
    """
    # 内容处理钩子
    PRE_PROCESS = "pre_process"       # 处理前
    POST_PROCESS = "post_process"     # 处理后
    PRE_CLASSIFY = "pre_classify"     # 分类前
    POST_CLASSIFY = "post_classify"   # 分类后
    
    # 下载钩子
    PRE_DOWNLOAD = "pre_download"     # 下载前
    POST_DOWNLOAD = "post_download"   # 下载后
    DOWNLOAD_COMPLETE = "download_complete"  # 下载完成
    DOWNLOAD_ERROR = "download_error"        # 下载错误
    
    # 通知钩子
    PRE_NOTIFY = "pre_notify"         # 发送通知前
    POST_NOTIFY = "post_notify"       # 发送通知后
    
    # 系统钩子
    PLUGIN_LOAD = "plugin_load"       # 插件加载
    PLUGIN_UNLOAD = "plugin_unload"   # 插件卸载
    CONFIG_CHANGE = "config_change"   # 配置变更
    SHUTDOWN = "shutdown"             # 系统关闭


class HookPriority(Enum):
    """钩子优先级"""
    HIGHEST = 0
    HIGH = 25
    NORMAL = 50
    LOW = 75
    LOWEST = 100


class Hook:
    """钩子定义"""
    
    def __init__(
        self,
        callback: HookCallback,
        priority: HookPriority = HookPriority.NORMAL,
        plugin_name: Optional[str] = None,
        once: bool = False
    ):
        self.callback = callback
        self.priority = priority
        self.plugin_name = plugin_name
        self.once = once
        self.call_count = 0
        
    async def invoke(self, *args, **kwargs) -> Any:
        """调用钩子
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            钩子返回值
        """
        try:
            self.call_count += 1
            
            if asyncio.iscoroutinefunction(self.callback):
                return await self.callback(*args, **kwargs)
            else:
                return self.callback(*args, **kwargs)
                
        except Exception as e:
            logger.error(f"钩子执行失败 ({self.plugin_name}): {e}")
            raise
            
    def should_remove(self) -> bool:
        """检查是否应该移除（一次性钩子）"""
        return self.once and self.call_count > 0


class HookRegistry:
    """钩子注册表
    
    管理所有钩子的注册、调用和生命周期。
    
    Example:
        >>> registry = HookRegistry()
        >>> 
        >>> # 注册钩子
        >>> @registry.register(HookType.PRE_DOWNLOAD)
        >>> async def on_pre_download(magnet_url: str):
        ...     print(f"准备下载: {magnet_url}")
        ... 
        >>> # 调用钩子
        >>> results = await registry.invoke(HookType.PRE_DOWNLOAD, magnet_url="magnet:?...")
    """
    
    _instance: Optional["HookRegistry"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._hooks: Dict[HookType, List[Hook]] = {
            hook_type: [] for hook_type in HookType
        }
        self._initialized = True
        self._lock = asyncio.Lock()
        
    def register(
        self,
        hook_type: HookType,
        priority: HookPriority = HookPriority.NORMAL,
        plugin_name: Optional[str] = None,
        once: bool = False
    ) -> Callable:
        """注册钩子装饰器
        
        Args:
            hook_type: 钩子类型
            priority: 优先级
            plugin_name: 插件名称
            once: 是否只执行一次
            
        Returns:
            装饰器函数
        """
        def decorator(func: HookCallback) -> HookCallback:
            hook = Hook(
                callback=func,
                priority=priority,
                plugin_name=plugin_name or func.__module__,
                once=once
            )
            self._add_hook(hook_type, hook)
            return func
        return decorator
    
    def _add_hook(self, hook_type: HookType, hook: Hook) -> None:
        """添加钩子（内部方法）
        
        Args:
            hook_type: 钩子类型
            hook: 钩子实例
        """
        hooks = self._hooks[hook_type]
        hooks.append(hook)
        # 按优先级排序
        hooks.sort(key=lambda h: h.priority.value)
        
        logger.debug(f"已注册钩子 {hook_type.value} (优先级: {hook.priority.name})")
    
    def unregister(
        self,
        hook_type: HookType,
        callback: Optional[HookCallback] = None,
        plugin_name: Optional[str] = None
    ) -> int:
        """注销钩子
        
        Args:
            hook_type: 钩子类型
            callback: 要注销的回调函数，None 则注销该类型所有钩子
            plugin_name: 插件名称，指定则只注销该插件的钩子
            
        Returns:
            注销的钩子数量
        """
        hooks = self._hooks[hook_type]
        original_count = len(hooks)
        
        if callback is None and plugin_name is None:
            # 清除所有
            self._hooks[hook_type] = []
            return original_count
            
        # 过滤掉匹配的钩子
        self._hooks[hook_type] = [
            h for h in hooks 
            if not (
                (callback is None or h.callback == callback) and
                (plugin_name is None or h.plugin_name == plugin_name)
            )
        ]
        
        removed = original_count - len(self._hooks[hook_type])
        logger.debug(f"已注销 {removed} 个 {hook_type.value} 钩子")
        return removed
    
    async def invoke(
        self,
        hook_type: HookType,
        *args,
        stop_on_error: bool = False,
        **kwargs
    ) -> List[Any]:
        """调用钩子
        
        按优先级顺序调用所有注册的钩子。
        
        Args:
            hook_type: 钩子类型
            *args: 位置参数
            stop_on_error: 出错时是否停止
            **kwargs: 关键字参数
            
        Returns:
            所有钩子的返回值列表
        """
        hooks = self._hooks[hook_type].copy()
        results = []
        hooks_to_remove = []
        
        for hook in hooks:
            try:
                result = await hook.invoke(*args, **kwargs)
                results.append(result)
                
                # 检查是否需要移除
                if hook.should_remove():
                    hooks_to_remove.append(hook)
                    
            except Exception as e:
                logger.error(f"钩子 {hook_type.value} 执行失败: {e}")
                if stop_on_error:
                    raise
                    
        # 清理一次性钩子
        for hook in hooks_to_remove:
            self._hooks[hook_type].remove(hook)
            
        return results
    
    async def invoke_first(
        self,
        hook_type: HookType,
        *args,
        **kwargs
    ) -> Optional[Any]:
        """调用第一个钩子并返回结果
        
        用于只需要一个处理结果的场景。
        
        Args:
            hook_type: 钩子类型
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            第一个钩子的返回值，如果没有则返回 None
        """
        hooks = self._hooks[hook_type]
        if not hooks:
            return None
            
        for hook in hooks:
            try:
                return await hook.invoke(*args, **kwargs)
            except Exception as e:
                logger.error(f"钩子 {hook_type.value} 执行失败: {e}")
                continue
                
        return None
    
    async def invoke_filter(
        self,
        hook_type: HookType,
        data: Any,
        *args,
        **kwargs
    ) -> Any:
        """调用钩子链进行过滤
        
        每个钩子的返回值作为下一个钩子的输入，用于数据转换。
        
        Args:
            hook_type: 钩子类型
            data: 初始数据
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            经过所有钩子处理后的数据
        """
        hooks = self._hooks[hook_type]
        current_data = data
        
        for hook in hooks:
            try:
                result = await hook.invoke(current_data, *args, **kwargs)
                if result is not None:
                    current_data = result
            except Exception as e:
                logger.error(f"钩子 {hook_type.value} 执行失败: {e}")
                
        return current_data
    
    def get_hooks(
        self,
        hook_type: Optional[HookType] = None,
        plugin_name: Optional[str] = None
    ) -> List[Hook]:
        """获取钩子列表
        
        Args:
            hook_type: 钩子类型，None 则返回所有类型
            plugin_name: 插件名称，None 则返回所有插件
            
        Returns:
            钩子列表
        """
        if hook_type is not None:
            hooks = self._hooks[hook_type]
        else:
            hooks = []
            for h_list in self._hooks.values():
                hooks.extend(h_list)
                
        if plugin_name is not None:
            hooks = [h for h in hooks if h.plugin_name == plugin_name]
            
        return hooks
    
    def clear(self) -> None:
        """清除所有钩子"""
        for hook_type in self._hooks:
            self._hooks[hook_type] = []
        logger.info("已清除所有钩子")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        stats = {}
        total = 0
        
        for hook_type, hooks in self._hooks.items():
            count = len(hooks)
            stats[hook_type.value] = count
            total += count
            
        stats["total"] = total
        return stats


# 全局钩子注册表实例
hook_registry = HookRegistry()


def register_hook(
    hook_type: HookType,
    priority: HookPriority = HookPriority.NORMAL,
    plugin_name: Optional[str] = None,
    once: bool = False
):
    """全局钩子注册装饰器
    
    便捷函数，使用全局钩子注册表。
    
    Example:
        >>> @register_hook(HookType.PRE_DOWNLOAD)
        >>> async def my_hook(magnet_url: str):
        ...     print(f"准备下载: {magnet_url}")
    """
    return hook_registry.register(hook_type, priority, plugin_name, once)


async def invoke_hooks(
    hook_type: HookType,
    *args,
    stop_on_error: bool = False,
    **kwargs
) -> List[Any]:
    """全局调用钩子
    
    便捷函数，使用全局钩子注册表。
    """
    return await hook_registry.invoke(hook_type, *args, stop_on_error=stop_on_error, **kwargs)
