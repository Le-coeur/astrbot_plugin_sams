"""OCR 识别服务封装。

使用腾讯云通用印刷体识别（高精度版）识别商品截图中的文字，
并从识别结果中提取商品名称与单价。

为避免 SDK 的同步 HTTP 调用阻塞事件循环，底层识别通过
``asyncio.to_thread`` 在线程池中执行。
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
from dataclasses import dataclass
from typing import Any

from astrbot.api import logger
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
    TencentCloudSDKException,
)
from tencentcloud.common.profile import client_profile, http_profile
from tencentcloud.ocr.v20181119 import ocr_client, models


@dataclass
class OcrProduct:
    """OCR 识别出的商品信息。"""

    name: str
    price: float


class OcrService:
    """腾讯云 OCR 服务封装。"""

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        region: str = "ap-guangzhou",
    ) -> None:
        """初始化 OCR 服务。

        Args:
            secret_id: 腾讯云 SecretId。
            secret_key: 腾讯云 SecretKey。
            region: 腾讯云地域，默认广州。
        """
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.region = region
        self.endpoint = "ocr.tencentcloudapi.com"

    def _build_client(self) -> ocr_client.OcrClient:
        """构造腾讯云 OCR 客户端。"""
        cred = credential.Credential(self.secret_id, self.secret_key)
        http_profile_obj = http_profile.HttpProfile()
        http_profile_obj.endpoint = self.endpoint
        client_profile_obj = client_profile.ClientProfile()
        client_profile_obj.httpProfile = http_profile_obj
        return ocr_client.OcrClient(cred, self.region, client_profile_obj)

    def _recognize_sync(self, image_bytes: bytes) -> list[str]:
        """同步调用腾讯云 OCR，返回识别到的文本行列表。"""
        client = self._build_client()
        req = models.GeneralAccurateOCRRequest()
        req.ImageBase64 = base64.b64encode(image_bytes).decode("utf-8")
        resp = client.GeneralAccurateOCR(req)

        # 将响应对象转为字典
        resp_dict = json.loads(resp.to_json_string())
        detections = resp_dict.get("TextDetections", [])
        texts = [item.get("DetectedText", "").strip() for item in detections]
        return [t for t in texts if t]

    async def recognize(self, image_bytes: bytes) -> list[str]:
        """异步识别图片文字。

        Args:
            image_bytes: 图片二进制数据。

        Returns:
            识别到的文本行列表。

        Raises:
            RuntimeError: OCR 调用失败。
        """
        try:
            texts = await asyncio.to_thread(self._recognize_sync, image_bytes)
            logger.info(f"[Sams] OCR 识别完成，共 {len(texts)} 行文本")
            return texts
        except TencentCloudSDKException as e:
            logger.error(f"[Sams] 腾讯云 OCR 调用失败: {e}")
            raise RuntimeError(f"OCR 识别失败: {e}") from e
        except Exception as e:
            logger.error(f"[Sams] OCR 发生未知错误: {e}")
            raise RuntimeError(f"OCR 识别异常: {e}") from e

    def extract_products(self, texts: list[str]) -> list[OcrProduct]:
        """从 OCR 文本中提取商品名称与单价。

        采用启发式规则：
        1. 识别包含价格的行；
        2. 若价格同行有前置文字，则作为商品名；
        3. 否则取上方最近的一行非噪声文本作为商品名。

        Args:
            texts: OCR 识别出的文本行。

        Returns:
            识别出的商品列表。
        """
        products: list[OcrProduct] = []
        price_pattern = re.compile(r"[¥￥]?\s*(\d{1,6}(?:\.\d{1,2})?)\s*[元]?")

        for idx, line in enumerate(texts):
            match = price_pattern.search(line)
            if not match:
                continue

            price_str = match.group(1)
            try:
                price = float(price_str)
            except ValueError:
                continue

            # 忽略过大或过小的价格（如订单总价、数量等）
            if not 0.01 <= price <= 99999.99:
                continue

            # 同行中价格之前的文字
            prefix = line[: match.start()].strip(" ¥￥")
            name = ""
            if prefix and not self._is_noise(prefix):
                name = prefix
            else:
                # 向上查找最近的有效文本
                for prev in reversed(texts[:idx]):
                    if self._is_valid_product_name(prev):
                        name = prev
                        break

            if name:
                products.append(OcrProduct(name=name, price=price))

        # 去重：相同商品名保留第一个
        seen: set[str] = set()
        unique: list[OcrProduct] = []
        for p in products:
            key = p.name.strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(p)

        logger.info(f"[Sams] 从 OCR 文本中提取到 {len(unique)} 个商品")
        return unique

    @staticmethod
    def _is_noise(text: str) -> bool:
        """判断文本是否为噪声（数字、日期、纯符号等）。"""
        if not text:
            return True
        # 纯数字或数量
        if re.fullmatch(r"\d+[件个盒瓶包]?", text):
            return True
        # 日期
        if re.search(r"\d{4}[-/年]\d{1,2}[-/月]", text):
            return True
        return False

    @staticmethod
    def _is_valid_product_name(text: str) -> bool:
        """判断文本是否可能为商品名。"""
        if not text:
            return False
        if OcrService._is_noise(text):
            return False
        # 包含明显价格符号的不行
        if re.search(r"[¥￥]\s*\d", text):
            return False
        # 至少包含一个中文字符或字母
        if not re.search(r"[\u4e00-\u9fa5a-zA-Z]", text):
            return False
        return True

    def to_products_dict(self, products: list[OcrProduct]) -> dict[str, dict[str, Any]]:
        """将商品列表转为持久化所需的字典格式。"""
        return {
            p.name: {"name": p.name, "price": p.price, "quantity": 0} for p in products
        }
