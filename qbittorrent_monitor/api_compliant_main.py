"""
100% API 合规的主程序

严格确保：
1. 所有 qBittorrent 操作通过官方 API
2. 本地功能与 API 功能完全分离
3. 详细记录每个 API 调用
4. 完整的错误处理和恢复
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
import pyperclip

from .config import AppConfig
from .api_compliant_client import APIClient, create_api_client
from .local_processor import (
    LocalClipboardProcessor,
    LocalCategoryMapper,
    LocalDuplicateDetector,
    create_local_processor,
    ProcessedContent
)
from .exceptions import QBittorrentError, NetworkError


class APICompliantMonitor:
    """
    100% API 合规的剪贴板监控器

    严格分离：
    - API 操作：仅通过官方 API 操作 qBittorrent
    - 本地操作：内容处理、分类、重复检测
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = logging.getLogger('APICompliantMonitor')

        # 初始化组件
        self.api_client: Optional[APIClient] = None
        self.local_processor: Optional[LocalClipboardProcessor] = None
        self.category_mapper: Optional[LocalCategoryMapper] = None
        self.duplicate_detector: Optional[LocalDuplicateDetector] = None

        # 监控状态
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

        # 统计信息
        self._stats = {
            'monitoring_started_at': None,
            'total_checks': 0,
            'successful_adds': 0,
            'failed_adds': 0,
            'duplicates_blocked': 0,
            'processing_errors': 0,
            'api_calls': 0
        }

    async def initialize(self):
        """初始化所有组件"""
        try:
            self.logger.info("初始化 API 合规监控器...")

            # 1. 初始化 API 客户端
            self.api_client = await create_api_client(self.config.qbittorrent)
            self.logger.info("✅ API 客户端初始化成功")

            # 2. 初始化本地处理器
            (
                self.local_processor,
                self.category_mapper,
                self.duplicate_detector
            ) = create_local_processor(self.config.categories)
            self.logger.info("✅ 本地处理器初始化成功")

            # 3. 确保 API 端点可用
            await self._verify_api_connectivity()
            self.logger.info("✅ API 连接验证成功")

            # 4. 初始化 qBittorrent 分类
            await self._initialize_categories()
            self.logger.info("✅ qBittorrent 分类初始化完成")

            self.logger.info("API 合规监控器初始化完成")
            return True

        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            raise

    async def start_monitoring(self, check_interval: float = 1.0):
        """开始监控剪贴板"""
        if self._running:
            self.logger.warning("监控已在运行中")
            return

        await self.initialize()

        self._running = True
        self._stats['monitoring_started_at'] = time.time()

        self.logger.info(f"开始监控剪贴板 (间隔: {check_interval}秒)")

        try:
            while self._running:
                await self._check_clipboard()
                await asyncio.sleep(check_interval)
        except asyncio.CancelledError:
            self.logger.info("监控任务被取消")
        except Exception as e:
            self.logger.error(f"监控过程中出错: {e}")
        finally:
            await self.stop_monitoring()

    async def stop_monitoring(self):
        """停止监控"""
        if not self._running:
            return

        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None

        # 关闭 API 客户端
        if self.api_client:
            await self.api_client.close()

        self.logger.info("剪贴板监控已停止")

    async def _check_clipboard(self):
        """检查剪贴板内容"""
        try:
            self._stats['total_checks'] += 1

            # 获取剪贴板内容
            clipboard_content = pyperclip.paste()
            if not clipboard_content:
                return

            # 本地处理剪贴板内容
            processed_content = self.local_processor.process_clipboard_content(clipboard_content)
            if not processed_content:
                return

            self.logger.info(f"发现下载内容: {processed_content.display_name}")

            # 本地重复检测
            if self.duplicate_detector.is_duplicate(processed_content.magnet_link):
                self._stats['duplicates_blocked'] += 1
                self.logger.info("检测到重复内容，跳过")
                return

            # 映射分类
            category = self.category_mapper.map_to_category(processed_content.content_type)
            if not category:
                category = "other"  # 默认分类

            # 通过 API 添加到 qBittorrent
            success = await self._add_torrent_via_api(processed_content, category)
            if success:
                self._stats['successful_adds'] += 1
                self.logger.info(f"成功添加到 qBittorrent: {processed_content.display_name}")
            else:
                self._stats['failed_adds'] += 1
                self.logger.error(f"添加到 qBittorrent 失败: {processed_content.display_name}")

        except Exception as e:
            self._stats['processing_errors'] += 1
            self.logger.error(f"检查剪贴板失败: {e}")

    async def _add_torrent_via_api(self, processed_content: ProcessedContent, category: str) -> bool:
        """
        通过 API 添加种子到 qBittorrent

        100% 使用官方 API，不进行任何本地操作
        """
        try:
            self._stats['api_calls'] += 1

            # 使用 API 添加种子
            success = await self.api_client.add_torrent(
                urls=processed_content.magnet_link,
                category=category,
                paused=self.config.monitor.pause_on_add
            )

            if success:
                self.logger.info(f"API: 种子添加成功 (分类: {category})")
                return True
            else:
                self.logger.error("API: 种子添加失败")
                return False

        except Exception as e:
            self.logger.error(f"API 调用失败: {e}")
            return False

    async def _verify_api_connectivity(self):
        """验证 API 连接性"""
        try:
            # 测试 API 版本端点
            version = await self.api_client.get_application_version()
            self.logger.info(f"API 连接成功，qBittorrent 版本: {version}")

            # 测试传输信息端点
            transfer_info = await self.api_client.get_transfer_info()
            self.logger.debug(f"传输状态: {transfer_info.get('connection_status', 'unknown')}")

        except Exception as e:
            raise QBittorrentError(f"API 连接验证失败: {e}")

    async def _initialize_categories(self):
        """初始化 qBittorrent 分类"""
        try:
            # 获取现有分类
            existing_categories = await self.api_client.get_categories()
            self.logger.debug(f"现有分类: {list(existing_categories.keys())}")

            # 确保配置的分类存在
            for category_name in self.config.categories:
                if category_name not in existing_categories:
                    success = await self.api_client.create_category(category_name)
                    if success:
                        self.logger.info(f"API: 创建分类成功: {category_name}")
                    else:
                        self.logger.error(f"API: 创建分类失败: {category_name}")

        except Exception as e:
            self.logger.error(f"初始化分类失败: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        stats = {
            **self._stats,
            'local_processor_stats': self.local_processor.get_statistics() if self.local_processor else {},
            'duplicate_detector_stats': self.duplicate_detector.get_statistics() if self.duplicate_detector else {},
            'api_client_stats': self.api_client.get_api_statistics() if self.api_client else {},
            'uptime_seconds': (
                time.time() - self._stats['monitoring_started_at']
                if self._stats['monitoring_started_at'] else 0
            )
        }

        # 计算成功率
        total_add_attempts = self._stats['successful_adds'] + self._stats['failed_adds']
        if total_add_attempts > 0:
            stats['success_rate'] = (self._stats['successful_adds'] / total_add_attempts) * 100

        return stats

    async def manual_add_torrent(self, magnet_link: str, category: str = None) -> bool:
        """
        手动添加种子

        通过 API 添加，确保 100% 合规
        """
        if not self.api_client:
            raise QBittorrentError("API 客户端未初始化")

        # 本地处理内容
        processed_content = self.local_processor.process_clipboard_content(magnet_link)
        if not processed_content:
            self.logger.error("无法处理磁力链接")
            return False

        # 确定分类
        if not category:
            category = self.category_mapper.map_to_category(processed_content.content_type)
        if not category:
            category = "other"

        # 通过 API 添加
        return await self._add_torrent_via_api(processed_content, category)

    async def get_torrent_list(self) -> list:
        """
        获取种子列表

        通过 API 获取
        """
        if not self.api_client:
            raise QBittorrentError("API 客户端未初始化")

        try:
            torrents = await self.api_client.get_torrents_info()
            return torrents
        except Exception as e:
            self.logger.error(f"获取种子列表失败: {e}")
            return []

    async def verify_compliance(self) -> Dict[str, Any]:
        """验证 API 合规性"""
        compliance_report = {
            'api_client_initialized': self.api_client is not None,
            'local_processor_initialized': self.local_processor is not None,
            'category_mapper_initialized': self.category_mapper is not None,
            'duplicate_detector_initialized': self.duplicate_detector is not None,
            'api_endpoints_used': set(),
            'compliance_score': 0
        }

        if self.api_client:
            stats = self.api_client.get_api_statistics()
            compliance_report['api_endpoints_used'] = stats['api_endpoints_used']
            compliance_report['api_calls_count'] = stats['total_requests']
            compliance_report['api_success_rate'] = stats['success_rate']

            # 计算合规分数
            required_endpoints = {
                '/auth/login',
                '/torrents/add',
                '/torrents/info',
                '/torrents/categories',
                '/torrents/createCategory'
            }

            used_required = len(compliance_report['api_endpoints_used'] & required_endpoints)
            compliance_report['compliance_score'] = (used_required / len(required_endpoints)) * 100

        return compliance_report


# 使用示例
async def main():
    """主函数示例"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建配置
    config = AppConfig(
        qbittorrent={
            "host": "localhost",
            "port": 8080,
            "username": "admin",
            "password": "adminpass"
        },
        categories={
            "movie": {"keywords": ["movie", "film", "电影"]},
            "tv": {"keywords": ["tv", "series", "电视剧"]},
            "anime": {"keywords": ["anime", "animation", "动漫"]}
        },
        monitor={
            "pause_on_add": False
        }
    )

    # 创建监控器
    monitor = APICompliantMonitor(config)

    try:
        # 开始监控
        await monitor.start_monitoring(check_interval=1.0)

    except KeyboardInterrupt:
        print("\n用户中断，正在停止...")
    except Exception as e:
        print(f"监控过程中出错: {e}")
    finally:
        await monitor.stop_monitoring()

        # 显示统计信息
        stats = monitor.get_statistics()
        print(f"\n监控统计:")
        print(f"总检查次数: {stats['total_checks']}")
        print(f"成功添加: {stats['successful_adds']}")
        print(f"重复阻塞: {stats['duplicates_blocked']}")
        print(f"运行时间: {stats['uptime_seconds']:.1f}秒")

        # 验证合规性
        compliance = await monitor.verify_compliance()
        print(f"\nAPI 合规性:")
        print(f"合规分数: {compliance['compliance_score']:.1f}%")
        print(f"使用的API端点: {len(compliance['api_endpoints_used'])}")


if __name__ == "__main__":
    asyncio.run(main())