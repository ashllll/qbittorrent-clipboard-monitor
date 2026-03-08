"""本地 AI 分类器插件

使用本地运行的 AI 模型（如 Ollama）进行内容分类。
"""

import json
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from ..base import ClassifierPlugin, PluginMetadata, PluginType, ClassificationResult

logger = logging.getLogger(__name__)


class LocalAIClassifier(ClassifierPlugin):
    """本地 AI 分类器插件
    
    通过调用本地运行的 AI 服务（如 Ollama、LocalAI 等）进行内容分类。
    相比云端 API，具有隐私性好、无需网络、响应快等优点。
    
    配置项:
        - base_url: AI 服务地址，默认 http://localhost:11434
        - model: 模型名称，默认 llama2
        - timeout: 请求超时时间（秒），默认 60
        - categories: 可用分类列表
        - prompt_template: 自定义提示词模板
        - temperature: 生成温度，默认 0.3
        - fallback_enabled: 失败时是否使用规则分类，默认 True
    
    Example:
        >>> plugin = LocalAIClassifier()
        >>> plugin.configure({
        ...     "base_url": "http://localhost:11434",
        ...     "model": "llama2",
        ...     "categories": ["movies", "tv", "anime", "music", "software"]
        ... })
        >>> result = await plugin.classify("The.Matrix.1999.1080p.BluRay.x264")
    """
    
    # 默认分类列表
    DEFAULT_CATEGORIES = [
        "movies", "tv", "anime", "music", 
        "software", "games", "books", "other"
    ]
    
    # 默认提示词模板
    DEFAULT_PROMPT = """You are a content classifier. Analyze the following torrent name and classify it into exactly one of these categories: {categories}.

Torrent name: "{name}"

Respond with ONLY the category name in lowercase, nothing else. If unsure, respond with "other".

Category:"""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="local_ai_classifier",
            version="1.0.0",
            description="使用本地 AI 模型进行内容分类",
            author="qBittorrent Monitor",
            plugin_type=PluginType.CLASSIFIER,
            config_schema={
                "base_url": {
                    "type": "string",
                    "required": False,
                    "description": "AI 服务地址"
                },
                "model": {
                    "type": "string",
                    "required": False,
                    "description": "模型名称"
                },
                "timeout": {
                    "type": "integer",
                    "required": False,
                    "description": "请求超时时间（秒）"
                },
                "categories": {
                    "type": "list",
                    "required": False,
                    "description": "可用分类列表"
                },
                "prompt_template": {
                    "type": "string",
                    "required": False,
                    "description": "自定义提示词模板"
                },
                "temperature": {
                    "type": "integer",
                    "required": False,
                    "description": "生成温度"
                },
                "fallback_enabled": {
                    "type": "boolean",
                    "required": False,
                    "description": "失败时是否使用规则分类"
                }
            }
        )
    
    def __init__(self):
        super().__init__()
        self._session: Optional[aiohttp.ClientSession] = None
        self._rule_keywords: Dict[str, List[str]] = {}
    
    async def initialize(self) -> bool:
        """初始化分类器"""
        try:
            timeout = aiohttp.ClientTimeout(
                total=self._config.get("timeout", 60)
            )
            self._session = aiohttp.ClientSession(timeout=timeout)
            
            # 初始化规则关键词（作为备用）
            self._init_rule_keywords()
            
            # 测试连接
            if await self._test_connection():
                logger.info("LocalAIClassifier 初始化成功")
                return True
            else:
                logger.warning("本地 AI 服务连接失败，将使用备用分类")
                return True  # 仍然返回 True，因为可以使用备用分类
                
        except Exception as e:
            logger.error(f"LocalAIClassifier 初始化失败: {e}")
            return False
    
    async def shutdown(self) -> None:
        """关闭分类器"""
        if self._session:
            await self._session.close()
            self._session = None
            logger.debug("LocalAIClassifier 已关闭")
    
    async def classify(self, name: str, **kwargs) -> ClassificationResult:
        """分类内容
        
        Args:
            name: 内容名称
            **kwargs: 额外参数
            
        Returns:
            分类结果
        """
        if not name or not name.strip():
            return ClassificationResult(
                category="other",
                confidence=0.0,
                method="local_ai_fallback"
            )
        
        name = name.strip()
        
        # 尝试使用本地 AI
        try:
            result = await self._classify_with_ai(name)
            if result:
                return result
        except Exception as e:
            logger.warning(f"本地 AI 分类失败: {e}")
        
        # 使用备用规则分类
        if self._config.get("fallback_enabled", True):
            return self._rule_classify(name)
        
        return ClassificationResult(
            category="other",
            confidence=0.3,
            method="local_ai_failed"
        )
    
    async def _classify_with_ai(self, name: str) -> Optional[ClassificationResult]:
        """使用本地 AI 进行分类
        
        Args:
            name: 内容名称
            
        Returns:
            分类结果或 None
        """
        if not self._session:
            return None
        
        base_url = self._config.get("base_url", "http://localhost:11434")
        model = self._config.get("model", "llama2")
        categories = self._config.get("categories", self.DEFAULT_CATEGORIES)
        prompt_template = self._config.get("prompt_template", self.DEFAULT_PROMPT)
        temperature = self._config.get("temperature", 0.3)
        
        # 构建提示词
        prompt = prompt_template.format(
            categories=", ".join(categories),
            name=name
        )
        
        # 构建请求
        # 支持 Ollama API 格式
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        try:
            async with self._session.post(
                f"{base_url}/api/generate",
                json=payload
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.warning(f"本地 AI 服务返回错误: {response.status} - {text}")
                    return None
                
                result = await response.json()
                response_text = result.get("response", "").strip().lower()
                
                # 解析结果
                category = self._parse_category(response_text, categories)
                confidence = self._calculate_confidence(response_text, category)
                
                return ClassificationResult(
                    category=category,
                    confidence=confidence,
                    method="local_ai",
                    metadata={
                        "model": model,
                        "raw_response": response_text[:100]
                    }
                )
                
        except aiohttp.ClientError as e:
            logger.warning(f"本地 AI 服务请求失败: {e}")
            return None
    
    def _parse_category(self, response: str, valid_categories: List[str]) -> str:
        """从响应中解析分类
        
        Args:
            response: AI 响应文本
            valid_categories: 有效分类列表
            
        Returns:
            分类名称
        """
        # 清理响应
        response = response.strip().lower()
        
        # 直接匹配
        for cat in valid_categories:
            if cat.lower() == response or cat.lower() in response.split():
                return cat
        
        # 模糊匹配
        for cat in valid_categories:
            if cat.lower() in response:
                return cat
        
        return "other"
    
    def _calculate_confidence(self, response: str, category: str) -> float:
        """计算分类置信度
        
        Args:
            response: AI 响应文本
            category: 解析出的分类
            
        Returns:
            置信度 0.0-1.0
        """
        response = response.strip().lower()
        
        # 如果响应很简洁，置信度较高
        if response == category:
            return 0.9
        
        # 如果响应包含分类但不是全部，置信度中等
        if category in response and len(response.split()) <= 3:
            return 0.75
        
        # 其他情况置信度较低
        return 0.6
    
    def _rule_classify(self, name: str) -> ClassificationResult:
        """规则分类（备用方法）
        
        Args:
            name: 内容名称
            
        Returns:
            分类结果
        """
        name_lower = name.lower()
        best_match = None
        best_score = 0
        
        for category, keywords in self._rule_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in name_lower:
                    score += len(keyword)
            
            if score > best_score:
                best_score = score
                best_match = category
        
        if best_match:
            confidence = min(0.5 + best_score / 100, 0.7)
            return ClassificationResult(
                category=best_match,
                confidence=confidence,
                method="local_ai_fallback_rule"
            )
        
        return ClassificationResult(
            category="other",
            confidence=0.3,
            method="local_ai_fallback"
        )
    
    def _init_rule_keywords(self) -> None:
        """初始化规则关键词"""
        self._rule_keywords = {
            "movies": [
                "1080p", "720p", "4K", "UHD", "BluRay", "WEB-DL",
                "x264", "x265", "HEVC", "H.264", "H.265",
                "电影", "Movie", "Film"
            ],
            "tv": [
                "S01", "S02", "E01", "E02", "Season", "Episode",
                "电视剧", "Series", "TV Show"
            ],
            "anime": [
                "动画", "Anime", "BD", "OVA", "OAD",
                "字幕组", "[GM-Team]"
            ],
            "music": [
                "FLAC", "MP3", "AAC", "Album", "EP", "Single",
                "音乐", "Music", "OST", "Soundtrack"
            ],
            "software": [
                "软件", "Software", "Portable", "Repack",
                "Crack", "Keygen", "Windows", "macOS", "Linux"
            ],
            "games": [
                "Game", "Games", "CODEX", "PLAZA", "SKIDROW",
                "REPACK", "DLC", "Update"
            ],
            "books": [
                "PDF", "EPUB", "MOBI", "Ebook", "电子书",
                "Book", "Novel"
            ]
        }
    
    async def _test_connection(self) -> bool:
        """测试与本地 AI 服务的连接
        
        Returns:
            连接是否成功
        """
        if not self._session:
            return False
        
        base_url = self._config.get("base_url", "http://localhost:11434")
        
        try:
            async with self._session.get(
                f"{base_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return response.status == 200
        except Exception:
            return False
    
    def get_available_models(self) -> List[str]:
        """获取可用的模型列表（需要已启用）
        
        Returns:
            模型名称列表
        """
        # 异步方法需要在同步上下文中调用
        # 这里返回配置中的模型作为备选
        return [self._config.get("model", "llama2")]
