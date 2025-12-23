"""
延迟加载模块

使用 PEP 562 __getattr__ 实现模块级延迟加载
优化启动速度，实现按需导入
"""

import sys
from typing import Any, Dict, Optional, Callable
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# 模块映射表：模块名 -> (导入路径, 延迟加载函数)
_MODULE_MAP: Dict[str, tuple[str, Optional[Callable]]] = {
    # 核心模块 - 必须立即加载
    "config": ("qbittorrent_monitor.config", None),
    "exceptions": ("qbittorrent_monitor.exceptions", None),
    
    # Web 界面模块 - 延迟加载
    "web_interface": ("qbittorrent_monitor.web_interface", None),
    "web_app": ("qbittorrent_monitor.web_interface.app", None),
    
    # 剪贴板监控 - 延迟加载
    "clipboard_monitor": ("qbittorrent_monitor.clipboard_monitor", None),
    "clipboard_actions": ("qbittorrent_monitor.clipboard_actions", None),
    
    # qBittorrent 客户端 - 延迟加载
    "qbittorrent_client": ("qbittorrent_monitor.qbittorrent_client", None),
    "qbittorrent_client_enhanced": ("qbittorrent_monitor.qbittorrent_client_enhanced", None),
    
    # RSS 管理器 - 延迟加载
    "rss_manager": ("qbittorrent_monitor.rss_manager", None),
    
    # 通知模块 - 延迟加载
    "notifications": ("qbittorrent_monitor.notifications", None),
    "notifications_enhanced": ("qbittorrent_monitor.notifications_enhanced", None),
    
    # AI 分类器 - 延迟加载
    "ai_classifier": ("qbittorrent_monitor.ai_classifier", None),
    
    # 网页爬虫 - 延迟加载
    "web_crawler": ("qbittorrent_monitor.web_crawler", None),
    "web_crawler_enhanced": ("qbittorrent_monitor.web_crawler_enhanced", None),
    
    # 监控与健康检查 - 延迟加载
    "monitoring": ("qbittorrent_monitor.monitoring", None),
    "health_check": ("qbittorrent_monitor.health_check", None),
    
    # 工作流引擎 - 延迟加载
    "workflow_engine": ("qbittorrent_monitor.workflow_engine", None),
    
    # 工具模块 - 延迟加载
    "utils": ("qbittorrent_monitor.utils", None),
    "resilience": ("qbittorrent_monitor.resilience", None),
    "retry": ("qbittorrent_monitor.retry", None),
    
    # 缓存模块 - 延迟加载
    "enhanced_cache": ("qbittorrent_monitor.enhanced_cache", None),
    
    # 日志模块 - 延迟加载
    "logging_config": ("qbittorrent_monitor.logging_config", None),
    "logging_enhanced": ("qbittorrent_monitor.logging_enhanced", None),
}


# 已缓存的模块
_CACHED_MODULES: Dict[str, Any] = {}


def _import_module(module_path: str) -> Any:
    """动态导入模块"""
    try:
        import importlib
        parts = module_path.split('.')
        
        if len(parts) == 1:
            # 简单模块
            return __import__(module_path)
        else:
            # 嵌套模块
            return importlib.import_module(module_path)
            
    except ImportError as e:
        logger.error(f"导入模块失败 {module_path}: {e}")
        raise


def lazy_getattr(name: str) -> Any:
    """延迟获取属性（PEP 562 实现）"""
    # 检查是否在映射表中
    if name in _MODULE_MAP:
        # 检查是否已缓存
        if name in _CACHED_MODULES:
            return _CACHED_MODULES[name]
        
        # 获取模块信息
        module_path, _ = _MODULE_MAP[name]
        
        try:
            # 动态导入
            module = _import_module(module_path)
            _CACHED_MODULES[name] = module
            logger.debug(f"延迟加载模块: {module_path}")
            return module
        except ImportError as e:
            logger.warning(f"无法延迟加载模块 {name}: {e}")
            raise AttributeError(f"模块 {name} 不可用")
    
    # 不在映射表中，抛出 AttributeError
    raise AttributeError(f"模块 'qbittorrent_monitor' 没有属性 '{name}'")


def preload_modules(module_names: Optional[list[str]] = None) -> None:
    """预热模块缓存"""
    if module_names is None:
        # 预热所有映射的模块
        module_names = list(_MODULE_MAP.keys())
    
    for name in module_names:
        if name not in _CACHED_MODULES:
            try:
                _ = lazy_getattr(name)  # 触发加载
            except (ImportError, AttributeError):
                pass  # 忽略加载失败的模块


def preload_critical_modules() -> None:
    """预热关键模块"""
    critical = [
        "config",
        "exceptions",
        "utils",
    ]
    preload_modules(critical)


def clear_cache(module_name: Optional[str] = None) -> None:
    """清除模块缓存"""
    global _CACHED_MODULES
    
    if module_name:
        _CACHED_MODULES.pop(module_name, None)
        # 从 sys.modules 中移除
        if module_name in sys.modules:
            del sys.modules[module_name]
    else:
        _CACHED_MODULES.clear()


def get_cached_modules() -> Dict[str, Any]:
    """获取已缓存的模块"""
    return _CACHED_MODULES.copy()


def is_module_cached(module_name: str) -> bool:
    """检查模块是否已缓存"""
    return module_name in _CACHED_MODULES


# 在包级别实现 PEP 562 __getattr__
# 这使得 from qbittorrent_monitor import xxx 会触发延迟加载
def __getattr__(name: str) -> Any:
    """模块级 __getattr__ (PEP 562)"""
    return lazy_getattr(name)


def __dir__() -> list:
    """列出可用的模块属性"""
    # 返回所有映射的模块名
    return list(_MODULE_MAP.keys()) + list(globals().keys())


# ============================================================================
# 便捷导入函数
# ============================================================================

def import_config() -> Any:
    """导入配置模块"""
    from . import config
    return config


def import_clipboard_monitor() -> Any:
    """导入剪贴板监控模块"""
    from . import clipboard_monitor
    return clipboard_monitor


def import_qbittorrent_client() -> Any:
    """导入 qBittorrent 客户端模块"""
    from . import qbittorrent_client
    return qbittorrent_client


def import_rss_manager() -> Any:
    """导入 RSS 管理器模块"""
    from . import rss_manager
    return rss_manager


def import_notifications() -> Any:
    """导入通知模块"""
    from . import notifications
    return notifications


def import_ai_classifier() -> Any:
    """导入 AI 分类器模块"""
    from . import ai_classifier
    return ai_classifier


def import_web_interface() -> Any:
    """导入 Web 界面模块"""
    from . import web_interface
    return web_interface


def import_health_check() -> Any:
    """导入健康检查模块"""
    from . import health_check
    return health_check


def import_workflow_engine() -> Any:
    """导入工作流引擎模块"""
    from . import workflow_engine
    return workflow_engine


def import_web_crawler() -> Any:
    """导入网页爬虫模块"""
    from . import web_crawler
    return web_crawler


# ============================================================================
# 启动时预热
# ============================================================================

# 在模块导入时预热关键模块
preload_critical_modules()
