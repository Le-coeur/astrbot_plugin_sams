"""大模型（LLM）服务。

通过 OpenAI 兼容接口调用大模型，用于：
1. 从 OCR 文本中提取商品名称与单价。
2. 从接龙文本中解析接龙人、商品、数量。

未配置 LLM 或调用失败时，主入口会回退到正则/启发式解析。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import aiohttp
from astrbot.api import logger

from services.parser_service import OrderItem


@dataclass
class LlmProduct:
    """LLM 提取出的商品信息。"""

    name: str
    price: float


class LlmService:
    """OpenAI 兼容格式的大模型调用封装。"""

    DEFAULT_BASE_URLS = {
        "moonshot": "https://api.moonshot.cn/v1",
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
    }

    def __init__(
        self,
        api_key: str,
        provider: str = "moonshot",
        base_url: str | None = None,
        model: str = "moonshot-v1-8k",
    ) -> None:
        """初始化 LLM 服务。

        Args:
            api_key: 大模型 API Key。
            provider: 提供商，如 moonshot、openai、deepseek、custom。
            base_url: 自定义 Base URL，为空时使用 provider 默认值。
            model: 模型名称。
        """
        self.api_key = api_key
        self.provider = provider
        self.model = model
        self.base_url = (base_url or self.DEFAULT_BASE_URLS.get(provider, "")).rstrip(
            "/"
        )
        if not self.base_url:
            raise ValueError(f"未知或缺少 Base URL 的 LLM 提供商: {provider}")

    async def _chat(
        self, system_prompt: str, user_content: str, temperature: float = 0.0
    ) -> str:
        """调用大模型聊天接口，返回模型回复文本。"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": temperature,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"LLM 请求失败 ({resp.status}): {text}")

                data = await resp.json()
                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError("LLM 返回结果为空")

                content = choices[0].get("message", {}).get("content", "")
                if not content:
                    raise RuntimeError("LLM 返回内容为空")
                return content

    @staticmethod
    def _extract_json(text: str) -> Any:
        """从模型回复中提取 JSON 数组或对象。"""
        # 尝试直接解析
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 或 [...] 或 {...}
        patterns = [
            r"```json\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```",
            r"(\[\s*\{.*?\}\s*\])",
            r"(\{.*?\})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        raise ValueError("无法从 LLM 回复中提取有效 JSON")

    async def extract_products(self, ocr_text: str) -> list[LlmProduct]:
        """从 OCR 文本中提取商品名称与单价。

        Args:
            ocr_text: OCR 识别出的原始文本，多行字符串。

        Returns:
            商品列表。
        """
        system_prompt = (
            "你是一个商品信息提取助手。用户会提供一段从山姆 APP 截图中 OCR 识别出的文字，"
            "请你从中提取出商品名称和对应单价，以 JSON 数组格式返回。"
            "每个元素包含 name（商品名称，字符串）和 price（单价，数字）。"
            "只返回 JSON 数组，不要任何解释。"
        )
        user_content = f"OCR 文本：\n{ocr_text}"

        raw = await self._chat(system_prompt, user_content)
        data = self._extract_json(raw)

        if not isinstance(data, list):
            raise ValueError("LLM 返回格式错误，期望 JSON 数组")

        products: list[LlmProduct] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            price = item.get("price")
            if name and price is not None:
                try:
                    products.append(LlmProduct(name=name, price=float(price)))
                except (ValueError, TypeError):
                    continue

        logger.info(f"[Sams] LLM 提取到 {len(products)} 个商品")
        return products

    async def parse_order(self, text: str) -> list[OrderItem]:
        """从接龙文本中解析订单。

        Args:
            text: 用户输入的接龙文本，已去掉命令前缀。

        Returns:
            订单列表。
        """
        system_prompt = (
            "你是一个接龙文本解析助手。用户会提供一段团购接龙内容，"
            "请你解析出每条记录中的接龙人（person）、商品（product）、数量（quantity），"
            "并以 JSON 数组格式返回。每个元素包含 person、product、quantity 三个字段。"
            "数量必须是整数。如果同一行有多个商品，请拆分为多条记录。"
            "只返回 JSON 数组，不要任何解释。"
        )
        user_content = f"接龙文本：\n{text}"

        raw = await self._chat(system_prompt, user_content)
        data = self._extract_json(raw)

        if not isinstance(data, list):
            raise ValueError("LLM 返回格式错误，期望 JSON 数组")

        orders: list[OrderItem] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            person = str(item.get("person", "")).strip()
            product = str(item.get("product", "")).strip()
            quantity = item.get("quantity", 1)
            if person and product:
                try:
                    orders.append(
                        OrderItem(
                            person=person, product=product, quantity=int(quantity)
                        )
                    )
                except (ValueError, TypeError):
                    continue

        logger.info(f"[Sams] LLM 解析到 {len(orders)} 条订单")
        return orders

    def to_products_dict(self, products: list[LlmProduct]) -> dict[str, dict[str, Any]]:
        """将商品列表转为持久化所需的字典格式。"""
        return {
            p.name: {"name": p.name, "price": p.price, "quantity": 0} for p in products
        }
