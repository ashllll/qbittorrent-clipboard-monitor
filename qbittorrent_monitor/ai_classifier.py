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
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
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
from .exceptions import (
    AIError, AIApiError, AICreditError, AIRateLimitError, 
    ClassificationError
)


class BaseAIClassifier(ABC):
    """AI分类器抽象基类"""
    
    def __init__(self, config: Any):
        self.config = config
        self.logger = logging.getLogger(f'AIClassifier.{self.__class__.__name__}')
    
    @abstractmethod
    async def classify(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str:
        """分类种子名称"""
        pass


class DeepSeekClassifier(BaseAIClassifier):
    """DeepSeek AI分类器实现"""
    
    def __init__(self, config: DeepSeekConfig):
        super().__init__(config)
        self.client: Optional[OpenAI] = None
        
        if config.api_key:
            try:
                self.client = OpenAI(
                    api_key=config.api_key,
                    base_url=config.base_url,
                    timeout=config.timeout
                )
                self.logger.info(f"DeepSeek客户端初始化成功: {config.model}")
            except Exception as e:
                self.logger.error(f"DeepSeek客户端初始化失败: {str(e)}")
                self.client = None
        else:
            self.logger.warning("DeepSeek API Key未配置，AI分类器将不可用")
    
    async def classify(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str:
        """使用DeepSeek AI进行分类"""
        if not self.client:
            self.logger.warning("AI分类器未初始化，使用规则引擎")
            return self._rule_based_classify(torrent_name, categories)
        
        if not torrent_name:
            self.logger.warning("种子名称为空，返回默认分类")
            return "other"
        
        try:
            result = await self._classify_with_retry(torrent_name, categories)
            if result in categories:
                return result
            else:
                self.logger.warning(f"AI返回无效分类 '{result}'，使用规则引擎")
                return self._rule_based_classify(torrent_name, categories)
                
        except (AICreditError, AIRateLimitError) as e:
            self.logger.error(f"AI服务限制: {str(e)}，使用规则引擎")
            return self._rule_based_classify(torrent_name, categories)
        except Exception as e:
            self.logger.error(f"AI分类失败: {str(e)}，使用规则引擎")
            return self._rule_based_classify(torrent_name, categories)
    
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
            
            if completion.choices and completion.choices[0].message:
                raw_category = completion.choices[0].message.content
                if raw_category:
                    category = raw_category.strip().lower()
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
        
        # 构建关键词提示
        category_keywords = "\n".join([
            f"- {name} 关键词: {', '.join(cfg.keywords + (cfg.foreign_keywords or []))}" 
            for name, cfg in categories.items() 
            if cfg.keywords or cfg.foreign_keywords
        ])
        
        # 构建Few-shot示例
        few_shot_examples = ""
        if self.config.few_shot_examples:
            examples = []
            for example in self.config.few_shot_examples:
                examples.append(f"示例: '{example['torrent_name']}' -> {example['category']}")
            few_shot_examples = "参考示例:\n" + "\n".join(examples) + "\n"
        
        return self.config.prompt_template.format(
            torrent_name=torrent_name,
            category_descriptions=category_descriptions,
            category_keywords=category_keywords,
            few_shot_examples=few_shot_examples
        )
    
    def _rule_based_classify(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str:
        """增强的规则引擎分类"""
        if not torrent_name:
            return "other"
        
        self.logger.info(f"使用规则引擎分类: {torrent_name}")
        name_lower = torrent_name.lower()
        
        # 预定义的正则表达式模式
        patterns = {
            'tv_episode': re.compile(r's\d+e\d+|season\s+\d+|episode\s+\d+|\d+x\d+', re.IGNORECASE),
            'movie_year': re.compile(r'\.(19|20)\d{2}\.|\((19|20)\d{2}\)|\[(19|20)\d{2}\]'),
            'movie_quality': re.compile(r'1080p|720p|2160p|4k|uhd|bluray|web-?dl|hdtv', re.IGNORECASE),
            'anime_fansub': re.compile(r'\[.*\].*\d+.*\[.*\]', re.IGNORECASE)  # [字幕组]标题[质量]格式
        }
        
        category_scores = {}
        
        # 基于模式的加分
        if patterns['tv_episode'].search(name_lower):
            category_scores['tv'] = category_scores.get('tv', 0) + 8
            
        if patterns['movie_year'].search(name_lower) or patterns['movie_quality'].search(name_lower):
            category_scores['movies'] = category_scores.get('movies', 0) + 6
            
        if patterns['anime_fansub'].search(torrent_name):
            category_scores['anime'] = category_scores.get('anime', 0) + 7
        
        # 基于分类规则的评分
        for cat_name, cat_config in categories.items():
            score = 0
            matched_items = []
            
            # 处理增强规则
            if cat_config.rules:
                for rule in cat_config.rules:
                    rule_score = self._apply_rule(rule, torrent_name, name_lower)
                    if rule_score > 0:
                        score += rule_score
                        matched_items.append(f"{rule.get('type', 'unknown')}(+{rule_score})")
            
            # 处理传统关键词
            for keyword in cat_config.keywords:
                if keyword.lower() in name_lower:
                    score += 2
                    matched_items.append(f"{keyword}(+2)")
            
            # 处理外语关键词
            if cat_config.foreign_keywords:
                for keyword in cat_config.foreign_keywords:
                    if keyword.lower() in name_lower:
                        score += 3
                        matched_items.append(f"{keyword}(+3)")
            
            # 应用优先级权重
            if score > 0:
                weighted_score = score * (1 + cat_config.priority * 0.1)
                category_scores[cat_name] = category_scores.get(cat_name, 0) + weighted_score
                
                if matched_items:
                    self.logger.info(f"{cat_name} 匹配: {', '.join(matched_items)}, 权重分数: {weighted_score:.1f}")
        
        # 选择最高分的分类
        if category_scores:
            best_category = max(category_scores.items(), key=lambda x: x[1])[0]
            scores_display = ", ".join([f"{k}: {v:.1f}" for k, v in category_scores.items()])
            self.logger.info(f"规则引擎分类结果: {best_category} (所有分数: {scores_display})")
            return best_category
        
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


class OpenAIClassifier(BaseAIClassifier):
    """OpenAI分类器实现（可扩展）"""
    
    def __init__(self, config: Any):
        super().__init__(config)
        # 实现OpenAI接口
        self.logger.info("OpenAI分类器初始化（待实现）")
    
    async def classify(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str:
        """OpenAI分类实现"""
        # TODO: 实现OpenAI分类逻辑
        self.logger.warning("OpenAI分类器尚未实现，返回other")
        return "other"


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