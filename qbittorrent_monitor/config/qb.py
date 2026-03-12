"""qBittorrent 连接配置模块

提供 QBConfig 数据类和验证逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

import aiohttp

from ..exceptions_unified import ConfigurationError
from ..security import validate_hostname
from .constants import MIN_PORT, MAX_PORT, DEFAULT_QBIT_HOST, DEFAULT_QBIT_PORT, DEFAULT_QBIT_USERNAME


@dataclass
class QBConfig:
    """qBittorrent 连接配置
    
    Attributes:
        host: qBittorrent 服务器地址，可以是主机名或 IP 地址
        port: qBittorrent Web UI 端口，范围 1-65535
        username: qBittorrent 登录用户名
        password: qBittorrent 登录密码
        use_https: 是否使用 HTTPS 连接
    
    Example:
        >>> config = QBConfig(
        ...     host="192.168.1.100",
        ...     port=8080,
        ...     username="admin",
        ...     password="secure_password",
        ...     use_https=False
        ... )
    """
    host: str = DEFAULT_QBIT_HOST
    port: int = DEFAULT_QBIT_PORT
    username: str = DEFAULT_QBIT_USERNAME
    password: str = ""
    use_https: bool = False

    def validate(self) -> None:
        """验证 qBittorrent 配置
        
        Raises:
            ConfigurationError: 当配置项无效时抛出
        """
        # 验证主机名安全性
        validate_hostname(self.host, "QBIT_HOST")
        
        if not isinstance(self.port, int) or not (MIN_PORT <= self.port <= MAX_PORT):
            raise ConfigurationError(
                f"QBIT_PORT 必须是 {MIN_PORT}-{MAX_PORT} 范围内的整数，当前值: {self.port}"
            )
        
        if not self.username or not isinstance(self.username, str):
            raise ConfigurationError(f"QBIT_USERNAME 必须是有效的非空字符串，当前值: {self.username}")
        
        if not self.password or not isinstance(self.password, str):
            raise ConfigurationError("QBIT_PASSWORD 必须设置，不能为空")
        
        # 密码强度基本检查
        if len(self.password) < 1:
            raise ConfigurationError("QBIT_PASSWORD 不能为空字符串")
    
    async def verify_connection(self, timeout: int = 10) -> Dict[str, Any]:
        """验证 qBittorrent 连接配置的有效性
        
        尝试连接到 qBittorrent 服务器进行登录验证。
        
        Args:
            timeout: 连接超时时间（秒）
            
        Returns:
            包含连接信息的字典，包括：
            - success: 是否连接成功
            - version: qBittorrent 版本（如果成功）
            - message: 状态消息
            
        Raises:
            ConfigurationError: 配置验证失败时抛出
        """
        self.validate()
        
        base_url = f"{'https' if self.use_https else 'http'}://{self.host}:{self.port}"
        login_url = f"{base_url}/api/v2/auth/login"
        version_url = f"{base_url}/api/v2/app/version"
        
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                # 尝试登录
                login_data = {
                    "username": self.username,
                    "password": self.password
                }
                async with session.post(login_url, data=login_data) as resp:
                    if resp.status == 200:
                        result = await resp.text()
                        if result == "Ok.":
                            # 获取版本信息
                            async with session.get(version_url) as ver_resp:
                                version = await ver_resp.text() if ver_resp.status == 200 else "unknown"
                            return {
                                "success": True,
                                "version": version,
                                "message": f"成功连接到 qBittorrent {version}"
                            }
                        else:
                            raise ConfigurationError(f"登录失败: {result}")
                    elif resp.status == 403:
                        raise ConfigError("IP 被禁止访问，请在 qBittorrent Web UI 设置中添加信任 IP")
                    else:
                        raise ConfigError(f"登录失败，HTTP 状态码: {resp.status}")
                        
        except aiohttp.ClientConnectorError as e:
            raise ConfigurationError(f"无法连接到 qBittorrent 服务器 ({base_url}): {e}")
        except aiohttp.ServerTimeoutError:
            raise ConfigurationError(f"连接超时，请检查服务器地址和端口是否正确")
        except Exception as e:
            raise ConfigurationError(f"验证连接时发生错误: {e}")
