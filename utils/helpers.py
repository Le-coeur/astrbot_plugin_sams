"""工具函数。

包含价格清洗、商品名称匹配、汇总表格生成等通用能力。
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from astrbot.api import logger


def clean_price(text: str) -> float | None:
    """从字符串中提取价格数字。

    支持格式：¥25.0、25.0元、25.00 等。

    Args:
        text: 包含价格的字符串。

    Returns:
        提取到的价格，若无法提取则返回 None。
    """
    if not text:
        return None
    # 去掉货币符号、单位、逗号、空格
    cleaned = re.sub(r"[¥￥,，\s元]", "", str(text))
    # 保留第一个符合价格格式的数字
    match = re.search(r"\d+(?:\.\d{1,2})?", cleaned)
    if not match:
        return None
    try:
        price = float(match.group(0))
        return price if price >= 0 else None
    except ValueError:
        return None


def normalize_name(name: str) -> str:
    """标准化商品名或人名，用于匹配比较。"""
    name = str(name).lower().strip()
    # 去掉常见单位、数量词
    name = re.sub(r"\d+[件个盒瓶包]?", "", name)
    # 去掉多余空格
    name = re.sub(r"\s+", "", name)
    return name


def match_product(order_product: str, products: dict[str, Any]) -> str | None:
    """将接龙商品名与商品表进行模糊匹配。

    匹配策略（按优先级）：
    1. 完全匹配；
    2. 忽略大小写与空格后的完全匹配；
    3. 商品表名称包含于订单名称；
    4. 订单名称包含于商品表名称；
    5. 标准化后互相包含。

    Args:
        order_product: 接龙中的商品名。
        products: 商品表字典，key 为商品名。

    Returns:
        匹配到的商品表 key，未匹配返回 None。
    """
    if not products:
        return None

    order = order_product.strip()
    order_norm = normalize_name(order)

    candidates = list(products.keys())

    # 1. 完全匹配
    if order in products:
        return order

    # 2. 忽略大小写与空格
    for name in candidates:
        if name.replace(" ", "").lower() == order.replace(" ", "").lower():
            return name

    # 3. 商品表名称包含于订单名称
    for name in candidates:
        if name in order:
            return name

    # 4. 订单名称包含于商品表名称
    for name in candidates:
        if order in name:
            return name

    # 5. 标准化后互相包含
    for name in candidates:
        name_norm = normalize_name(name)
        if name_norm and (name_norm in order_norm or order_norm in name_norm):
            return name

    return None


def build_summary(
    orders: list[dict[str, Any]],
    products: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """生成采购汇总。

    Args:
        orders: 订单列表，每项包含 person、product、quantity。
        products: 商品表，key 为商品名，value 包含 price。

    Returns:
        汇总结果字典，包含：
        - items: 采购物品详单
        - persons: 采购人详单
        - unmatched: 未匹配清单
        - total: 总价
    """
    # 采购物品汇总：商品 -> 总数量
    item_summary: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"quantity": 0, "price": 0.0}
    )
    # 采购人汇总：人 -> 商品 -> 数量
    person_summary: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {"quantity": 0, "price": 0.0})
    )
    unmatched: list[dict[str, Any]] = []
    total = 0.0

    for order in orders:
        person = order.get("person", "").strip()
        product_input = order.get("product", "").strip()
        quantity = int(order.get("quantity", 1))

        if not person or not product_input or quantity <= 0:
            continue

        matched_key = match_product(product_input, products)
        if matched_key:
            product_name = matched_key
            price = float(products[matched_key].get("price", 0.0))
            subtotal = price * quantity
            total += subtotal

            item_summary[product_name]["quantity"] += quantity
            item_summary[product_name]["price"] = price

            person_summary[person][product_name]["quantity"] += quantity
            person_summary[person][product_name]["price"] = price
        else:
            unmatched.append(
                {
                    "person": person,
                    "product": product_input,
                    "quantity": quantity,
                }
            )

    # 转换为列表并按名称排序
    items = []
    for name, info in sorted(item_summary.items()):
        qty = info["quantity"]
        price = info["price"]
        items.append(
            {
                "name": name,
                "price": price,
                "quantity": qty,
                "subtotal": round(price * qty, 2),
            }
        )

    persons = []
    for person_name, products_map in sorted(person_summary.items()):
        person_items = []
        person_total = 0.0
        for product_name, info in sorted(products_map.items()):
            qty = info["quantity"]
            price = info["price"]
            subtotal = price * qty
            person_total += subtotal
            person_items.append(
                {
                    "name": product_name,
                    "price": price,
                    "quantity": qty,
                    "subtotal": round(subtotal, 2),
                }
            )
        persons.append(
            {
                "person": person_name,
                "items": person_items,
                "total": round(person_total, 2),
            }
        )

    result = {
        "items": items,
        "persons": persons,
        "unmatched": unmatched,
        "total": round(total, 2),
    }
    logger.info(
        f"[Sams] 汇总完成：商品 {len(items)} 项，"
        f"采购人 {len(persons)} 人，未匹配 {len(unmatched)} 项"
    )
    return result


def remove_orders(
    orders: list[dict[str, Any]], person: str, product: str | None = None
) -> tuple[list[dict[str, Any]], int]:
    """移除指定接龙记录。

    Args:
        orders: 订单列表。
        person: 要移除的接龙人。
        product: 若指定，则只移除该商品；否则移除该接龙人全部记录。

    Returns:
        (新订单列表, 移除数量)
    """
    if product:
        new_orders = [
            o
            for o in orders
            if not (o.get("person") == person and o.get("product") == product)
        ]
    else:
        new_orders = [o for o in orders if o.get("person") != person]

    removed = len(orders) - len(new_orders)
    logger.info(f"[Sams] 移除接龙记录 {removed} 条")
    return new_orders, removed


def format_summary(summary: dict[str, Any]) -> str:
    """将汇总结果格式化为可读的 Markdown 表格。"""
    lines: list[str] = []

    lines.append("## 采购汇总\n")

    # 采购物品详单
    lines.append("### 采购物品详单\n")
    lines.append("| 商品 | 单价 | 数量 | 小计 |")
    lines.append("|------|------|------|------|")
    for item in summary["items"]:
        lines.append(
            f"| {item['name']} | ¥{item['price']:.2f} | {item['quantity']} | "
            f"¥{item['subtotal']:.2f} |"
        )
    lines.append(f"| **合计** | | | **¥{summary['total']:.2f}** |\n")

    # 采购人详单
    lines.append("### 采购人详单\n")
    for person in summary["persons"]:
        lines.append(f"**{person['person']}**  合计：¥{person['total']:.2f}\n")
        lines.append("| 商品 | 单价 | 数量 | 小计 |")
        lines.append("|------|------|------|------|")
        for item in person["items"]:
            lines.append(
                f"| {item['name']} | ¥{item['price']:.2f} | {item['quantity']} | "
                f"¥{item['subtotal']:.2f} |"
            )
        lines.append("")

    # 未匹配清单
    if summary["unmatched"]:
        lines.append("### 未匹配清单\n")
        lines.append("| 接龙人 | 商品 | 数量 |")
        lines.append("|--------|------|------|")
        for item in summary["unmatched"]:
            lines.append(
                f"| {item['person']} | {item['product']} | {item['quantity']} |"
            )
        lines.append("")

    return "\n".join(lines)


def format_products(products: dict[str, dict[str, Any]]) -> str:
    """将商品表格式化为 Markdown 表格。"""
    if not products:
        return "当前商品表为空，请先使用 `/sams_scan` 识别图片或 `/sams_add` 手动添加。"

    lines = ["| 商品 | 单价 |", "|------|------|"]
    for name in sorted(products.keys()):
        price = float(products[name].get("price", 0.0))
        lines.append(f"| {name} | ¥{price:.2f} |")
    return "\n".join(lines)
