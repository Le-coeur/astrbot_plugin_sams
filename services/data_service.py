"""数据持久化服务。

负责商品表、订单表的读写，以及图片的本地保存。
所有持久化数据均写入 AstrBot 的 data/plugins/<插件名>/ 目录下，
避免插件更新或重装时数据被覆盖。
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from astrbot.api import logger


class DataService:
    """封装 KV 持久化与图片存储。"""

    # KV 存储键名
    KEY_PRODUCTS = "sams_products"
    KEY_ORDERS = "sams_orders"

    def __init__(self, plugin: Any) -> None:
        """初始化数据服务。

        Args:
            plugin: 插件 Star 实例，需继承 PluginKVStoreMixin，
                    提供 put_async / get_async 方法。
        """
        self.plugin = plugin
        self.data_dir = self._resolve_data_dir()
        self.images_dir = self.data_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[Sams] 数据目录: {self.data_dir}")

    def _resolve_data_dir(self) -> Path:
        """解析插件数据目录。"""
        context = getattr(self.plugin, "context", None)

        # 优先使用 AstrBot 上下文提供的数据目录
        if context is not None:
            # 新版 AstrBot 通常在 context 上暴露 data_dir
            base_dir = getattr(context, "data_dir", None)
            if base_dir:
                return Path(base_dir) / "plugins" / "astrbot_plugin_sams"

            # 兼容旧版或不同命名
            base_dir = getattr(context, "plugin_data_dir", None)
            if base_dir:
                return Path(base_dir)

        # 兜底：当前工作目录下的 data 文件夹，便于本地测试
        fallback = Path(os.getcwd()) / "data" / "plugins" / "astrbot_plugin_sams"
        logger.warning(f"[Sams] 未找到 AstrBot 数据目录，使用兜底路径: {fallback}")
        return fallback

    async def get_products(self) -> dict[str, dict[str, Any]]:
        """读取商品表。"""
        data = await self.plugin.get_async(self.KEY_PRODUCTS)
        if data is None:
            return {}
        if isinstance(data, dict):
            return data
        logger.warning(f"[Sams] 商品表格式异常，已重置。类型: {type(data)}")
        return {}

    async def set_products(self, products: dict[str, dict[str, Any]]) -> None:
        """写入商品表。"""
        await self.plugin.put_async(self.KEY_PRODUCTS, products)
        logger.info(f"[Sams] 商品表已更新，共 {len(products)} 条")

    async def get_orders(self) -> list[dict[str, Any]]:
        """读取订单表。"""
        data = await self.plugin.get_async(self.KEY_ORDERS)
        if data is None:
            return []
        if isinstance(data, list):
            return data
        logger.warning(f"[Sams] 订单表格式异常，已重置。类型: {type(data)}")
        return []

    async def set_orders(self, orders: list[dict[str, Any]]) -> None:
        """写入订单表。"""
        await self.plugin.put_async(self.KEY_ORDERS, orders)
        logger.info(f"[Sams] 订单表已更新，共 {len(orders)} 条")

    async def clear(self) -> None:
        """清空商品表与订单表。"""
        await self.plugin.put_async(self.KEY_PRODUCTS, {})
        await self.plugin.put_async(self.KEY_ORDERS, [])
        logger.info("[Sams] 会话数据已清空")

    def save_image(self, image_bytes: bytes, suffix: str = ".jpg") -> Path:
        """保存图片到按日期分类的目录。

        Args:
            image_bytes: 图片二进制数据。
            suffix: 文件扩展名。

        Returns:
            保存后的文件路径。
        """
        today = datetime.now().strftime("%Y-%m-%d")
        folder = self.images_dir / today
        folder.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%H%M%S_%f")
        filename = f"scan_{timestamp}{suffix}"
        path = folder / filename
        path.write_bytes(image_bytes)
        logger.info(f"[Sams] 图片已保存: {path}")
        return path
