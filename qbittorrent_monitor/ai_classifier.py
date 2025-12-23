"""
增强的AI分类器模块

支持：
- 多种AI模型（DeepSeek, OpenAI, Claude等）
- 指数退避重试机制
- Few-shot学习
- 健壮的错误处理
"""

import asyncio
import logging
import re
import time
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote_plus
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from openai import OpenAI
import openai

from .config import DeepSeekConfig, CategoryConfig
from .resilience import RateLimiter, CircuitBreaker, LRUCache
from .exceptions import (
    AIError, AIApiError, AICreditError, AIRateLimitError, 
    ClassificationError
)


class BaseAIClassifier(ABC):
    """AI分类器抽象基类 - 高性能版"""
    
    def __init__(self, config: Any):
        self.config = config
        self.logger = logging.getLogger(f'AIClassifier.{self.__class__.__name__}')
        
        # 缓存系统
        self._cache_ttl = getattr(config, 'cache_ttl_hours', 24)
        self._cache = LRUCache(
            max_size=getattr(config, 'cache_max_size', 1000),
            ttl_seconds=int(self._cache_ttl * 3600),
        )
        
        # 清理状态标志
        self._is_cleaned_up = False
        
        # 性能监控
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'ai_requests': 0,
            'rule_fallbacks': 0,
            'total_time': 0.0,
            'avg_response_time': 0.0,
            'error_count': 0,
            'last_error_time': None
        }
        
        # 线程池用于异步操作
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="AIClassifier")
        
        # 速率限制
        self._max_requests_per_minute = getattr(config, 'max_requests_per_minute', 60)
        self._rate_limiters: Dict[str, RateLimiter] = {}
    
    def _get_cache_key(self, torrent_name: str, categories_hash: str) -> str:
        """生成缓存键"""
        content = f"{torrent_name}:{categories_hash}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_categories_hash(self, categories: Dict[str, CategoryConfig]) -> str:
        """生成分类配置的哈希值"""
        # 简化的哈希，基于分类名称和关键词
        content = "|".join(sorted([
            f"{name}:{','.join(sorted(cfg.keywords or []))}"
            for name, cfg in categories.items()
        ]))
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """从缓存获取结果"""
        result = self._cache.get(cache_key)
        if result is not None:
            self._stats['cache_hits'] += 1
            return result
        self._stats['cache_misses'] += 1
        return None
    
    def _put_to_cache(self, cache_key: str, result: str):
        """存储到缓存"""
        self._cache.set(cache_key, result)
    
    def _check_rate_limit(self, provider: str) -> bool:
        """检查速率限制"""
        limiter = self._rate_limiters.get(provider)
        if limiter is None:
            limiter = RateLimiter(self._max_requests_per_minute)
            self._rate_limiters[provider] = limiter
        return limiter.allow()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        stats = self._stats.copy()
        stats['cache_size'] = len(self._cache)
        stats['cache_hit_rate'] = (
            self._stats['cache_hits'] / max(self._stats['total_requests'], 1) * 100
        )
        return stats
    
    @abstractmethod
    async def classify(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str:
        """分类种子名称"""
        pass
    
    async def classify_with_cache(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str:
        """带缓存的分类方法"""
        start_time = time.time()
        self._stats['total_requests'] += 1
        
        try:
            if not torrent_name:
                return "other"
            
            # 检查缓存
            categories_hash = self._get_categories_hash(categories)
            cache_key = self._get_cache_key(torrent_name, categories_hash)
            
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                self.logger.debug(f"缓存命中: {torrent_name[:30]}... -> {cached_result}")
                return cached_result
            
            # 缓存未命中，进行分类
            result = await self.classify(torrent_name, categories)
            
            # 存储到缓存
            self._put_to_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            self._stats['error_count'] += 1
            self._stats['last_error_time'] = datetime.now()
            self.logger.error(f"分类失败: {str(e)}")
            raise
        finally:
            # 更新性能统计
            process_time = time.time() - start_time
            self._stats['total_time'] += process_time
            self._stats['avg_response_time'] = (
                self._stats['total_time'] / self._stats['total_requests']
            )
    
    async def cleanup(self):
        """异步清理所有资源"""
        if self._is_cleaned_up:
            return
            
        self.logger.info("开始清理AIClassifier资源...")
        
        try:
            # 关闭线程池
            if hasattr(self, '_executor') and self._executor:
                self._executor.shutdown(wait=True)
                self.logger.debug("线程池已关闭")
            
            # 清理缓存
            if hasattr(self, '_cache'):
                self._cache.clear()
                self.logger.debug("缓存已清理")
            
            self._is_cleaned_up = True
            self.logger.info("AIClassifier资源清理完成")
            
        except Exception as e:
            self.logger.error(f"清理AIClassifier资源时出错: {str(e)}")
    
    def __del__(self):
        """析构函数，确保资源被清理"""
        try:
            # 同步清理关键资源
            if hasattr(self, '_executor') and self._executor:
                self._executor.shutdown(wait=False)
            
            # 清理缓存
            if hasattr(self, '_cache'):
                self._cache.clear()
                
        except Exception:
            pass  # 忽略析构时的异常


class DeepSeekClassifier(BaseAIClassifier):
    """DeepSeek AI分类器实现 - 高性能版"""
    
    def __init__(self, config: DeepSeekConfig):
        super().__init__(config)
        self.client: Optional[OpenAI] = None
        self._client_pool = []
        self._pool_size = getattr(config, 'connection_pool_size', 3)
        self._current_client_index = 0
        
        # 清理状态标志
        self._is_cleaned_up = False
        
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=getattr(config, 'failure_threshold', 5),
            recovery_timeout=getattr(config, 'recovery_timeout', 300),
            on_state_change=lambda state: self.logger.info(f"断路器状态 -> {state}"),
        )
        
        if config.api_key:
            try:
                # 创建连接池
                for i in range(self._pool_size):
                    client = OpenAI(
                        api_key=config.api_key,
                        base_url=config.base_url,
                        timeout=getattr(config, 'timeout', 30),
                        max_retries=0  # 我们自己处理重试
                    )
                    self._client_pool.append(client)
                
                self.client = self._client_pool[0] if self._client_pool else None
                self.logger.info(f"DeepSeek客户端池初始化成功: {config.model} (池大小: {self._pool_size})")
            except Exception as e:
                self.logger.error(f"DeepSeek客户端初始化失败: {str(e)}")
                self.client = None
        else:
            self.logger.warning("DeepSeek API Key未配置，AI分类器将不可用")
    
    def _get_next_client(self) -> Optional[OpenAI]:
        """获取下一个可用的客户端（负载均衡）"""
        if not self._client_pool:
            return None
        
        client = self._client_pool[self._current_client_index]
        self._current_client_index = (self._current_client_index + 1) % len(self._client_pool)
        return client
    
    def _check_circuit_breaker(self) -> bool:
        """检查断路器状态"""
        return self._circuit_breaker.allow()
    
    def _record_success(self):
        """记录成功请求"""
        self._circuit_breaker.record_success()
    
    def _record_failure(self):
        """记录失败请求"""
        self._circuit_breaker.record_failure()
    
    def _is_available(self) -> bool:
        """检查服务是否可用"""
        return (self.client is not None and 
                self._check_circuit_breaker() and 
                self._check_rate_limit('deepseek'))
    
    async def classify(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str:
        """使用DeepSeek AI进行分类 - 高性能版"""
        if not torrent_name:
            self.logger.warning("种子名称为空，返回默认分类")
            return "other"
        
        # 检查服务可用性
        if not self._is_available():
            self.logger.warning("AI服务不可用，使用规则引擎")
            self._stats['rule_fallbacks'] += 1
            return self._rule_based_classify(torrent_name, categories)
        
        start_time = time.time()
        
        try:
            # 使用连接池和重试机制进行分类
            result = await self._classify_with_retry(torrent_name, categories)
            
            # 记录成功
            self._record_success()
            self._stats['ai_requests'] += 1
            
            if result in categories:
                self.logger.info(f"AI分类成功: {torrent_name[:50]}... -> {result}")
                return result
            else:
                self.logger.warning(f"AI返回无效分类 '{result}'，使用规则引擎")
                self._stats['rule_fallbacks'] += 1
                return self._rule_based_classify(torrent_name, categories)
                
        except (AICreditError, AIRateLimitError) as e:
            self._record_failure()
            self.logger.error(f"AI服务限制: {str(e)}，使用规则引擎")
            self._stats['rule_fallbacks'] += 1
            return self._rule_based_classify(torrent_name, categories)
        except Exception as e:
            self._record_failure()
            self.logger.error(f"AI分类失败: {str(e)}，使用规则引擎")
            self._stats['rule_fallbacks'] += 1
            return self._rule_based_classify(torrent_name, categories)
        finally:
            # 更新响应时间统计
            response_time = time.time() - start_time
            if hasattr(self, '_response_times'):
                self._response_times.append(response_time)
                # 只保留最近100次的响应时间
                if len(self._response_times) > 100:
                    self._response_times.pop(0)
            else:
                self._response_times = [response_time]
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.3, max=3),
        retry=retry_if_exception_type((AIApiError, AIRateLimitError)),
        before_sleep=before_sleep_log(logging.getLogger('AIClassifier.Retry'), logging.INFO)
    )
    async def _classify_with_retry(self, torrent_name: str, categories: Dict[str, CategoryConfig]) -> str:
        """带重试机制的分类方法"""
        try:
            prompt = self._build_prompt(torrent_name, categories)

            def _stream_completion():
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个专业的种子分类助手，擅长根据文件名进行准确分类。请只返回最合适的分类名称，不要包含任何其他解释或文字。"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    stream=True,
                    timeout=self.config.timeout
                )

                reasoning_chunks = []
                content_chunks = []
                for chunk in response:
                    delta = chunk.choices[0].delta
                    reasoning_piece = getattr(delta, 'reasoning_content', None)
                    if reasoning_piece:
                        reasoning_chunks.append(reasoning_piece)
                    content_piece = getattr(delta, 'content', None)
                    if content_piece:
                        content_chunks.append(content_piece)
                return ''.join(reasoning_chunks), ''.join(content_chunks)

            try:
                reasoning_text, final_text = await asyncio.to_thread(_stream_completion)
            except TypeError:
                completion = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.config.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个专业的种子分类助手，擅长根据文件名进行准确分类。请只返回最合适的分类名称，不要包含任何其他解释或文字。"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    timeout=self.config.timeout
                )
                reasoning_text = ""
                final_text = completion.choices[0].message.content if completion.choices and completion.choices[0].message else ""

            if reasoning_text:
                self.logger.debug(f"AI思考轨迹: {reasoning_text[:200]}")

            raw_category = (final_text or reasoning_text).strip()
            if raw_category:
                category = raw_category.lower()
                self.logger.info(f"AI分类结果: {torrent_name[:50]}... -> {category}")
                return category

            raise AIApiError("AI返回空响应")
            
        except openai.RateLimitError as e:
            # 解析重试时间
            retry_after = getattr(e, 'retry_after', 300)
            raise AIRateLimitError(f"API限速: {str(e)}", retry_after)
        except openai.APIStatusError as e:
            if e.status_code == 429:
                raise AIRateLimitError(f"API限速: {str(e)}")
            elif e.status_code == 402:
                raise AICreditError(f"API额度不足: {str(e)}")
            elif e.status_code >= 500:
                raise AIApiError(f"服务器错误: {str(e)}")
            else:
                raise AIApiError(f"API错误: {str(e)}")
        except openai.APIConnectionError as e:
            raise AIApiError(f"连接错误: {str(e)}")
        except Exception as e:
            raise AIApiError(f"未知错误: {str(e)}")
    
    def _build_prompt(self, torrent_name: str, categories: Dict[str, CategoryConfig]) -> str:
        """构建AI提示词"""
        # 构建分类描述
        category_descriptions = "\n".join([
            f"- {name}: {cfg.description}" 
            for name, cfg in categories.items()
        ])
        
        # 构建关键词提示（每个分类最多3个关键词）
        keyword_lines = []
        for name, cfg in categories.items():
            keywords = (cfg.keywords or [])[:3]
            foreign = (cfg.foreign_keywords or [])[:1]
            merged = [k for k in (keywords + foreign) if k]
            if merged:
                keyword_lines.append(f"- {name}: {', '.join(merged)}")
        category_keywords = "\n".join(keyword_lines)
        
        # 构建Few-shot示例（仅保留前2个）
        few_shot_examples = ""
        if self.config.few_shot_examples:
            examples = []
            for example in self.config.few_shot_examples[:2]:
                examples.append(f"示例: '{example['torrent_name']}' -> {example['category']}")
            few_shot_examples = "参考示例:\n" + "\n".join(examples) + "\n"
        
        return self.config.prompt_template.format(
            torrent_name=torrent_name,
            category_descriptions=category_descriptions,
            category_keywords=category_keywords,
            few_shot_examples=few_shot_examples
        )
    
    def _make_api_call_with_client(self, client: OpenAI, prompt: str) -> Optional[str]:
        """使用指定客户端调用DeepSeek API"""
        try:
            response = client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的种子文件分类助手。请根据种子名称判断其类型，只返回分类名称，不要其他内容。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.1,
                timeout=getattr(self.config, 'timeout', 30)
            )
            
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content
            
        except Exception as e:
            error_msg = str(e).lower()
            if "insufficient_quota" in error_msg or "quota" in error_msg:
                raise AICreditError(f"DeepSeek API额度不足: {str(e)}")
            elif "rate_limit" in error_msg or "too many requests" in error_msg:
                raise AIRateLimitError(f"DeepSeek API请求频率限制: {str(e)}")
            elif "timeout" in error_msg:
                raise AIAPIError(f"DeepSeek API请求超时: {str(e)}")
            else:
                raise AIAPIError(f"DeepSeek API调用失败: {str(e)}")
        
        return None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING)
    )
    def _make_api_call(self, prompt: str) -> Optional[str]:
        """调用DeepSeek API（向后兼容）"""
        if not self.client:
            raise AIAPIError("DeepSeek客户端未初始化")
        return self._make_api_call_with_client(self.client, prompt)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        stats = super().get_stats().copy()
        
        # 添加DeepSeek特定统计
        if hasattr(self, '_response_times') and self._response_times:
            stats['avg_response_time'] = sum(self._response_times) / len(self._response_times)
            stats['max_response_time'] = max(self._response_times)
            stats['min_response_time'] = min(self._response_times)
        
        # 断路器状态
        stats['circuit_breaker_state'] = self._circuit_breaker.state
        stats['circuit_breaker_failures'] = self._circuit_breaker.failure_count
        
        # 连接池状态
        stats['connection_pool_size'] = len(self._client_pool)
        stats['current_client_index'] = self._current_client_index
        
        return stats
    
    def _rule_based_classify(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str:
        """增强的规则引擎分类"""
        if not torrent_name:
            return "other"

        normalized_name = torrent_name
        if torrent_name.lower().startswith("magnet:?"):
            try:
                query = parse_qs(urlparse(torrent_name).query)
                dn = query.get("dn")
                if dn:
                    normalized_name = unquote_plus(dn[0])
            except Exception:
                normalized_name = torrent_name

        name_lower = normalized_name.lower()
        tokens = [tok for tok in re.split(r"[\s._\-\[\]\(\)]+", name_lower) if tok]
        ext = Path(normalized_name).suffix.lower()

        heuristics = {
            "tv": {
                "regex": [r"s\d{1,2}e\d{1,3}", r"season\s+\d+", r"episode\s+\d+", r"\d+x\d+"],
                "keywords": ["hdtv", "web-dl", "complete", "miniseries", "hbo"],
            },
            "movies": {
                "regex": [r"(19|20)\d{2}", r"1080p|720p|2160p|4k|uhd", r"bluray|hdrip|brrip|remux"],
                "keywords": ["dvdrip", "webrip", "imax", "criterion", "camrip"],
            },
            "anime": {
                "regex": [r"\[[^\]]+\][^\[]+\[[^\]]+\]", r"\bfansub\b", r"\banime\b"],
                "keywords": ["bdrip", "jp", "zhsub", "bangumi", "ona", "tv tokyo"],
            },
            "adult": {
                "regex": [r"\b(jav|fc2|uncensored|18\+)\b"],
                "keywords": ["xxx", "porn", "brazzers", "realitykings", "x-art", "sapphic"],
            },
            "music": {
                "extensions": [".flac", ".mp3", ".aac", ".alac", ".wav"],
                "keywords": ["lossless", "320kbps", "discography", "album", "ep", "mtv"],
            },
            "games": {
                "regex": [r"fitgirl", r"repack", r"codex", r"skidrow"],
                "keywords": ["pc game", "switch", "ps5", "gog", "emu", "steam"],
                "extensions": [".iso", ".nsp", ".xci", ".pkg"],
            },
            "software": {
                "regex": [r"crack", r"patch", r"license"],
                "keywords": ["installer", "portable", "x64", "activation", "keygen"],
                "extensions": [".iso", ".dmg", ".exe", ".msi"],
            },
        }

        category_scores: Dict[str, float] = {}

        def add_score(cat: str, value: float):
            if value:
                category_scores[cat] = category_scores.get(cat, 0.0) + value

        for cat, rules in heuristics.items():
            for pattern in rules.get("regex", []):
                if re.search(pattern, name_lower):
                    add_score(cat, 5)
            for kw in rules.get("keywords", []):
                if kw in name_lower or kw in tokens:
                    add_score(cat, 3)
            if ext and ext in rules.get("extensions", []):
                add_score(cat, 4)

        for cat_name, cat_config in categories.items():
            score = 0
            if cat_config.rules:
                for rule in cat_config.rules:
                    score += self._apply_rule(rule, normalized_name, name_lower)
            for keyword in cat_config.keywords:
                if keyword.lower() in name_lower:
                    score += 2
            if cat_config.foreign_keywords:
                for keyword in cat_config.foreign_keywords:
                    if keyword.lower() in name_lower:
                        score += 3
            if score > 0:
                weighted = score * (1 + cat_config.priority * 0.05)
                add_score(cat_name, weighted)

        if category_scores:
            positive = {k: v for k, v in category_scores.items() if v > 0}
            if positive:
                return max(positive.items(), key=lambda x: x[1])[0]

        self.logger.info("规则引擎未找到匹配，返回 'other'")
        return "other"

    
    def _apply_rule(self, rule: Dict[str, Any], original_name: str, lower_name: str) -> int:
        """应用单个规则"""
        rule_type = rule.get('type', '')
        score = rule.get('score', 1)
        
        if rule_type == 'regex':
            pattern = rule.get('pattern', '')
            if pattern and re.search(pattern, original_name, re.IGNORECASE):
                return score
                
        elif rule_type == 'keyword':
            keywords = rule.get('keywords', [])
            for keyword in keywords:
                if keyword.lower() in lower_name:
                    return score
                    
        elif rule_type == 'exclude':
            # 排除规则：如果匹配则返回负分
            keywords = rule.get('keywords', [])
            for keyword in keywords:
                if keyword.lower() in lower_name:
                    return -score
                    
        elif rule_type == 'size_range':
            # 基于文件大小的规则（需要额外的文件大小信息）
            # 这里可以扩展支持基于种子大小的分类
            pass
            
        return 0
    
    async def cleanup(self):
        """清理DeepSeek分类器资源"""
        if self._is_cleaned_up:
            return
        
        self.logger.info("开始清理DeepSeek分类器资源...")
        
        try:
            # 关闭客户端连接池
            for client in self._client_pool:
                if hasattr(client, '_client') and hasattr(client._client, 'close'):
                    try:
                        await client._client.aclose()
                    except Exception as e:
                        self.logger.debug(f"关闭客户端连接时出错: {e}")
            
            # 清空连接池
            self._client_pool.clear()
            self.client = None
            
            # 调用父类清理方法
            await super().cleanup()
            
            self._is_cleaned_up = True
            self.logger.info("DeepSeek分类器资源清理完成")
            
        except Exception as e:
            self.logger.error(f"清理DeepSeek分类器资源时出错: {str(e)}")
    
    def __del__(self):
        """析构函数，确保资源被清理"""
        try:
            # 同步清理关键资源
            self._client_pool.clear()
            self.client = None
        except Exception:
            pass  # 忽略析构时的异常


class OpenAIClassifier(BaseAIClassifier):
    """OpenAI分类器实现"""
    
    def __init__(self, config: Any):
        super().__init__(config)
        self.logger = logging.getLogger('OpenAIClassifier')
        
        # 连接池配置
        self.pool_size = getattr(config, 'pool_size', 3)
        self.clients = []
        
        # 初始化连接池
        for i in range(self.pool_size):
            try:
                client = OpenAI(
                    api_key=config.api_key,
                    base_url=getattr(config, 'base_url', 'https://api.openai.com/v1'),
                    timeout=getattr(config, 'timeout', 30)
                )
                self.clients.append(client)
                self.logger.debug(f"OpenAI客户端 {i+1} 初始化成功")
            except Exception as e:
                self.logger.error(f"OpenAI客户端 {i+1} 初始化失败: {e}")
        
        if not self.clients:
            raise AIError("所有OpenAI客户端初始化失败")
        
        self.current_client_index = 0
        
        # 熔断器配置
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=getattr(config, 'failure_threshold', 5),
            recovery_timeout=getattr(config, 'recovery_timeout', 60),
            on_state_change=self._on_cb_state_change,
        )
        
        # 性能统计
        self.openai_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'response_times': [],
            'circuit_breaker_trips': 0,
            'pool_rotations': 0
        }
        
        self.logger.info(f"OpenAI分类器初始化完成，连接池大小: {len(self.clients)}")
        
        # 清理状态标志
        self._is_cleaned_up = False
    
    def _get_next_client(self) -> Optional[OpenAI]:
        """获取下一个可用的客户端"""
        if not self.clients:
            return None
        
        client = self.clients[self.current_client_index]
        self.current_client_index = (self.current_client_index + 1) % len(self.clients)
        self.openai_stats['pool_rotations'] += 1
        return client
    
    def _on_cb_state_change(self, state: str):
        if state == 'open':
            self.openai_stats['circuit_breaker_trips'] += 1
            self.logger.warning("熔断器触发，进入打开状态")
        elif state == 'half_open':
            self.logger.info("熔断器进入半开状态")
        elif state == 'closed':
            self.logger.info("熔断器恢复到关闭状态")

    def _check_circuit_breaker(self) -> bool:
        """检查熔断器状态"""
        return self.circuit_breaker.allow()
    
    def _record_success(self):
        """记录成功请求"""
        self.circuit_breaker.record_success()
    
    def _record_failure(self):
        """记录失败请求"""
        self.circuit_breaker.record_failure()
    
    def _is_available(self) -> bool:
        """检查服务是否可用"""
        return self._check_circuit_breaker() and len(self.clients) > 0
    
    async def classify(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str:
        """OpenAI分类实现"""
        if not torrent_name or not torrent_name.strip():
            self.logger.warning("种子名称为空，返回默认分类")
            return "other"
        
        # 检查服务可用性
        if not self._is_available():
            self.logger.warning("OpenAI服务不可用，使用规则分类")
            return self._rule_based_classify(torrent_name, categories)
        
        # 检查速率限制
        if not self._check_rate_limit('openai'):
            self.logger.warning("OpenAI速率限制，使用规则分类")
            return self._rule_based_classify(torrent_name, categories)
        
        start_time = time.time()
        self.openai_stats['total_requests'] += 1
        
        try:
            # 使用重试机制进行分类
            result = await self._classify_with_retry(torrent_name, categories)
            
            # 记录成功
            response_time = time.time() - start_time
            self.openai_stats['response_times'].append(response_time)
            self.openai_stats['successful_requests'] += 1
            self._record_success()
            
            return result
            
        except Exception as e:
            # 记录失败
            self._stats['failed_requests'] += 1
            self.openai_stats['failed_requests'] += 1
            self._record_failure()
            
            self.logger.error(f"OpenAI分类失败: {e}，使用规则分类")
            return self._rule_based_classify(torrent_name, categories)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.3, max=3),
        retry=retry_if_exception_type((AIApiError, AIRateLimitError)),
        before_sleep=before_sleep_log(logging.getLogger('OpenAIClassifier.Retry'), logging.INFO)
    )
    async def _classify_with_retry(self, torrent_name: str, categories: Dict[str, CategoryConfig]) -> str:
        """带重试的分类方法 - 复用线程池"""
        try:
            # 复用父类的线程池，避免重复创建
            prompt = self._build_prompt(torrent_name, categories)
            client = self._get_next_client()
            
            # 使用线程池执行同步API调用
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                lambda: self._make_api_call_with_client(client, prompt)
            )
            
            if result and result.strip():
                return result.strip().lower()
            else:
                raise AIApiError("OpenAI返回空结果")
                
        except Exception as e:
            self.logger.error(f"OpenAI API调用失败: {e}")
            raise AIApiError(f"OpenAI分类失败: {e}")
    
    def _build_prompt(self, torrent_name: str, categories: Dict[str, CategoryConfig]) -> str:
        """构建分类提示词"""
        category_descriptions = []
        for name, config in categories.items():
            desc = f"- {name}: {config.description or '无描述'}"
            if config.keywords:
                desc += f" (关键词: {', '.join(config.keywords)})"
            category_descriptions.append(desc)
        
        prompt = f"""请根据种子文件名称对其进行分类。

可用分类：
{chr(10).join(category_descriptions)}
- other: 其他/未分类

种子名称: "{torrent_name}"

请仅返回最合适的分类名称（小写），不要包含任何解释或其他文本。"""
        
        return prompt
    
    def _make_api_call_with_client(self, client: OpenAI, prompt: str) -> Optional[str]:
        """使用指定客户端进行API调用"""
        if not client:
            raise AIApiError("没有可用的OpenAI客户端")
        
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "你是一个专业的种子文件分类助手。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.1,
                timeout=30
            )
            
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content
            else:
                raise AIApiError("OpenAI响应格式异常")
                
        except openai.APITimeoutError as e:
            raise AIApiError(f"OpenAI API超时: {e}")
        except openai.RateLimitError as e:
            raise AIRateLimitError(f"OpenAI速率限制: {e}")
        except openai.APIError as e:
            raise AIApiError(f"OpenAI API错误: {e}")
        except Exception as e:
            raise AIApiError(f"OpenAI调用异常: {e}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取OpenAI特定的性能统计"""
        base_stats = self.get_stats()
        
        openai_specific = {
            'openai_total_requests': self.openai_stats['total_requests'],
            'openai_successful_requests': self.openai_stats['successful_requests'],
            'openai_failed_requests': self.openai_stats['failed_requests'],
            'openai_success_rate': (
                self.openai_stats['successful_requests'] / max(1, self.openai_stats['total_requests'])
            ) * 100,
            'openai_avg_response_time': (
                sum(self.openai_stats['response_times']) / len(self.openai_stats['response_times'])
                if self.openai_stats['response_times'] else 0
            ),
            'openai_max_response_time': (
                max(self.openai_stats['response_times'])
                if self.openai_stats['response_times'] else 0
            ),
            'openai_min_response_time': (
                min(self.openai_stats['response_times'])
                if self.openai_stats['response_times'] else 0
            ),
            'circuit_breaker_state': self.circuit_breaker.state,
            'circuit_breaker_failures': self.circuit_breaker.failure_count,
            'circuit_breaker_trips': self.openai_stats['circuit_breaker_trips'],
            'connection_pool_size': len(self.clients),
            'pool_rotations': self.openai_stats['pool_rotations']
        }
        
        return {**base_stats, **openai_specific}
    
    async def cleanup(self):
        """清理OpenAI分类器资源"""
        if self._is_cleaned_up:
            return
        
        self.logger.info("开始清理OpenAI分类器资源...")
        
        try:
            # 关闭客户端连接池
            for client in self.clients:
                if hasattr(client, '_client') and hasattr(client._client, 'close'):
                    try:
                        await client._client.aclose()
                    except Exception as e:
                        self.logger.debug(f"关闭OpenAI客户端连接时出错: {e}")
            
            # 清理客户端连接池
            self.clients.clear()
            
            # 调用父类清理方法
            await super().cleanup()
            
            self._is_cleaned_up = True
            self.logger.info("OpenAI分类器资源清理完成")
            
        except Exception as e:
            self.logger.error(f"清理OpenAI分类器资源时出错: {str(e)}")
    
    def __del__(self):
        """析构函数，确保资源被清理"""
        try:
            # 同步清理关键资源
            self.clients.clear()
        except Exception:
            pass  # 忽略析构时的异常


class AIClassifierFactory:
    """AI分类器工厂类"""
    
    @staticmethod
    def create_classifier(provider: str, config: Any) -> BaseAIClassifier:
        """根据提供商创建对应的分类器"""
        if provider.lower() == 'deepseek':
            return DeepSeekClassifier(config)
        elif provider.lower() == 'openai':
            return OpenAIClassifier(config)
        else:
            raise ValueError(f"不支持的AI提供商: {provider}")


# 为了保持向后兼容性，保留原来的AIClassifier类
class AIClassifier(DeepSeekClassifier):
    """默认AI分类器（基于DeepSeek）"""
    
    def __init__(self, config: DeepSeekConfig):
        super().__init__(config)
        self.logger = logging.getLogger('AIClassifier')
