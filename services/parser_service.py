"""接龙文本解析服务。

将用户提交的接龙内容解析为结构化订单数据：
每条订单包含接龙人、商品名称、数量。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from astrbot.api import logger


@dataclass
class OrderItem:
    """一条接龙订单。"""

    person: str
    product: str
    quantity: int


class ParserService:
    """接龙文本解析器。"""

    # 数量前缀/后缀匹配：x2、*2、2个、2盒 等
    QTY_PATTERN = re.compile(r"^(\d+)([件个盒瓶包])?$")
    SUFFIX_QTY_PATTERN = re.compile(r"[xX*×](\d+)$")

    def parse_order(self, text: str) -> list[OrderItem]:
        """解析接龙文本。

        支持两种输入：
        1. 单行：``/order 张三 牛奶 2``
        2. 多行：每行 ``人名 商品 数量``

        Args:
            text: 用户输入的完整文本。

        Returns:
            解析出的订单列表。

        Raises:
            ValueError: 输入格式不正确。
        """
        if not text or not text.strip():
            raise ValueError("接龙内容不能为空")

        # 去掉命令前缀 /sams_order
        body = re.sub(r"^/sams_order\s*", "", text.strip(), flags=re.IGNORECASE)
        if not body:
            raise ValueError(
                "请在 /sams_order 后输入接龙内容，例如：/sams_order 张三 牛奶 2"
            )

        lines = [line.strip() for line in body.splitlines() if line.strip()]
        if not lines:
            raise ValueError("未解析到有效接龙内容")

        orders: list[OrderItem] = []
        for line in lines:
            item = self._parse_line(line)
            if item:
                orders.append(item)

        if not orders:
            raise ValueError(
                "未解析到有效订单，请检查格式。示例：\n张三 牛奶 2\n李四 面包 1"
            )

        logger.info(f"[Sams] 解析到 {len(orders)} 条订单")
        return orders

    def _parse_line(self, line: str) -> OrderItem | None:
        """解析单行接龙文本。"""
        # 去掉常见序号前缀：1. 1、 - 等
        line = re.sub(r"^\s*[-・•]+\s*", "", line)
        line = re.sub(r"^\d+[\.、,，)\]\}]+\s*", "", line)

        # 尝试分离数量后缀，如 "牛奶x2"
        suffix_match = self.SUFFIX_QTY_PATTERN.search(line)
        if suffix_match:
            qty = int(suffix_match.group(1))
            clean = line[: suffix_match.start()].strip()
            parts = clean.split()
            if len(parts) >= 2:
                person = parts[0]
                product = " ".join(parts[1:])
                return OrderItem(person=person, product=product, quantity=qty)

        # 按空格拆分
        parts = line.split()
        if len(parts) < 2:
            return None

        person = parts[0]

        # 最后一段是数量
        last = parts[-1]
        qty_match = self.QTY_PATTERN.match(last)
        if qty_match:
            quantity = int(qty_match.group(1))
            product = " ".join(parts[1:-1])
        else:
            # 尝试在文本中找独立的数量词
            quantity, product = self._extract_quantity(parts[1:])

        product = product.strip()
        if not product:
            return None

        return OrderItem(person=person, product=product, quantity=quantity)

    def _extract_quantity(self, parts: list[str]) -> tuple[int, str]:
        """从商品片段中提取数量。"""
        # 默认数量为 1
        quantity = 1
        product_parts: list[str] = []

        for part in parts:
            qty_match = self.QTY_PATTERN.match(part)
            if qty_match and not product_parts:
                # 数量在商品前面，暂不处理，直接作为商品名一部分
                product_parts.append(part)
            elif qty_match:
                quantity = int(qty_match.group(1))
            else:
                product_parts.append(part)

        return quantity, " ".join(product_parts)
