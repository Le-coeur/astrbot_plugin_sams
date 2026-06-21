# astrbot_plugin_sams — Agent 项目指南

本文档面向 AI Coding Agent，用于快速理解本项目架构与开发惯例。

## 1. 项目概述

`astrbot_plugin_sams` 是为 [AstrBot](https://github.com/Soulter/AstrBot) 开发的插件，用于微信群/团购场景中的山姆商品接龙汇总。

### 1.1 使用场景
公司团建、家庭采购时，多人接龙所需山姆商品。汇总人将接龙文本与山姆 APP 商品截图发送给 Agent，Agent 返回：
- 采购物品详单（商品名称、单价、数量、小计）。
- 采购人详单（每位接龙人购买的商品、单价、数量、小计）。
- 未匹配清单（接龙中有但商品截图中未识别出的商品）。

### 1.2 管理员操作流程
1. 发送群里的接龙消息给 Agent。
2. 发送山姆 APP 商品截图（包含商品名称、单价）。

### 1.3 Agent 处理流程
1. 接收接龙信息（接龙人、商品名称、数量）。
2. 接收图片，调用 OCR 服务识别商品名称与单价，持久化存储。
3. 将接龙信息与商品列表匹配，输出采购汇总。

### 1.4 运行流程图

```mermaid
graph TD
    Start([开始]) --> A{用户输入类型}
    A -->|商品截图| B[/sams_scan]
    A -->|接龙文本| F[/sams_order]
    A -->|汇总请求| J[/sams_summary]

    B --> C[腾讯云 OCR 识别图片文字]
    C --> D{LLM 是否启用}
    D -->|是| E1[LLM 提取商品名称与单价]
    D -->|否| E2[启发式规则提取商品]
    E1 --> E3[保存商品表]
    E2 --> E3
    E3 --> End1([返回识别结果])

    F --> G{LLM 是否启用}
    G -->|是| H1[LLM 解析接龙人/商品/数量]
    G -->|否| H2[正则解析接龙文本]
    H1 --> H3[保存订单表]
    H2 --> H3
    H3 --> End2([返回订单记录])

    J --> K[读取商品表与订单表]
    K --> L[匹配商品与订单]
    L --> M[生成采购物品详单]
    L --> N[生成采购人详单]
    L --> O[生成未匹配清单]
    M --> End3([返回采购汇总])
    N --> End3
    O --> End3
```

## 2. 指令说明

| 指令 | 功能 | 示例 |
|------|------|------|
| `/sams_scan` | 识别图片中的购物小票/商品截图，更新商品表 | `/sams_scan` + 图片 |
| `/sams_add` | 手动录入商品信息 | `/sams_add 牛奶 25.0` 或 `/sams_add 牛奶 25.0 10` |
| `/sams_edit` | 修改商品单价 | `/sams_edit 牛奶 26.0` |
| `/sams_rename` | 重命名商品 | `/sams_rename 牛奶 蒙牛纯牛奶` |
| `/sams_list` | 查看当前商品表 | `/sams_list` |
| `/sams_delete` | 删除商品信息 | `/sams_delete 牛奶` |
| `/sams_order` | 提交或解析接龙信息 | `/sams_order 张三 牛奶 2` 或粘贴接龙文本 |
| `/sams_remove_order` | 移除指定接龙记录 | `/sams_remove_order 张三` 或 `/sams_remove_order 张三 牛奶` |
| `/sams_clear_order` | 清空订单表（保留商品表） | `/sams_clear_order` |
| `/sams_summary` | 输出完整采购汇总表格 | `/sams_summary` |
| `/sams_clear` | 清空当前会话数据 | `/sams_clear` |
| `/sams_help` | 显示帮助信息 | `/sams_help` |

### 2.1 配置说明

插件通过 `_conf_schema.json` 在 AstrBot WebUI 中提供可视化配置：

- **腾讯云 OCR**
  - `secret_id` / `secret_key` / `region`：调用腾讯云通用印刷体识别服务。
- **大模型（可选）**
  - `llm_provider` / `llm_api_key` / `llm_base_url` / `llm_model`：用于智能解析接龙文本和 OCR 结果。
  - `use_llm_for_order`：是否启用 LLM 解析接龙。
  - `use_llm_for_ocr`：是否启用 LLM 分析 OCR 商品提取。

未配置 LLM 时，插件自动回退到本地正则/启发式解析。

## 3. 技术栈与依赖

### 3.1 开发语言与框架
- **Python 3.12+**
- **AstrBot Star 系统**：继承 `Star` 基类，使用 `@register` 装饰器注册插件。

### 3.2 异步网络请求
- 使用 `aiohttp` 或 `httpx` 进行异步 HTTP 请求。
- **禁止**使用 `requests` 库（同步阻塞）。

### 3.3 OCR 服务
- 使用 **腾讯云 OCR**（推荐通用印刷体识别高精度版 `GeneralAccurateOCR`）。

### 3.4 数据持久化
- 使用 AstrBot 提供的 `PluginKVStoreMixin` 进行键值存储。
- 数据存储在 `data/plugins/<插件名>/` 目录下，防止插件更新/重装时数据被覆盖。
- 商品表采用 JSON 格式持久化，新数据覆盖旧数据。
- 图片也按日期文件夹分类保存。

### 3.5 依赖管理
- 在插件目录下创建 `requirements.txt` 声明依赖，方便 AstrBot 用户侧安装。
- 本地开发使用 **Poetry** 管理依赖，通过 `poetry add` 添加，`poetry run python` 运行。

## 4. 目录结构

```
astrbot_plugin_sams/
├── main.py                    # 插件入口，Star 类定义
├── metadata.yaml              # 插件元数据
├── _conf_schema.json          # AstrBot WebUI 配置 Schema
├── requirements.txt           # Python 依赖（用户侧）
├── pyproject.toml             # Poetry 配置（开发侧）
├── README.md                  # 使用说明
├── AGENTS.md                  # 本指南
├── PLAN.md                    # 开发计划与实施记录
├── services/
│   ├── __init__.py
│   ├── ocr_service.py         # OCR 识别服务封装
│   ├── llm_service.py         # 大模型服务封装
│   ├── parser_service.py      # 接龙文本解析服务
│   └── data_service.py        # 数据持久化服务
├── utils/
│   ├── __init__.py
│   └── helpers.py             # 工具函数（清洗、匹配、汇总）
└── tests/
    ├── __init__.py
    ├── test_parser.py         # 解析服务测试
    ├── test_helpers.py        # 工具函数测试
    └── test_llm_service.py    # 大模型服务测试
```

> 目录结构可根据实现需要调整，但需在本文件或 `PLAN.md` 中同步记录。

## 5. 开发规范

### 5.1 代码规范
- 使用 **ruff** 工具格式化代码。
- 核心逻辑需包含良好注释。
- 功能需经过测试。

### 5.2 日志规范
- 使用 `from astrbot.api import logger` 获取日志对象。
- **禁止**直接使用 Python 的 `logging` 模块。
- 关键操作（如 OCR 调用、数据更新）需记录 `INFO` 级别日志。

### 5.3 错误处理
- 具备良好的错误处理机制，避免插件因单个错误崩溃。
- OCR 识别失败时返回友好提示。
- 解析失败时提示用户检查格式。

### 5.4 数据存储
- 持久化数据必须存储于 `data/` 目录下。
- **禁止**将数据存储在插件自身目录。
- 使用 `PluginKVStoreMixin` 提供的 `put_async` / `get_async` 方法。

## 6. 参考资料

- [AstrBot 源码](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件开发指南（中文）](https://docs.astrbot.app/dev/star/plugin-new.html)
- [AstrBot 插件开发指南（英文）](https://docs.astrbot.app/en/dev/star/plugin-new.html)
- [AstrBot 插件模板](https://github.com/Soulter/helloworld)
- [腾讯云 OCR 文档](https://cloud.tencent.com/document/product/866/33526)
