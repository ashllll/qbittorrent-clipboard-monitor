"""
版本信息管理模块
提供统一的版本信息管理，避免硬编码版本号
"""

__version__ = "2.5.0"
__version_info__ = (2, 5, 0)

# 项目元数据
PROJECT_NAME = "qbittorrent-clipboard-monitor"
PROJECT_DESCRIPTION = "qBittorrent 剪贴板监控与自动分类下载器"
AUTHOR = "qBittorrent Monitor Team"
LICENSE = "MIT"

# 版本常量
VERSION_MAJOR = __version_info__[0]
VERSION_MINOR = __version_info__[1]
VERSION_PATCH = __version_info__[2]

# 版本类型标识
VERSION_TYPE = "stable"  # stable, beta, alpha, rc

def get_version_string():
    """获取版本字符串"""
    version = __version__
    if VERSION_TYPE != "stable":
        version += f"-{VERSION_TYPE}"
    return version

def get_version_info():
    """获取版本信息字典"""
    return {
        "version": __version__,
        "version_info": __version_info__,
        "major": VERSION_MAJOR,
        "minor": VERSION_MINOR,
        "patch": VERSION_PATCH,
        "type": VERSION_TYPE,
        "string": get_version_string(),
        "name": PROJECT_NAME,
        "description": PROJECT_DESCRIPTION
    }

def is_compatible(min_version):
    """检查版本兼容性"""
    import operator

    min_info = tuple(map(int, min_version.split('.')))
    return __version_info__ >= min_info

# 导出版本相关函数
__all__ = [
    "__version__",
    "__version_info__",
    "PROJECT_NAME",
    "PROJECT_DESCRIPTION",
    "VERSION_MAJOR",
    "VERSION_MINOR",
    "VERSION_PATCH",
    "VERSION_TYPE",
    "get_version_string",
    "get_version_info",
    "is_compatible"
]
