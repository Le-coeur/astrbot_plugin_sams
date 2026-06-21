# astrbot_plugin_sams 开发计划

## 1. 项目目标
为 AstrBot 打造一个山姆团购接龙助手插件。管理员发送商品截图与接龙文本后，插件自动识别商品单价、汇总每个人要买什么、算出总价，并输出可复制的采购清单。

## 2. 已确认的需求与约束

### 2.1 业务需求
- 接收山姆 APP 商品截图，识别商品名称与单价。
- 接收微信群接龙文本，解析出“接龙人、商品、数量”。
- 将接龙信息与商品表匹配，生成：
  - 采购物品详单（商品、单价、数量、小计）。
  - 采购人详单（每人买了什么、各自小计）。
  - 未匹配清单（商品表里没有的接龙项）。
- 支持手动增删改商品、清空会话、查看帮助。

### 2.2 指令集
| 指令 | 功能 | 示例 |
|------|------|------|
| `/sams_scan` | 识别图片，更新商品表 | `/sams_scan` + 图片 |
| `/sams_add` | 手动添加商品 | `/sams_add 牛奶 25.0` 或 `/sams_add 牛奶 25.0 10` |
| `/sams_edit` | 修改商品单价 | `/sams_edit 牛奶 26.0` |
| `/sams_rename` | 重命名商品 | `/sams_rename 牛奶 蒙牛纯牛奶` |
| `/sams_list` | 查看商品表 | `/sams_list` |
| `/sams_delete` | 删除商品 | `/sams_delete 牛奶` |
| `/sams_order` | 提交/解析接龙 | `/sams_order 张三 牛奶 2` 或粘贴接龙文本 |
| `/sams_remove_order` | 移除指定接龙记录 | `/sams_remove_order 张三` 或 `/sams_remove_order 张三 牛奶` |
| `/sams_clear_order` | 清空订单表（保留商品表） | `/sams_clear_order` |
| `/sams_summary` | 输出汇总表格 | `/sams_summary` |
| `/sams_clear` | 清空商品表与订单表 | `/sams_clear` |
| `/sams_help` | 显示帮助 | `/sams_help` |

### 2.3 技术约束
- Python 3.12+，AstrBot Star 插件框架。
- 异步 HTTP：使用 `aiohttp` / `httpx`，禁止 `requests`。
- OCR：腾讯云 OCR（通用印刷体识别高精度版 `GeneralAccurateOCR`）。
- 持久化：AstrBot `PluginKVStoreMixin`，数据存 `data/plugins/astrbot_plugin_sams/`。
- 日志：`from astrbot.api import logger`，禁止原生 `logging`。
- 本地开发：禁用 pip/pip3，使用 `poetry add` 安装依赖；运行使用 `poetry run python`。
- 代码风格：`ruff` 格式化。

## 3. 目录结构（可调整）

> `AGENTS.md` 给出的目录结构并非强制不可改，以下结构根据实际实现需要优化，最终结构会在“实施记录”中同步更新。

```
astrbot_plugin_sams/
├── main.py                      # 插件入口，指令注册与分发
├── metadata.yaml                # 插件元数据
├── requirements.txt             # 用户侧依赖声明
├── pyproject.toml               # Poetry 依赖与项目配置
├── README.md                    # 使用说明
├── AGENTS.md                    # 项目指南（随实现同步更新）
├── PLAN.md                      # 本计划与实施记录
├── services/
│   ├── __init__.py
│   ├── data_service.py          # KV 持久化 + 图片按日期保存
│   ├── ocr_service.py           # 腾讯云 OCR 封装
│   └── parser_service.py        # 接龙文本解析
├── utils/
│   ├── __init__.py
│   └── helpers.py               # 价格清洗、商品匹配、汇总表格
└── tests/                       # 本地测试脚本（新增）
    ├── __init__.py
    ├── test_parser.py
    └── test_helpers.py
```

## 4. 实施步骤

### 步骤 1：整理说明文档
- 重写 `AGENTS.md`：用通顺中文重新梳理场景、指令、规范，去掉重复和歧义。
- 更新 `README.md`：补充安装、指令示例、注意事项。
- 完善 `metadata.yaml`：增加 `short_desc`、`astrbot_version`、`support_platforms` 等字段。

### 步骤 2：创建目录与依赖
- 创建 `services/`、`utils/`、`tests/` 包。
- 创建 `requirements.txt`，声明 `tencentcloud-sdk-python`、`aiohttp`。
- 使用 `poetry add` 同步依赖到 `pyproject.toml`。

### 步骤 3：实现核心服务
- `data_service.py`：读写 `products`（商品表）和 `orders`（订单表）；图片保存到 `data/plugins/astrbot_plugin_sams/images/<YYYY-MM-DD>/`。
- `ocr_service.py`：调用腾讯云 `GeneralAccurateOCR`；解析 `TextDetections[].DetectedText` 提取商品名与价格；失败时抛出友好异常。
- `parser_service.py`：支持单行 `/sams_order 张三 牛奶 2`；支持多行接龙文本自动拆分。
- `helpers.py`：价格清洗、商品名模糊匹配、汇总表格生成。

### 步骤 4：改造 `main.py`
- 注册 `/sams_scan`、`/sams_add`、`/sams_edit`、`/sams_rename`、`/sams_list`、`/sams_delete`、`/sams_order`、`/sams_remove_order`、`/sams_clear_order`、`/sams_summary`、`/sams_clear`、`/sams_help`。
- 每个 handler 加 try/except，异常返回中文提示，不崩溃。
- 使用 `logger.info` 记录 OCR 调用、数据更新。
- 从消息链中提取图片并下载。

### 步骤 5：本地测试
- 编写 `tests/test_parser.py` 与 `tests/test_helpers.py`。
- 使用 `poetry run python` 运行测试。

### 步骤 6：代码质量
- 运行 `ruff check .` 与 `ruff format .`。
- 修复所有警告。

## 5. 实施记录（实时同步）

| 时间 | 操作 | 结果 | 备注 |
|------|------|------|------|
| 2026-06-21 07:37 | 计划获批 | 退出 Plan Mode | 开始执行初始化，创建本 PLAN.md |
| 2026-06-21 07:38 | 重写 AGENTS.md | 完成 | 用通顺中文梳理场景、指令、规范与目录结构 |
| 2026-06-21 07:39 | 更新 README.md | 完成 | 补充安装、配置、指令示例与注意事项 |
| 2026-06-21 07:39 | 完善 metadata.yaml | 完成 | 新增 short_desc、astrbot_version、support_platforms |
| 2026-06-21 07:40 | 创建 services/、utils/、tests/ | 完成 | 含 __init__.py |
| 2026-06-21 07:41 | 创建 requirements.txt 并安装依赖 | 完成 | poetry add aiohttp、tencentcloud-sdk-python；dev 组添加 ruff |
| 2026-06-21 07:42 | 实现 data_service.py | 完成 | 使用 PluginKVStoreMixin，图片按日期保存 |
| 2026-06-21 07:44 | 实现 ocr_service.py | 完成 | 腾讯云 GeneralAccurateOCR，线程池异步调用 |
| 2026-06-21 07:45 | 实现 parser_service.py | 完成 | 支持单行、多行、数量后缀 |
| 2026-06-21 07:46 | 实现 utils/helpers.py | 完成 | 价格清洗、模糊匹配、汇总表格 |
| 2026-06-21 07:48 | 重写 main.py | 完成 | 注册 8 个指令，错误处理，图片提取 |
| 2026-06-21 07:49 | 编写测试脚本 | 完成 | test_parser.py、test_helpers.py |
| 2026-06-21 07:50 | 运行 ruff 检查与格式化 | 通过 | 修复 main.py 未使用导入 |
| 2026-06-21 07:50 | 运行本地测试 | 通过 | parser、helpers 测试均通过 |
| 2026-06-21 07:51 | 最终审查 | 完成 | 目录结构完整，.gitignore 已覆盖缓存文件 |
| 2026-06-21 07:55 | 扩容指令集 | 完成 | main.py 新增 /edit、/rename、/clear_order、/remove_order；/add 数量改为可选（库存含义） |
| 2026-06-21 07:56 | 更新 AGENTS.md / README.md | 完成 | 同步新指令表与使用示例 |
| 2026-06-21 07:57 | 新增 remove_orders 工具函数 | 完成 | 提取到 helpers.py 以便测试，main.py 调用该函数 |
| 2026-06-21 07:58 | 补充本地测试 | 完成 | test_helpers.py 增加 test_remove_orders |
| 2026-06-21 07:58 | 运行 ruff 与测试 | 通过 | ruff 检查/格式化通过，parser、helpers 测试通过 |
| 2026-06-21 07:59 | 同步 PLAN.md | 完成 | 追加扩容指令集的实施记录 |
| 2026-06-21 08:05 | 指令集加 sams_ 前缀 | 完成 | main.py 所有 `@filter.command` 改为 sams_ 前缀，文本解析与提示同步更新 |
| 2026-06-21 08:06 | 同步文档中的指令前缀 | 完成 | AGENTS.md、README.md、PLAN.md 指令表与示例全部改为 `/sams_*` |
| 2026-06-21 08:07 | 运行 ruff 与测试 | 通过 | ruff 检查/格式化通过，parser、helpers 测试通过 |
| 2026-06-21 08:07 | 同步 PLAN.md | 完成 | 追加指令前缀调整的实施记录 |
| 2026-06-21 08:10 | 在 AGENTS.md 补充流程图 | 完成 | 增加 Mermaid 运行流程图，含 LLM 分支 |
| 2026-06-21 08:11 | 创建 _conf_schema.json | 完成 | 配置 UI Schema，支持 OCR 与 LLM 参数可视化配置 |
| 2026-06-21 08:13 | 实现 services/llm_service.py | 完成 | OpenAI 兼容接口，支持 OCR 商品提取与接龙解析 |
| 2026-06-21 08:15 | 改造 main.py 集成 LLM | 完成 | 读取插件配置、初始化 LLM、/sams_scan 与 /sams_order 优先使用 LLM 并支持回退 |
| 2026-06-21 08:16 | 调整 parser_service | 完成 | 命令前缀改为 /sams_order |
| 2026-06-21 08:17 | 更新文档 | 完成 | AGENTS.md 增加配置说明与目录更新；README.md 增加 LLM/OCR 配置说明 |
| 2026-06-21 08:18 | 新增 LLM 测试 | 完成 | tests/test_llm_service.py |
| 2026-06-21 08:19 | 运行 ruff 与全部测试 | 通过 | parser、helpers、llm_service 测试均通过 |
| 2026-06-21 08:20 | 同步 PLAN.md | 完成 | 追加 LLM 与配置 Schema 的实施记录 |
| 2026-06-21 08:25 | 敏感信息检查 | 完成 | 未发现硬编码 SecretId/SecretKey/API Key；data/、.python-version 已加入 .gitignore |
| 2026-06-21 08:26 | SSH 推送到 GitHub | 完成 | 提交 21 个文件到 master 分支，仓库地址 git@github.com:Le-coeur/astrbot_plugin_sams.git |
