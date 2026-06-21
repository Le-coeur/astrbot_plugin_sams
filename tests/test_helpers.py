"""工具函数测试。"""

from utils.helpers import (
    build_summary,
    clean_price,
    format_summary,
    match_product,
    remove_orders,
)


def test_clean_price() -> None:
    assert clean_price("¥25.0") == 25.0
    assert clean_price("25.0元") == 25.0
    assert clean_price("1,234.56") == 1234.56
    assert clean_price("abc") is None


def test_match_product() -> None:
    products = {
        "蒙牛纯牛奶": {"price": 25.0},
        "全麦面包": {"price": 15.5},
    }
    assert match_product("纯牛奶", products) == "蒙牛纯牛奶"
    assert match_product("全麦面包", products) == "全麦面包"
    assert match_product("不存在的商品", products) is None


def test_build_summary() -> None:
    products = {
        "牛奶": {"price": 25.0},
        "面包": {"price": 15.5},
    }
    orders = [
        {"person": "张三", "product": "牛奶", "quantity": 2},
        {"person": "李四", "product": "面包", "quantity": 1},
        {"person": "王五", "product": "牛奶", "quantity": 1},
        {"person": "赵六", "product": "鸡蛋", "quantity": 1},
    ]
    summary = build_summary(orders, products)

    # 汇总项
    items = {item["name"]: item for item in summary["items"]}
    assert items["牛奶"]["quantity"] == 3
    assert items["牛奶"]["subtotal"] == 75.0
    assert items["面包"]["quantity"] == 1

    # 总价
    assert summary["total"] == 90.5

    # 未匹配
    assert len(summary["unmatched"]) == 1
    assert summary["unmatched"][0]["product"] == "鸡蛋"

    # 采购人
    persons = {p["person"]: p for p in summary["persons"]}
    assert persons["张三"]["total"] == 50.0


def test_format_summary() -> None:
    products = {"牛奶": {"price": 25.0}}
    orders = [{"person": "张三", "product": "牛奶", "quantity": 2}]
    summary = build_summary(orders, products)
    text = format_summary(summary)
    assert "牛奶" in text
    assert "张三" in text
    assert "¥50.00" in text


def test_remove_orders() -> None:
    orders = [
        {"person": "张三", "product": "牛奶", "quantity": 2},
        {"person": "李四", "product": "面包", "quantity": 1},
        {"person": "张三", "product": "面包", "quantity": 1},
    ]
    new_orders, removed = remove_orders(orders, "张三", "面包")
    assert removed == 1
    assert len(new_orders) == 2
    assert all(
        not (o["person"] == "张三" and o["product"] == "面包") for o in new_orders
    )

    new_orders, removed = remove_orders(orders, "张三")
    assert removed == 2
    assert all(o["person"] != "张三" for o in new_orders)


if __name__ == "__main__":
    test_clean_price()
    test_match_product()
    test_build_summary()
    test_format_summary()
    test_remove_orders()
    print("helpers tests passed")
