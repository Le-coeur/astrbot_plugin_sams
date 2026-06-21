"""接龙解析服务测试。"""

from services.parser_service import ParserService


def test_single_line() -> None:
    parser = ParserService()
    orders = parser.parse_order("/sams_order 张三 牛奶 2")
    assert len(orders) == 1
    assert orders[0].person == "张三"
    assert orders[0].product == "牛奶"
    assert orders[0].quantity == 2


def test_multi_line() -> None:
    parser = ParserService()
    text = """/sams_order
张三 牛奶 2
李四 面包 1
王五 牛奶 1"""
    orders = parser.parse_order(text)
    assert len(orders) == 3
    assert orders[0].person == "张三"
    assert orders[1].product == "面包"
    assert orders[2].quantity == 1


def test_quantity_suffix() -> None:
    parser = ParserService()
    orders = parser.parse_order("/sams_order 张三 牛奶x2")
    assert len(orders) == 1
    assert orders[0].quantity == 2


def test_prefix_number() -> None:
    parser = ParserService()
    orders = parser.parse_order("/sams_order 1. 张三 牛奶 2")
    assert len(orders) == 1
    assert orders[0].person == "张三"


if __name__ == "__main__":
    test_single_line()
    test_multi_line()
    test_quantity_suffix()
    test_prefix_number()
    print("parser tests passed")
