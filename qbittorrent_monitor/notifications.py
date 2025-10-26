"""
通知管理模块
"""

import logging
from datetime import datetime
from typing import Dict, Any

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False


class NotificationManager:
    """简化的控制台通知管理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger('NotificationManager')
        self.use_colors = HAS_COLORAMA and config.get('console', {}).get('colored', True)
        self.base_url = config.get('qbittorrent', {}).get('base_url', 'http://localhost:8080')

    def _get_timestamp(self) -> str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _truncate_name(self, name: str, limit: int = 80) -> str:
        return name if len(name) <= limit else name[:limit - 3] + '...'

    async def send_torrent_success(self, torrent_name: str, category: str,
                                   save_path: str, torrent_hash: str,
                                   classification_method: str = "AI"):
        timestamp = self._get_timestamp()
        short_name = self._truncate_name(torrent_name, 80)

        if not self.config.get('console', {}).get('enabled', True):
            return

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

    async def send_torrent_failure(self, torrent_name: str, error_message: str,
                                   torrent_hash: str, attempted_category: str = ""):
        timestamp = self._get_timestamp()
        short_name = self._truncate_name(torrent_name, 80)

        if not self.config.get('console', {}).get('enabled', True):
            return

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
        timestamp = self._get_timestamp()
        short_name = self._truncate_name(torrent_name, 80)

        if not self.config.get('console', {}).get('enabled', True):
            return

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
        if not self.config.get('console', {}).get('show_statistics', True):
            return

        if self.use_colors:
            print(f"\n{Fore.BLUE}📊 运行统计")
            print(f"{Fore.BLUE}{'─'*40}")
            print(f"{Fore.CYAN}总处理数: {Fore.WHITE}{stats.get('total_processed', 0)}")
            print(f"{Fore.GREEN}成功添加: {Fore.WHITE}{stats.get('successful_adds', 0)}")
            print(f"{Fore.RED}添加失败: {Fore.WHITE}{stats.get('failed_adds', 0)}")
            print(f"{Fore.YELLOW}重复跳过: {Fore.WHITE}{stats.get('duplicates_skipped', 0)}")
            print(f"{Fore.MAGENTA}AI分类: {Fore.WHITE}{stats.get('ai_classifications', 0)}")
            print(f"{Fore.MAGENTA}规则分类: {Fore.WHITE}{stats.get('rule_classifications', 0)}")
            total = stats.get('total_processed', 0)
            success = stats.get('successful_adds', 0)
            if total > 0:
                rate = (success / total) * 100
                color = Fore.GREEN if rate >= 80 else Fore.YELLOW if rate >= 60 else Fore.RED
                print(f"{Fore.CYAN}成功率: {color}{rate:.1f}%")
            print(f"{Fore.BLUE}{'─'*40}{Style.RESET_ALL}")
        else:
            print(f"\n📊 运行统计")
            print(f"{'-'*40}")
            print(f"总处理数: {stats.get('total_processed', 0)}")
            print(f"成功添加: {stats.get('successful_adds', 0)}")
            print(f"添加失败: {stats.get('failed_adds', 0)}")
            print(f"重复跳过: {stats.get('duplicates_skipped', 0)}")
            print(f"AI分类: {stats.get('ai_classifications', 0)}")
            print(f"规则分类: {stats.get('rule_classifications', 0)}")
            total = stats.get('total_processed', 0)
            success = stats.get('successful_adds', 0)
            if total > 0:
                rate = (success / total) * 100
                print(f"成功率: {rate:.1f}%")
            print(f"{'-'*40}")


__all__ = ["NotificationManager"]
