"""
增强的通知管理模块

支持多种通知渠道、错误级别过滤、通知队列、模板和速率限制。
"""

import asyncio
import json
import logging
import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import aiohttp
import aiofiles

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False


class NotificationLevel(Enum):
    """通知级别枚举"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    """通知渠道枚举"""
    CONSOLE = "console"
    EMAIL = "email"
    DESKTOP = "desktop"
    WEBHOOK = "webhook"
    FILE = "file"
    SLACK = "slack"
    TELEGRAM = "telegram"
    DISCORD = "discord"


@dataclass
class NotificationConfig:
    """通知配置"""
    # 基本配置
    enabled: bool = True
    global_level: NotificationLevel = NotificationLevel.INFO
    
    # 控制台配置
    console: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "colored": True,
        "show_details": True,
        "truncate_length": 100
    })
    
    # 邮件配置
    email: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "smtp_server": "",
        "smtp_port": 587,
        "username": "",
        "password": "",
        "use_tls": True,
        "from_address": "",
        "to_addresses": [],
        "subject_template": "[{level}] {title}",
        "rate_limit_per_hour": 10
    })
    
    # 桌面通知配置
    desktop: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "timeout": 5000,
        "sound": True
    })
    
    # Webhook配置
    webhook: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "urls": [],
        "headers": {},
        "timeout": 10,
        "rate_limit_per_hour": 30
    })
    
    # 文件配置
    file: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "path": "notifications.log",
        "format": "json",
        "max_size_mb": 100,
        "backup_count": 5
    })
    
    # Slack配置
    slack: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "webhook_url": "",
        "channel": "",
        "username": "Notification Bot",
        "icon_emoji": ":bell:"
    })
    
    # Telegram配置
    telegram: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "bot_token": "",
        "chat_ids": [],
        "parse_mode": "HTML"
    })
    
    # Discord配置
    discord: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "webhook_url": "",
        "username": "Notification Bot"
    })


@dataclass
class NotificationMessage:
    """通知消息"""
    level: NotificationLevel
    title: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


class NotificationQueue:
    """通知队列"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.queue = asyncio.Queue(maxsize=max_size)
        self._processing = False
        self._task = None
    
    async def start(self):
        """启动队列处理"""
        if self._processing:
            return
        
        self._processing = True
        self._task = asyncio.create_task(self._process_queue())
    
    async def stop(self):
        """停止队列处理"""
        if not self._processing:
            return
        
        self._processing = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def put(self, notification: NotificationMessage):
        """添加通知到队列"""
        try:
            self.queue.put_nowait(notification)
        except asyncio.QueueFull:
            # 队列满时丢弃最旧的通知
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(notification)
            except asyncio.QueueEmpty:
                pass
    
    async def _process_queue(self):
        """处理队列中的通知"""
        while self._processing:
            try:
                notification = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                # 这里会由NotificationManager处理具体的发送逻辑
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"处理通知队列时出错: {str(e)}")


class RateLimiter:
    """通知速率限制器"""
    
    def __init__(self, max_notifications: int, time_window: int = 3600):
        self.max_notifications = max_notifications
        self.time_window = time_window
        self.notifications = []
    
    def is_allowed(self) -> bool:
        """检查是否允许发送通知"""
        now = datetime.now()
        
        # 清理过期的通知记录
        self.notifications = [
            timestamp for timestamp in self.notifications
            if (now - timestamp).total_seconds() < self.time_window
        ]
        
        # 检查是否超过限制
        return len(self.notifications) < self.max_notifications
    
    def record(self):
        """记录一次通知发送"""
        self.notifications.append(datetime.now())


class NotificationManager:
    """增强的通知管理器"""
    
    def __init__(self, config: Union[Dict[str, Any], NotificationConfig]):
        self.config = config if isinstance(config, NotificationConfig) else NotificationConfig(**config)
        self.logger = logging.getLogger('NotificationManager')
        self.use_colors = HAS_COLORAMA and self.config.console.get('colored', True)
        
        # 初始化各渠道的速率限制器
        self._rate_limiters = {
            NotificationChannel.EMAIL: RateLimiter(
                self.config.email.get('rate_limit_per_hour', 10), 3600
            ),
            NotificationChannel.WEBHOOK: RateLimiter(
                self.config.webhook.get('rate_limit_per_hour', 30), 3600
            ),
            NotificationChannel.SLACK: RateLimiter(100, 3600),
            NotificationChannel.TELEGRAM: RateLimiter(30, 3600),
            NotificationChannel.DISCORD: RateLimiter(30, 3600)
        }
        
        # 通知队列
        self._queue = NotificationQueue()
        
        # 通知处理器
        self._handlers = {
            NotificationChannel.CONSOLE: self._handle_console,
            NotificationChannel.EMAIL: self._handle_email,
            NotificationChannel.DESKTOP: self._handle_desktop,
            NotificationChannel.WEBHOOK: self._handle_webhook,
            NotificationChannel.FILE: self._handle_file,
            NotificationChannel.SLACK: self._handle_slack,
            NotificationChannel.TELEGRAM: self._handle_telegram,
            NotificationChannel.DISCORD: self._handle_discord
        }
        
        # 通知过滤器
        self._level_filters = {
            NotificationChannel.CONSOLE: NotificationLevel.INFO,
            NotificationChannel.EMAIL: NotificationLevel.WARNING,
            NotificationChannel.DESKTOP: NotificationLevel.ERROR,
            NotificationChannel.WEBHOOK: NotificationLevel.WARNING,
            NotificationChannel.FILE: NotificationLevel.DEBUG,
            NotificationChannel.SLACK: NotificationLevel.INFO,
            NotificationChannel.TELEGRAM: NotificationLevel.WARNING,
            NotificationChannel.DISCORD: NotificationLevel.INFO
        }
        
        # 自定义过滤器
        self._custom_filters: List[Callable[[NotificationMessage], bool]] = []
        
        # 模板
        self._templates = {
            "default": {
                "title": "{title}",
                "message": "{message}",
                "details": "{details}"
            },
            "error": {
                "title": "❌ {title}",
                "message": "错误信息: {message}",
                "details": "详细信息: {details}"
            },
            "warning": {
                "title": "⚠️ {title}",
                "message": "警告信息: {message}",
                "details": "详细信息: {details}"
            },
            "success": {
                "title": "✅ {title}",
                "message": "成功信息: {message}",
                "details": "详细信息: {details}"
            }
        }
        
        # 统计信息
        self._stats = {
            "total_sent": 0,
            "sent_by_channel": {channel.value: 0 for channel in NotificationChannel},
            "failed_by_channel": {channel.value: 0 for channel in NotificationChannel},
            "filtered_out": 0,
            "rate_limited": 0,
            "last_sent": {}
        }
    
    async def start(self):
        """启动通知管理器"""
        await self._queue.start()
        self.logger.info("通知管理器已启动")
    
    async def stop(self):
        """停止通知管理器"""
        await self._queue.stop()
        self.logger.info("通知管理器已停止")
    
    def add_filter(self, filter_func: Callable[[NotificationMessage], bool]):
        """添加自定义过滤器"""
        self._custom_filters.append(filter_func)
    
    def add_template(self, name: str, template: Dict[str, str]):
        """添加通知模板"""
        self._templates[name] = template
    
    async def send_notification(
        self,
        level: NotificationLevel,
        title: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        channels: Optional[List[NotificationChannel]] = None
    ):
        """发送通知"""
        # 创建通知消息
        notification = NotificationMessage(
            level=level,
            title=title,
            message=message,
            details=details,
            source=source,
            tags=tags or [],
            context=context or {}
        )
        
        # 检查是否应该发送
        if not await self._should_send(notification):
            self._stats["filtered_out"] += 1
            return
        
        # 默认使用所有启用的渠道
        if channels is None:
            channels = self._get_enabled_channels()
        
        # 发送通知到各渠道
        tasks = []
        for channel in channels:
            if self._should_send_to_channel(notification, channel):
                tasks.append(self._send_to_channel(channel, notification))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_error_notification(
        self,
        title: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None
    ):
        """发送错误通知"""
        await self.send_notification(
            level=NotificationLevel.ERROR,
            title=title,
            message=str(error),
            details={
                "error_type": type(error).__name__,
                "traceback": getattr(error, '__traceback__', None)
            },
            source=source,
            context=context
        )
    
    async def send_fallback_notification(
        self,
        title: str,
        original_error: Exception,
        fallback_method: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """发送降级通知"""
        await self.send_notification(
            level=NotificationLevel.WARNING,
            title=title,
            message=f"AI服务降级到{fallback_method}模式",
            details={
                "original_error": str(original_error),
                "fallback_method": fallback_method,
                "error_type": type(original_error).__name__
            },
            source="fallback_system",
            context=context
        )
    
    def _get_enabled_channels(self) -> List[NotificationChannel]:
        """获取启用的通知渠道"""
        channels = []
        
        if self.config.console.get('enabled', True):
            channels.append(NotificationChannel.CONSOLE)
        
        if self.config.email.get('enabled', False):
            channels.append(NotificationChannel.EMAIL)
        
        if self.config.desktop.get('enabled', False):
            channels.append(NotificationChannel.DESKTOP)
        
        if self.config.webhook.get('enabled', False) and self.config.webhook.get('urls'):
            channels.append(NotificationChannel.WEBHOOK)
        
        if self.config.file.get('enabled', False):
            channels.append(NotificationChannel.FILE)
        
        if self.config.slack.get('enabled', False) and self.config.slack.get('webhook_url'):
            channels.append(NotificationChannel.SLACK)
        
        if self.config.telegram.get('enabled', False) and self.config.telegram.get('bot_token'):
            channels.append(NotificationChannel.TELEGRAM)
        
        if self.config.discord.get('enabled', False) and self.config.discord.get('webhook_url'):
            channels.append(NotificationChannel.DISCORD)
        
        return channels
    
    async def _should_send(self, notification: NotificationMessage) -> bool:
        """检查是否应该发送通知"""
        # 检查全局级别
        if notification.level.value < self.config.global_level.value:
            return False
        
        # 检查自定义过滤器
        for filter_func in self._custom_filters:
            if not filter_func(notification):
                return False
        
        return True
    
    def _should_send_to_channel(self, notification: NotificationMessage, channel: NotificationChannel) -> bool:
        """检查是否应该发送到特定渠道"""
        # 检查渠道级别过滤
        channel_level = self._level_filters.get(channel, NotificationLevel.INFO)
        if notification.level.value < channel_level.value:
            return False
        
        # 检查速率限制
        rate_limiter = self._rate_limiters.get(channel)
        if rate_limiter and not rate_limiter.is_allowed():
            self._stats["rate_limited"] += 1
            return False
        
        return True
    
    async def _send_to_channel(self, channel: NotificationChannel, notification: NotificationMessage):
        """发送通知到特定渠道"""
        try:
            handler = self._handlers[channel]
            await handler(notification)
            
            # 记录成功
            self._stats["total_sent"] += 1
            self._stats["sent_by_channel"][channel.value] += 1
            self._stats["last_sent"][channel.value] = datetime.now().isoformat()
            
            # 记录速率限制
            rate_limiter = self._rate_limiters.get(channel)
            if rate_limiter:
                rate_limiter.record()
        
        except Exception as e:
            # 记录失败
            self._stats["failed_by_channel"][channel.value] += 1
            self.logger.error(f"发送{channel.value}通知失败: {str(e)}")
    
    async def _handle_console(self, notification: NotificationMessage):
        """处理控制台通知"""
        if not self.config.console.get('enabled', True):
            return
        
        level_colors = {
            NotificationLevel.DEBUG: Fore.CYAN,
            NotificationLevel.INFO: Fore.BLUE,
            NotificationLevel.WARNING: Fore.YELLOW,
            NotificationLevel.ERROR: Fore.RED,
            NotificationLevel.CRITICAL: Fore.MAGENTA
        }
        
        level_symbols = {
            NotificationLevel.DEBUG: "🔍",
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.ERROR: "❌",
            NotificationLevel.CRITICAL: "🚨"
        }
        
        color = level_colors.get(notification.level, Fore.WHITE)
        symbol = level_symbols.get(notification.level, "📢")
        
        # 格式化消息
        timestamp = notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        truncate_length = self.config.console.get('truncate_length', 100)
        
        # 截断长消息
        title = notification.title if len(notification.title) <= truncate_length else notification.title[:truncate_length-3] + "..."
        message = notification.message if len(notification.message) <= truncate_length else notification.message[:truncate_length-3] + "..."
        
        if self.use_colors:
            print(f"\n{color}{symbol} [{notification.level.value.upper()}] {title}")
            print(f"{Fore.CYAN}📝 {message}")
            
            if self.config.console.get('show_details', True) and notification.details:
                print(f"{Fore.CYAN}📊 详细信息:")
                for key, value in notification.details.items():
                    if key != 'traceback':  # 不显示完整的traceback
                        print(f"   {key}: {value}")
            
            print(f"{Fore.CYAN}⏰ {timestamp}")
            if notification.source:
                print(f"{Fore.CYAN}📍 来源: {notification.source}")
            
            print(f"{color}{'─' * 60}{Style.RESET_ALL}")
        else:
            print(f"\n{symbol} [{notification.level.value.upper()}] {title}")
            print(f"📝 {message}")
            
            if self.config.console.get('show_details', True) and notification.details:
                print(f"📊 详细信息:")
                for key, value in notification.details.items():
                    if key != 'traceback':
                        print(f"   {key}: {value}")
            
            print(f"⏰ {timestamp}")
            if notification.source:
                print(f"📍 来源: {notification.source}")
            
            print(f"{'─' * 60}")
    
    async def _handle_email(self, notification: NotificationMessage):
        """处理邮件通知"""
        email_config = self.config.email
        if not email_config.get('enabled', False):
            return
        
        try:
            # 创建邮件内容
            subject = email_config.get('subject_template', '[{level}] {title}').format(
                level=notification.level.value.upper(),
                title=notification.title
            )
            
            # 格式化邮件正文
            body = self._format_email_body(notification)
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = email_config.get('from_address')
            msg['To'] = ', '.join(email_config.get('to_addresses', []))
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            # 发送邮件
            server = smtplib.SMTP(email_config.get('smtp_server'), email_config.get('smtp_port'))
            if email_config.get('use_tls', True):
                server.starttls()
            
            server.login(email_config.get('username'), email_config.get('password'))
            text = msg.as_string()
            server.sendmail(email_config.get('from_address'), email_config.get('to_addresses'), text)
            server.quit()
            
            self.logger.debug(f"邮件通知已发送: {subject}")
        
        except Exception as e:
            self.logger.error(f"发送邮件通知失败: {str(e)}")
            raise
    
    def _format_email_body(self, notification: NotificationMessage) -> str:
        """格式化邮件正文"""
        level_colors = {
            NotificationLevel.DEBUG: "#6c757d",
            NotificationLevel.INFO: "#17a2b8",
            NotificationLevel.WARNING: "#ffc107",
            NotificationLevel.ERROR: "#dc3545",
            NotificationLevel.CRITICAL: "#6f42c1"
        }
        
        color = level_colors.get(notification.level, "#000000")
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: {color}; color: white; padding: 10px; border-radius: 5px; }}
                .content {{ margin: 20px 0; }}
                .details {{ background-color: #f8f9fa; padding: 10px; border-radius: 5px; }}
                .footer {{ font-size: 12px; color: #6c757d; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>{notification.title}</h2>
                <p>级别: {notification.level.value.upper()}</p>
            </div>
            <div class="content">
                <p><strong>消息:</strong> {notification.message}</p>
            </div>
        """
        
        if notification.details:
            html += '<div class="details"><h3>详细信息:</h3><ul>'
            for key, value in notification.details.items():
                if key != 'traceback':
                    html += f'<li><strong>{key}:</strong> {value}</li>'
            html += '</ul></div>'
        
        html += f"""
            <div class="footer">
                <p>发送时间: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                {"<p>来源: " + notification.source + "</p>" if notification.source else ""}
            </div>
        </body>
        </html>
        """
        
        return html
    
    async def _handle_desktop(self, notification: NotificationMessage):
        """处理桌面通知"""
        desktop_config = self.config.desktop
        if not desktop_config.get('enabled', False):
            return
        
        try:
            # 使用plyer库发送桌面通知
            try:
                from plyer import notification
                
                timeout = desktop_config.get('timeout', 5000)
                notification.notify(
                    title=notification.title,
                    message=notification.message,
                    timeout=timeout
                )
            except ImportError:
                self.logger.warning("plyer库未安装，无法发送桌面通知")
        
        except Exception as e:
            self.logger.error(f"发送桌面通知失败: {str(e)}")
    
    async def _handle_webhook(self, notification: NotificationMessage):
        """处理Webhook通知"""
        webhook_config = self.config.webhook
        if not webhook_config.get('enabled', False):
            return
        
        urls = webhook_config.get('urls', [])
        if not urls:
            return
        
        timeout = webhook_config.get('timeout', 10)
        headers = webhook_config.get('headers', {})
        
        # 准备Webhook数据
        webhook_data = {
            "level": notification.level.value,
            "title": notification.title,
            "message": notification.message,
            "details": notification.details,
            "timestamp": notification.timestamp.isoformat(),
            "source": notification.source,
            "tags": notification.tags
        }
        
        # 发送到所有URL
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            for url in urls:
                try:
                    async with session.post(url, json=webhook_data, headers=headers) as response:
                        if response.status == 200:
                            self.logger.debug(f"Webhook通知已发送到: {url}")
                        else:
                            self.logger.warning(f"Webhook通知发送失败，状态码: {response.status}")
                except Exception as e:
                    self.logger.error(f"Webhook通知发送到{url}失败: {str(e)}")
    
    async def _handle_file(self, notification: NotificationMessage):
        """处理文件通知"""
        file_config = self.config.file
        if not file_config.get('enabled', False):
            return
        
        try:
            file_path = Path(file_config.get('path', 'notifications.log'))
            format_type = file_config.get('format', 'json')
            
            # 准备日志内容
            if format_type == 'json':
                content = json.dumps({
                    "timestamp": notification.timestamp.isoformat(),
                    "level": notification.level.value,
                    "title": notification.title,
                    "message": notification.message,
                    "details": notification.details,
                    "source": notification.source,
                    "tags": notification.tags
                }, ensure_ascii=False, indent=2)
            else:
                # 简单的文本格式
                content = f"[{notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] " \
                         f"[{notification.level.value.upper()}] " \
                         f"{notification.title}: {notification.message}"
                
                if notification.details:
                    content += f"\nDetails: {notification.details}"
                
                if notification.source:
                    content += f"\nSource: {notification.source}"
            
            # 写入文件
            async with aiofiles.open(file_path, 'a', encoding='utf-8') as f:
                await f.write(content + '\n')
            
            self.logger.debug(f"文件通知已写入: {file_path}")
        
        except Exception as e:
            self.logger.error(f"写入文件通知失败: {str(e)}")
    
    async def _handle_slack(self, notification: NotificationMessage):
        """处理Slack通知"""
        slack_config = self.config.slack
        if not slack_config.get('enabled', False):
            return
        
        webhook_url = slack_config.get('webhook_url')
        if not webhook_url:
            return
        
        try:
            # 准备Slack消息
            level_colors = {
                NotificationLevel.DEBUG: "#6c757d",
                NotificationLevel.INFO: "#17a2b8",
                NotificationLevel.WARNING: "#ffc107",
                NotificationLevel.ERROR: "#dc3545",
                NotificationLevel.CRITICAL: "#6f42c1"
            }
            
            color = level_colors.get(notification.level, "#000000")
            
            slack_data = {
                "username": slack_config.get('username', 'Notification Bot'),
                "icon_emoji": slack_config.get('icon_emoji', ':bell:'),
                "attachments": [{
                    "color": color,
                    "title": notification.title,
                    "text": notification.message,
                    "fields": [
                        {"title": "级别", "value": notification.level.value.upper(), "short": True},
                        {"title": "时间", "value": notification.timestamp.strftime('%Y-%m-%d %H:%M:%S'), "short": True}
                    ],
                    "footer": "qBittorrent Monitor",
                    "ts": int(notification.timestamp.timestamp())
                }]
            }
            
            if notification.details:
                fields = []
                for key, value in notification.details.items():
                    if key != 'traceback':
                        fields.append({
                            "title": key,
                            "value": str(value),
                            "short": True
                        })
                
                if fields:
                    slack_data["attachments"][0]["fields"] = fields
            
            # 发送Slack消息
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=slack_data) as response:
                    if response.status == 200:
                        self.logger.debug("Slack通知已发送")
                    else:
                        self.logger.warning(f"Slack通知发送失败，状态码: {response.status}")
        
        except Exception as e:
            self.logger.error(f"发送Slack通知失败: {str(e)}")
    
    async def _handle_telegram(self, notification: NotificationMessage):
        """处理Telegram通知"""
        telegram_config = self.config.telegram
        if not telegram_config.get('enabled', False):
            return
        
        bot_token = telegram_config.get('bot_token')
        chat_ids = telegram_config.get('chat_ids', [])
        if not bot_token or not chat_ids:
            return
        
        try:
            # 准备Telegram消息
            message = f"*{notification.title}*\n\n"
            message += f"级别: {notification.level.value.upper()}\n"
            message += f"消息: {notification.message}\n"
            
            if notification.details:
                message += "\n详细信息:\n"
                for key, value in notification.details.items():
                    if key != 'traceback':
                        message += f"• {key}: {value}\n"
            
            message += f"\n时间: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            if notification.source:
                message += f"\n来源: {notification.source}"
            
            # 发送Telegram消息
            base_url = f"https://api.telegram.org/bot{bot_token}"
            async with aiohttp.ClientSession() as session:
                for chat_id in chat_ids:
                    data = {
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": telegram_config.get('parse_mode', 'HTML')
                    }
                    
                    async with session.post(f"{base_url}/sendMessage", data=data) as response:
                        if response.status == 200:
                            self.logger.debug(f"Telegram通知已发送到chat_id: {chat_id}")
                        else:
                            self.logger.warning(f"Telegram通知发送失败，状态码: {response.status}")
        
        except Exception as e:
            self.logger.error(f"发送Telegram通知失败: {str(e)}")
    
    async def _handle_discord(self, notification: NotificationMessage):
        """处理Discord通知"""
        discord_config = self.config.discord
        if not discord_config.get('enabled', False):
            return
        
        webhook_url = discord_config.get('webhook_url')
        if not webhook_url:
            return
        
        try:
            # 准备Discord消息
            level_colors = {
                NotificationLevel.DEBUG: 0x6c757d,
                NotificationLevel.INFO: 0x17a2b8,
                NotificationLevel.WARNING: 0xffc107,
                NotificationLevel.ERROR: 0xdc3545,
                NotificationLevel.CRITICAL: 0x6f42c1
            }
            
            color = level_colors.get(notification.level, 0x000000)
            
            discord_data = {
                "username": discord_config.get('username', 'Notification Bot'),
                "embeds": [{
                    "title": notification.title,
                    "description": notification.message,
                    "color": color,
                    "timestamp": notification.timestamp.isoformat(),
                    "footer": {
                        "text": "qBittorrent Monitor"
                    }
                }]
            }
            
            if notification.details:
                fields = []
                for key, value in notification.details.items():
                    if key != 'traceback':
                        fields.append({
                            "name": key,
                            "value": str(value),
                            "inline": True
                        })
                
                if fields:
                    discord_data["embeds"][0]["fields"] = fields
            
            # 发送Discord消息
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=discord_data) as response:
                    if response.status == 204:
                        self.logger.debug("Discord通知已发送")
                    else:
                        self.logger.warning(f"Discord通知发送失败，状态码: {response.status}")
        
        except Exception as e:
            self.logger.error(f"发送Discord通知失败: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        
        # 添加速率限制状态
        rate_limit_status = {}
        for channel, limiter in self._rate_limiters.items():
            rate_limit_status[channel.value] = {
                "current_count": len(limiter.notifications),
                "max_count": limiter.max_notifications,
                "window_seconds": limiter.time_window,
                "is_allowed": limiter.is_allowed()
            }
        
        stats["rate_limit_status"] = rate_limit_status
        
        return stats
    
    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "total_sent": 0,
            "sent_by_channel": {channel.value: 0 for channel in NotificationChannel},
            "failed_by_channel": {channel.value: 0 for channel in NotificationChannel},
            "filtered_out": 0,
            "rate_limited": 0,
            "last_sent": {}
        }
        
        # 重置速率限制器
        for limiter in self._rate_limiters.values():
            limiter.notifications.clear()
        
        self.logger.info("通知管理器统计已重置")


# 便利函数
def create_notification_manager(config: Dict[str, Any]) -> NotificationManager:
    """创建通知管理器"""
    return NotificationManager(NotificationConfig(**config))


# 导出
__all__ = [
    "NotificationManager",
    "NotificationConfig", 
    "NotificationMessage",
    "NotificationLevel",
    "NotificationChannel",
    "create_notification_manager"
]

