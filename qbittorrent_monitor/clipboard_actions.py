"""
剪贴板执行器

负责根据处理任务执行磁力链接添加、URL 爬取等操作。
"""

import asyncio
import logging
import time
from typing import Callable, Dict, Any, Optional

from .clipboard_models import TorrentRecord
from .exceptions import TorrentParseError
from .utils import parse_magnet, validate_magnet_link
from .intelligent_filter import get_intelligent_filter, FilterAction
from .workflow_engine import get_workflow_engine


class ClipboardActionExecutor:
    """处理具体的磁力/URL 执行动作"""

    def __init__(
        self,
        qbt_client,
        config,
        ai_classifier,
        notification_manager,
        stats: Dict[str, Any],
        add_history: Callable[[TorrentRecord], None],
        logger: Optional[logging.Logger] = None,
    ):
        self.qbt = qbt_client
        self.config = config
        self.ai_classifier = ai_classifier
        self.notification_manager = notification_manager
        self.stats = stats
        self._add_history = add_history
        self.logger = logger or logging.getLogger("ClipboardActionExecutor")
        # 初始化智能过滤器
        self.intelligent_filter = get_intelligent_filter()

    async def handle_magnet(self, magnet_link: str):
        process_start = time.time()
        self.logger.info(f"🔍 发现新磁力链接: {magnet_link[:60]}...")

        if not validate_magnet_link(magnet_link):
            self.logger.error("❌ 无效的磁力链接格式")
            self.stats['failed_adds'] += 1
            return

        try:
            # 先尝试解析磁力链接获取基本信息
            torrent_hash, temp_name = parse_magnet(magnet_link)
            if not torrent_hash:
                raise TorrentParseError("无法解析磁力链接哈希值")

            # 使用临时名称进行智能过滤（如果需要获取真实名称，先添加种子）
            filter_title = temp_name or f"未命名_{torrent_hash[:8]}"

            # 执行智能过滤检查
            try:
                filter_result = await self.intelligent_filter.filter_content(
                    title=filter_title,
                    magnet_link=magnet_link,
                    seeders=self.stats.get('last_seeders', 0),
                    leechers=self.stats.get('last_leechers', 0),
                    category="other"
                )

                # 检查过滤结果
                if not filter_result.allowed:
                    self.logger.warning(
                        f"🚫 智能过滤阻止: {filter_title[:50]}... "
                        f"原因: {', '.join(filter_result.reasons)}"
                    )
                    self.stats['filtered_out'] += 1
                    return

                # 记录质量分数和标签
                if filter_result.score > 0:
                    self.logger.info(
                        f"✨ 质量评分: {filter_result.score:.1f}分 "
                        f"({filter_result.quality_level.value}) "
                        f"{' '.join(filter_result.tags[:3])}"
                    )
                    self.stats['total_quality_score'] = (
                        self.stats.get('total_quality_score', 0) + filter_result.score
                    )
                    self.stats['avg_quality_score'] = (
                        self.stats['total_quality_score'] /
                        max(1, self.stats.get('total_processed', 0))
                    )

            except Exception as filter_error:
                self.logger.warning(f"智能过滤失败，跳过过滤: {filter_error}")
                # 过滤失败不阻止处理，继续后续流程

            # 获取工作流引擎并处理
            workflow_engine = get_workflow_engine()
            if workflow_engine:
                try:
                    workflow_result = await workflow_engine.process_torrent(
                        title=filter_title,
                        magnet_link=magnet_link,
                        size=filter_result.size if 'filter_result' in locals() else None,
                        seeders=filter_result.seeders if 'filter_result' in locals() else 0,
                        leechers=filter_result.leechers if 'filter_result' in locals() else 0,
                        category="other"
                    )

                    if workflow_result.get("success"):
                        self.logger.info(
                            f"⚙️ 工作流处理完成: {filter_title[:50]}... "
                            f"质量:{workflow_result.get('quality_score', 0):.1f} "
                            f"规则匹配:{workflow_result.get('matched_rules', [])}"
                        )
                        self.stats['workflows_triggered'] = self.stats.get('workflows_triggered', 0) + 1
                    else:
                        self.logger.warning(f"工作流处理失败: {workflow_result.get('error')}")

                except Exception as workflow_error:
                    self.logger.warning(f"工作流引擎错误: {workflow_error}")
                    # 工作流失败不阻止处理，继续后续流程

            if await self.qbt._is_duplicate(torrent_hash):
                self.logger.info(f"⚠️ 跳过重复种子: {torrent_hash[:8]}")
                self.stats['duplicates_skipped'] += 1
                return

            temp_added = False
            torrent_name = temp_name
            if not torrent_name:
                self.logger.info("📥 磁力链接缺少文件名，先添加种子以获取真实名称...")
                if not await self.qbt.add_torrent(magnet_link, "other"):
                    self.logger.error("❌ 添加种子失败")
                    self.stats['failed_adds'] += 1
                    return
                temp_added = True
                await asyncio.sleep(2)
                torrent_name = await self._fetch_torrent_name(torrent_hash)

            record = TorrentRecord(magnet_link, torrent_hash, torrent_name)
            self._add_history(record)
            self.stats['total_processed'] += 1

            ds_timeout = float(getattr(getattr(self.config, 'deepseek', None), 'timeout', 15.0))
            classify_timeout = max(8.0, min(ds_timeout, 18.0))
            try:
                category = await asyncio.wait_for(
                    self._classify_torrent(record),
                    timeout=classify_timeout
                )
                record.category = category
            except asyncio.TimeoutError:
                self.logger.warning("AI分类超时，使用默认分类")
                record.category = "other"
            except Exception as exc:
                self.logger.warning(f"分类失败: {exc}，使用默认分类")
                record.category = "other"

            record.save_path = await self._get_save_path(record.category)

            if temp_added:
                await self._update_category(torrent_hash, record.category)
                record.status = "success"
            else:
                success = await self._add_torrent_to_client(record)
                if not success:
                    return

            process_time = time.time() - process_start
            self.stats['performance_metrics']['total_process_time'] += process_time
            await self._send_success_notification(record)
            self.stats['successful_adds'] += 1
            self.logger.info(
                f"✅ 成功添加种子: {record.torrent_name} -> {record.category} ({process_time:.2f}s)"
            )

        except Exception as exc:
            process_time = time.time() - process_start
            self.logger.error(f"❌ 处理磁力链接失败: {exc} ({process_time:.2f}s)")
            self.stats['failed_adds'] += 1
            self.stats.setdefault('errors', 0)
            self.stats['errors'] += 1

    async def handle_url(self, url: str):
        """处理网页 URL，调用 WebCrawler"""
        from .web_crawler import crawl_and_add_torrents

        process_start = time.time()
        self.logger.info(f"🌐 检测到网页URL: {url}")

        try:
            result = await asyncio.wait_for(
                crawl_and_add_torrents(
                    url,
                    self.config,
                    self.qbt,
                    max_pages=1
                ),
                timeout=60.0
            )

            process_time = time.time() - process_start
            self.stats['performance_metrics']['total_process_time'] += process_time

            if result['success']:
                stats = result['stats']['stats']
                self.stats['url_crawls'] += 1
                self.stats['total_processed'] += stats.get('torrents_found', 0)
                self.stats['successful_adds'] += stats.get('torrents_added', 0)
                self.stats['duplicates_skipped'] += stats.get('duplicates_skipped', 0)
                self.stats['failed_adds'] += stats.get('failed_adds', 0)
                if stats.get('torrents_added', 0) > 0:
                    self.stats['batch_adds'] += 1
            else:
                self.stats['failed_adds'] += 1

        except asyncio.TimeoutError:
            self.logger.error("网页处理超时（60秒）")
            self.stats['failed_adds'] += 1
        except Exception as exc:
            self.logger.error(f"处理网页URL失败: {exc}")
            self.stats['failed_adds'] += 1

    async def _fetch_torrent_name(self, torrent_hash: str) -> str:
        try:
            torrent_info = await self.qbt.get_torrent_properties(torrent_hash)
            if 'name' in torrent_info and torrent_info['name']:
                name = torrent_info['name']
                self.logger.info(f"📁 获取到真实文件名: {name}")
                return name
            raise ValueError("空名称")
        except Exception as exc:
            self.logger.warning(f"⚠️ 获取种子信息失败: {exc}")
            return f"未命名_{torrent_hash[:8]}"

    async def _classify_torrent(self, record: TorrentRecord) -> str:
        """先尝试规则分类，再调用AI"""
        try:
            rule_guess = self.ai_classifier._rule_based_classify(
                record.torrent_name,
                self.config.categories
            )
        except Exception:
            rule_guess = None

        if rule_guess and rule_guess != "other":
            self.stats['rule_classifications'] += 1
            record.classification_method = "规则"
            self.logger.info(
                f"🧠 规则分类结果: {record.torrent_name[:50]}... -> {rule_guess}"
            )
            return rule_guess

        try:
            category = await self.ai_classifier.classify(
                record.torrent_name,
                self.config.categories
            )
            self.stats['ai_classifications'] += 1
            record.classification_method = "AI"
            self.logger.info(
                f"🧠 AI分类结果: {record.torrent_name[:50]}... -> {category}"
            )
            return category
        except Exception as exc:
            self.logger.error(f"❌ 分类失败: {exc}, 使用默认分类 'other'")
            self.stats['rule_classifications'] += 1
            record.classification_method = "默认"
            return "other"

    async def _add_torrent_to_client(self, record: TorrentRecord) -> bool:
        try:
            torrent_params = {
                'paused': self.config.add_torrents_paused
            }
            if record.torrent_name:
                torrent_params['rename'] = record.torrent_name

            success = await self.qbt.add_torrent(
                record.magnet_link,
                record.category or "other",
                **torrent_params
            )
            if not success:
                record.error_message = "添加到客户端失败"
                return False
            return True
        except Exception as exc:
            self.logger.error(f"添加种子到qBittorrent时出错: {exc}")
            record.error_message = f"客户端错误: {exc}"
            return False

    async def _update_category(self, torrent_hash: str, category: str):
        if category == "other":
            return
        try:
            url = f"{self.qbt._base_url}/api/v2/torrents/setCategory"
            data = {
                'hashes': torrent_hash,
                'category': category
            }
            async with self.qbt.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.logger.info(f"✅ 种子分类已更新: {category}")
                else:
                    self.logger.warning(f"⚠️ 更新分类失败 (HTTP {resp.status})")
        except Exception as exc:
            self.logger.warning(f"⚠️ 更新分类异常: {exc}")

    async def _send_success_notification(self, record: TorrentRecord):
        try:
            await self.notification_manager.send_torrent_success(
                record.torrent_name,
                record.category,
                record.save_path or "默认路径",
                record.torrent_hash,
                record.classification_method or "AI"
            )
        except Exception as exc:
            self.logger.warning(f"发送通知失败: {exc}")

    async def _get_save_path(self, category: str) -> str:
        categories = self.config.categories or {}
        if category in categories:
            return categories[category].save_path
        if 'other' in categories:
            return categories['other'].save_path
        # fallback to任意分类
        first = next(iter(categories.values()))
        return first.save_path
