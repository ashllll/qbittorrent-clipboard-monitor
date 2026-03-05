"""简化版AI内容分类器"""

import logging
import re
from typing import Dict, Optional

import openai

from .config import Config, CategoryConfig
from .exceptions import AIError, ClassificationError


logger = logging.getLogger(__name__)


class ContentClassifier:
    """内容分类器 - 支持AI和规则分类"""
    
    def __init__(self, config: Config):
        self.config = config
        self.ai_config = config.ai
        self.client: Optional[openai.OpenAI] = None
        
        if self.ai_config.enabled and self.ai_config.api_key:
            self.client = openai.OpenAI(
                api_key=self.ai_config.api_key,
                base_url=self.ai_config.base_url,
            )
    
    async def classify(self, name: str) -> str:
        """分类内容，返回分类名称"""
        if not name:
            return "other"
        
        # 先尝试规则匹配
        rule_result = self._rule_classify(name)
        if rule_result:
            return rule_result
        
        # 如果AI可用，使用AI分类
        if self.client:
            try:
                return await self._ai_classify(name)
            except Exception as e:
                logger.warning(f"AI分类失败，使用默认分类: {e}")
        
        return "other"
    
    def _rule_classify(self, name: str) -> Optional[str]:
        """基于规则分类"""
        name_lower = name.lower()
        
        for cat_name, cat_config in self.config.categories.items():
            if cat_name == "other":
                continue
            for keyword in cat_config.keywords:
                if keyword.lower() in name_lower:
                    return cat_name
        return None
    
    async def _ai_classify(self, name: str) -> str:
        """使用AI分类"""
        import asyncio
        
        categories = ", ".join(self.config.categories.keys())
        
        prompt = f"""请分析以下种子名称，选择最合适的分类。

种子名称: {name}

可选分类: {categories}

请只返回分类名称，不要其他解释。"""

        def _call_api():
            return self.client.chat.completions.create(
                model=self.ai_config.model,
                messages=[
                    {"role": "system", "content": "你是一个种子分类助手。请根据种子名称选择最合适的分类。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=50,
            )
        
        try:
            # 在线程池中运行同步API调用
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, _call_api),
                timeout=self.ai_config.timeout,
            )
            
            result = response.choices[0].message.content.strip().lower()
            
            # 验证返回的分类是否有效
            if result in self.config.categories:
                return result
            
            # 尝试模糊匹配
            for cat in self.config.categories:
                if cat in result:
                    return cat
            
            return "other"
            
        except asyncio.TimeoutError:
            raise AIError("AI分类超时")
        except Exception as e:
            raise AIError(f"AI分类失败: {e}")


# 兼容旧版API
class AIClassifier(ContentClassifier):
    """兼容旧版API的别名"""
    pass
