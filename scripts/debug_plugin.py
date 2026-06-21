"""本地调试脚本。

模拟 AstrBot 加载插件并调用 initialize，用于在本地快速验证配置读取、
OCR 与 LLM 初始化是否正常，无需部署到云端。

运行方式：
    PYTHONPATH=. poetry run python scripts/debug_plugin.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 将插件根目录加入模块搜索路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import SamsPlugin


class FakeContext:
    """模拟 AstrBot 的 Context 对象。"""

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}
        self.plugin_id = "astrbot_plugin_sams"


async def main() -> None:
    """测试插件初始化。"""
    # 情况 1：没有配置
    print("=== 测试 1：无配置 ===")
    ctx = FakeContext(config={})
    plugin = SamsPlugin(ctx)
    await plugin.initialize()
    print(f"OCR 初始化: {plugin.ocr is not None}")
    print(f"LLM 初始化: {plugin.llm is not None}")

    # 情况 2：context.config 中嵌套插件配置
    print("\n=== 测试 2：嵌套插件配置 ===")
    ctx = FakeContext(
        config={
            "astrbot_plugin_sams": {
                "secret_id": "test_secret_id",
                "secret_key": "test_secret_key",
                "region": "ap-guangzhou",
                "llm_provider": "moonshot",
                "llm_api_key": "test_api_key",
                "llm_model": "moonshot-v1-8k",
            }
        }
    )
    plugin = SamsPlugin(ctx)
    await plugin.initialize()
    print(f"OCR 初始化: {plugin.ocr is not None}")
    print(f"LLM 初始化: {plugin.llm is not None}")

    # 情况 3：self.config 直接注入插件配置
    print("\n=== 测试 3：self.config 直接注入 ===")
    ctx = FakeContext(config={})
    plugin = SamsPlugin(ctx)
    plugin.config = {
        "secret_id": "test_secret_id",
        "secret_key": "test_secret_key",
        "llm_provider": "moonshot",
        "llm_api_key": "test_api_key",
    }
    await plugin.initialize()
    print(f"OCR 初始化: {plugin.ocr is not None}")
    print(f"LLM 初始化: {plugin.llm is not None}")

    print("\n=== 本地调试通过 ===")


if __name__ == "__main__":
    asyncio.run(main())
