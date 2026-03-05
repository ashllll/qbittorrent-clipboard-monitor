"""内容分类器"""

import asyncio
import logging
from typing import Dict, Optional

import openai

from .config import Config
from .exceptions import AIError

logger = logging.getLogger(__name__)


class ContentClassifier:
    """内容分类器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.ai_config = config.ai
        self.client: Optional[openai.OpenAI] = None
        
        if self.ai_config.enabled and self.ai_config.api_key:
            self.client = openai.OpenAI(api_key=self.ai_config.api_key, base_url=self.ai_config.base_url)
    
    async def classify(self, name: str) -> str:
        """分类内容"""
        if not name:
            return "other"
        
        # 规则匹配
        rule_result = self._rule_classify(name)
        if rule_result:
            return rule_result
        
        # AI分类
        if self.client:
            try:
                return await self._ai_classify(name)
            except Exception as e:
                logger.warning(f"AI分类失败: {e}")
        
        return "other"
    
    def _rule_classify(self, name: str) -> Optional[str]:
        """规则分类"""
        name_lower = name.lower()
        for cat_name, cat_config in self.config.categories.items():
            if cat_name == "other":
                continue
            for keyword in cat_config.keywords:
                if keyword.lower() in name_lower:
                    return cat_name
        return None
    
    async def _ai_classify(self, name: str) -> str:
        """AI分类"""
        def _call():
            return self.client.chat.completions.create(
                model=self.ai_config.model,
                messages=[
                    {"role": "system", "content": "你是一个种子分类助手，只返回分类名称。"},
                    {"role": "user", "content": f"分类: {name}\n可选: {', '.join(self.config.categories.keys())}"},
                ],
                temperature=0.3,
                max_tokens=20,
            )
        
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(loop.run_in_executor(None, _call), timeout=self.ai_config.timeout)
        result = response.choices[0].message.content.strip().lower()
        
        for cat in self.config.categories:
            if cat in result:
                return cat
        return "other"


AIClassifier = ContentClassifier  # 兼容旧名
