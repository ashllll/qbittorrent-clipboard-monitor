"""插件基类定义

定义所有插件的抽象基类和具体插件类型的接口。
"""

import abc
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Callable, Awaitable

logger = logging.getLogger(__name__)


class PluginType(Enum):
    """插件类型枚举"""
    NOTIFIER = "notifier"       # 通知插件
    CLASSIFIER = "classifier"   # 分类器插件
    HANDLER = "handler"         # 处理器插件
    CUSTOM = "custom"           # 自定义插件


class PluginState(Enum):
    """插件状态枚举"""
    UNLOADED = auto()     # 未加载
    LOADING = auto()      # 加载中
    LOADED = auto()       # 已加载
    ENABLING = auto()     # 启用中
    ENABLED = auto()      # 已启用
    DISABLING = auto()    # 禁用中
    DISABLED = auto()     # 已禁用
    ERROR = auto()        # 错误状态


@dataclass
class PluginMetadata:
    """插件元数据
    
    Attributes:
        name: 插件唯一标识名
        version: 插件版本
        description: 插件描述
        author: 作者信息
        plugin_type: 插件类型
        dependencies: 依赖的其他插件列表
        config_schema: 配置项定义
        entry_point: 插件入口类名
    """
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    plugin_type: PluginType = PluginType.CUSTOM
    dependencies: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    entry_point: str = "Plugin"

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """验证配置是否符合 schema
        
        Args:
            config: 要验证的配置字典
            
        Returns:
            错误信息列表，空列表表示验证通过
        """
        errors = []
        
        for key, schema_def in self.config_schema.items():
            if schema_def.get("required", False) and key not in config:
                errors.append(f"缺少必需配置项: {key}")
                continue
                
            if key in config:
                value = config[key]
                value_type = schema_def.get("type")
                
                if value_type == "string" and not isinstance(value, str):
                    errors.append(f"配置项 {key} 必须是字符串")
                elif value_type == "integer" and not isinstance(value, int):
                    errors.append(f"配置项 {key} 必须是整数")
                elif value_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"配置项 {key} 必须是布尔值")
                elif value_type == "list" and not isinstance(value, list):
                    errors.append(f"配置项 {key} 必须是列表")
                elif value_type == "dict" and not isinstance(value, dict):
                    errors.append(f"配置项 {key} 必须是字典")
                    
                # 验证枚举值
                if "enum" in schema_def and value not in schema_def["enum"]:
                    errors.append(f"配置项 {key} 必须是以下值之一: {schema_def['enum']}")
                    
        return errors


class BasePlugin(abc.ABC):
    """插件抽象基类
    
    所有插件必须继承此类并实现必要的方法。
    
    Example:
        >>> class MyPlugin(BasePlugin):
        ...     @property
        ...     def metadata(self) -> PluginMetadata:
        ...         return PluginMetadata(
        ...             name="my_plugin",
        ...             version="1.0.0",
        ...             plugin_type=PluginType.CUSTOM
        ...         )
        ...     
        ...     async def initialize(self) -> bool:
        ...         # 初始化逻辑
        ...         return True
        ...     
        ...     async def shutdown(self) -> None:
        ...         # 清理逻辑
        ...         pass
    """
    
    def __init__(self):
        self._state = PluginState.UNLOADED
        self._config: Dict[str, Any] = {}
        self._plugin_dir: Optional[Path] = None
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._created_at = datetime.now()
        self._enabled_at: Optional[datetime] = None
        
    @property
    @abc.abstractmethod
    def metadata(self) -> PluginMetadata:
        """返回插件元数据"""
        pass
    
    @property
    def state(self) -> PluginState:
        """返回当前插件状态"""
        return self._state
    
    @property
    def config(self) -> Dict[str, Any]:
        """返回当前配置"""
        return self._config.copy()
    
    @property
    def name(self) -> str:
        """返回插件名称"""
        return self.metadata.name
    
    @property
    def is_enabled(self) -> bool:
        """检查插件是否已启用"""
        return self._state == PluginState.ENABLED
    
    def _set_state(self, state: PluginState) -> None:
        """设置插件状态（内部方法）"""
        old_state = self._state
        self._state = state
        
        if state == PluginState.ENABLED:
            self._enabled_at = datetime.now()
            
        self._logger.debug(f"插件 {self.name} 状态变更: {old_state.name} -> {state.name}")
    
    def configure(self, config: Dict[str, Any]) -> List[str]:
        """配置插件
        
        Args:
            config: 配置字典
            
        Returns:
            验证错误列表，空列表表示配置成功
        """
        # 验证配置
        errors = self.metadata.validate_config(config)
        if errors:
            return errors
            
        # 应用配置
        self._config.update(config)
        self._logger.debug(f"插件 {self.name} 已更新配置")
        return []
    
    @abc.abstractmethod
    async def initialize(self) -> bool:
        """初始化插件
        
        在插件加载后调用，用于初始化资源、连接服务等。
        
        Returns:
            初始化是否成功
        """
        pass
    
    @abc.abstractmethod
    async def shutdown(self) -> None:
        """关闭插件
        
        在插件卸载或禁用时调用，用于清理资源。
        """
        pass
    
    async def enable(self) -> bool:
        """启用插件
        
        Returns:
            启用是否成功
        """
        if self._state == PluginState.ENABLED:
            return True
            
        if self._state not in (PluginState.LOADED, PluginState.DISABLED):
            self._logger.warning(f"插件 {self.name} 当前状态 {self._state.name} 无法启用")
            return False
            
        try:
            self._set_state(PluginState.ENABLING)
            success = await self.initialize()
            
            if success:
                self._set_state(PluginState.ENABLED)
                self._logger.info(f"插件 {self.name} 已启用")
                return True
            else:
                self._set_state(PluginState.ERROR)
                self._logger.error(f"插件 {self.name} 初始化失败")
                return False
                
        except Exception as e:
            self._set_state(PluginState.ERROR)
            self._logger.exception(f"启用插件 {self.name} 时发生错误: {e}")
            return False
    
    async def disable(self) -> bool:
        """禁用插件
        
        Returns:
            禁用是否成功
        """
        if self._state == PluginState.DISABLED:
            return True
            
        if self._state != PluginState.ENABLED:
            self._logger.warning(f"插件 {self.name} 当前状态 {self._state.name} 无法禁用")
            return False
            
        try:
            self._set_state(PluginState.DISABLING)
            await self.shutdown()
            self._set_state(PluginState.DISABLED)
            self._logger.info(f"插件 {self.name} 已禁用")
            return True
            
        except Exception as e:
            self._set_state(PluginState.ERROR)
            self._logger.exception(f"禁用插件 {self.name} 时发生错误: {e}")
            return False
    
    def on_event(self, event_name: str, handler: Callable) -> None:
        """注册事件处理器
        
        Args:
            event_name: 事件名称
            handler: 处理函数
        """
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)
        
    def emit_event(self, event_name: str, *args, **kwargs) -> None:
        """触发事件
        
        Args:
            event_name: 事件名称
            *args: 位置参数
            **kwargs: 关键字参数
        """
        handlers = self._event_handlers.get(event_name, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(*args, **kwargs))
                else:
                    handler(*args, **kwargs)
            except Exception as e:
                self._logger.error(f"事件处理器执行失败: {e}")
                
    def get_info(self) -> Dict[str, Any]:
        """获取插件信息
        
        Returns:
            包含插件信息的字典
        """
        return {
            "name": self.name,
            "version": self.metadata.version,
            "description": self.metadata.description,
            "author": self.metadata.author,
            "type": self.metadata.plugin_type.value,
            "state": self._state.name,
            "is_enabled": self.is_enabled,
            "created_at": self._created_at.isoformat(),
            "enabled_at": self._enabled_at.isoformat() if self._enabled_at else None,
            "config_keys": list(self._config.keys()),
        }


class NotifierPlugin(BasePlugin):
    """通知插件基类
    
    用于发送各种通知，如下载完成、错误告警等。
    
    Example:
        >>> class EmailNotifier(NotifierPlugin):
        ...     @property
        ...     def metadata(self) -> PluginMetadata:
        ...         return PluginMetadata(
        ...             name="email_notifier",
        ...             plugin_type=PluginType.NOTIFIER,
        ...             config_schema={
        ...                 "smtp_host": {"type": "string", "required": True},
        ...                 "smtp_port": {"type": "integer", "required": True},
        ...             }
        ...         )
        ...     
        ...     async def notify(self, title: str, message: str, **kwargs) -> bool:
        ...         # 发送邮件逻辑
        ...         return True
    """
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="base_notifier",
            plugin_type=PluginType.NOTIFIER
        )
    
    @abc.abstractmethod
    async def notify(self, title: str, message: str, **kwargs) -> bool:
        """发送通知
        
        Args:
            title: 通知标题
            message: 通知内容
            **kwargs: 额外的通知参数
            
        Returns:
            发送是否成功
        """
        pass
    
    async def notify_download_complete(
        self, 
        torrent_name: str, 
        category: str,
        save_path: str,
        **kwargs
    ) -> bool:
        """下载完成通知（便捷方法）
        
        Args:
            torrent_name: 种子名称
            category: 分类
            save_path: 保存路径
            **kwargs: 额外参数
            
        Returns:
            发送是否成功
        """
        return await self.notify(
            title=f"下载完成: {torrent_name}",
            message=f"分类: {category}\n保存路径: {save_path}",
            torrent_name=torrent_name,
            category=category,
            save_path=save_path,
            event_type="download_complete",
            **kwargs
        )
    
    async def notify_error(
        self, 
        error_message: str, 
        context: Optional[Dict] = None,
        **kwargs
    ) -> bool:
        """错误通知（便捷方法）
        
        Args:
            error_message: 错误信息
            context: 错误上下文
            **kwargs: 额外参数
            
        Returns:
            发送是否成功
        """
        return await self.notify(
            title="qBittorrent Monitor 错误",
            message=error_message,
            context=context or {},
            event_type="error",
            **kwargs
        )
    
    async def initialize(self) -> bool:
        """默认初始化，子类可覆盖"""
        return True
    
    async def shutdown(self) -> None:
        """默认关闭，子类可覆盖"""
        pass


class ClassifierPlugin(BasePlugin):
    """分类器插件基类
    
    用于自定义内容分类逻辑。
    
    Example:
        >>> class CustomClassifier(ClassifierPlugin):
        ...     async def classify(self, name: str, **kwargs) -> ClassificationResult:
        ...         # 自定义分类逻辑
        ...         return ClassificationResult(
        ...             category="custom",
        ...             confidence=0.9,
        ...             method="custom_classifier"
        ...         )
    """
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="base_classifier",
            plugin_type=PluginType.CLASSIFIER
        )
    
    @abc.abstractmethod
    async def classify(self, name: str, **kwargs) -> "ClassificationResult":
        """分类内容
        
        Args:
            name: 内容名称
            **kwargs: 额外参数
            
        Returns:
            分类结果
        """
        pass
    
    async def initialize(self) -> bool:
        """默认初始化，子类可覆盖"""
        return True
    
    async def shutdown(self) -> None:
        """默认关闭，子类可覆盖"""
        pass


@dataclass
class ClassificationResult:
    """分类结果"""
    category: str
    confidence: float  # 0.0 - 1.0
    method: str        # 分类方法标识
    metadata: Dict[str, Any] = field(default_factory=dict)


class HandlerPlugin(BasePlugin):
    """处理器插件基类
    
    用于处理特定类型的内容或事件。
    
    Example:
        >>> class RSSHandler(HandlerPlugin):
        ...     async def can_handle(self, content: str, **kwargs) -> bool:
        ...         return content.startswith("rss://")
        ...     
        ...     async def handle(self, content: str, **kwargs) -> HandlerResult:
        ...         # 处理 RSS 内容
        ...         return HandlerResult(success=True, message="已处理")
    """
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="base_handler",
            plugin_type=PluginType.HANDLER
        )
    
    @abc.abstractmethod
    async def can_handle(self, content: str, **kwargs) -> bool:
        """检查是否可以处理该内容
        
        Args:
            content: 要检查的内容
            **kwargs: 额外参数
            
        Returns:
            是否可以处理
        """
        pass
    
    @abc.abstractmethod
    async def handle(self, content: str, **kwargs) -> "HandlerResult":
        """处理内容
        
        Args:
            content: 要处理的内容
            **kwargs: 额外参数
            
        Returns:
            处理结果
        """
        pass
    
    async def initialize(self) -> bool:
        """默认初始化，子类可覆盖"""
        return True
    
    async def shutdown(self) -> None:
        """默认关闭，子类可覆盖"""
        pass


@dataclass
class HandlerResult:
    """处理结果"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
