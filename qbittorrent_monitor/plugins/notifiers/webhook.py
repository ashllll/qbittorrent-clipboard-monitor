"""Webhook 通知插件

支持发送 HTTP POST 请求到指定的 Webhook 地址。
"""

import json
import logging
from typing import Any, Dict, Optional

import aiohttp

from ..base import NotifierPlugin, PluginMetadata, PluginType
from ...security import get_secure_headers

logger = logging.getLogger(__name__)


class WebhookNotifier(NotifierPlugin):
    """Webhook 通知插件
    
    发送 HTTP POST 请求到指定的 Webhook URL。
    
    配置项:
        - url: Webhook URL (必需)
        - method: HTTP 方法，默认 POST
        - headers: 自定义请求头
        - timeout: 请求超时时间（秒），默认 30
        - template: 消息模板，支持 {title} 和 {message} 占位符
        - retry_count: 失败重试次数，默认 3
    
    Example:
        >>> plugin = WebhookNotifier()
        >>> plugin.configure({
        ...     "url": "https://hooks.example.com/notify",
        ...     "headers": {"Authorization": "Bearer token123"}
        ... })
        >>> await plugin.notify("测试标题", "测试消息")
    """
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="webhook_notifier",
            version="1.0.0",
            description="通过 HTTP Webhook 发送通知",
            author="qBittorrent Monitor",
            plugin_type=PluginType.NOTIFIER,
            config_schema={
                "url": {
                    "type": "string",
                    "required": True,
                    "description": "Webhook URL"
                },
                "method": {
                    "type": "string",
                    "required": False,
                    "enum": ["POST", "PUT", "PATCH"],
                    "description": "HTTP 方法"
                },
                "headers": {
                    "type": "dict",
                    "required": False,
                    "description": "自定义请求头"
                },
                "timeout": {
                    "type": "integer",
                    "required": False,
                    "description": "请求超时时间（秒）"
                },
                "template": {
                    "type": "dict",
                    "required": False,
                    "description": "消息模板"
                },
                "retry_count": {
                    "type": "integer",
                    "required": False,
                    "description": "失败重试次数"
                }
            }
        )
    
    def __init__(self):
        super().__init__()
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def initialize(self) -> bool:
        """初始化 HTTP 会话"""
        try:
            timeout = aiohttp.ClientTimeout(
                total=self._config.get("timeout", 30)
            )
            self._session = aiohttp.ClientSession(timeout=timeout)
            logger.debug("WebhookNotifier 初始化成功")
            return True
        except Exception as e:
            logger.error(f"WebhookNotifier 初始化失败: {e}")
            return False
    
    async def shutdown(self) -> None:
        """关闭 HTTP 会话"""
        if self._session:
            await self._session.close()
            self._session = None
            logger.debug("WebhookNotifier 已关闭")
    
    async def notify(self, title: str, message: str, **kwargs) -> bool:
        """发送 Webhook 通知
        
        Args:
            title: 通知标题
            message: 通知内容
            **kwargs: 额外参数，会合并到 payload 中
            
        Returns:
            发送是否成功
        """
        url = self._config.get("url")
        if not url:
            logger.error("Webhook URL 未配置")
            return False
        
        if not self._session:
            logger.error("HTTP 会话未初始化")
            return False
        
        # 构建请求头
        headers = get_secure_headers()
        custom_headers = self._config.get("headers", {})
        headers.update(custom_headers)
        headers["Content-Type"] = "application/json"
        
        # 构建 payload
        template = self._config.get("template", {})
        if template:
            payload = self._apply_template(template, title, message, **kwargs)
        else:
            payload = {
                "title": title,
                "message": message,
                "event_type": kwargs.get("event_type", "notification"),
                "timestamp": self._get_timestamp(),
                **kwargs
            }
        
        # 发送请求
        method = self._config.get("method", "POST").upper()
        retry_count = self._config.get("retry_count", 3)
        
        for attempt in range(retry_count + 1):
            try:
                async with self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status < 400:
                        logger.debug(f"Webhook 通知发送成功: {url}")
                        return True
                    else:
                        text = await response.text()
                        logger.warning(f"Webhook 返回错误状态 {response.status}: {text}")
                        
            except aiohttp.ClientError as e:
                if attempt < retry_count:
                    logger.debug(f"Webhook 请求失败，重试 {attempt + 1}/{retry_count}: {e}")
                    await asyncio.sleep(1 * (attempt + 1))
                else:
                    logger.error(f"Webhook 通知发送失败: {e}")
                    
        return False
    
    def _apply_template(
        self, 
        template: Dict[str, Any], 
        title: str, 
        message: str,
        **kwargs
    ) -> Dict[str, Any]:
        """应用消息模板
        
        递归处理模板中的字符串，替换占位符。
        
        Args:
            template: 模板字典
            title: 通知标题
            message: 通知内容
            **kwargs: 额外参数
            
        Returns:
            处理后的 payload
        """
        def process_value(value):
            if isinstance(value, str):
                return value.format(
                    title=title,
                    message=message,
                    timestamp=self._get_timestamp(),
                    **kwargs
                )
            elif isinstance(value, dict):
                return {k: process_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [process_value(item) for item in value]
            return value
        
        return process_value(template)
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


# 导入 asyncio 用于重试延迟
import asyncio
