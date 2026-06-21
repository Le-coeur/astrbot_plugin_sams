"""astrbot_plugin_sams 插件入口。

实现山姆团购接龙助手的所有指令：
/sams_scan、/sams_add、/sams_edit、/sams_rename、/sams_list、/sams_delete、
/sams_order、/sams_remove_order、/sams_clear_order、/sams_summary、
/sams_clear、/sams_help。
"""

from __future__ import annotations

import aiohttp
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import Image, Plain
from astrbot.api.star import Context, Star, register
from astrbot.core.star.filter.plugin import PluginKVStoreMixin

from services.data_service import DataService
from services.llm_service import LlmService
from services.ocr_service import OcrService
from services.parser_service import ParserService
from utils.helpers import (
    build_summary,
    clean_price,
    format_products,
    format_summary,
    products_to_dict,
    remove_orders,
)


@register(
    "astrbot_plugin_sams",
    "Le-coeur",
    "山姆团购接龙助手：识别商品截图、解析接龙、生成采购汇总",
    "1.0.0",
)
class SamsPlugin(Star, PluginKVStoreMixin):
    """山姆接龙助手插件主类。"""

    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.data_service = DataService(self)
        self.parser = ParserService()
        self.ocr: OcrService | None = None
        self.llm: LlmService | None = None
        self.use_llm_for_order = False
        self.use_llm_for_ocr = False

    async def initialize(self) -> None:
        """插件初始化时读取 OCR 与 LLM 配置。"""
        cfg = self._get_config()

        # OCR
        secret_id = cfg.get("secret_id", "")
        secret_key = cfg.get("secret_key", "")
        region = cfg.get("region", "ap-guangzhou")
        if secret_id and secret_key:
            self.ocr = OcrService(secret_id, secret_key, region)
            logger.info("[Sams] OCR 服务已初始化")
        else:
            logger.warning("[Sams] 未配置腾讯云 OCR 密钥，/sams_scan 指令不可用")

        # LLM
        self.use_llm_for_order = cfg.get("use_llm_for_order", True)
        self.use_llm_for_ocr = cfg.get("use_llm_for_ocr", True)
        llm_api_key = cfg.get("llm_api_key", "")
        if llm_api_key:
            try:
                self.llm = LlmService(
                    api_key=llm_api_key,
                    provider=cfg.get("llm_provider", "moonshot"),
                    base_url=cfg.get("llm_base_url", None),
                    model=cfg.get("llm_model", "moonshot-v1-8k"),
                )
                logger.info("[Sams] LLM 服务已初始化")
            except Exception as e:
                logger.error(f"[Sams] LLM 服务初始化失败: {e}")
                self.llm = None
        else:
            logger.warning("[Sams] 未配置 LLM API Key，将使用本地正则/启发式解析")

    def _get_config(self) -> dict:
        """读取插件配置，支持多层级访问。"""
        # 优先读取 AstrBot 注入的 self.config
        direct_cfg = getattr(self, "config", None)
        if isinstance(direct_cfg, dict) and direct_cfg:
            return direct_cfg

        # 其次从 context.config 中读取
        plugin_cfg = getattr(self.context, "config", None)
        if plugin_cfg is not None:
            if hasattr(plugin_cfg, "get"):
                cfg = plugin_cfg.get("astrbot_plugin_sams", {})
                if isinstance(cfg, dict):
                    return cfg
                return dict(cfg) if cfg else {}
        return {}

    def _get_plain_text(self, event: AstrMessageEvent) -> str:
        """从消息事件中提取纯文本。"""
        text = event.message_str or ""
        if text:
            return text

        parts = []
        for comp in event.get_messages():
            if isinstance(comp, Plain):
                parts.append(comp.text)
        return "".join(parts).strip()

    async def _extract_first_image(self, event: AstrMessageEvent) -> bytes | None:
        """从消息链中提取第一张图片的二进制数据。"""
        for comp in event.get_messages():
            if not isinstance(comp, Image):
                continue

            url = getattr(comp, "url", None) or getattr(comp, "file", None)
            if url and url.startswith("http"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            return await resp.read()
                        logger.warning(f"[Sams] 图片下载失败，状态码: {resp.status}")
            elif url:
                try:
                    from pathlib import Path

                    return Path(url).read_bytes()
                except Exception as e:
                    logger.warning(f"[Sams] 读取本地图片失败: {e}")
        return None

    @filter.command("sams_scan")
    async def scan(self, event: AstrMessageEvent):
        """识别图片中的商品信息并更新商品表。"""
        try:
            if self.ocr is None:
                yield event.plain_result(
                    "OCR 服务未配置，请在插件配置中填写腾讯云 SecretId 与 SecretKey。"
                )
                return

            image_bytes = await self._extract_first_image(event)
            if image_bytes is None:
                yield event.plain_result(
                    "未检测到图片，请在发送 /sams_scan 时附带商品截图。"
                )
                return

            self.data_service.save_image(image_bytes)
            texts = await self.ocr.recognize(image_bytes)
            if not texts:
                yield event.plain_result("未能从图片中识别出文字，请尝试更换截图。")
                return

            products_list = None
            if self.use_llm_for_ocr and self.llm is not None:
                try:
                    products_list = await self.llm.extract_products("\n".join(texts))
                    logger.info("[Sams] 使用 LLM 提取 OCR 商品")
                except Exception as e:
                    logger.warning(f"[Sams] LLM 提取商品失败，回退到启发式规则: {e}")

            if products_list is None:
                products_list = self.ocr.extract_products(texts)

            if not products_list:
                yield event.plain_result(
                    "识别到文字但未提取到有效商品与价格，请检查截图是否包含价格信息。"
                )
                return

            products = products_to_dict(products_list)
            await self.data_service.set_products(products)

            msg = "商品识别完成：\n" + format_products(products)
            yield event.plain_result(msg)

        except Exception as e:
            logger.error(f"[Sams] /sams_scan 指令异常: {e}")
            yield event.plain_result(f"识别失败: {e}")

    @filter.command("sams_add")
    async def add(self, event: AstrMessageEvent):
        """手动添加商品。用法：/sams_add 名称 单价 [库存数量]"""
        try:
            text = self._get_plain_text(event)
            body = text.replace("/sams_add", "", 1).strip()
            parts = body.split()
            if len(parts) < 2:
                yield event.plain_result(
                    "格式错误。示例：/sams_add 牛奶 25.0 或 /sams_add 牛奶 25.0 10"
                )
                return

            name = parts[0]
            price = clean_price(parts[1])
            if price is None:
                yield event.plain_result(f"无法解析价格：{parts[1]}")
                return

            quantity = 1
            if len(parts) >= 3:
                try:
                    quantity = int(parts[2])
                except ValueError:
                    yield event.plain_result(f"数量格式错误：{parts[2]}")
                    return

            products = await self.data_service.get_products()
            products[name] = {"name": name, "price": price, "quantity": quantity}
            await self.data_service.set_products(products)
            yield event.plain_result(
                f"已添加商品：{name} ¥{price:.2f}（库存 {quantity}）"
            )

        except Exception as e:
            logger.error(f"[Sams] /sams_add 指令异常: {e}")
            yield event.plain_result(f"添加失败: {e}")

    @filter.command("sams_edit")
    async def edit(self, event: AstrMessageEvent):
        """修改商品单价。用法：/sams_edit 名称 新单价"""
        try:
            text = self._get_plain_text(event)
            body = text.replace("/sams_edit", "", 1).strip()
            parts = body.split()
            if len(parts) != 2:
                yield event.plain_result("格式错误。示例：/sams_edit 牛奶 26.0")
                return

            name = parts[0]
            price = clean_price(parts[1])
            if price is None:
                yield event.plain_result(f"无法解析价格：{parts[1]}")
                return

            products = await self.data_service.get_products()
            if name not in products:
                yield event.plain_result(f"商品表中不存在：{name}")
                return

            old_price = products[name].get("price", 0.0)
            products[name]["price"] = price
            await self.data_service.set_products(products)
            yield event.plain_result(
                f"已修改 {name} 的价格：¥{old_price:.2f} → ¥{price:.2f}"
            )

        except Exception as e:
            logger.error(f"[Sams] /sams_edit 指令异常: {e}")
            yield event.plain_result(f"修改失败: {e}")

    @filter.command("sams_rename")
    async def rename(self, event: AstrMessageEvent):
        """重命名商品。用法：/sams_rename 旧名称 新名称"""
        try:
            text = self._get_plain_text(event)
            body = text.replace("/sams_rename", "", 1).strip()
            parts = body.split()
            if len(parts) != 2:
                yield event.plain_result("格式错误。示例：/sams_rename 牛奶 蒙牛纯牛奶")
                return

            old_name, new_name = parts[0], parts[1]
            products = await self.data_service.get_products()
            if old_name not in products:
                yield event.plain_result(f"商品表中不存在：{old_name}")
                return
            if new_name in products and new_name != old_name:
                yield event.plain_result(f"商品表中已存在：{new_name}")
                return

            info = products.pop(old_name)
            info["name"] = new_name
            products[new_name] = info
            await self.data_service.set_products(products)
            yield event.plain_result(f"已重命名：{old_name} → {new_name}")

        except Exception as e:
            logger.error(f"[Sams] /sams_rename 指令异常: {e}")
            yield event.plain_result(f"重命名失败: {e}")

    @filter.command("sams_list")
    async def list_products(self, event: AstrMessageEvent):
        """查看当前商品表。"""
        try:
            products = await self.data_service.get_products()
            yield event.plain_result(format_products(products))
        except Exception as e:
            logger.error(f"[Sams] /sams_list 指令异常: {e}")
            yield event.plain_result(f"查询失败: {e}")

    @filter.command("sams_delete")
    async def delete(self, event: AstrMessageEvent):
        """删除指定商品。用法：/sams_delete 名称"""
        try:
            text = self._get_plain_text(event)
            body = text.replace("/sams_delete", "", 1).strip()
            if not body:
                yield event.plain_result("格式错误。示例：/sams_delete 牛奶")
                return

            products = await self.data_service.get_products()
            if body not in products:
                yield event.plain_result(f"商品表中不存在：{body}")
                return

            del products[body]
            await self.data_service.set_products(products)
            yield event.plain_result(f"已删除商品：{body}")

        except Exception as e:
            logger.error(f"[Sams] /sams_delete 指令异常: {e}")
            yield event.plain_result(f"删除失败: {e}")

    @filter.command("sams_order")
    async def order(self, event: AstrMessageEvent):
        """提交或解析接龙信息。"""
        try:
            text = self._get_plain_text(event)
            body = text.replace("/sams_order", "", 1).strip()

            orders = None
            if self.use_llm_for_order and self.llm is not None:
                try:
                    orders = await self.llm.parse_order(body)
                    logger.info("[Sams] 使用 LLM 解析接龙文本")
                except Exception as e:
                    logger.warning(f"[Sams] LLM 解析接龙失败，回退到正则解析: {e}")

            if orders is None:
                orders = self.parser.parse_order(text)

            products = await self.data_service.get_products()
            existing = await self.data_service.get_orders()

            for item in orders:
                existing.append(
                    {
                        "person": item.person,
                        "product": item.product,
                        "quantity": item.quantity,
                    }
                )

            await self.data_service.set_orders(existing)

            lines = [f"已记录 {len(orders)} 条订单："]
            for item in orders:
                matched = "（未匹配）" if not products.get(item.product) else ""
                lines.append(
                    f"- {item.person}：{item.product} x{item.quantity}{matched}"
                )
            yield event.plain_result("\n".join(lines))

        except Exception as e:
            logger.error(f"[Sams] /sams_order 指令异常: {e}")
            yield event.plain_result(f"解析失败: {e}")

    @filter.command("sams_remove_order")
    async def remove_order(self, event: AstrMessageEvent):
        """移除指定接龙记录。用法：/sams_remove_order 接龙人 [商品]"""
        try:
            text = self._get_plain_text(event)
            body = text.replace("/sams_remove_order", "", 1).strip()
            parts = body.split()
            if len(parts) < 1:
                yield event.plain_result(
                    "格式错误。示例：/sams_remove_order 张三 或 /sams_remove_order 张三 牛奶"
                )
                return

            person = parts[0]
            product = parts[1] if len(parts) >= 2 else None

            orders = await self.data_service.get_orders()
            new_orders, removed = remove_orders(orders, person, product)
            if removed == 0:
                yield event.plain_result("未找到匹配的接龙记录。")
                return

            await self.data_service.set_orders(new_orders)
            yield event.plain_result(f"已移除 {removed} 条接龙记录。")

        except Exception as e:
            logger.error(f"[Sams] /sams_remove_order 指令异常: {e}")
            yield event.plain_result(f"移除失败: {e}")

    @filter.command("sams_summary")
    async def summary(self, event: AstrMessageEvent):
        """输出完整采购汇总表格。"""
        try:
            products = await self.data_service.get_products()
            orders = await self.data_service.get_orders()

            if not orders:
                yield event.plain_result(
                    "当前没有订单，请先使用 /sams_order 提交接龙。"
                )
                return

            summary_data = build_summary(orders, products)
            yield event.plain_result(format_summary(summary_data))

        except Exception as e:
            logger.error(f"[Sams] /sams_summary 指令异常: {e}")
            yield event.plain_result(f"汇总失败: {e}")

    @filter.command("sams_clear_order")
    async def clear_order(self, event: AstrMessageEvent):
        """清空订单表（保留商品表）。"""
        try:
            await self.data_service.set_orders([])
            yield event.plain_result("已清空订单表，商品表保持不变。")
        except Exception as e:
            logger.error(f"[Sams] /sams_clear_order 指令异常: {e}")
            yield event.plain_result(f"清空失败: {e}")

    @filter.command("sams_clear")
    async def clear(self, event: AstrMessageEvent):
        """清空当前会话数据。"""
        try:
            await self.data_service.clear()
            yield event.plain_result("已清空商品表与订单表。")
        except Exception as e:
            logger.error(f"[Sams] /sams_clear 指令异常: {e}")
            yield event.plain_result(f"清空失败: {e}")

    @filter.command("sams_help")
    async def help(self, event: AstrMessageEvent):
        """显示帮助信息。"""
        help_text = """山姆接龙助手 指令帮助：

商品管理：
/sams_scan + 图片          识别商品截图，更新商品表
/sams_add 名称 单价 [库存]  手动添加商品
/sams_edit 名称 新单价      修改商品单价
/sams_rename 旧名 新名      重命名商品
/sams_list                  查看商品表
/sams_delete 名称           删除商品

接龙管理：
/sams_order 接龙内容        提交/解析接龙（支持多行）
/sams_remove_order 人 [商品] 移除某人的接龙记录
/sams_clear_order           清空订单表（保留商品表）

汇总：
/sams_summary               输出采购汇总表格
/sams_clear                 清空商品表与订单表
/sams_help                  显示本帮助

使用前请在插件配置中填写腾讯云 SecretId、SecretKey 与 Region。"""
        yield event.plain_result(help_text)

    async def terminate(self) -> None:
        """插件卸载/停用时的清理。"""
        logger.info("[Sams] 插件已停用")
