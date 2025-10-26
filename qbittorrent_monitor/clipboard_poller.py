"""
剪贴板轮询器

负责读取剪贴板、检测变化并根据活动情况自动调整轮询间隔。
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Callable

import pyperclip


@dataclass
class PollerConfig:
    base_interval: float
    min_interval: float = 0.5
    max_interval_multiplier: float = 4.0

    @property
    def max_interval(self) -> float:
        return self.base_interval * self.max_interval_multiplier


class ClipboardPoller:
    """管理剪贴板读取频率和变化检测"""

    def __init__(
        self,
        config: PollerConfig,
        on_change: Callable[[str], None],
    ):
        self.config = config
        self.on_change = on_change
        self.current_interval = max(self.config.min_interval, self.config.base_interval)
        self._last_clip = ""
        self._last_clip_hash = 0
        self._idle_count = 0
        self._running = False
        self._lock = asyncio.Lock()
        self.clipboard_reads = 0

    async def start(self):
        """开始轮询剪贴板"""
        self._running = True
        while self._running:
            text = await self._read_clipboard()
            changed = self._detect_change(text)
            if changed:
                self._idle_count = 0
                self.current_interval = self.config.base_interval
                self.on_change(text)
            else:
                self._idle_count += 1
                self._adjust_interval()

            await asyncio.sleep(self.current_interval)

    def stop(self):
        self._running = False

    async def _read_clipboard(self) -> str:
        """异步读取剪贴板内容"""
        self.clipboard_reads += 1
        async with self._lock:
            return await asyncio.to_thread(pyperclip.paste)

    def _detect_change(self, text: Optional[str]) -> bool:
        current_hash = hash(text) if text else 0
        if current_hash == self._last_clip_hash:
            return False
        self._last_clip = text or ""
        self._last_clip_hash = current_hash
        return True

    def _adjust_interval(self):
        """根据空闲次数调整轮询间隔"""
        if self._idle_count > 5:
            self.current_interval = min(
                self.current_interval * 1.2,
                self.config.max_interval,
            )
        else:
            self.current_interval = max(
                self.config.min_interval,
                self.current_interval * 0.8,
            )
