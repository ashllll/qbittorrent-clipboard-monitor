"""通知插件包

提供各种通知方式的插件实现。
"""

from .webhook import WebhookNotifier
from .dingtalk import DingTalkNotifier

__all__ = ["WebhookNotifier", "DingTalkNotifier"]
