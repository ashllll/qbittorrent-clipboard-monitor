"""
剪贴板内容分析器

负责解析剪贴板文本并判定应触发的处理动作。
"""

import re
from typing import Optional

from .clipboard_models import ProcessingTask


class ClipboardContentProcessor:
    """根据内容类型生成处理任务"""

    def __init__(self):
        self.magnet_pattern = re.compile(
            r"^magnet:\?xt=urn:btih:[0-9a-fA-F]{40,}.*",
            re.IGNORECASE
        )
        self.xxxclub_pattern = re.compile(
            r"https?://(?:www\.)?xxxclub\.to/torrents/search/.*",
            re.IGNORECASE
        )
        self.url_pattern = re.compile(
            r"https?://[^\s]+",
            re.IGNORECASE
        )

    def process(self, raw_text: Optional[str]) -> ProcessingTask:
        if not raw_text:
            return ProcessingTask(kind="ignore", content="")

        content = raw_text.strip()
        if not content:
            return ProcessingTask(kind="ignore", content="")

        if self.magnet_pattern.match(content):
            return ProcessingTask(kind="magnet", content=content)

        if self.xxxclub_pattern.match(content) or self.url_pattern.match(content):
            return ProcessingTask(kind="url", content=content)

        return ProcessingTask(kind="ignore", content=content)
