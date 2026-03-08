"""插件管理器

负责插件的加载、启用、禁用和生命周期管理。
"""

import importlib
import importlib.util
import inspect
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, Callable
import asyncio

from .base import BasePlugin, PluginMetadata, PluginState, PluginType
from .hooks import HookRegistry, HookType

logger = logging.getLogger(__name__)


class PluginManager:
    """插件管理器
    
    管理所有插件的生命周期，包括发现、加载、启用、禁用和卸载。
    
    Attributes:
        plugins_dir: 插件目录
        config_dir: 插件配置目录
        auto_discover: 是否自动发现插件
    
    Example:
        >>> manager = PluginManager()
        >>> await manager.load_plugins()
        >>> await manager.enable_all()
        >>> 
        >>> # 获取通知插件
        >>> notifiers = manager.get_plugins_by_type(PluginType.NOTIFIER)
    """
    
    # 内置插件路径
    BUILTIN_PLUGINS_PATH = Path(__file__).parent.parent / "plugins"
    
    def __init__(
        self,
        plugins_dir: Optional[Path] = None,
        config_dir: Optional[Path] = None,
        auto_discover: bool = True
    ):
        """初始化插件管理器
        
        Args:
            plugins_dir: 外部插件目录，默认 ~/.config/qb-monitor/plugins/
            config_dir: 插件配置目录，默认 ~/.config/qb-monitor/plugins/config/
            auto_discover: 是否自动发现插件
        """
        self._plugins: Dict[str, BasePlugin] = {}
        self._states: Dict[str, PluginState] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._hooks = HookRegistry()
        
        # 设置目录
        home = Path.home()
        self.plugins_dir = plugins_dir or (home / ".config" / "qb-monitor" / "plugins")
        self.config_dir = config_dir or (home / ".config" / "qb-monitor" / "plugins" / "config")
        
        self._auto_discover = auto_discover
        self._loaded = False
        
        # 确保目录存在
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"插件管理器初始化完成，插件目录: {self.plugins_dir}")
    
    # ==================== 插件发现 ====================
    
    async def discover_plugins(self) -> List[Type[BasePlugin]]:
        """发现所有可用插件
        
        扫描内置插件目录和外部插件目录。
        
        Returns:
            发现的插件类列表
        """
        discovered: List[Type[BasePlugin]] = []
        
        # 发现内置插件
        builtin_plugins = await self._discover_in_directory(
            self.BUILTIN_PLUGINS_PATH, 
            is_builtin=True
        )
        discovered.extend(builtin_plugins)
        
        # 发现外部插件
        if self.plugins_dir.exists():
            external_plugins = await self._discover_in_directory(
                self.plugins_dir,
                is_builtin=False
            )
            discovered.extend(external_plugins)
        
        logger.info(f"发现 {len(discovered)} 个插件类")
        return discovered
    
    async def _discover_in_directory(
        self, 
        directory: Path, 
        is_builtin: bool
    ) -> List[Type[BasePlugin]]:
        """在指定目录发现插件
        
        Args:
            directory: 要扫描的目录
            is_builtin: 是否为内置插件
            
        Returns:
            插件类列表
        """
        discovered: List[Type[BasePlugin]] = []
        
        if not directory.exists():
            return discovered
        
        # 扫描子目录中的 Python 文件
        for item in directory.iterdir():
            if item.is_dir() and not item.name.startswith("__"):
                # 子包模式 (plugins/notifiers/webhook.py)
                for py_file in item.glob("*.py"):
                    if py_file.name.startswith("__"):
                        continue
                    plugin_class = self._load_plugin_class(py_file, is_builtin)
                    if plugin_class:
                        discovered.append(plugin_class)
                        
            elif item.is_file() and item.suffix == ".py" and not item.name.startswith("__"):
                # 独立文件模式
                plugin_class = self._load_plugin_class(item, is_builtin)
                if plugin_class:
                    discovered.append(plugin_class)
        
        return discovered
    
    def _load_plugin_class(
        self, 
        file_path: Path, 
        is_builtin: bool
    ) -> Optional[Type[BasePlugin]]:
        """从文件加载插件类
        
        Args:
            file_path: Python 文件路径
            is_builtin: 是否为内置插件
            
        Returns:
            插件类或 None
        """
        try:
            # 构建模块名
            if is_builtin:
                relative = file_path.relative_to(self.BUILTIN_PLUGINS_PATH.parent)
                module_name = f"qbittorrent_monitor.{relative.with_suffix('').as_posix().replace('/', '.')}"
            else:
                # 外部插件需要动态加载
                module_name = f"qbmonitor_plugin_{file_path.stem}"
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if not spec or not spec.loader:
                    return None
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # 在模块中查找插件类
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, BasePlugin) and 
                        obj is not BasePlugin and
                        not obj.__name__.startswith("Base")):
                        return obj
                return None
            
            # 导入内置模块
            module = importlib.import_module(module_name)
            
            # 查找插件类
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BasePlugin) and 
                    obj is not BasePlugin and
                    not obj.__name__.startswith("Base")):
                    return obj
                    
        except Exception as e:
            logger.warning(f"加载插件文件失败 {file_path}: {e}")
            
        return None
    
    # ==================== 插件加载 ====================
    
    async def load_plugins(self) -> int:
        """加载所有发现的插件
        
        Returns:
            加载的插件数量
        """
        if self._loaded:
            return len(self._plugins)
            
        discovered = await self.discover_plugins()
        loaded_count = 0
        
        for plugin_class in discovered:
            try:
                # 创建实例
                plugin = plugin_class()
                name = plugin.name
                
                # 检查名称冲突
                if name in self._plugins:
                    logger.warning(f"插件名称冲突: {name}，跳过")
                    continue
                
                # 加载配置
                config = self._load_plugin_config(name)
                if config:
                    errors = plugin.configure(config)
                    if errors:
                        logger.warning(f"插件 {name} 配置验证失败: {errors}")
                
                # 注册插件
                self._plugins[name] = plugin
                self._states[name] = PluginState.LOADED
                loaded_count += 1
                
                logger.debug(f"已加载插件: {name} ({plugin.metadata.plugin_type.value})")
                
            except Exception as e:
                logger.error(f"加载插件类失败: {e}")
        
        self._loaded = True
        logger.info(f"成功加载 {loaded_count} 个插件")
        return loaded_count
    
    def _load_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """加载插件配置
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            配置字典
        """
        config_file = self.config_dir / f"{plugin_name}.json"
        
        if not config_file.exists():
            return {}
            
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载插件配置失败 {plugin_name}: {e}")
            return {}
    
    def _save_plugin_config(self, plugin_name: str) -> bool:
        """保存插件配置
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            保存是否成功
        """
        if plugin_name not in self._plugins:
            return False
            
        config_file = self.config_dir / f"{plugin_name}.json"
        
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self._plugins[plugin_name].config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存插件配置失败 {plugin_name}: {e}")
            return False
    
    # ==================== 插件控制 ====================
    
    async def enable_plugin(self, name: str) -> bool:
        """启用指定插件
        
        Args:
            name: 插件名称
            
        Returns:
            启用是否成功
        """
        if name not in self._plugins:
            logger.error(f"插件不存在: {name}")
            return False
            
        plugin = self._plugins[name]
        
        # 检查依赖
        for dep in plugin.metadata.dependencies:
            if dep not in self._plugins:
                logger.error(f"插件 {name} 依赖 {dep} 未加载")
                return False
            if not self._plugins[dep].is_enabled:
                success = await self.enable_plugin(dep)
                if not success:
                    logger.error(f"插件 {name} 的依赖 {dep} 启用失败")
                    return False
        
        # 启用插件
        success = await plugin.enable()
        if success:
            self._states[name] = PluginState.ENABLED
            # 触发钩子
            await self._hooks.invoke(HookType.PLUGIN_LOAD, plugin)
            
        return success
    
    async def disable_plugin(self, name: str) -> bool:
        """禁用指定插件
        
        Args:
            name: 插件名称
            
        Returns:
            禁用是否成功
        """
        if name not in self._plugins:
            logger.error(f"插件不存在: {name}")
            return False
            
        plugin = self._plugins[name]
        success = await plugin.disable()
        
        if success:
            self._states[name] = PluginState.DISABLED
            # 触发钩子
            await self._hooks.invoke(HookType.PLUGIN_UNLOAD, plugin)
            
        return success
    
    async def unload_plugin(self, name: str) -> bool:
        """卸载插件
        
        Args:
            name: 插件名称
            
        Returns:
            卸载是否成功
        """
        if name not in self._plugins:
            return False
            
        # 先禁用
        if self._plugins[name].is_enabled:
            await self.disable_plugin(name)
        
        # 移除
        del self._plugins[name]
        del self._states[name]
        if name in self._configs:
            del self._configs[name]
            
        logger.info(f"已卸载插件: {name}")
        return True
    
    async def enable_all(self) -> Dict[str, bool]:
        """启用所有已加载的插件
        
        Returns:
            每个插件的启用结果
        """
        results = {}
        for name in self._plugins:
            results[name] = await self.enable_plugin(name)
        return results
    
    async def disable_all(self) -> Dict[str, bool]:
        """禁用所有已启用的插件
        
        Returns:
            每个插件的禁用结果
        """
        results = {}
        for name, plugin in self._plugins.items():
            if plugin.is_enabled:
                results[name] = await self.disable_plugin(name)
        return results
    
    # ==================== 插件查询 ====================
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """获取指定插件
        
        Args:
            name: 插件名称
            
        Returns:
            插件实例或 None
        """
        return self._plugins.get(name)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[BasePlugin]:
        """获取指定类型的所有插件
        
        Args:
            plugin_type: 插件类型
            
        Returns:
            插件列表
        """
        return [
            p for p in self._plugins.values()
            if p.metadata.plugin_type == plugin_type
        ]
    
    def get_enabled_plugins(self) -> List[BasePlugin]:
        """获取所有已启用的插件
        
        Returns:
            已启用插件列表
        """
        return [p for p in self._plugins.values() if p.is_enabled]
    
    def get_plugin_names(self) -> List[str]:
        """获取所有插件名称
        
        Returns:
            插件名称列表
        """
        return list(self._plugins.keys())
    
    def is_loaded(self, name: str) -> bool:
        """检查插件是否已加载
        
        Args:
            name: 插件名称
            
        Returns:
            是否已加载
        """
        return name in self._plugins
    
    def is_enabled(self, name: str) -> bool:
        """检查插件是否已启用
        
        Args:
            name: 插件名称
            
        Returns:
            是否已启用
        """
        return name in self._plugins and self._plugins[name].is_enabled
    
    # ==================== 配置管理 ====================
    
    def configure_plugin(self, name: str, config: Dict[str, Any]) -> List[str]:
        """配置指定插件
        
        Args:
            name: 插件名称
            config: 配置字典
            
        Returns:
            验证错误列表
        """
        if name not in self._plugins:
            return [f"插件不存在: {name}"]
            
        plugin = self._plugins[name]
        errors = plugin.configure(config)
        
        if not errors:
            self._save_plugin_config(name)
            
        return errors
    
    def get_plugin_config(self, name: str) -> Optional[Dict[str, Any]]:
        """获取插件配置
        
        Args:
            name: 插件名称
            
        Returns:
            配置字典或 None
        """
        if name not in self._plugins:
            return None
        return self._plugins[name].config
    
    # ==================== 便捷方法 ====================
    
    async def notify_all(
        self, 
        title: str, 
        message: str, 
        **kwargs
    ) -> Dict[str, bool]:
        """调用所有已启用的通知插件
        
        Args:
            title: 通知标题
            message: 通知内容
            **kwargs: 额外参数
            
        Returns:
            每个插件的发送结果
        """
        from .base import NotifierPlugin
        
        results = {}
        notifiers = self.get_plugins_by_type(PluginType.NOTIFIER)
        
        for plugin in notifiers:
            if plugin.is_enabled and isinstance(plugin, NotifierPlugin):
                try:
                    results[plugin.name] = await plugin.notify(title, message, **kwargs)
                except Exception as e:
                    logger.error(f"通知插件 {plugin.name} 执行失败: {e}")
                    results[plugin.name] = False
                    
        return results
    
    async def classify_with_plugins(
        self, 
        name: str, 
        **kwargs
    ) -> List["ClassificationResult"]:
        """使用所有分类器插件进行分类
        
        Args:
            name: 内容名称
            **kwargs: 额外参数
            
        Returns:
            分类结果列表
        """
        from .base import ClassifierPlugin, ClassificationResult
        
        results = []
        classifiers = self.get_plugins_by_type(PluginType.CLASSIFIER)
        
        for plugin in classifiers:
            if plugin.is_enabled and isinstance(plugin, ClassifierPlugin):
                try:
                    result = await plugin.classify(name, **kwargs)
                    results.append(result)
                except Exception as e:
                    logger.error(f"分类器插件 {plugin.name} 执行失败: {e}")
                    
        return results
    
    async def handle_with_plugins(
        self, 
        content: str, 
        **kwargs
    ) -> Optional["HandlerResult"]:
        """使用处理器插件处理内容
        
        找到第一个可以处理该内容的插件并执行。
        
        Args:
            content: 要处理的内容
            **kwargs: 额外参数
            
        Returns:
            处理结果或 None
        """
        from .base import HandlerPlugin
        
        handlers = self.get_plugins_by_type(PluginType.HANDLER)
        
        for plugin in handlers:
            if plugin.is_enabled and isinstance(plugin, HandlerPlugin):
                try:
                    if await plugin.can_handle(content, **kwargs):
                        return await plugin.handle(content, **kwargs)
                except Exception as e:
                    logger.error(f"处理器插件 {plugin.name} 执行失败: {e}")
                    
        return None
    
    # ==================== 生命周期 ====================
    
    async def shutdown(self) -> None:
        """关闭所有插件"""
        await self.disable_all()
        self._plugins.clear()
        self._states.clear()
        self._loaded = False
        logger.info("插件管理器已关闭")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        total = len(self._plugins)
        enabled = sum(1 for p in self._plugins.values() if p.is_enabled)
        
        by_type = {}
        for plugin_type in PluginType:
            count = len(self.get_plugins_by_type(plugin_type))
            by_type[plugin_type.value] = count
        
        return {
            "total": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "by_type": by_type,
            "plugins": {
                name: {
                    "state": self._states.get(name, PluginState.UNLOADED).name,
                    "type": p.metadata.plugin_type.value,
                    "version": p.metadata.version,
                }
                for name, p in self._plugins.items()
            }
        }
