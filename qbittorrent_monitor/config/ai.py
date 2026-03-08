"""AI 分类器配置模块

提供 AIConfig 数据类和验证逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..exceptions import ConfigError
from ..security import validate_url
from .constants import (
    MIN_TIMEOUT, MAX_TIMEOUT, MIN_RETRIES, MAX_RETRIES,
    DEFAULT_AI_MODEL, DEFAULT_AI_BASE_URL, DEFAULT_AI_TIMEOUT, DEFAULT_AI_MAX_RETRIES
)
from .validators import validate_api_key


@dataclass
class AIConfig:
    """AI 分类器配置
    
    Attributes:
        enabled: 是否启用 AI 自动分类
        api_key: AI API 密钥（启用 AI 时必需）
        model: AI 模型名称（Minimax: MiniMax-M2.5, MiniMax-M2.5-highspeed 等）
        base_url: API 基础 URL（Minimax: https://api.minimaxi.com/v1）
        timeout: 请求超时时间（秒）
        max_retries: 请求失败时的最大重试次数
    
    Example:
        >>> config = AIConfig(
        ...     enabled=True,
        ...     api_key="sk-xxxxxxxx",
        ...     model="MiniMax-M2.5",
        ...     base_url="https://api.minimaxi.com/v1",
        ...     timeout=30,
        ...     max_retries=3
        ... )
    """
    enabled: bool = True  # 默认启用（向后兼容）
    api_key: str = ""
    model: str = "deepseek-chat"
    base_url: str = DEFAULT_AI_BASE_URL
    timeout: int = DEFAULT_AI_TIMEOUT
    max_retries: int = DEFAULT_AI_MAX_RETRIES

    def validate(self) -> None:
        """验证 AI 配置
        
        Raises:
            ConfigError: 当配置项无效时抛出
        """
        if not isinstance(self.enabled, bool):
            raise ConfigError(f"AI_ENABLED 必须是布尔值 (true/false)，当前值: {self.enabled}")
        
        if self.enabled:
            validate_api_key(self.api_key, "AI_API_KEY")
        
        if not self.model or not isinstance(self.model, str):
            raise ConfigError(f"AI_MODEL 必须是有效的非空字符串，当前值: {self.model}")
        
        # 验证 URL 安全性
        validate_url(self.base_url, "AI_BASE_URL")
        
        if not isinstance(self.timeout, int) or not (MIN_TIMEOUT <= self.timeout <= MAX_TIMEOUT):
            raise ConfigError(
                f"AI_TIMEOUT 必须是 {MIN_TIMEOUT}-{MAX_TIMEOUT} 范围内的整数，当前值: {self.timeout}"
            )
        
        if not isinstance(self.max_retries, int) or not (MIN_RETRIES <= self.max_retries <= MAX_RETRIES):
            raise ConfigError(
                f"AI_MAX_RETRIES 必须是 {MIN_RETRIES}-{MAX_RETRIES} 范围内的整数，当前值: {self.max_retries}"
            )
