"""
Ruflo AI 集成模块

提供基于 Ruflo (原 Claude Flow) 的增强型 AI 分类功能:
1. 增强型 AI 分类器 - 多 Agent 协作分析
2. Swarm 批量处理 - 并行处理多个任务
3. 自学习优化 - 持续改进分类准确率

安装 Ruflo:
    npm install -g claude-flow
    npx ruflo@latest init --wizard

文档: https://github.com/ruvnet/ruflo
"""

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .config import DeepSeekConfig, CategoryConfig
from .resilience import LRUCache, RateLimiter
from .exceptions import AIError, ClassificationError


class RufloConfig:
    """Ruflo 配置"""
    
    def __init__(
        self,
        enabled: bool = False,
        ruflo_path: str = "npx ruflo@latest",
        default_agent: str = "classifier",
        swarm_topology: str = "mesh",
        max_agents: int = 5,
        timeout: int = 30,
        cache_ttl_hours: int = 24,
        cache_max_size: int = 1000,
        learning_enabled: bool = True,
        feedback_storage_path: str = ".ruflo_feedback"
    ):
        self.enabled = enabled
        self.ruflo_path = ruflo_path
        self.default_agent = default_agent
        self.swarm_topology = swarm_topology
        self.max_agents = max_agents
        self.timeout = timeout
        self.cache_ttl_hours = cache_ttl_hours
        self.cache_max_size = cache_max_size
        self.learning_enabled = learning_enabled
        self.feedback_storage_path = feedback_storage_path


class RufloAgentResult:
    """Ruflo Agent 执行结果"""
    
    def __init__(
        self,
        success: bool,
        result: str = "",
        agent_name: str = "",
        execution_time: float = 0.0,
        error: str = ""
    ):
        self.success = success
        self.result = result
        self.agent_name = agent_name
        self.execution_time = execution_time
        self.error = error
        self.timestamp = datetime.now()


class FeedbackEntry:
    """反馈条目 - 用于自学习"""
    
    def __init__(
        self,
        torrent_name: str,
        predicted_category: str,
        actual_category: str,
        correction_made: bool,
        timestamp: datetime = None
    ):
        self.torrent_name = torrent_name
        self.predicted_category = predicted_category
        self.actual_category = actual_category
        self.correction_made = correction_made
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "torrent_name": self.torrent_name,
            "predicted_category": self.predicted_category,
            "actual_category": self.actual_category,
            "correction_made": self.correction_made,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "FeedbackEntry":
        return cls(
            torrent_name=data["torrent_name"],
            predicted_category=data["predicted_category"],
            actual_category=data["actual_category"],
            correction_made=data["correction_made"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


class RufloClassifier:
    """
    基于 Ruflo 的增强型 AI 分类器
    
    特性:
    - 多 Agent 协作分析
    - 结果缓存
    - Swarm 批量处理支持
    - 自学习优化
    """
    
    def __init__(self, config: RufloConfig):
        self.config = config
        self.logger = logging.getLogger('RufloClassifier')
        
        # 缓存系统
        self._cache = LRUCache(
            max_size=config.cache_max_size,
            ttl_seconds=int(config.cache_ttl_hours * 3600)
        )
        
        # 速率限制
        self._rate_limiter = RateLimiter(rate=60, period=60)
        
        # 反馈存储
        self._feedback: List[FeedbackEntry] = []
        self._load_feedback()
        
        # 学习模式
        self._learned_patterns: Dict[str, str] = {}
        self._load_learned_patterns()
        
        # 统计
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'successful_classifications': 0,
            'failed_classifications': 0,
            'corrections': 0,
            'avg_response_time': 0.0
        }
    
    def _get_cache_key(self, torrent_name: str) -> str:
        """生成缓存键"""
        content = f"{torrent_name}:{json.dumps(sorted(self._learned_patterns.items()))}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _is_available(self) -> bool:
        """检查 Ruflo 是否可用"""
        if not self.config.enabled:
            return False
        
        try:
            # 检查 Ruflo 是否安装
            result = subprocess.run(
                [self.config.ruflo_path, "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def classify(
        self,
        torrent_name: str,
        categories: Dict[str, CategoryConfig]
    ) -> str:
        """
        使用 Ruflo Agent 分类 torrent
        
        流程:
        1. 检查缓存
        2. 检查学习模式
        3. 调用 Ruflo Agent
        4. 存储结果
        """
        self._stats['total_requests'] += 1
        
        # 1. 检查缓存
        cache_key = self._get_cache_key(torrent_name)
        cached_result = self._cache.get(cache_key)
        if cached_result:
            self._stats['cache_hits'] += 1
            self.logger.debug(f"缓存命中: {torrent_name}")
            return cached_result
        
        self._stats['cache_misses'] += 1
        
        # 2. 检查学习模式 (自学习优化)
        learned_result = self._check_learned_patterns(torrent_name, categories)
        if learned_result:
            self._cache.set(cache_key, learned_result)
            return learned_result
        
        # 3. 调用 Ruflo Agent
        if not self._is_available():
            raise AIError("Ruflo 不可用，请确保已安装: npm install -g claude-flow")
        
        try:
            result = await self._run_agent(torrent_name, categories)
            
            if result.success:
                self._stats['successful_classifications'] += 1
                self._cache.set(cache_key, result.result)
                return result.result
            else:
                self._stats['failed_classifications'] += 1
                raise AIError(f"Ruflo 分类失败: {result.error}")
                
        except Exception as e:
            self._stats['failed_classifications'] += 1
            self.logger.error(f"Ruflo 分类异常: {str(e)}")
            raise
    
    async def _run_agent(
        self,
        torrent_name: str,
        categories: Dict[str, CategoryConfig]
    ) -> RufloAgentResult:
        """运行 Ruflo Agent 进行分类"""
        
        # 构建分类列表
        category_list = ", ".join(categories.keys())
        
        # 构建提示
        prompt = f"""你是一个 torrent 分类助手。根据给定的 torrent 名称，分类到最合适的类别。

Torrent 名称: {torrent_name}

可选类别: {category_list}

请只返回类别名称，不要其他内容。"""
        
        start_time = time.time()
        
        try:
            # 调用 Ruflo
            process = await asyncio.create_subprocess_exec(
                *self.config.ruflo_path.split(),
                "run",
                "--agent", self.config.default_agent,
                "--input", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return RufloAgentResult(
                    success=False,
                    error="执行超时",
                    agent_name=self.config.default_agent
                )
            
            execution_time = time.time() - start_time
            self._stats['avg_response_time'] = (
                (self._stats['avg_response_time'] * (self._stats['total_requests'] - 1) + execution_time)
                / self._stats['total_requests']
            )
            
            if process.returncode == 0:
                result = stdout.decode().strip()
                # 提取分类结果
                category = self._extract_category(result, categories)
                return RufloAgentResult(
                    success=True,
                    result=category,
                    agent_name=self.config.default_agent,
                    execution_time=execution_time
                )
            else:
                error = stderr.decode().strip() if stderr else "未知错误"
                return RufloAgentResult(
                    success=False,
                    error=error,
                    agent_name=self.config.default_agent,
                    execution_time=execution_time
                )
                
        except FileNotFoundError:
            return RufloAgentResult(
                success=False,
                error="Ruflo 未安装",
                agent_name=self.config.default_agent
            )
        except Exception as e:
            return RufloAgentResult(
                success=False,
                error=str(e),
                agent_name=self.config.default_agent
            )
    
    def _extract_category(
        self,
        result: str,
        categories: Dict[str, CategoryConfig]
    ) -> str:
        """从 Agent 结果中提取分类"""
        result_lower = result.lower().strip()
        
        # 直接匹配
        for category in categories.keys():
            if category.lower() == result_lower:
                return category
        
        # 关键词匹配
        for category, config in categories.items():
            keywords = config.keywords or []
            for keyword in keywords:
                if keyword.lower() in result_lower:
                    return category
        
        # 默认返回 other
        return "other"
    
    def _check_learned_patterns(
        self,
        torrent_name: str,
        categories: Dict[str, CategoryConfig]
    ) -> Optional[str]:
        """检查学习到的模式"""
        if not self.config.learning_enabled:
            return None
        
        torrent_lower = torrent_name.lower()
        
        # 精确匹配
        if torrent_lower in self._learned_patterns:
            category = self._learned_patterns[torrent_lower]
            if category in categories:
                return category
        
        # 模糊匹配 (关键词)
        for category, pattern in self._learned_patterns.items():
            if pattern in torrent_lower:
                if category in categories:
                    return category
        
        return None
    
    # =========================================================================
    # 自学习功能
    # =========================================================================
    
    def record_correction(
        self,
        torrent_name: str,
        predicted_category: str,
        actual_category: str
    ):
        """记录分类纠正 - 用于自学习"""
        
        entry = FeedbackEntry(
            torrent_name=torrent_name,
            predicted_category=predicted_category,
            actual_category=actual_category,
            correction_made=True
        )
        
        self._feedback.append(entry)
        self._stats['corrections'] += 1
        
        # 更新学习模式
        self._learned_patterns[torrent_name.lower()] = actual_category
        
        # 保存
        self._save_feedback()
        self._save_learned_patterns()
        
        self.logger.info(f"记录纠正: {torrent_name} - {predicted_category} -> {actual_category}")
    
    def _load_feedback(self):
        """加载反馈数据"""
        if not self.config.learning_enabled:
            return
        
        feedback_file = Path(self.config.feedback_storage_path)
        if feedback_file.exists():
            try:
                with open(feedback_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._feedback = [FeedbackEntry.from_dict(e) for e in data]
            except Exception as e:
                self.logger.warning(f"加载反馈失败: {e}")
    
    def _save_feedback(self):
        """保存反馈数据"""
        if not self.config.learning_enabled:
            return
        
        try:
            with open(self.config.feedback_storage_path, 'w', encoding='utf-8') as f:
                json.dump([e.to_dict() for e in self._self_feedback], f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存反馈失败: {e}")
    
    def _load_learned_patterns(self):
        """加载学习到的模式"""
        if not self.config.learning_enabled:
            return
        
        patterns_file = Path(f"{self.config.feedback_storage_path}_patterns.json")
        if patterns_file.exists():
            try:
                with open(patterns_file, 'r', encoding='utf-8') as f:
                    self._learned_patterns = json.load(f)
            except Exception as e:
                self.logger.warning(f"加载模式失败: {e}")
    
    def _save_learned_patterns(self):
        """保存学习到的模式"""
        if not self.config.learning_enabled:
            return
        
        try:
            patterns_file = Path(f"{self.config.feedback_storage_path}_patterns.json")
            with open(patterns_file, 'w', encoding='utf-8') as f:
                json.dump(self._learned_patterns, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存模式失败: {e}")
    
    def get_learning_stats(self) -> Dict:
        """获取学习统计"""
        total_corrections = len(self._feedback)
        accuracy = 0
        
        if total_corrections > 0:
            correct = sum(1 for e in self._feedback if not e.correction_made)
            accuracy = correct / total_corrections * 100
        
        return {
            'total_feedback': total_corrections,
            'learned_patterns': len(self._learned_patterns),
            'accuracy_percent': accuracy,
            'recent_corrections': len([e for e in self._feedback[-10:]])
        }
    
    # =========================================================================
    # Swarm 批量处理
    # =========================================================================
    
    async def classify_batch(
        self,
        torrent_names: List[str],
        categories: Dict[str, CategoryConfig]
    ) -> Dict[str, str]:
        """
        使用 Swarm 批量分类
        
        适用场景:
        - 批量 URL 爬取
        - 多个种子同时处理
        """
        
        if not self._is_available():
            # 降级到普通分类
            results = {}
            for name in torrent_names:
                try:
                    results[name] = await self.classify(name, categories)
                except Exception as e:
                    self.logger.error(f"分类失败 {name}: {e}")
                    results[name] = "other"
            return results
        
        # Swarm 模式分类
        self.logger.info(f"使用 Swarm 批量分类: {len(torrent_names)} 个任务")
        
        # 并行执行 (使用信号量控制并发)
        semaphore = asyncio.Semaphore(self.config.max_agents)
        
        async def classify_single(name: str) -> tuple:
            async with semaphore:
                try:
                    category = await self.classify(name, categories)
                    return name, category
                except Exception as e:
                    self.logger.error(f"分类失败 {name}: {e}")
                    return name, "other"
        
        tasks = [classify_single(name) for name in torrent_names]
        results_list = await asyncio.gather(*tasks)
        
        return dict(results_list)
    
    # =========================================================================
    # 统计与状态
    # =========================================================================
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        cache_total = self._stats['cache_hits'] + self._stats['cache_misses']
        cache_hit_rate = (
            self._stats['cache_hits'] / cache_total * 100 
            if cache_total > 0 else 0
        )
        
        return {
            **self._stats,
            'cache_hit_rate_percent': round(cache_hit_rate, 2),
            'ruflo_available': self._is_available(),
            'learning_stats': self.get_learning_stats()
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self.logger.info("缓存已清空")
    
    def reset_learning(self):
        """重置学习数据"""
        self._feedback.clear()
        self._learned_patterns.clear()
        self._save_feedback()
        self._save_learned_patterns()
        self.logger.info("学习数据已重置")


# =========================================================================
# 便捷函数
# =========================================================================

def create_ruflo_classifier(
    enabled: bool = False,
    ruflo_path: str = "npx ruflo@latest",
    **kwargs
) -> RufloClassifier:
    """创建 Ruflo 分类器"""
    config = RufloConfig(enabled=enabled, ruflo_path=ruflo_path, **kwargs)
    return RufloClassifier(config)
