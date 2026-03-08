"""钉钉通知插件

支持钉钉群机器人的消息推送。
"""

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from typing import Any, Dict, Optional

import aiohttp

from ..base import NotifierPlugin, PluginMetadata, PluginType

logger = logging.getLogger(__name__)


class DingTalkNotifier(NotifierPlugin):
    """钉钉通知插件
    
    通过钉钉群机器人发送消息通知。
    
    配置项:
        - webhook_url: 钉钉机器人 Webhook 地址 (必需)
        - secret: 加签密钥（可选，用于安全验证）
        - at_mobiles: @用户的手机号列表
        - at_all: 是否 @所有人，默认 False
        - timeout: 请求超时时间（秒），默认 30
    
    Example:
        >>> plugin = DingTalkNotifier()
        >>> plugin.configure({
        ...     "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
        ...     "secret": "SECxxx",
        ...     "at_mobiles": ["13800138000"]
        ... })
        >>> await plugin.notify("下载完成", "电影已下载完成")
    """
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="dingtalk_notifier",
            version="1.0.0",
            description="通过钉钉群机器人发送通知",
            author="qBittorrent Monitor",
            plugin_type=PluginType.NOTIFIER,
            config_schema={
                "webhook_url": {
                    "type": "string",
                    "required": True,
                    "description": "钉钉机器人 Webhook 地址"
                },
                "secret": {
                    "type": "string",
                    "required": False,
                    "description": "加签密钥"
                },
                "at_mobiles": {
                    "type": "list",
                    "required": False,
                    "description": "@用户的手机号列表"
                },
                "at_all": {
                    "type": "boolean",
                    "required": False,
                    "description": "是否 @所有人"
                },
                "timeout": {
                    "type": "integer",
                    "required": False,
                    "description": "请求超时时间（秒）"
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
            logger.debug("DingTalkNotifier 初始化成功")
            return True
        except Exception as e:
            logger.error(f"DingTalkNotifier 初始化失败: {e}")
            return False
    
    async def shutdown(self) -> None:
        """关闭 HTTP 会话"""
        if self._session:
            await self._session.close()
            self._session = None
            logger.debug("DingTalkNotifier 已关闭")
    
    async def notify(self, title: str, message: str, **kwargs) -> bool:
        """发送钉钉通知
        
        Args:
            title: 通知标题
            message: 通知内容
            **kwargs: 额外参数
            
        Returns:
            发送是否成功
        """
        webhook_url = self._config.get("webhook_url")
        if not webhook_url:
            logger.error("钉钉 Webhook URL 未配置")
            return False
        
        if not self._session:
            logger.error("HTTP 会话未初始化")
            return False
        
        # 构建消息内容
        content = f"**{title}**\n\n{message}"
        
        # 构建 @ 信息
        at_mobiles = self._config.get("at_mobiles", [])
        at_all = self._config.get("at_all", False)
        
        # 构建 payload
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            },
            "at": {
                "atMobiles": at_mobiles,
                "isAtAll": at_all
            }
        }
        
        # 计算签名
        url = self._sign_url(webhook_url)
        
        # 发送请求
        try:
            headers = {"Content-Type": "application/json"}
            
            async with self._session.post(
                url=url,
                headers=headers,
                json=payload
            ) as response:
                result = await response.json()
                
                if result.get("errcode") == 0:
                    logger.debug("钉钉通知发送成功")
                    return True
                else:
                    logger.error(f"钉钉通知发送失败: {result.get('errmsg')}")
                    return False
                    
        except aiohttp.ClientError as e:
            logger.error(f"钉钉通知请求失败: {e}")
            return False
        except Exception as e:
            logger.exception(f"钉钉通知发送异常: {e}")
            return False
    
    async def notify_download_complete(
        self, 
        torrent_name: str, 
        category: str,
        save_path: str,
        **kwargs
    ) -> bool:
        """发送下载完成通知（钉钉优化版）
        
        使用 Markdown 格式展示更美观的通知。
        
        Args:
            torrent_name: 种子名称
            category: 分类
            save_path: 保存路径
            **kwargs: 额外参数
            
        Returns:
            发送是否成功
        """
        webhook_url = self._config.get("webhook_url")
        if not webhook_url:
            logger.error("钉钉 Webhook URL 未配置")
            return False
        
        if not self._session:
            logger.error("HTTP 会话未初始化")
            return False
        
        # 构建 Markdown 内容
        title = f"🎉 下载完成: {torrent_name[:50]}"
        
        lines = [
            f"### 📥 {torrent_name}",
            "",
            f"- **分类**: {category}",
            f"- **保存路径**: `{save_path}`",
        ]
        
        # 添加额外信息
        if "size" in kwargs:
            lines.append(f"- **大小**: {kwargs['size']}")
        if "download_time" in kwargs:
            lines.append(f"- **下载用时**: {kwargs['download_time']}")
        if "tracker" in kwargs:
            lines.append(f"- **Tracker**: {kwargs['tracker']}")
            
        lines.append("")
        lines.append(f"> ⏰ {self._format_time()}")
        
        content = "\n".join(lines)
        
        # 构建 payload
        at_mobiles = self._config.get("at_mobiles", [])
        at_all = self._config.get("at_all", False)
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            },
            "at": {
                "atMobiles": at_mobiles,
                "isAtAll": at_all
            }
        }
        
        # 发送请求
        try:
            url = self._sign_url(webhook_url)
            headers = {"Content-Type": "application/json"}
            
            async with self._session.post(
                url=url,
                headers=headers,
                json=payload
            ) as response:
                result = await response.json()
                
                if result.get("errcode") == 0:
                    logger.debug("钉钉通知发送成功")
                    return True
                else:
                    logger.error(f"钉钉通知发送失败: {result.get('errmsg')}")
                    return False
                    
        except Exception as e:
            logger.exception(f"钉钉通知发送异常: {e}")
            return False
    
    def _sign_url(self, webhook_url: str) -> str:
        """为 URL 添加签名
        
        Args:
            webhook_url: 原始 Webhook URL
            
        Returns:
            带签名的 URL
        """
        secret = self._config.get("secret")
        if not secret:
            return webhook_url
        
        timestamp = str(round(time.time() * 1000))
        secret_enc = secret.encode("utf-8")
        string_to_sign = f"{timestamp}\n{secret}"
        string_to_sign_enc = string_to_sign.encode("utf-8")
        hmac_code = hmac.new(
            secret_enc, 
            string_to_sign_enc, 
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        
        separator = "&" if "?" in webhook_url else "?"
        return f"{webhook_url}{separator}timestamp={timestamp}&sign={sign}"
    
    def _format_time(self) -> str:
        """格式化当前时间"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
