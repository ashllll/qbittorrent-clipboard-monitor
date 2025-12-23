"""
降级策略模块

实现AI服务不可用时自动切换到规则引擎的机制，包括：
1. 降级状态跟踪
2. 自动恢复机制
3. 降级通知
4. 降级统计
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum

from .exceptions import AIFallbackError
from .config import CategoryConfig
from .retry import RetryConfig, CircuitBreaker


class FallbackStrategy(Enum):
    """降级策略枚举"""
    IMMEDIATE = "immediate"          # 立即降级
    GRADUAL = "gradual"             # 渐进降级
    THRESHOLD = "threshold"         # 阈值降级
    ADAPTIVE = "adaptive"           # 自适应降级


class FallbackState(Enum):
    """降级状态枚举"""
    NORMAL = "normal"               # 正常状态
    DEGRADED = "degraded"          # 降级状态
    RECOVERY = "recovery"           # 恢复状态


class FallbackManager:
    """降级管理器"""
    
    def __init__(
        self,
        strategy: FallbackStrategy = FallbackStrategy.THRESHOLD,
        ai_failure_threshold: int = 3,
        recovery_threshold: int = 5,
        degradation_duration: int = 300,  # 5分钟
        check_interval: int = 30,         # 30秒检查一次
        on_state_change: Optional[Callable[[FallbackState, FallbackState], None]] = None,
        on_fallback_activated: Optional[Callable[[], None]] = None,
        on_fallback_recovered: Optional[Callable[[], None]] = None
    ):
        """
        初始化降级管理器
        
        Args:
            strategy: 降级策略
            ai_failure_threshold: AI服务失败阈值
            recovery_threshold: AI服务恢复阈值
            degradation_duration: 降级状态持续时间（秒）
            check_interval: 检查间隔（秒）
            on_state_change: 状态变化回调
            on_fallback_activated: 降级激活回调
            on_fallback_recovered: 降级恢复回调
        """
        self.strategy = strategy
        self.ai_failure_threshold = ai_failure_threshold
        self.recovery_threshold = recovery_threshold
        self.degradation_duration = degradation_duration
        self.check_interval = check_interval
        self.on_state_change = on_state_change
        self.on_fallback_activated = on_fallback_activated
        self.on_fallback_recovered = on_fallback_recovered
        
        self.logger = logging.getLogger(__name__)
        
        # 状态跟踪
        self._state = FallbackState.NORMAL
        self._ai_failures = 0
        self._ai_successes = 0
        self._fallback_activations = 0
        self._last_failure_time = None
        self._last_success_time = None
        self._degradation_start_time = None
        self._lock = asyncio.Lock()
        
        # 统计信息
        self._stats = {
            "total_ai_requests": 0,
            "successful_ai_requests": 0,
            "failed_ai_requests": 0,
            "fallback_activations": 0,
            "total_fallback_time": 0.0,
            "avg_fallback_duration": 0.0,
            "max_fallback_duration": 0.0,
            "last_fallback_time": None,
            "fallback_success_rate": 0.0,
            "current_state": self._state.value,
            "state_duration": 0.0,
            "consecutive_ai_failures": 0,
            "consecutive_ai_successes": 0
        }
        
        # 状态计时器
        self._state_start_time = datetime.now()
        
        # 监控任务
        self._monitor_task = None
        self._is_running = False
    
    async def start_monitoring(self):
        """启动监控任务"""
        if self._is_running:
            return
        
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("降级管理器监控已启动")
    
    async def stop_monitoring(self):
        """停止监控任务"""
        if not self._is_running:
            return
        
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("降级管理器监控已停止")
    
    async def _monitor_loop(self):
        """监控循环"""
        while self._is_running:
            try:
                await asyncio.sleep(self.check_interval)
                await self._check_and_update_state()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"降级监控循环出错: {str(e)}")
    
    async def _check_and_update_state(self):
        """检查并更新状态"""
        async with self._lock:
            current_time = datetime.now()
            
            # 检查是否需要恢复
            if self._state == FallbackState.DEGRADED:
                degradation_duration = (current_time - self._degradation_start_time).total_seconds()
                
                # 根据策略判断是否恢复
                should_recover = False
                
                if self.strategy == FallbackStrategy.IMMEDIATE:
                    # 立即降级策略：固定时间后恢复
                    should_recover = degradation_duration >= self.degradation_duration
                
                elif self.strategy == FallbackStrategy.THRESHOLD:
                    # 阈值降级策略：达到成功阈值后恢复
                    should_recover = self._ai_successes >= self.recovery_threshold
                
                elif self.strategy == FallbackStrategy.GRADUAL:
                    # 渐进降级策略：逐渐降低失败阈值
                    threshold = max(1, self.ai_failure_threshold - (degradation_duration // 60))
                    should_recover = self._ai_failures < threshold
                
                elif self.strategy == FallbackStrategy.ADAPTIVE:
                    # 自适应策略：基于历史性能动态调整
                    recent_failures = self._get_recent_failure_count()
                    should_recover = recent_failures == 0 and degradation_duration >= 60
                
                if should_recover:
                    await self._change_state(FallbackState.RECOVERY)
            
            # 检查状态持续时间
            self._stats["state_duration"] = (current_time - self._state_start_time).total_seconds()
    
    def _get_recent_failure_count(self, window_minutes: int = 5) -> int:
        """获取最近的失败次数"""
        # 这里可以实现基于时间窗口的失败计数
        # 为了简化，这里直接返回累计失败数
        return self._ai_failures
    
    async def _change_state(self, new_state: FallbackState):
        """改变状态"""
        if self._state == new_state:
            return
        
        old_state = self._state
        self._state = new_state
        
        # 更新状态开始时间
        self._state_start_time = datetime.now()
        
        # 更新状态统计
        self._stats["current_state"] = new_state.value
        self._stats["state_duration"] = 0.0
        
        # 执行状态变化回调
        if self.on_state_change:
            try:
                self.on_state_change(old_state, new_state)
            except Exception as e:
                self.logger.error(f"状态变化回调执行失败: {str(e)}")
        
        # 处理状态变化
        if new_state == FallbackState.DEGRADED:
            self._fallback_activations += 1
            self._stats["fallback_activations"] += 1
            self._degradation_start_time = datetime.now()
            
            if self.on_fallback_activated:
                try:
                    self.on_fallback_activated()
                except Exception as e:
                    self.logger.error(f"降级激活回调执行失败: {str(e)}")
            
            self.logger.warning(f"AI服务降级激活，已切换到规则引擎")
        
        elif new_state == FallbackState.RECOVERY:
            # 计算降级持续时间
            if self._degradation_start_time:
                degradation_duration = (datetime.now() - self._degradation_start_time).total_seconds()
                self._stats["total_fallback_time"] += degradation_duration
                self._stats["max_fallback_duration"] = max(
                    self._stats["max_fallback_duration"], degradation_duration
                )
                self._stats["avg_fallback_time"] = (
                    self._stats["total_fallback_time"] / self._fallback_activations
                )
                self._stats["last_fallback_time"] = datetime.now().isoformat()
            
            if self.on_fallback_recovered:
                try:
                    self.on_fallback_recovered()
                except Exception as e:
                    self.logger.error(f"降级恢复回调执行失败: {str(e)}")
            
            self.logger.info("AI服务降级恢复，已切换回AI分类")
    
    async def record_ai_request(self, success: bool, duration: float = 0.0):
        """记录AI请求结果"""
        async with self._lock:
            self._stats["total_ai_requests"] += 1
            
            if success:
                self._stats["successful_ai_requests"] += 1
                self._ai_successes += 1
                self._ai_failures = 0  # 重置连续失败计数
                self._stats["consecutive_ai_failures"] = 0
                self._stats["consecutive_ai_successes"] += 1
                self._last_success_time = datetime.now()
            else:
                self._stats["failed_ai_requests"] += 1
                self._ai_failures += 1
                self._ai_successes = 0  # 重置连续成功计数
                self._stats["consecutive_ai_successes"] = 0
                self._stats["consecutive_ai_failures"] += 1
                self._last_failure_time = datetime.now()
            
            # 检查是否需要降级
            if self._state == FallbackState.NORMAL:
                should_degrade = False
                
                if self.strategy == FallbackStrategy.IMMEDIATE:
                    should_degrade = True  # 立即降级
                
                elif self.strategy == FallbackStrategy.THRESHOLD:
                    should_degrade = self._ai_failures >= self.ai_failure_threshold
                
                elif self.strategy == FallbackStrategy.GRADUAL:
                    should_degrade = self._ai_failures >= max(1, self.ai_failure_threshold // 2)
                
                elif self.strategy == FallbackStrategy.ADAPTIVE:
                    recent_failures = self._get_recent_failure_count()
                    should_degrade = recent_failures >= 2
            
                if should_degrade:
                    await self._change_state(FallbackState.DEGRADED)
    
    def should_use_fallback(self) -> bool:
        """检查是否应该使用降级策略"""
        return self._state == FallbackState.DEGRADED
    
    def is_ai_available(self) -> bool:
        """检查AI服务是否可用"""
        # 如果在降级状态，AI服务不可用
        if self._state == FallbackState.DEGRADED:
            return False
        
        # 其他情况下，基于连续失败次数判断
        return self._stats["consecutive_ai_failures"] < self.ai_failure_threshold
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        stats["current_state"] = self._state.value
        
        # 计算成功率
        if stats["total_ai_requests"] > 0:
            stats["ai_success_rate"] = (
                stats["successful_ai_requests"] / stats["total_ai_requests"] * 100
            )
        else:
            stats["ai_success_rate"] = 0.0
        
        # 计算降级激活率
        if stats["total_ai_requests"] > 0:
            stats["fallback_activation_rate"] = (
                stats["fallback_activations"] / stats["total_ai_requests"] * 100
            )
        else:
            stats["fallback_activation_rate"] = 0.0
        
        return stats
    
    def reset_stats(self):
        """重置统计信息"""
        self._ai_failures = 0
        self._ai_successes = 0
        self._fallback_activations = 0
        self._last_failure_time = None
        self._last_success_time = None
        self._degradation_start_time = None
        
        self._stats = {
            "total_ai_requests": 0,
            "successful_ai_requests": 0,
            "failed_ai_requests": 0,
            "fallback_activations": 0,
            "total_fallback_time": 0.0,
            "avg_fallback_duration": 0.0,
            "max_fallback_duration": 0.0,
            "last_fallback_time": None,
            "fallback_success_rate": 0.0,
            "current_state": self._state.value,
            "state_duration": 0.0,
            "consecutive_ai_failures": 0,
            "consecutive_ai_successes": 0
        }
        
        self.logger.info("降级管理器统计已重置")


class AdaptiveAIClassifier:
    """自适应AI分类器，集成了降级策略"""
    
    def __init__(
        self,
        ai_classifier: Any,
        rule_classifier: Any,
        fallback_manager: Optional[FallbackManager] = None,
        fallback_strategy: FallbackStrategy = FallbackStrategy.THRESHOLD,
        enable_monitoring: bool = True
    ):
        """
        初始化自适应AI分类器
        
        Args:
            ai_classifier: AI分类器实例
            rule_classifier: 规则分类器实例
            fallback_manager: 降级管理器实例，如果为None则创建默认实例
            fallback_strategy: 降级策略
            enable_monitoring: 是否启用监控
        """
        self.ai_classifier = ai_classifier
        self.rule_classifier = rule_classifier
        self.fallback_manager = fallback_manager or FallbackManager(strategy=fallback_strategy)
        self.enable_monitoring = enable_monitoring
        
        self.logger = logging.getLogger(__name__)
        
        # 统计信息
        self._stats = {
            "total_classifications": 0,
            "ai_classifications": 0,
            "fallback_classifications": 0,
            "failed_classifications": 0,
            "avg_ai_response_time": 0.0,
            "avg_fallback_response_time": 0.0,
            "ai_success_rate": 0.0,
            "fallback_success_rate": 0.0
        }
        
        # 响应时间跟踪
        self._ai_response_times = []
        self._fallback_response_times = []
        
        # 启动监控
        if self.enable_monitoring:
            asyncio.create_task(self.fallback_manager.start_monitoring())
    
    async def classify(
        self, 
        torrent_name: str, 
        categories: Dict[str, CategoryConfig]
    ) -> str:
        """分类种子名称"""
        start_time = datetime.now()
        self._stats["total_classifications"] += 1
        
        try:
            # 检查是否应该使用降级策略
            if self.fallback_manager.should_use_fallback():
                self.logger.debug("使用规则引擎进行分类（降级模式）")
                return await self._classify_with_fallback(torrent_name, categories)
            
            # 尝试使用AI分类器
            try:
                result = await self._classify_with_ai(torrent_name, categories)
                self._stats["ai_classifications"] += 1
                
                # 记录AI请求成功
                await self.fallback_manager.record_ai_request(success=True)
                
                # 更新响应时间
                duration = (datetime.now() - start_time).total_seconds()
                self._ai_response_times.append(duration)
                if len(self._ai_response_times) > 100:
                    self._ai_response_times.pop(0)
                
                return result
                
            except Exception as e:
                self.logger.warning(f"AI分类失败: {str(e)}")
                
                # 记录AI请求失败
                duration = (datetime.now() - start_time).total_seconds()
                await self.fallback_manager.record_ai_request(success=False, duration=duration)
                
                # 降级到规则引擎
                self.logger.info("AI分类失败，降级到规则引擎")
                return await self._classify_with_fallback(torrent_name, categories)
        
        except Exception as e:
            self.logger.error(f"分类失败: {str(e)}")
            self._stats["failed_classifications"] += 1
            
            # 抛出降级异常
            raise AIFallbackError(f"分类失败: {str(e)}", details={"torrent_name": torrent_name})
        
        finally:
            # 更新统计信息
            self._update_stats()
    
    async def _classify_with_ai(self, torrent_name: str, categories: Dict[str, CategoryConfig]) -> str:
        """使用AI分类器进行分类"""
        if hasattr(self.ai_classifier, 'classify_with_cache'):
            return await self.ai_classifier.classify_with_cache(torrent_name, categories)
        elif hasattr(self.ai_classifier, 'classify'):
            return await self.ai_classifier.classify(torrent_name, categories)
        else:
            raise AIFallbackError("AI分类器不支持classify方法")
    
    async def _classify_with_fallback(self, torrent_name: str, categories: Dict[str, CategoryConfig]) -> str:
        """使用规则引擎进行分类"""
        self._stats["fallback_classifications"] += 1
        
        start_time = datetime.now()
        
        try:
            # 使用规则分类器
            if hasattr(self.rule_classifier, '_rule_based_classify'):
                result = self.rule_classifier._rule_based_classify(torrent_name, categories)
            elif hasattr(self.rule_classifier, 'classify'):
                result = await self.rule_classifier.classify(torrent_name, categories)
            else:
                raise AIFallbackError("规则分类器不支持分类方法")
            
            # 更新响应时间
            duration = (datetime.now() - start_time).total_seconds()
            self._fallback_response_times.append(duration)
            if len(self._fallback_response_times) > 100:
                self._fallback_response_times.pop(0)
            
            return result
            
        except Exception as e:
            self.logger.error(f"规则引擎分类失败: {str(e)}")
            raise AIFallbackError(f"规则引擎分类失败: {str(e)}", details={"torrent_name": torrent_name})
    
    def _update_stats(self):
        """更新统计信息"""
        # 计算平均响应时间
        if self._ai_response_times:
            self._stats["avg_ai_response_time"] = sum(self._ai_response_times) / len(self._ai_response_times)
        
        if self._fallback_response_times:
            self._stats["avg_fallback_response_time"] = sum(self._fallback_response_times) / len(self._fallback_response_times)
        
        # 计算成功率
        ai_stats = self.fallback_manager.get_stats()
        if ai_stats["total_ai_requests"] > 0:
            self._stats["ai_success_rate"] = ai_stats["ai_success_rate"]
        
        self._stats["fallback_success_rate"] = (
            (self._stats["fallback_classifications"] - self._stats["failed_classifications"]) / 
            max(1, self._stats["fallback_classifications"]) * 100
        )
    
    def get_fallback_stats(self) -> Dict[str, Any]:
        """获取降级统计信息"""
        fallback_stats = self.fallback_manager.get_stats()
        classifier_stats = self._stats.copy()
        
        return {
            "fallback_manager": fallback_stats,
            "classifier": classifier_stats,
            "ai_classifier_available": self.fallback_manager.is_ai_available(),
            "using_fallback": self.fallback_manager.should_use_fallback()
        }
    
    async def force_fallback(self):
        """强制启用降级模式"""
        await self.fallback_manager._change_state(FallbackState.DEGRADED)
        self.logger.warning("强制启用降级模式")
    
    async def force_recovery(self):
        """强制恢复AI模式"""
        await self.fallback_manager._change_state(FallbackState.RECOVERY)
        self.logger.info("强制恢复AI模式")
    
    async def cleanup(self):
        """清理资源"""
        if self.enable_monitoring:
            await self.fallback_manager.stop_monitoring()
        
        # 清理AI分类器资源
        if hasattr(self.ai_classifier, 'cleanup'):
            await self.ai_classifier.cleanup()
        
        # 清理规则分类器资源
        if hasattr(self.rule_classifier, 'cleanup'):
            await self.rule_classifier.cleanup()
        
        self.logger.info("自适应AI分类器资源已清理")


# 便利函数
def create_adaptive_classifier(
    ai_classifier: Any,
    rule_classifier: Any,
    strategy: FallbackStrategy = FallbackStrategy.THRESHOLD,
    **kwargs
) -> AdaptiveAIClassifier:
    """
    创建自适应AI分类器
    
    Args:
        ai_classifier: AI分类器实例
        rule_classifier: 规则分类器实例
        strategy: 降级策略
        **kwargs: 降级管理器额外参数
    
    Returns:
        AdaptiveAIClassifier: 自适应AI分类器实例
    """
    return AdaptiveAIClassifier(
        ai_classifier=ai_classifier,
        rule_classifier=rule_classifier,
        fallback_strategy=strategy,
        **kwargs
    )

