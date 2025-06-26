"""
通用工具函数模块

包含：
- 磁力链接解析
- 日志配置
- 控制台通知显示
- 文件处理等工具函数
"""

import asyncio
import logging
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from colorama import Back, Fore, Style, init

    init(autoreset=True)  # 自动重置颜色
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False


def setup_logging(
    level: str = "INFO", log_file: Optional[str] = None
) -> logging.Logger:
    """配置日志系统"""
    logger = logging.getLogger("QBittorrentMonitor")

    # 避免重复配置
    if logger.handlers:
        return logger

    # 设置日志级别
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # 创建格式器
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        try:
            # 确保日志目录存在
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"无法创建日志文件 {log_file}: {str(e)}")

    return logger


def parse_magnet(magnet_link: str) -> Tuple[Optional[str], Optional[str]]:
    """
    增强版磁力链接解析器，支持：
    - 标准URL解析
    - 多tracker参数
    - 更健壮的文件名处理
    - 详细的错误日志

    Args:
        magnet_link: 磁力链接字符串

    Returns:
        (哈希值, 名称) 元组
    """
    logger = logging.getLogger("MagnetParser")

    if not magnet_link or not magnet_link.startswith("magnet:"):
        logger.debug("无效的磁力链接格式")
        return None, None

    try:
        # 解析URL组件
        parsed = urllib.parse.urlparse(magnet_link)
        query = urllib.parse.parse_qs(parsed.query)

        # 提取哈希值
        xt = query.get("xt", [])
        torrent_hash = None

        for xt_val in xt:
            if xt_val.startswith("urn:btih:"):
                hash_val = xt_val[9:]  # 去掉urn:btih:前缀
                # 支持Base32和Base16格式
                if len(hash_val) == 32:
                    torrent_hash = hash_val.lower()  # Base32
                elif len(hash_val) == 40:
                    torrent_hash = hash_val.lower()  # Base16
                break

        # 提取文件名(支持多个dn参数)
        torrent_name = None
        dn_values = query.get("dn", [])
        if dn_values:
            try:
                torrent_name = urllib.parse.unquote_plus(dn_values[0])
                # 清理文件名
                torrent_name = sanitize_filename(torrent_name)
            except Exception as e:
                logger.warning(f"文件名解码失败: {str(e)}")
                torrent_name = dn_values[0]

        # 提取tracker列表(调试用)
        trackers = []
        for key in query:
            if key.startswith("tr.") or key == "tr":
                trackers.extend(query[key])

        logger.debug(
            f"解析结果 - 哈希: {torrent_hash}, 名称: {torrent_name}, "
            f"trackers: {len(trackers)}个"
        )

        return torrent_hash, torrent_name

    except Exception as e:
        logger.error(f"磁力链接解析失败: {str(e)}")
        return None, None


def validate_magnet_link(magnet_link: str) -> bool:
    """验证磁力链接格式是否正确"""
    if not magnet_link or not isinstance(magnet_link, str):
        return False

    # 基本格式检查
    if not magnet_link.startswith("magnet:"):
        return False

    # 检查是否包含必要的参数
    hash_pattern = r"xt=urn:btih:[0-9a-fA-F]{40}|[0-9a-zA-Z]{32}"
    return bool(re.search(hash_pattern, magnet_link, re.IGNORECASE))


def extract_file_extensions(file_list: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    从文件列表中提取文件扩展名统计

    Args:
        file_list: qBittorrent API返回的文件列表

    Returns:
        扩展名统计字典
    """
    extensions = {}

    for file_info in file_list:
        filename = file_info.get("name", "")
        if filename:
            # 提取扩展名
            ext = Path(filename).suffix.lower()
            if ext:
                extensions[ext] = extensions.get(ext, 0) + 1

    return extensions


def analyze_torrent_content(file_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分析种子内容特征

    Args:
        file_list: qBittorrent API返回的文件列表

    Returns:
        内容分析结果
    """
    if not file_list:
        return {}

    # 统计文件扩展名
    extensions = extract_file_extensions(file_list)

    # 计算总大小
    total_size = sum(file_info.get("size", 0) for file_info in file_list)

    # 文件数量
    file_count = len(file_list)

    # 分析内容类型
    content_type = "unknown"
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}
    audio_exts = {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma"}
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
    archive_exts = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"}
    executable_exts = {".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm"}

    # 判断主要内容类型
    if any(ext in video_exts for ext in extensions):
        content_type = "video"
    elif any(ext in audio_exts for ext in extensions):
        content_type = "audio"
    elif any(ext in image_exts for ext in extensions):
        content_type = "image"
    elif any(ext in archive_exts for ext in extensions):
        content_type = "archive"
    elif any(ext in executable_exts for ext in extensions):
        content_type = "software"

    return {
        "content_type": content_type,
        "file_count": file_count,
        "total_size": total_size,
        "extensions": extensions,
        "main_files": [
            f for f in file_list if f.get("size", 0) > total_size * 0.1
        ],  # 大于总大小10%的文件
    }


def format_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f} {size_names[i]}"


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除不安全字符"""
    # 移除或替换不安全字符
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, "_")

    # 移除前后空格和点
    filename = filename.strip(" .")

    # 限制长度
    if len(filename) > 255:
        filename = filename[:255]

    return filename


def is_episode_content(filename: str) -> bool:
    """判断是否为剧集内容"""
    patterns = [
        r"S\d+E\d+",  # S01E01 格式
        r"Season\s+\d+",  # Season 1 格式
        r"Episode\s+\d+",  # Episode 1 格式
        r"\d+x\d+",  # 1x01 格式
        r"EP\d+",  # EP01 格式
        r"第\d+季",  # 第1季
        r"第\d+集",  # 第1集
    ]

    for pattern in patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            return True

    return False


def is_movie_content(filename: str) -> bool:
    """判断是否为电影内容"""
    patterns = [
        r"\b(19|20)\d{2}\b",  # 年份
        r"\b(1080p|720p|4K|2160p)\b",  # 分辨率
        r"\b(BluRay|BDRip|WEB-DL|HDRip|DVDRip)\b",  # 来源
        r"\b(x264|x265|H\.264|H\.265|HEVC)\b",  # 编码
    ]

    movie_score = 0
    for pattern in patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            movie_score += 1

    # 如果匹配多个电影特征，认为是电影
    return movie_score >= 2


class SimpleNotificationManager:
    """简化的控制台通知管理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("NotificationManager")

        # 检查颜色支持
        self.use_colors = HAS_COLORAMA and config.get("console", {}).get(
            "colored", True
        )

    async def send_torrent_success(
        self,
        torrent_name: str,
        category: str,
        save_path: str,
        torrent_hash: str,
        classification_method: str = "AI",
    ):
        """发送种子添加成功通知"""
        timestamp = self._get_timestamp()

        # 构建消息内容
        short_name = self._truncate_name(torrent_name, 80)

        if self.config.get("console", {}).get("enabled", True):
            if self.use_colors:
                print(f"\n{Fore.GREEN}✅ 种子添加成功!")
                print(f"{Fore.CYAN}📁 名称: {Fore.WHITE}{short_name}")
                print(f"{Fore.CYAN}📂 分类: {Fore.YELLOW}{category}")
                print(f"{Fore.CYAN}💾 路径: {Fore.WHITE}{save_path}")
                print(f"{Fore.CYAN}🧠 分类方式: {Fore.GREEN}{classification_method}")
                print(f"{Fore.CYAN}⏰ 时间: {Fore.WHITE}{timestamp}")
                print(f"{Fore.GREEN}{'─'*60}{Style.RESET_ALL}")
            else:
                print(f"\n✅ 种子添加成功!")
                print(f"📁 名称: {short_name}")
                print(f"📂 分类: {category}")
                print(f"💾 路径: {save_path}")
                print(f"🧠 分类方式: {classification_method}")
                print(f"⏰ 时间: {timestamp}")
                print(f"{'─'*60}")

    async def send_torrent_failure(
        self,
        torrent_name: str,
        error_message: str,
        torrent_hash: str,
        attempted_category: str = "",
    ):
        """发送种子添加失败通知"""
        timestamp = self._get_timestamp()
        short_name = self._truncate_name(torrent_name, 80)

        if self.config.get("console", {}).get("enabled", True):
            if self.use_colors:
                print(f"\n{Fore.RED}❌ 种子添加失败!")
                print(f"{Fore.CYAN}📁 名称: {Fore.WHITE}{short_name}")
                if attempted_category:
                    print(f"{Fore.CYAN}📂 目标分类: {Fore.YELLOW}{attempted_category}")
                print(f"{Fore.CYAN}❌ 错误: {Fore.RED}{error_message}")
                print(f"{Fore.CYAN}⏰ 时间: {Fore.WHITE}{timestamp}")
                print(f"{Fore.RED}{'─'*60}{Style.RESET_ALL}")
            else:
                print(f"\n❌ 种子添加失败!")
                print(f"📁 名称: {short_name}")
                if attempted_category:
                    print(f"📂 目标分类: {attempted_category}")
                print(f"❌ 错误: {error_message}")
                print(f"⏰ 时间: {timestamp}")
                print(f"{'─'*60}")

    async def send_duplicate_notification(self, torrent_name: str, torrent_hash: str):
        """发送重复种子通知（直接跳过）"""
        timestamp = self._get_timestamp()
        short_name = self._truncate_name(torrent_name, 80)

        if self.config.get("console", {}).get("enabled", True):
            if self.use_colors:
                print(f"\n{Fore.YELLOW}⚠️ ⚠️ ⚠️  检测到重复种子  ⚠️ ⚠️ ⚠️")
                print(f"{Fore.CYAN}📁 种子名称: {Fore.WHITE}{short_name}")
                print(f"{Fore.CYAN}🔗 种子哈希: {Fore.WHITE}{torrent_hash[:16]}...")
                print(f"{Fore.CYAN}⏰ 检测时间: {Fore.WHITE}{timestamp}")
                print(f"{Fore.YELLOW}💡 该种子已存在于qBittorrent中，自动跳过下载")
                print(f"{Fore.YELLOW}{'─'*60}{Style.RESET_ALL}")
            else:
                print(f"\n⚠️ ⚠️ ⚠️  检测到重复种子  ⚠️ ⚠️ ⚠️")
                print(f"📁 种子名称: {short_name}")
                print(f"🔗 种子哈希: {torrent_hash[:16]}...")
                print(f"⏰ 检测时间: {timestamp}")
                print(f"💡 该种子已存在于qBittorrent中，自动跳过下载")
                print(f"{'─'*60}")

    async def send_statistics(self, stats: Dict[str, int]):
        """发送统计信息"""
        if not self.config.get("console", {}).get("show_statistics", True):
            return

        if self.use_colors:
            print(f"\n{Fore.BLUE}📊 运行统计")
            print(f"{Fore.BLUE}{'─'*40}")
            print(f"{Fore.CYAN}总处理数: {Fore.WHITE}{stats.get('total_processed', 0)}")
            print(
                f"{Fore.GREEN}成功添加: {Fore.WHITE}{stats.get('successful_adds', 0)}"
            )
            print(f"{Fore.RED}添加失败: {Fore.WHITE}{stats.get('failed_adds', 0)}")
            print(
                f"{Fore.YELLOW}重复跳过: {Fore.WHITE}{stats.get('duplicates_skipped', 0)}"
            )
            print(
                f"{Fore.MAGENTA}AI分类: {Fore.WHITE}{stats.get('ai_classifications', 0)}"
            )
            print(
                f"{Fore.MAGENTA}规则分类: {Fore.WHITE}{stats.get('rule_classifications', 0)}"
            )

            # 计算成功率
            total = stats.get("total_processed", 0)
            success = stats.get("successful_adds", 0)
            if total > 0:
                success_rate = (success / total) * 100
                color = (
                    Fore.GREEN
                    if success_rate >= 80
                    else Fore.YELLOW if success_rate >= 60 else Fore.RED
                )
                print(f"{Fore.CYAN}成功率: {color}{success_rate:.1f}%")

            print(f"{Fore.BLUE}{'─'*40}{Style.RESET_ALL}")
        else:
            print(f"\n📊 运行统计")
            print(f"{'─'*40}")
            print(f"总处理数: {stats.get('total_processed', 0)}")
            print(f"成功添加: {stats.get('successful_adds', 0)}")
            print(f"添加失败: {stats.get('failed_adds', 0)}")
            print(f"重复跳过: {stats.get('duplicates_skipped', 0)}")
            print(f"AI分类: {stats.get('ai_classifications', 0)}")
            print(f"规则分类: {stats.get('rule_classifications', 0)}")

            total = stats.get("total_processed", 0)
            success = stats.get("successful_adds", 0)
            if total > 0:
                success_rate = (success / total) * 100
                print(f"成功率: {success_rate:.1f}%")

            print(f"{'─'*40}")

    def _truncate_name(self, name: str, max_length: int) -> str:
        """截断种子名称"""
        if len(name) <= max_length:
            return name
        return name[: max_length - 3] + "..."

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 为了保持向后兼容性，创建一个别名
NotificationManager = SimpleNotificationManager


async def send_notification(message: str, config: Dict[str, Any]):
    """发送通知的简化接口（保持向后兼容）"""
    if not config.get("enabled", False):
        return

    notification_manager = SimpleNotificationManager(config)
    print(f"💬 {message}")


def ensure_directory(path: str) -> bool:
    """确保目录存在"""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logging.getLogger("Utils").error(f"创建目录失败 {path}: {str(e)}")
        return False


def get_config_path() -> Path:
    """获取默认配置文件路径"""
    # 首先尝试从环境变量获取
    config_path = os.getenv("QBMONITOR_CONFIG")
    if config_path:
        return Path(config_path)

    # 尝试当前目录
    current_dir = Path.cwd()
    config_files = ["config.json", "config.yaml", "config.yml", "config.toml"]

    for config_file in config_files:
        config_path = current_dir / config_file
        if config_path.exists():
            return config_path

    # 尝试脚本目录
    script_dir = Path(__file__).parent
    for config_file in config_files:
        config_path = script_dir / config_file
        if config_path.exists():
            return config_path

    # 默认返回JSON配置文件路径
    return script_dir / "config.json"
