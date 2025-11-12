"""
优雅关闭管理器
处理系统信号，确保资源正确释放
"""

import signal
import asyncio
import logging
import time
import threading
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import sys

logger = logging.getLogger(__name__)


class ShutdownPhase(Enum):
    """关闭阶段"""
    INITIATED = "initiated"  # 关闭已启动
    GRACEFUL = "graceful"    # 优雅关闭中
    FORCE = "force"         # 强制关闭中
    COMPLETED = "completed"  # 关闭完成


@dataclass
class ShutdownTask:
    """关闭任务"""
    name: str
    func: Callable
    timeout: float = 30.0
    priority: int = 100  # 优先级，数字越小优先级越高
    phase: ShutdownPhase = ShutdownPhase.GRACEFUL
    retries: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务名称
    completed: bool = False
    error: Optional[Exception] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


@dataclass
class ShutdownStatus:
    """关闭状态"""
    phase: ShutdownPhase
    start_time: float
    end_time: Optional[float] = None
    signal: Optional[str] = None
    tasks: Dict[str, ShutdownTask] = field(default_factory=dict)
    completed_tasks: List[str] = field(default_factory=list)
    failed_tasks: List[str] = field(default_factory=list)
    total_duration: Optional[float] = None


class GracefulShutdown:
    """优雅关闭管理器"""

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout
        self.shutdown_status = ShutdownStatus(
            phase=ShutdownPhase.INITIATED,
            start_time=0
        )
        self.tasks: Dict[str, ShutdownTask] = {}
        self.running = False
        self.shutdown_event = asyncio.Event()
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.cleanup_complete = asyncio.Event()

        # 注册系统信号处理器
        self._setup_signal_handlers()

        logger.info("优雅关闭管理器初始化完成")

    def _setup_signal_handlers(self):
        """设置系统信号处理器"""
        # 处理SIGINT (Ctrl+C)
        signal.signal(signal.SIGINT, self._signal_handler)

        # 处理SIGTERM (终止信号)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, self._signal_handler)

        # 在Windows上处理SIGBREAK
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """信号处理器"""
        signal_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
        logger.info(f"收到关闭信号: {signal_name}")

        if self.loop and self.loop.is_running():
            # 在事件循环中调度关闭
            if signum == signal.SIGINT:
                asyncio.create_task(self.shutdown("SIGINT", force=False))
            elif signum == signal.SIGTERM:
                asyncio.create_task(self.shutdown("SIGTERM", force=False))
            else:
                asyncio.create_task(self.shutdown(signal_name, force=True))
        else:
            # 如果事件循环未运行，设置事件
            self.shutdown_event.set()

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """设置事件循环"""
        self.loop = loop

    def register_task(self,
                     name: str,
                     func: Callable,
                     timeout: float = 30.0,
                     priority: int = 100,
                     phase: ShutdownPhase = ShutdownPhase.GRACEFUL,
                     dependencies: List[str] = None,
                     max_retries: int = 3):
        """注册关闭任务"""
        task = ShutdownTask(
            name=name,
            func=func,
            timeout=timeout,
            priority=priority,
            phase=phase,
            dependencies=dependencies or [],
            max_retries=max_retries
        )

        self.tasks[name] = task
        logger.debug(f"注册关闭任务: {name} (优先级: {priority}, 超时: {timeout}s)")

    def register_immediate_task(self, name: str, func: Callable, timeout: float = 5.0):
        """注册立即执行任务（最高优先级）"""
        self.register_task(name, func, timeout, priority=1, phase=ShutdownPhase.INITIATED)

    def register_force_task(self, name: str, func: Callable, timeout: float = 10.0):
        """注册强制关闭任务"""
        self.register_task(name, func, timeout, priority=200, phase=ShutdownPhase.FORCE)

    def register_graceful_task(self, name: str, func: Callable, timeout: float = 30.0, priority: int = 100):
        """注册优雅关闭任务"""
        self.register_task(name, func, timeout, priority, phase=ShutdownPhase.GRACEFUL)

    async def shutdown(self, signal: str = "MANUAL", force: bool = False) -> ShutdownStatus:
        """执行优雅关闭"""
        if self.running:
            logger.warning("关闭流程已在进行中")
            return self.shutdown_status

        self.running = True
        start_time = time.time()

        self.shutdown_status = ShutdownStatus(
            phase=ShutdownPhase.INITIATED,
            start_time=start_time,
            signal=signal,
            tasks=self.tasks.copy()
        )

        logger.info(f"开始优雅关闭流程 (信号: {signal}, 强制: {force})")

        try:
            # 第一阶段：立即任务
            await self._execute_phase_tasks(ShutdownPhase.INITIATED)

            # 第二阶段：优雅关闭任务（除非强制关闭）
            if not force:
                await self._execute_phase_tasks(ShutdownPhase.GRACEFUL)

            # 第三阶段：强制关闭任务
            await self._execute_phase_tasks(ShutdownPhase.FORCE)

            self.shutdown_status.phase = ShutdownPhase.COMPLETED
            self.shutdown_status.end_time = time.time()
            self.shutdown_status.total_duration = self.shutdown_status.end_time - start_time

            logger.info(f"优雅关闭完成，总耗时: {self.shutdown_status.total_duration:.2f}s")

        except Exception as e:
            logger.error(f"优雅关闭过程中出错: {e}")
            self.shutdown_status.end_time = time.time()
            self.shutdown_status.total_duration = self.shutdown_status.end_time - start_time

        finally:
            self.running = False
            self.cleanup_complete.set()

        return self.shutdown_status

    async def _execute_phase_tasks(self, phase: ShutdownPhase):
        """执行特定阶段的任务"""
        phase_tasks = [task for task in self.tasks.values() if task.phase == phase]

        if not phase_tasks:
            return

        logger.info(f"执行 {phase.value} 阶段任务 ({len(phase_tasks)} 个)")

        # 按优先级排序
        phase_tasks.sort(key=lambda t: t.priority)

        # 按依赖关系执行
        executed_tasks = set()

        for task in phase_tasks:
            if task.name in executed_tasks:
                continue

            # 检查依赖
            if not self._check_dependencies(task, executed_tasks):
                logger.warning(f"任务 {task.name} 的依赖未满足，跳过")
                continue

            await self._execute_task_with_retry(task)
            executed_tasks.add(task.name)

    def _check_dependencies(self, task: ShutdownTask, executed_tasks: set) -> bool:
        """检查任务依赖"""
        for dep in task.dependencies:
            if dep not in executed_tasks:
                return False
        return True

    async def _execute_task_with_retry(self, task: ShutdownTask):
        """执行任务并支持重试"""
        self.shutdown_status.tasks[task.name] = task

        for attempt in range(task.max_retries + 1):
            task.start_time = time.time()

            try:
                logger.info(f"执行关闭任务: {task.name} (尝试 {attempt + 1}/{task.max_retries + 1})")

                # 执行任务
                if asyncio.iscoroutinefunction(task.func):
                    await asyncio.wait_for(task.func(), timeout=task.timeout)
                else:
                    # 在线程池中执行同步函数
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, task.func),
                        timeout=task.timeout
                    )

                task.end_time = time.time()
                task.completed = True
                duration = task.end_time - task.start_time

                self.shutdown_status.completed_tasks.append(task.name)
                logger.info(f"关闭任务完成: {task.name} (耗时: {duration:.2f}s)")
                return

            except asyncio.TimeoutError:
                task.error = Exception(f"任务超时 ({task.timeout}s)")
                logger.error(f"关闭任务超时: {task.name}")

            except Exception as e:
                task.error = e
                logger.error(f"关闭任务失败: {task.name} - {str(e)}")

            task.retries = attempt + 1

            # 如果不是最后一次尝试，等待一段时间再重试
            if attempt < task.max_retries:
                wait_time = min(2 ** attempt, 10)  # 指数退避，最大10秒
                logger.info(f"等待 {wait_time}s 后重试任务: {task.name}")
                await asyncio.sleep(wait_time)

        # 所有重试都失败了
        task.end_time = time.time()
        self.shutdown_status.failed_tasks.append(task.name)
        logger.error(f"关闭任务最终失败: {task.name} (重试 {task.max_retries} 次)")

    async def wait_for_shutdown(self, timeout: Optional[float] = None) -> ShutdownStatus:
        """等待关闭完成"""
        if timeout is None:
            timeout = self.timeout

        try:
            await asyncio.wait_for(self.cleanup_complete.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"等待关闭超时 ({timeout}s)，强制完成")
            self.shutdown_status.phase = ShutdownPhase.COMPLETED
            self.shutdown_status.end_time = time.time()
            self.shutdown_status.total_duration = self.shutdown_status.end_time - self.shutdown_status.start_time

        return self.shutdown_status

    def get_shutdown_status(self) -> ShutdownStatus:
        """获取关闭状态"""
        return self.shutdown_status

    def is_shutting_down(self) -> bool:
        """检查是否正在关闭"""
        return self.running

    def print_shutdown_summary(self):
        """打印关闭摘要"""
        status = self.shutdown_status

        print("\n" + "="*60)
        print("🛑 优雅关闭摘要")
        print("="*60)
        print(f"📊 关闭状态: {status.phase.value}")
        print(f"⏱️  总耗时: {status.total_duration or 0:.2f}s")
        print(f"📡 触发信号: {status.signal or 'MANUAL'}")

        print(f"\n✅ 完成任务 ({len(status.completed_tasks)}):")
        for task_name in status.completed_tasks:
            task = status.tasks.get(task_name)
            if task and task.start_time and task.end_time:
                duration = task.end_time - task.start_time
                print(f"   ✅ {task_name} ({duration:.2f}s)")
            else:
                print(f"   ✅ {task_name}")

        print(f"\n❌ 失败任务 ({len(status.failed_tasks)}):")
        for task_name in status.failed_tasks:
            task = status.tasks.get(task_name)
            if task and task.error:
                print(f"   ❌ {task_name}: {str(task.error)[:100]}")
            else:
                print(f"   ❌ {task_name}")

        print("="*60)


class ShutdownManager:
    """关闭管理器 - 高级封装"""

    def __init__(self, timeout: float = 60.0):
        self.graceful_shutdown = GracefulShutdown(timeout)
        self.components: Dict[str, Any] = {}
        self.registered = False

    def register_component(self, name: str, component: Any):
        """注册组件"""
        self.components[name] = component
        logger.info(f"注册组件: {name}")

    def auto_register(self,
                     qbt_client=None,
                     clipboard_monitor=None,
                     ai_classifier=None,
                     web_server=None,
                     health_checker=None,
                     prometheus_server=None):
        """自动注册常见组件的关闭任务"""
        if self.registered:
            logger.warning("组件已注册，跳过重复注册")
            return

        # 注册qBittorrent客户端关闭
        if qbt_client:
            self.graceful_shutdown.register_graceful_task(
                "qbt_client_close",
                self._create_cleanup_task(qbt_client, "close"),
                timeout=15.0,
                priority=10
            )

        # 注册剪贴板监控器关闭
        if clipboard_monitor:
            self.graceful_shutdown.register_graceful_task(
                "clipboard_monitor_stop",
                self._create_cleanup_task(clipboard_monitor, "stop"),
                timeout=10.0,
                priority=20
            )

        # 注册AI分类器关闭
        if ai_classifier:
            self.graceful_shutdown.register_graceful_task(
                "ai_classifier_cleanup",
                self._create_cleanup_task(ai_classifier, "cleanup"),
                timeout=10.0,
                priority=30
            )

        # 注册Web服务器关闭
        if web_server:
            self.graceful_shutdown.register_graceful_task(
                "web_server_stop",
                self._create_cleanup_task(web_server, "stop"),
                timeout=15.0,
                priority=40
            )

        # 注册健康检查服务关闭
        if health_checker:
            self.graceful_shutdown.register_force_task(
                "health_checker_stop",
                self._create_cleanup_task(health_checker, "stop"),
                timeout=5.0
            )

        # 注册Prometheus指标服务关闭
        if prometheus_server:
            self.graceful_shutdown.register_force_task(
                "prometheus_server_stop",
                self._create_cleanup_task(prometheus_server, "stop"),
                timeout=5.0
            )

        # 注册通用资源清理
        self.graceful_shutdown.register_force_task(
            "resource_cleanup",
            self._general_cleanup,
            timeout=10.0
        )

        # 注册日志刷新
        self.graceful_shutdown.register_immediate_task(
            "log_flush",
            self._flush_logs,
            timeout=5.0
        )

        self.registered = True
        logger.info("自动组件注册完成")

    def _create_cleanup_task(self, component: Any, method_name: str) -> Callable:
        """创建组件清理任务"""
        async def cleanup_task():
            method = getattr(component, method_name, None)
            if method:
                if asyncio.iscoroutinefunction(method):
                    await method()
                else:
                    method()
            else:
                logger.warning(f"组件 {type(component).__name__} 没有 {method_name} 方法")

        return cleanup_task

    async def _general_cleanup(self):
        """通用资源清理"""
        logger.info("执行通用资源清理")

        # 清理事件循环中的任务
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

        if tasks:
            logger.info(f"等待 {len(tasks)} 个后台任务完成...")

            # 等待任务完成，但设置超时
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("部分后台任务未在超时时间内完成")

                # 取消未完成的任务
                for task in tasks:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

    def _flush_logs(self):
        """刷新日志"""
        logger.info("刷新日志缓冲区")

        # 刷新所有日志处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if hasattr(handler, 'flush'):
                try:
                    handler.flush()
                except Exception as e:
                    logger.error(f"刷新日志处理器失败: {e}")

    async def wait_for_signal(self):
        """等待关闭信号"""
        await self.graceful_shutdown.shutdown_event.wait()

    async def execute_shutdown(self, signal: str = "MANUAL", force: bool = False) -> ShutdownStatus:
        """执行关闭"""
        return await self.graceful_shutdown.shutdown(signal, force)

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """设置事件循环"""
        self.graceful_shutdown.set_event_loop(loop)


# 全局关闭管理器实例
global_shutdown_manager = ShutdownManager()


def get_shutdown_manager() -> ShutdownManager:
    """获取全局关闭管理器"""
    return global_shutdown_manager


def register_component(name: str, component: Any):
    """注册组件到全局关闭管理器"""
    global_shutdown_manager.register_component(name, component)


def auto_register_components(**kwargs):
    """自动注册组件到全局关闭管理器"""
    global_shutdown_manager.auto_register(**kwargs)


# 装饰器：自动注册关闭任务
def on_shutdown(name: str = None, timeout: float = 30.0, priority: int = 100, phase: ShutdownPhase = ShutdownPhase.GRACEFUL):
    """装饰器：自动注册关闭任务"""
    def decorator(func):
        task_name = name or func.__name__
        global_shutdown_manager.graceful_shutdown.register_task(
            name=task_name,
            func=func,
            timeout=timeout,
            priority=priority,
            phase=phase
        )
        return func
    return decorator


# 装饰器：优雅关闭
def graceful_shutdown_task(name: str = None, timeout: float = 30.0, priority: int = 100):
    """装饰器：注册优雅关闭任务"""
    return on_shutdown(name, timeout, priority, ShutdownPhase.GRACEFUL)


# 装饰器：强制关闭
def force_shutdown_task(name: str = None, timeout: float = 10.0, priority: int = 200):
    """装饰器：注册强制关闭任务"""
    return on_shutdown(name, timeout, priority, ShutdownPhase.FORCE)


# 装饰器：立即关闭
def immediate_shutdown_task(name: str = None, timeout: float = 5.0, priority: int = 1):
    """装饰器：注册立即关闭任务"""
    return on_shutdown(name, timeout, priority, ShutdownPhase.INITIATED)