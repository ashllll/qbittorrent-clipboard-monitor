"""环境变量加载模块

从环境变量加载配置并覆盖现有配置。
"""

from __future__ import annotations

import os
import logging
from typing import Optional

from ..exceptions import ConfigError
from ..security import validate_hostname, validate_url
from .constants import (
    MIN_PORT, MAX_PORT, MIN_TIMEOUT, MAX_TIMEOUT,
    MIN_RETRIES, MAX_RETRIES, MIN_CHECK_INTERVAL, MAX_CHECK_INTERVAL,
    VALID_LOG_LEVELS
)
from .validators import parse_bool, parse_int, parse_float, validate_non_empty_string, validate_api_key

logger = logging.getLogger(__name__)


def load_from_env(config) -> None:
    """从环境变量加载配置，覆盖现有配置
    
    支持的环境变量及其说明：
    
    qBittorrent 配置：
        QBIT_HOST: 服务器地址
        QBIT_PORT: 服务器端口 (1-65535)
        QBIT_USERNAME: 用户名
        QBIT_PASSWORD: 密码（必需）
        QBIT_USE_HTTPS: 是否使用 HTTPS (true/false)

    AI 配置：
        AI_ENABLED: 是否启用 AI (true/false)
        AI_API_KEY: API 密钥
        AI_MODEL: 模型名称
        AI_BASE_URL: API 基础 URL
        AI_TIMEOUT: 请求超时 (1-300)
        AI_MAX_RETRIES: 最大重试次数 (0-10)

    应用配置：
        CHECK_INTERVAL: 检查间隔秒数 (0.1-60.0)
        LOG_LEVEL: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    
    数据库配置：
        DATABASE_ENABLED: 是否启用数据持久化 (true/false)
        DATABASE_PATH: 数据库文件路径
        DATABASE_AUTO_CLEANUP_DAYS: 自动清理旧数据的天数 (0-365, 0表示不清理)
    
    指标配置：
        METRICS_ENABLED: 是否启用指标导出 (true/false)
        METRICS_HOST: 指标服务器监听地址
        METRICS_PORT: 指标服务器端口
    
    插件配置：
        PLUGINS_ENABLED: 是否启用插件系统 (true/false)
        PLUGINS_DIR: 外部插件目录路径
        PLUGINS_AUTO_ENABLE: 是否自动启用所有插件 (true/false)

    Args:
        config: 要修改的配置对象
        
    Raises:
        ConfigError: 当环境变量值无效时抛出
    """
    # qBittorrent 配置
    if host := os.getenv("QBIT_HOST"):
        validated_host = validate_non_empty_string(host, "QBIT_HOST")
        validate_hostname(validated_host, "QBIT_HOST")
        config.qbittorrent.host = validated_host

    if port := os.getenv("QBIT_PORT"):
        config.qbittorrent.port = parse_int(port, "QBIT_PORT", MIN_PORT, MAX_PORT)

    if username := os.getenv("QBIT_USERNAME"):
        config.qbittorrent.username = validate_non_empty_string(username, "QBIT_USERNAME")

    if password := os.getenv("QBIT_PASSWORD"):
        config.qbittorrent.password = password
    # 注意：环境变量中的空字符串表示显式清除密码
    elif os.getenv("QBIT_PASSWORD") == "":
        raise ConfigError("QBIT_PASSWORD 环境变量已设置但为空，请提供密码或删除该环境变量")

    if use_https := os.getenv("QBIT_USE_HTTPS"):
        config.qbittorrent.use_https = parse_bool(use_https)

    # AI 配置
    if ai_enabled := os.getenv("AI_ENABLED"):
        config.ai.enabled = parse_bool(ai_enabled)

    if api_key := os.getenv("AI_API_KEY"):
        validate_api_key(api_key, "AI_API_KEY")
        config.ai.api_key = api_key

    if model := os.getenv("AI_MODEL"):
        config.ai.model = validate_non_empty_string(model, "AI_MODEL")

    if base_url := os.getenv("AI_BASE_URL"):
        validated_url = validate_non_empty_string(base_url, "AI_BASE_URL")
        validate_url(validated_url, "AI_BASE_URL")
        config.ai.base_url = validated_url

    if timeout := os.getenv("AI_TIMEOUT"):
        config.ai.timeout = parse_int(timeout, "AI_TIMEOUT", MIN_TIMEOUT, MAX_TIMEOUT)

    if max_retries := os.getenv("AI_MAX_RETRIES"):
        config.ai.max_retries = parse_int(max_retries, "AI_MAX_RETRIES", MIN_RETRIES, MAX_RETRIES)

    # 应用配置
    if interval := os.getenv("CHECK_INTERVAL"):
        config.check_interval = parse_float(interval, "CHECK_INTERVAL", MIN_CHECK_INTERVAL, MAX_CHECK_INTERVAL)
    
    if log_level := os.getenv("LOG_LEVEL"):
        log_level_upper = log_level.upper()
        if log_level_upper not in VALID_LOG_LEVELS:
            raise ConfigError(
                f"LOG_LEVEL 必须是以下值之一: {', '.join(VALID_LOG_LEVELS)}，当前值: {log_level}"
            )
        config.log_level = log_level_upper

    # 数据库配置
    if db_enabled := os.getenv("DATABASE_ENABLED"):
        config.database.enabled = parse_bool(db_enabled)

    if db_path := os.getenv("DATABASE_PATH"):
        config.database.db_path = validate_non_empty_string(db_path, "DATABASE_PATH")

    if db_cleanup := os.getenv("DATABASE_AUTO_CLEANUP_DAYS"):
        config.database.auto_cleanup_days = parse_int(
            db_cleanup, "DATABASE_AUTO_CLEANUP_DAYS", 0, 365
        )
    
    # 指标配置
    if metrics_enabled := os.getenv("METRICS_ENABLED"):
        config.metrics.enabled = parse_bool(metrics_enabled)
    
    if metrics_host := os.getenv("METRICS_HOST"):
        config.metrics.host = validate_non_empty_string(metrics_host, "METRICS_HOST")
    
    if metrics_port := os.getenv("METRICS_PORT"):
        config.metrics.port = parse_int(metrics_port, "METRICS_PORT", MIN_PORT, MAX_PORT)
    
    # 插件配置
    if plugins_enabled := os.getenv("PLUGINS_ENABLED"):
        config.plugins.enabled = parse_bool(plugins_enabled)

    if plugins_dir := os.getenv("PLUGINS_DIR"):
        config.plugins.plugins_dir = validate_non_empty_string(plugins_dir, "PLUGINS_DIR")

    if auto_enable := os.getenv("PLUGINS_AUTO_ENABLE"):
        config.plugins.auto_enable = parse_bool(auto_enable)


def load_config(path: Optional[Path] = None, strict: bool = True):
    """加载配置的便捷函数
    
    加载顺序：
    1. 从配置文件加载（如果不存在则创建默认配置）
    2. 从环境变量加载并覆盖
    3. 验证配置有效性
    
    Args:
        path: 配置文件路径，默认使用 ~/.config/qb-monitor/config.json
        strict: 如果为 True，配置验证失败时抛出异常
        
    Returns:
        配置对象
        
    Raises:
        ConfigError: 当 strict=True 且配置无效时抛出
    """
    from pathlib import Path
    from .base import Config
    
    # 从配置文件加载
    config = Config.load(path)

    # 从环境变量加载并覆盖
    load_from_env(config)

    # 验证配置
    warnings = config.validate(strict=strict)
    if warnings and not strict:
        for warning in warnings:
            logger.warning(warning)

    return config
