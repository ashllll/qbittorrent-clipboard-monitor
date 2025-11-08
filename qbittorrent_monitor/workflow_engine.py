"""
自动化工作流引擎

提供：
- 智能规则引擎
- 自动化任务调度
- 批量处理工作流
- 通知规则管理
- 工作流状态追踪
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .intelligent_filter import get_intelligent_filter, ContentQuality
from .utils import parse_magnet


logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    SKIPPED = "skipped"  # 跳过
    CANCELLED = "cancelled"  # 取消


class TaskType(Enum):
    """任务类型"""
    CLASSIFY = "classify"  # 分类任务
    DOWNLOAD = "download"  # 下载任务
    ARCHIVE = "archive"  # 归档任务
    CLEANUP = "cleanup"  # 清理任务
    NOTIFY = "notify"  # 通知任务
    MONITOR = "monitor"  # 监控任务
    BATCH = "batch"  # 批处理任务


class RuleCondition(Enum):
    """规则条件"""
    EQUALS = "equals"  # 等于
    NOT_EQUALS = "not_equals"  # 不等于
    CONTAINS = "contains"  # 包含
    NOT_CONTAINS = "not_contains"  # 不包含
    GREATER_THAN = "greater_than"  # 大于
    LESS_THAN = "less_than"  # 小于
    IN = "in"  # 在列表中
    NOT_IN = "not_in"  # 不在列表中
    REGEX = "regex"  # 正则匹配


class RuleAction(Enum):
    """规则动作"""
    SET_CATEGORY = "set_category"  # 设置分类
    SET_PRIORITY = "set_priority"  # 设置优先级
    ADD_TAG = "add_tag"  # 添加标签
    SEND_NOTIFICATION = "send_notification"  # 发送通知
    PAUSE_DOWNLOAD = "pause_download"  # 暂停下载
    START_DOWNLOAD = "start_download"  # 开始下载
    MOVE_FILES = "move_files"  # 移动文件
    EXECUTE_SCRIPT = "execute_script"  # 执行脚本
    ARCHIVE = "archive"  # 归档


@dataclass
class WorkflowRule:
    """工作流规则"""
    name: str
    enabled: bool = True
    priority: int = 0
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """评估规则条件"""
        for condition in self.conditions:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")

            if not self._evaluate_condition(context.get(field), operator, value):
                return False
        return True

    def _evaluate_condition(self, field_value: Any, operator: str, condition_value: Any) -> bool:
        """评估单个条件"""
        try:
            if operator == RuleCondition.EQUALS.value:
                return field_value == condition_value
            elif operator == RuleCondition.NOT_EQUALS.value:
                return field_value != condition_value
            elif operator == RuleCondition.CONTAINS.value:
                return str(condition_value) in str(field_value)
            elif operator == RuleCondition.NOT_CONTAINS.value:
                return str(condition_value) not in str(field_value)
            elif operator == RuleCondition.GREATER_THAN.value:
                return float(field_value) > float(condition_value)
            elif operator == RuleCondition.LESS_THAN.value:
                return float(field_value) < float(condition_value)
            elif operator == RuleCondition.IN.value:
                return field_value in condition_value
            elif operator == RuleCondition.NOT_IN.value:
                return field_value not in condition_value
            elif operator == RuleCondition.REGEX.value:
                import re
                return bool(re.search(str(condition_value), str(field_value)))
            return False
        except Exception as e:
            logger.warning(f"规则条件评估失败: {e}")
            return False


@dataclass
class WorkflowTask:
    """工作流任务"""
    id: str
    type: TaskType
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    data: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class WorkflowExecution:
    """工作流执行记录"""
    id: str
    name: str
    status: WorkflowStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    tasks: List[WorkflowTask] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class RuleEngine:
    """规则引擎"""

    def __init__(self):
        self.rules: List[WorkflowRule] = []
        self.rule_stats = {
            "total_rules": 0,
            "enabled_rules": 0,
            "total_executions": 0,
            "successful_matches": 0
        }

    def add_rule(self, rule: WorkflowRule):
        """添加规则"""
        self.rules.append(rule)
        self.rule_stats["total_rules"] += 1
        if rule.enabled:
            self.rule_stats["enabled_rules"] += 1
        logger.info(f"添加工作流规则: {rule.name}")

    def remove_rule(self, name: str):
        """移除规则"""
        self.rules = [r for r in self.rules if r.name != name]
        self.rule_stats["total_rules"] = len(self.rules)
        self.rule_stats["enabled_rules"] = sum(1 for r in self.rules if r.enabled)
        logger.info(f"移除工作流规则: {name}")

    def evaluate_rules(self, context: Dict[str, Any]) -> List[WorkflowRule]:
        """评估规则"""
        self.rule_stats["total_executions"] += 1
        matched_rules = []

        # 按优先级排序
        sorted_rules = sorted(
            [r for r in self.rules if r.enabled],
            key=lambda r: r.priority,
            reverse=True
        )

        for rule in sorted_rules:
            if rule.evaluate(context):
                matched_rules.append(rule)
                self.rule_stats["successful_matches"] += 1

        return matched_rules

    def get_rule_stats(self) -> Dict[str, Any]:
        """获取规则统计"""
        return {
            **self.rule_stats,
            "match_rate": (
                self.rule_stats["successful_matches"] /
                max(1, self.rule_stats["total_executions"]) * 100
            )
        }


class TaskScheduler:
    """任务调度器"""

    def __init__(self):
        self.scheduled_tasks: Dict[str, Dict[str, Any]] = {}
        self.running_tasks: Set[str] = set()
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.scheduler_task: Optional[asyncio.Task] = None
        self.logger = logger

    async def start(self):
        """启动调度器"""
        if self.scheduler_task is None or self.scheduler_task.done():
            self.scheduler_task = asyncio.create_task(self._scheduler_loop())
            self.logger.info("任务调度器已启动")

    async def stop(self):
        """停止调度器"""
        if self.scheduler_task and not self.scheduler_task.done():
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
            self.logger.info("任务调度器已停止")

    async def schedule_task(
        self,
        task_id: str,
        task_func: Callable,
        interval: float,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        immediate: bool = True
    ):
        """调度任务"""
        kwargs = kwargs or {}
        self.scheduled_tasks[task_id] = {
            "func": task_func,
            "interval": interval,
            "args": args,
            "kwargs": kwargs,
            "last_run": 0,
            "next_run": datetime.now().timestamp() if immediate else 0
        }
        self.logger.info(f"已调度任务: {task_id} (间隔: {interval}秒)")

    async def _scheduler_loop(self):
        """调度器主循环"""
        while True:
            try:
                current_time = datetime.now().timestamp()
                tasks_to_run = []

                for task_id, task_info in self.scheduled_tasks.items():
                    if task_id in self.running_tasks:
                        continue

                    if task_info["next_run"] <= current_time:
                        tasks_to_run.append((task_id, task_info))

                # 执行到期的任务
                for task_id, task_info in tasks_to_run:
                    self.running_tasks.add(task_id)
                    asyncio.create_task(self._run_task(task_id, task_info))

                await asyncio.sleep(1)  # 每秒检查一次

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"调度器循环错误: {e}")
                await asyncio.sleep(5)

    async def _run_task(self, task_id: str, task_info: Dict[str, Any]):
        """运行任务"""
        try:
            self.logger.debug(f"执行任务: {task_id}")
            await task_info["func"](*task_info["args"], **task_info["kwargs"])

            # 更新下次执行时间
            task_info["last_run"] = datetime.now().timestamp()
            task_info["next_run"] = task_info["last_run"] + task_info["interval"]

        except Exception as e:
            self.logger.error(f"任务执行失败 {task_id}: {e}")
        finally:
            self.running_tasks.discard(task_id)


class NotificationRules:
    """通知规则管理"""

    def __init__(self, notification_manager):
        self.notification_manager = notification_manager
        self.rules: List[WorkflowRule] = []

    def add_rule(self, rule: WorkflowRule):
        """添加通知规则"""
        self.rules.append(rule)

    def should_notify(self, context: Dict[str, Any]) -> List[WorkflowRule]:
        """检查是否应该发送通知"""
        matched_rules = []
        for rule in self.rules:
            if rule.enabled and rule.evaluate(context):
                matched_rules.append(rule)
        return matched_rules

    async def send_notifications(self, context: Dict[str, Any], matched_rules: List[WorkflowRule]):
        """发送通知"""
        for rule in matched_rules:
            for action in rule.actions:
                if action.get("type") == RuleAction.SEND_NOTIFICATION.value:
                    notification_type = action.get("value", "info")
                    title = action.get("title", "工作流通知")
                    message = action.get("message", "").format(**context)

                    try:
                        await self.notification_manager.send_custom_notification(
                            title, message, notification_type
                        )
                    except Exception as e:
                        logger.error(f"发送通知失败: {e}")


class BatchProcessor:
    """批量处理器"""

    def __init__(self, qbt_client, config):
        self.qbt = qbt_client
        self.config = config
        self.batch_queue: List[Dict[str, Any]] = []
        self.batch_stats = {
            "total_batches": 0,
            "processed_batches": 0,
            "total_items": 0,
            "processed_items": 0
        }

    async def add_to_batch(self, item: Dict[str, Any], batch_type: str = "torrent"):
        """添加到批处理队列"""
        self.batch_queue.append({
            "type": batch_type,
            "data": item,
            "added_at": datetime.now()
        })
        self.batch_stats["total_items"] += 1

    async def process_batch(self, batch_size: int = 10, timeout: int = 30):
        """处理批处理队列"""
        if not self.batch_queue:
            return

        self.batch_stats["total_batches"] += 1
        batch = self.batch_queue[:batch_size]
        self.batch_queue = self.batch_queue[batch_size:]

        try:
            self.logger.info(f"处理批处理任务: {len(batch)} 项")

            # 并行处理批次中的项目
            tasks = []
            for item in batch:
                if item["type"] == "torrent":
                    task = asyncio.create_task(
                        self._process_torrent_batch_item(item["data"])
                    )
                    tasks.append(task)

            if tasks:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout
                )

            self.batch_stats["processed_batches"] += 1
            self.batch_stats["processed_items"] += len(batch)
            self.logger.info(f"批处理完成: {len(batch)} 项")

        except asyncio.TimeoutError:
            self.logger.error(f"批处理超时 ({timeout}秒)")
        except Exception as e:
            self.logger.error(f"批处理失败: {e}")

    async def _process_torrent_batch_item(self, item: Dict[str, Any]):
        """处理单个批处理项目"""
        try:
            magnet_link = item.get("magnet_link")
            category = item.get("category", "other")

            if magnet_link:
                success = await self.qbt.add_torrent(magnet_link, category)
                if success:
                    logger.debug(f"批处理添加成功: {magnet_link[:50]}...")
                else:
                    logger.warning(f"批处理添加失败: {magnet_link[:50]}...")

        except Exception as e:
            logger.error(f"批处理项目处理失败: {e}")


class WorkflowEngine:
    """
    自动化工作流引擎

    整合规则引擎、任务调度器、通知规则和批处理器
    """

    def __init__(self, qbt_client, config, ai_classifier, notification_manager):
        self.qbt = qbt_client
        self.config = config
        self.ai_classifier = ai_classifier
        self.notification_manager = notification_manager
        self.intelligent_filter = get_intelligent_filter()

        # 初始化各个组件
        self.rule_engine = RuleEngine()
        self.task_scheduler = TaskScheduler()
        self.notification_rules = NotificationRules(notification_manager)
        self.batch_processor = BatchProcessor(qbt_client, config)

        # 工作流执行记录
        self.executions: List[WorkflowExecution] = []
        self.workflow_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_tasks": 0,
            "completed_tasks": 0
        }

        # 加载默认规则
        self._load_default_rules()

    def _load_default_rules(self):
        """加载默认工作流规则"""
        # 高质量内容自动优先下载
        high_quality_rule = WorkflowRule(
            name="high_quality_auto_download",
            enabled=True,
            priority=100,
            description="高质量内容自动优先下载",
            conditions=[
                {"field": "quality_score", "operator": "greater_than", "value": 80},
                {"field": "seeders", "operator": "greater_than", "value": 10}
            ],
            actions=[
                {"type": "set_priority", "value": "high"},
                {"type": "add_tag", "value": "auto_high_quality"},
                {"type": "send_notification", "value": "success", "title": "高质量种子", "message": "检测到高质量种子: {title}"}
            ]
        )
        self.rule_engine.add_rule(high_quality_rule)

        # 小文件自动分类
        small_file_rule = WorkflowRule(
            name="small_file_auto_classify",
            enabled=True,
            priority=80,
            description="小文件自动分类为文档",
            conditions=[
                {"field": "size", "operator": "less_than", "value": 100 * 1024 * 1024},  # < 100MB
                {"field": "title", "operator": "regex", "value": r"\.(pdf|epub|mobi|txt|doc)$"}
            ],
            actions=[
                {"type": "set_category", "value": "document"},
                {"type": "add_tag", "value": "small_file"}
            ]
        )
        self.rule_engine.add_rule(small_file_rule)

        # 低质量内容暂停下载
        low_quality_rule = WorkflowRule(
            name="low_quality_pause",
            enabled=True,
            priority=90,
            description="低质量内容暂停下载",
            conditions=[
                {"field": "quality_score", "operator": "less_than", "value": 30},
                {"field": "seeders", "operator": "less_than", "value": 5}
            ],
            actions=[
                {"type": "pause_download", "value": True},
                {"type": "add_tag", "value": "low_quality"},
                {"type": "send_notification", "value": "warning", "title": "低质量种子", "message": "检测到低质量种子: {title}"}
            ]
        )
        self.rule_engine.add_rule(low_quality_rule)

        # 通知规则
        notify_rule = WorkflowRule(
            name="new_torrent_notification",
            enabled=True,
            priority=50,
            description="新种子通知",
            conditions=[
                {"field": "action", "operator": "equals", "value": "new_torrent"}
            ],
            actions=[
                {"type": "send_notification", "value": "info", "title": "新种子", "message": "添加了新种子: {title} -> {category}"}
            ]
        )
        self.notification_rules.add_rule(notify_rule)

    async def start(self):
        """启动工作流引擎"""
        await self.task_scheduler.start()

        # 调度定期任务
        await self.task_scheduler.schedule_task(
            "cleanup_old_torrents",
            self._cleanup_old_torrents,
            interval=3600,  # 每小时清理一次
            immediate=False
        )

        await self.task_scheduler.schedule_task(
            "process_batch_queue",
            self._process_batch_queue,
            interval=30,  # 每30秒处理一次批处理队列
            immediate=True
        )

        await self.task_scheduler.schedule_task(
            "archive_completed",
            self._archive_completed,
            interval=7200,  # 每2小时归档一次
            immediate=False
        )

        logger.info("工作流引擎已启动")

    async def stop(self):
        """停止工作流引擎"""
        await self.task_scheduler.stop()
        logger.info("工作流引擎已停止")

    async def process_torrent(self, title: str, magnet_link: str, **kwargs) -> Dict[str, Any]:
        """处理种子，触发工作流"""
        execution_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        execution = WorkflowExecution(
            id=execution_id,
            name="torrent_processing",
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now(),
            context={
                "title": title,
                "magnet_link": magnet_link,
                **kwargs
            }
        )

        self.executions.append(execution)
        self.workflow_stats["total_executions"] += 1

        try:
            # 创建任务
            task = WorkflowTask(
                id=f"{execution_id}_task_1",
                type=TaskType.CLASSIFY,
                data={"title": title, "magnet_link": magnet_link}
            )
            execution.tasks.append(task)

            # 获取质量分数
            filter_result = await self.intelligent_filter.filter_content(
                title=title,
                magnet_link=magnet_link,
                **kwargs
            )

            # 评估规则
            context = {
                "title": title,
                "magnet_link": magnet_link,
                "quality_score": filter_result.score,
                "quality_level": filter_result.quality_level.value,
                "size": kwargs.get("size"),
                "seeders": kwargs.get("seeders", 0),
                "leechers": kwargs.get("leechers", 0),
                "category": kwargs.get("category", "other"),
                "tags": filter_result.tags,
                "action": "new_torrent"
            }

            matched_rules = self.rule_engine.evaluate_rules(context)

            # 执行规则动作
            for rule in matched_rules:
                await self._execute_rule_actions(rule, context)

            # 检查通知规则
            notification_rules = self.notification_rules.should_notify(context)
            if notification_rules:
                await self.notification_rules.send_notifications(context, notification_rules)

            # 标记任务完成
            task.status = WorkflowStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = {
                "quality_score": filter_result.score,
                "quality_level": filter_result.quality_level.value,
                "matched_rules": [r.name for r in matched_rules]
            }

            # 标记执行完成
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now()
            self.workflow_stats["successful_executions"] += 1

            return {
                "success": True,
                "execution_id": execution_id,
                "quality_score": filter_result.score,
                "quality_level": filter_result.quality_level.value,
                "matched_rules": [r.name for r in matched_rules],
                "actions_taken": len(matched_rules)
            }

        except Exception as e:
            # 处理错误
            execution.status = WorkflowStatus.FAILED
            execution.completed_at = datetime.now()
            execution.context["error"] = str(e)
            self.workflow_stats["failed_executions"] += 1

            logger.error(f"工作流执行失败: {e}")
            return {
                "success": False,
                "execution_id": execution_id,
                "error": str(e)
            }

    async def _execute_rule_actions(self, rule: WorkflowRule, context: Dict[str, Any]):
        """执行规则动作"""
        for action in rule.actions:
            action_type = action.get("type")
            action_value = action.get("value")

            try:
                if action_type == RuleAction.SET_CATEGORY.value:
                    context["category"] = action_value
                    logger.info(f"规则 {rule.name}: 设置分类为 {action_value}")

                elif action_type == RuleAction.ADD_TAG.value:
                    if "tags" not in context:
                        context["tags"] = []
                    context["tags"].append(action_value)
                    logger.info(f"规则 {rule.name}: 添加标签 {action_value}")

                elif action_type == RuleAction.PAUSE_DOWNLOAD.value:
                    if action_value and context.get("magnet_link"):
                        # 暂停下载逻辑
                        logger.info(f"规则 {rule.name}: 暂停下载")

                # 可以添加更多动作类型

            except Exception as e:
                logger.error(f"执行规则动作失败 {rule.name}: {e}")

    async def _cleanup_old_torrents(self):
        """清理旧的种子"""
        try:
            logger.info("开始清理旧种子...")
            # 这里可以添加清理逻辑，比如删除已完成且超过一定时间的种子
            # 例如: 删除已完成且超过30天的种子
            # await self.qbt.delete_torrents(older_than=30)
            logger.info("旧种子清理完成")
        except Exception as e:
            logger.error(f"清理旧种子失败: {e}")

    async def _process_batch_queue(self):
        """处理批处理队列"""
        try:
            await self.batch_processor.process_batch(batch_size=5, timeout=10)
        except Exception as e:
            logger.error(f"处理批处理队列失败: {e}")

    async def _archive_completed(self):
        """归档已完成的下载"""
        try:
            logger.info("开始归档已完成的下载...")
            # 这里可以添加归档逻辑
            # 例如: 将已完成的种子移动到归档目录
            logger.info("归档完成")
        except Exception as e:
            logger.error(f"归档失败: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取工作流统计"""
        return {
            **self.workflow_stats,
            "rule_engine": self.rule_engine.get_rule_stats(),
            "batch_processor": self.batch_processor.batch_stats,
            "active_executions": len([e for e in self.executions if e.status == WorkflowStatus.RUNNING]),
            "total_executions_history": len(self.executions)
        }

    def get_recent_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的执行记录"""
        recent = sorted(
            self.executions,
            key=lambda e: e.started_at,
            reverse=True
        )[:limit]

        return [
            {
                "id": e.id,
                "name": e.name,
                "status": e.status.value,
                "started_at": e.started_at.isoformat(),
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "task_count": len(e.tasks)
            }
            for e in recent
        ]


# 全局工作流引擎实例
_workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> Optional[WorkflowEngine]:
    """获取全局工作流引擎"""
    return _workflow_engine


async def initialize_workflow_engine(
    qbt_client,
    config,
    ai_classifier,
    notification_manager
) -> WorkflowEngine:
    """初始化全局工作流引擎"""
    global _workflow_engine
    _workflow_engine = WorkflowEngine(
        qbt_client, config, ai_classifier, notification_manager
    )
    await _workflow_engine.start()
    return _workflow_engine
