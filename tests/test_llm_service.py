"""大模型服务测试。"""

import asyncio

from services.llm_service import LlmService


def test_extract_json() -> None:
    service = LlmService(api_key="fake", provider="moonshot")

    # 纯 JSON
    assert service._extract_json('[{"name": "牛奶", "price": 25.0}]') == [
        {"name": "牛奶", "price": 25.0}
    ]

    # Markdown 代码块
    md = '```json\n[{"name": "面包", "price": 15.5}]\n```'
    assert service._extract_json(md) == [{"name": "面包", "price": 15.5}]

    # 包含额外说明文字
    mixed = '好的，结果如下：\n```\n[{"person": "张三", "product": "牛奶", "quantity": 2}]\n```'
    assert service._extract_json(mixed) == [
        {"person": "张三", "product": "牛奶", "quantity": 2}
    ]


def test_to_products_dict() -> None:
    from services.llm_service import LlmProduct

    service = LlmService(api_key="fake", provider="moonshot")
    products = [LlmProduct(name="牛奶", price=25.0)]
    result = service.to_products_dict(products)
    assert result == {"牛奶": {"name": "牛奶", "price": 25.0, "quantity": 0}}


async def test_extract_products_mock() -> None:
    service = LlmService(api_key="fake", provider="moonshot")

    async def fake_chat(
        system_prompt: str, user_content: str, temperature: float = 0.0
    ) -> str:
        return '[{"name": "牛奶", "price": 25.0}, {"name": "面包", "price": 15.5}]'

    service._chat = fake_chat  # type: ignore[assignment]
    products = await service.extract_products("牛奶 25\n面包 15.5")
    assert len(products) == 2
    assert products[0].name == "牛奶"
    assert products[0].price == 25.0


async def test_parse_order_mock() -> None:
    service = LlmService(api_key="fake", provider="moonshot")

    async def fake_chat(
        system_prompt: str, user_content: str, temperature: float = 0.0
    ) -> str:
        return '[{"person": "张三", "product": "牛奶", "quantity": 2}]'

    service._chat = fake_chat  # type: ignore[assignment]
    orders = await service.parse_order("张三 牛奶 2")
    assert len(orders) == 1
    assert orders[0].person == "张三"
    assert orders[0].product == "牛奶"
    assert orders[0].quantity == 2


def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


if __name__ == "__main__":
    test_extract_json()
    test_to_products_dict()
    run_async(test_extract_products_mock())
    run_async(test_parse_order_mock())
    print("llm_service tests passed")
