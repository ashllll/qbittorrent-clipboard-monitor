"""
ai 子包 - AI分类器模块

提供模块化的AI分类功能
"""

# 延迟导入以避免循环依赖
def __getattr__(name):
    if name == "BaseAIClassifier":
        from .base import BaseAIClassifier
        return BaseAIClassifier
    elif name == "DeepSeekClassifier":
        from .deepseek import DeepSeekClassifier
        return DeepSeekClassifier
    elif name == "OpenAIClassifier":
        from .openai import OpenAIClassifier
        return OpenAIClassifier
    elif name == "AIClassifierFactory":
        from .factory import AIClassifierFactory
        return AIClassifierFactory
    elif name == "AIClassifier":
        from .classifier import AIClassifier
        return AIClassifier
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
