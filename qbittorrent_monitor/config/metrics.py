"""Prometheus 指标配置模块

提供 MetricsConfig 数据类。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MetricsConfig:
    """Prometheus 指标导出配置
    
    Attributes:
        enabled: 是否启用指标导出
        host: 指标服务器监听地址
        port: 指标服务器监听端口
        path: 指标端点路径
    """
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 9090
    path: str = "/metrics"
    
    def validate(self) -> None:
        """验证指标配置
        
        Raises:
            ConfigurationError: 当配置无效时抛出
        """
        from .constants import MIN_PORT, MAX_PORT
        from ..exceptions_unified import ConfigurationError
        
        if not isinstance(self.enabled, bool):
            raise ConfigurationError(f"METRICS_ENABLED 必须是布尔值，当前值: {self.enabled}")
        
        if not isinstance(self.port, int) or not (MIN_PORT <= self.port <= MAX_PORT):
            raise ConfigurationError(
                f"METRICS_PORT 必须是 {MIN_PORT}-{MAX_PORT} 范围内的整数，当前值: {self.port}"
            )
        
        if not self.host or not isinstance(self.host, str):
            raise ConfigurationError(f"METRICS_HOST 必须是有效的非空字符串")
        
        if not self.path or not self.path.startswith("/"):
            raise ConfigurationError(f"METRICS_PATH 必须以 '/' 开头")
