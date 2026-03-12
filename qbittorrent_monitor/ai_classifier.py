"""AI 分类器模块 - 重构版

支持 DeepSeek、OpenAI 等 OpenAI SDK 兼容的 AI 服务。
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, Union

from openai import OpenAI, APIError, RateLimitError, Timeout

from .circuit_breaker import CircuitBreaker, AI_CIRCUIT_CONFIG
from .exceptions import AIError
from .interfaces.classifier import ClassificationResult, IClassifier
from .rule_based_classifier import RuleBasedClassifier
from .utils.connection_pool import ConnectionPoolManager

logger = logging.getLogger(__name__)


class BaseAIClassifier(IClassifier, ABC):
    """AI 分类器基类"""

    @abstractmethod
    async def classify(self, name: str) -> ClassificationResult:
        """分类内容"""
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        """清理资源"""
        ...


class OpenAICompatibleClassifier(BaseAIClassifier, ABC):
    """OpenAI SDK 兼容的分类器基类"""

    CONFIDENCE_MAP: Dict[str, float] = {
        "movies": 0.90, "tv": 0.90, "anime": 0.88, "music": 0.92,
        "software": 0.88, "games": 0.90, "books": 0.92, "other": 0.50,
    }

    def __init__(
        self,
        config: Union[Any, Any],
        pool_size: int = 3,
        timeout: float = 30.0,
    ):
        # 提取配置
        if hasattr(config, 'ai'):  # Config object
            ai_cfg = config.ai
            self._api_key = ai_cfg.api_key
            self._model = ai_cfg.model
            self._base_url = ai_cfg.base_url
            self._timeout = ai_cfg.timeout
            self._max_retries = ai_cfg.max_retries
        else:  # Direct config object
            self._api_key = getattr(config, "api_key", "")
            self._model = getattr(config, "model", "deepseek-chat")
            self._base_url = getattr(config, "base_url", "https://api.deepseek.com/v1")
            self._timeout = getattr(config, "timeout", 30)
            self._max_retries = getattr(config, "max_retries", 3)

        self._request_timeout = timeout
        self._rule_classifier = RuleBasedClassifier()
        self._circuit_breaker = CircuitBreaker(
            config=AI_CIRCUIT_CONFIG,
            name=self.__class__.__name__,
        )
        self._pool: Optional[ConnectionPoolManager[OpenAI]] = None
        self._initialized = False

    def _create_client(self) -> OpenAI:
        """创建 OpenAI 客户端"""
        if not self._api_key:
            raise AIError("API 密钥未配置")
        return OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
            max_retries=self._max_retries,
        )

    def initialize(self) -> None:
        """初始化分类器"""
        if self._initialized:
            return
        try:
            self._pool = ConnectionPoolManager(
                factory=self._create_client,
                pool_size=3,
            )
            self._pool.initialize()
            self._initialized = True
            logger.debug(f"{self.__class__.__name__} 初始化完成")
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise AIError(f"分类器初始化失败: {e}") from e

    @abstractmethod
    def _execute_api_call(self, client: OpenAI, prompt: str) -> str:
        """执行 API 调用"""
        ...

    @abstractmethod
    def _build_prompt(self, torrent_name: str, categories: Dict[str, Any]) -> str:
        """构建提示词"""
        ...

    async def _call_api(self, prompt: str) -> Optional[str]:
        """使用断路器调用 API"""
        if not self._initialized or not self._pool:
            return None
        client = self._pool.get_next()
        if not client:
            return None

        async def _api_call():
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, lambda: self._execute_api_call(client, prompt)
            )

        try:
            return await self._circuit_breaker.call(_api_call)
        except Exception as e:
            logger.warning(f"API 调用失败: {e}")
            return None

    def _parse_category(self, response: str) -> str:
        """解析 API 响应获取分类"""
        response_lower = response.lower().strip()
        for cat in self.CONFIDENCE_MAP.keys():
            if cat in response_lower:
                return cat
        logger.warning(f"无法识别的分类响应: {response}")
        return "other"

    async def classify(self, name: str) -> ClassificationResult:
        """分类内容"""
        if not name or not name.strip():
            return ClassificationResult(category="other", confidence=0.0, method="fallback")

        if not self._initialized:
            self.initialize()

        # 规则分类
        rule_result = self._rule_classifier.classify_with_confidence(name)
        if rule_result and rule_result[1] >= 0.7:
            return ClassificationResult(
                category=rule_result[0], confidence=rule_result[1], method="rule"
            )

        # AI 分类
        if not self._pool:
            return self._fallback(rule_result)

        prompt = self._build_prompt(name, {"categories": list(self.CONFIDENCE_MAP.keys())})

        try:
            response = await asyncio.wait_for(
                self._call_api(prompt), timeout=self._request_timeout
            )
            if response:
                category = self._parse_category(response)
                confidence = self.CONFIDENCE_MAP.get(category, 0.5)
                if rule_result and rule_result[0] == category:
                    confidence = min(confidence + 0.1, 1.0)
                return ClassificationResult(
                    category=category, confidence=confidence, method="ai"
                )
        except asyncio.TimeoutError:
            logger.warning(f"AI 分类超时: {name[:50]}...")
        except Exception as e:
            logger.warning(f"AI 分类失败: {e}")

        return self._fallback(rule_result)

    def _fallback(self, rule_result: Optional[Tuple[str, float]]) -> ClassificationResult:
        """降级处理"""
        if rule_result:
            return ClassificationResult(
                category=rule_result[0], confidence=rule_result[1], method="rule"
            )
        return ClassificationResult(category="other", confidence=0.3, method="fallback")

    async def cleanup(self) -> None:
        """清理资源"""
        if self._pool:
            await self._pool.cleanup()
            self._pool = None
        self._initialized = False

    def __del__(self):
        """析构函数"""
        if self._initialized and self._pool:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.cleanup())
                else:
                    asyncio.run(self.cleanup())
            except Exception:
                pass

    def get_stats(self) -> Dict[str, Any]:
        """获取分类器统计信息"""
        return {
            "initialized": self._initialized,
            "pool": self._pool.get_stats() if self._pool else None,
        }


class DeepSeekClassifier(OpenAICompatibleClassifier):
    """DeepSeek AI 分类器"""

    REASONING_MODELS = {"deepseek-reasoner"}

    def __init__(self, config: Union[Any, Any], pool_size: int = 3, timeout: float = 60.0):
        super().__init__(config, pool_size, timeout)
        self._is_reasoning_model = self._model in self.REASONING_MODELS

    def _create_client(self) -> OpenAI:
        """创建 DeepSeek 客户端"""
        if not self._base_url or "openai.com" in self._base_url:
            self._base_url = "https://api.deepseek.com/v1"
        return super()._create_client()

    def _execute_api_call(self, client: OpenAI, prompt: str) -> str:
        """执行 DeepSeek API 调用"""
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a content classifier. Analyze the torrent name "
                            "and classify it into exactly one category. "
                            "Respond with only the category name."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=50,
                stream=False,
            )
            if response.choices:
                content = response.choices[0].message.content
                if self._is_reasoning_model:
                    reasoning = getattr(response.choices[0].message, "reasoning_content", None)
                    if reasoning:
                        logger.debug(f"推理内容: {reasoning[:100]}...")
                return content.strip() if content else ""
            return ""
        except (APIError, RateLimitError, Timeout) as e:
            logger.warning(f"DeepSeek API 错误: {e}")
            raise

    def _build_prompt(self, torrent_name: str, categories: Dict[str, Any]) -> str:
        """构建 DeepSeek 提示词"""
        cat_list = categories.get("categories", [])
        return (
            f"Torrent name: '{torrent_name}'\n\n"
            f"Available categories: {', '.join(cat_list)}\n\n"
            f"Classify this torrent into exactly one category. "
            f"Respond with only the category name, nothing else."
        )


class OpenAIClassifier(OpenAICompatibleClassifier):
    """OpenAI GPT 分类器"""

    def _create_client(self) -> OpenAI:
        """创建 OpenAI 客户端"""
        if not self._base_url:
            self._base_url = "https://api.openai.com/v1"
        return super()._create_client()

    def _execute_api_call(self, client: OpenAI, prompt: str) -> str:
        """执行 OpenAI API 调用"""
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a torrent content classifier. "
                            "Analyze the name and classify into exactly one category. "
                            "Respond with only the category name."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=30,
            )
            if response.choices:
                content = response.choices[0].message.content
                return content.strip() if content else ""
            return ""
        except (APIError, RateLimitError, Timeout) as e:
            logger.warning(f"OpenAI API 错误: {e}")
            raise

    def _build_prompt(self, torrent_name: str, categories: Dict[str, Any]) -> str:
        """构建 OpenAI 提示词"""
        cat_list = categories.get("categories", [])
        return (
            f"Classify this torrent: '{torrent_name}'\n"
            f"Categories: {', '.join(cat_list)}\n"
            f"Respond with only the category name."
        )


# 向后兼容的别名
AIClassifier = DeepSeekClassifier


class AIClassifierFactory:
    """AI 分类器工厂"""

    @staticmethod
    def create(
        config: Union[Any, Any],
        classifier_type: Optional[str] = None,
    ) -> OpenAICompatibleClassifier:
        """创建分类器"""
        model = getattr(config, "model", "") or getattr(getattr(config, "ai", None), "model", "")
        classifier_type = (classifier_type or "auto").lower()

        if classifier_type == "auto":
            classifier_type = "deepseek" if "deepseek" in model.lower() else "openai"

        if classifier_type == "deepseek":
            return DeepSeekClassifier(config)
        elif classifier_type in ("openai", "gpt"):
            return OpenAIClassifier(config)
        raise ValueError(f"不支持的分类器类型: {classifier_type}")

    @staticmethod
    def create_deepseek(config: Union[Any, Any]) -> DeepSeekClassifier:
        """创建 DeepSeek 分类器"""
        return DeepSeekClassifier(config)

    @staticmethod
    def create_openai(config: Union[Any, Any]) -> OpenAIClassifier:
        """创建 OpenAI 分类器"""
        return OpenAIClassifier(config)


__all__ = [
    "BaseAIClassifier",
    "OpenAICompatibleClassifier",
    "DeepSeekClassifier",
    "OpenAIClassifier",
    "AIClassifierFactory",
    "AIClassifier",
]
