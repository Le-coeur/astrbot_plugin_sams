# astrbot_plugin_sams

一个用于 AstrBot 的山姆团购接龙汇总插件，适合公司团建、家庭采购等微信群团购场景。

## 功能简介

在微信群团购/接龙场景中，管理员只需：
1. 将群里的接龙消息发送给 Agent。
2. 发送山姆 APP 的商品截图（包含名称、单价）。

Agent 自动完成：
- 识别截图中的商品名称与单价。
- 解析接龙信息（接龙人、商品、数量）。
- 匹配商品与订单，输出：
  - **采购物品详单**：商品名称、单价、数量、小计。
  - **采购人详单**：每位接龙人购买的商品、单价、数量、小计。
  - **未匹配清单**：接龙中有但商品表未匹配到的商品。

## 安装

1. 将本插件放入 AstrBot 的插件目录：
   ```bash
   cd AstrBot/data/plugins
   git clone https://github.com/Le-coeur/astrbot_plugin_sams
   ```
2. AstrBot 会自动读取 `requirements.txt` 安装依赖。
3. 在 AstrBot 管理面板启用插件。

## 使用说明

### 插件配置

本插件支持在 AstrBot WebUI 中通过 `_conf_schema.json` 进行可视化配置。

#### 腾讯云 OCR（用于 `/sams_scan` 识别商品截图）
- `secret_id`：腾讯云 SecretId。
- `secret_key`：腾讯云 SecretKey。
- `region`：腾讯云地域（如 `ap-guangzhou`）。

#### 大模型（用于智能解析接龙与 OCR 结果）
- `llm_provider`：大模型提供商，可选 `moonshot`、`openai`、`deepseek`、`custom`。
- `llm_api_key`：对应平台的 API Key。
- `llm_base_url`：自定义 API Base URL（可选，留空使用默认值）。
- `llm_model`：模型名称，例如 `moonshot-v1-8k`、`gpt-4o`、`deepseek-chat`。
- `use_llm_for_order`：是否使用 LLM 解析接龙文本（默认 `true`）。
- `use_llm_for_ocr`：是否使用 LLM 分析 OCR 结果提取商品（默认 `true`）。

> 提示：若未配置 LLM，插件会自动回退到本地正则/启发式解析，仍可正常使用。

### 指令列表

> 所有指令均以 `sams_` 为前缀，避免与其他插件冲突。

| 指令 | 功能 | 示例 |
|------|------|------|
| `/sams_scan` | 识别图片中的商品信息并更新商品表 | 发送 `/sams_scan` 并附带图片 |
| `/sams_add` | 手动添加商品 | `/sams_add 牛奶 25.0` |
| `/sams_edit` | 修改商品单价 | `/sams_edit 牛奶 26.0` |
| `/sams_rename` | 重命名商品 | `/sams_rename 牛奶 蒙牛纯牛奶` |
| `/sams_list` | 查看当前商品表 | `/sams_list` |
| `/sams_delete` | 删除指定商品 | `/sams_delete 牛奶` |
| `/sams_order` | 提交或解析接龙信息 | `/sams_order 张三 牛奶 2` 或粘贴多行接龙文本 |
| `/sams_remove_order` | 移除指定接龙记录 | `/sams_remove_order 张三` 或 `/sams_remove_order 张三 牛奶` |
| `/sams_clear_order` | 清空订单表（保留商品表） | `/sams_clear_order` |
| `/sams_summary` | 输出完整采购汇总表格 | `/sams_summary` |
| `/sams_clear` | 清空商品表与订单表 | `/sams_clear` |
| `/sams_help` | 显示帮助信息 | `/sams_help` |

### 示例流程

1. 发送商品截图：
   ```
   /sams_scan
   ```
   （附带山姆 APP 截图）

2. 查看识别结果：
   ```
   /sams_list
   ```

3. 提交接龙信息：
   ```
   /sams_order 张三 牛奶 2
   /sams_order 李四 面包 1
   ```
   或一次性粘贴多行：
   ```
   /sams_order
   张三 牛奶 2
   李四 面包 1
   王五 牛奶 1
   ```

4. 修改识别有误的价格或名称：
   ```
   /sams_edit 牛奶 26.0
   /sams_rename 面包 全麦面包
   ```

5. 有人临时取消时移除记录：
   ```
   /sams_remove_order 张三
   ```
   或仅移除某人的某条记录：
   ```
   /sams_remove_order 张三 牛奶
   ```

6. 想重新收集接龙但保留商品表：
   ```
   /sams_clear_order
   ```

7. 输出汇总：
   ```
   /sams_summary
   ```

## 开发说明

- Python 3.12+
- 异步 HTTP 使用 `aiohttp` / `httpx`，禁止 `requests`。
- 本地开发使用 Poetry 管理依赖：
  ```bash
  poetry install
  PYTHONPATH=. poetry run python tests/test_parser.py
  ```
- 代码格式化使用 ruff：
  ```bash
  ruff check .
  ruff format .
  ```

## 注意事项

- 商品表数据会被新截图覆盖，如需保留请提前导出。
- OCR 识别可能存在误差，可通过 `/sams_add`、`/sams_edit`、`/sams_rename`、`/sams_delete` 手动修正商品表。
- 接龙记录默认追加，可通过 `/sams_remove_order` 或 `/sams_clear_order` 进行管理。
- 持久化数据存储在 AstrBot 的 `data/plugins/astrbot_plugin_sams/` 目录下。

## 支持与贡献

- [AstrBot 源码](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件开发指南](https://docs.astrbot.app/dev/star/plugin-new.html)
- [腾讯云 OCR 文档](https://cloud.tencent.com/document/product/866/33526)
