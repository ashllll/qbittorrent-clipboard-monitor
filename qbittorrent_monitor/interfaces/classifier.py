"""分类器接口定义"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from dataclasses import dataclass


@dataclass(frozen=True)
class ClassificationResult:
    """分类结果"""
    category: str
    confidence: float
    method: str


@runtime_checkable
class IClassifier(Protocol):
    """分类器接口"""
    
    async def classify(self, name: str) -> ClassificationResult:
        """分类内容
        
        Args:
            name: 内容名称
            
        Returns:
            分类结果
        """
        ...
