"""
分类管理器

处理种子分类的创建、更新和删除，包括：
- 创建分类
- 更新分类
- 删除分类
- 获取分类列表
- 路径映射
"""

import logging
from typing import Dict, Any, List, Optional
from ..config import CategoryConfig

logger = logging.getLogger(__name__)


class CategoryManager:
    """分类管理器"""

    def __init__(self, api_client):
        self.api_client = api_client
        self.logger = logging.getLogger('CategoryManager')

    async def get_existing_categories(self) -> Dict[str, Dict[str, Any]]:
        """获取现有分类"""
        try:
            status, categories = await self.api_client.get('torrents/categories')
            if status == 200:
                return categories if isinstance(categories, dict) else {}
            return {}
        except Exception as e:
            self.logger.error(f"获取分类列表失败: {e}")
            return {}

    async def ensure_categories(self, categories: Dict[str, CategoryConfig]) -> None:
        """确保所有分类存在"""
        try:
            existing = await self.get_existing_categories()

            for name, config in categories.items():
                if name not in existing:
                    # 分类不存在，创建它
                    save_path = config.save_path or self._map_save_path(name)
                    await self._create_category(name, save_path)
                    self.logger.info(f"创建分类: {name} -> {save_path}")
                else:
                    # 分类已存在，检查是否需要更新
                    existing_path = existing[name].get('savePath', '')
                    new_path = config.save_path or self._map_save_path(name)
                    if existing_path != new_path:
                        await self._update_category(name, new_path)
                        self.logger.info(f"更新分类路径: {name} -> {new_path}")

        except Exception as e:
            self.logger.error(f"确保分类存在失败: {e}")

    async def _create_category(self, name: str, save_path: str) -> bool:
        """创建分类"""
        try:
            data = {
                'category': name,
                'savePath': save_path
            }
            status, _ = await self.api_client.post('torrents/createCategory', data=data)
            return status == 200
        except Exception as e:
            self.logger.error(f"创建分类 {name} 失败: {e}")
            return False

    async def _update_category(self, name: str, save_path: str) -> bool:
        """更新分类"""
        try:
            data = {
                'category': name,
                'savePath': save_path
            }
            status, _ = await self.api_client.post('torrents/editCategory', data=data)
            return status == 200
        except Exception as e:
            self.logger.error(f"更新分类 {name} 失败: {e}")
            return False

    async def _delete_category(self, name: str) -> bool:
        """删除分类"""
        try:
            data = {'category': name}
            status, _ = await self.api_client.post('torrents/removeCategories', data=data)
            return status == 200
        except Exception as e:
            self.logger.error(f"删除分类 {name} 失败: {e}")
            return False

    def _map_save_path(self, original_path: str, category_name: str = "") -> str:
        """
        映射保存路径
        
        根据配置规则将原始路径映射到目标路径
        """
        # 这里可以实现路径映射逻辑
        # 例如根据分类名映射到不同的目录
        if category_name:
            return f"/downloads/{category_name}/"
        return original_path
