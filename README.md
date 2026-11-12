# 🤖 星辰商城 · 智能客服 Agent

基于 **RAG + ReAct Agent + LangChain + Streamlit + ChromaDB** 的电商智能客服系统，支持 Ollama 本地大模型部署。

## ✨ 核心特性

| 特性 | 说明 |
|---|---|
| 🧠 **ReAct 推理** | 基于 LangGraph `create_react_agent`，自主思考 → 调用工具 → 观察结果 → 最终回答 |
| 📚 **RAG 知识库** | ChromaDB 本地持久化向量库，支持 md/txt/pdf/docx，自动切分与 Top-K 检索 |
| 💾 **记忆持久化** | 基于 SQLite checkpointer，多轮对话历史自动落盘，重启程序不丢失 |
| 🔌 **LLM 统一封装** | 一处配置切换 Ollama / OpenAI / 通义千问 / DeepSeek（OpenAI 兼容接口） |
| 🛠 **可扩展工具** | 内置知识库检索、订单查询、物流查询、退款申请、库存查询 5 个工具 |
| 🗄 **业务数据落库** | 订单/物流/库存三表入 SQLite，多表 JOIN 关联，退款等写操作真实更新数据库 |
| 🖥 **Streamlit 界面** | 流式输出、工具调用可视化、侧边栏知识库测试、一键开新会话 |

## 📁 项目结构

```
ecommerce_agent_cs/
├── app.py                  # Streamlit 主应用
├── ingest.py               # 知识库入库脚本
├── debug_db.py             # 分层自检脚本（向量库/记忆库/Agent）
├── requirements.txt
├── .env.example            # 环境变量模板
├── config/
│   └── settings.py         # 全局配置
├── core/
│   ├── llm.py              # LLM 统一封装（Ollama/OpenAI 切换）
│   ├── embeddings.py       # Embedding 统一封装
│   └── prompts.py          # 系统提示词
├── rag/
│   ├── document_loader.py  # 文档加载与切分
│   ├── vector_store.py     # ChromaDB 封装
│   └── retriever.py        # 检索器
├── agent/
│   ├── tools.py            # Agent 工具集（订单/物流/退款/库存/知识库）
│   ├── memory.py           # SQLite 记忆持久化
│   └── react_agent.py      # ReAct Agent 封装
├── db/                     # 业务数据访问层（订单/物流/库存）
│   ├── schema 由 data/schema.sql 定义
│   ├── connection.py       # SQLite 连接单例（避免 closed database）
│   ├── business_repo.py    # 参数化 SQL 查询与退款事务
│   └── seed_mock_data.py   # 模拟数据生成器（120/120/111 条）
├── scripts/
│   └── init_mock_db.py     # 重建业务数据库的命令行入口
└── data/
    ├── schema.sql          # 三张表建表语句（含索引与外键）
    ├── seed_data.sql       # 纯 INSERT 脚本（可直接导入数据库工具）
    ├── ecommerce.db        # 业务数据库（自动生成，已 gitignore）
    ├── knowledge_base/     # 知识库文档（放这里）
    ├── chroma_db/          # ChromaDB 持久化（自动生成）
    └── conversations/      # 对话记忆 SQLite（自动生成）
```

## 🚀 快速开始

### 1. 安装 Ollama 并拉取模型（本地部署）

```bash
# 安装 Ollama: https://ollama.com/download
ollama pull qwen3:4b              # 对话模型（约 2.5GB，支持工具调用）
ollama pull qwen3-embedding:4b    # 嵌入模型（约 2.5GB，输出 2560 维向量）
```

### 2. 安装 Python 依赖

```bash
cd ecommerce_agent_cs
pip install -r requirements.txt
cp .env.example .env
```

### 3. 初始化业务数据库

```bash
python scripts/init_mock_db.py            # 首次生成
python scripts/init_mock_db.py --rebuild  # 删库重建（改了造数逻辑时用）
```

生成订单 120 条、物流 111 条、库存 120 条。若跳过这一步，程序首次查询时会自动创建。

> 数据用固定随机种子生成，每次重建结果完全一致，方便截图与复现。

### 4. 入库知识库

把你的产品文档、退换货政策、FAQ 等放到 `data/knowledge_base/`，然后：

```bash
python ingest.py            # 首次或增量入库
python ingest.py --rebuild  # 清空重建
```

### 5. 启动应用

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501` 即可。

## 🗄 业务数据模型（SQLite 三表）

| 表 | 行数 | 说明 | 关键字段 |
|---|---|---|---|
| `orders` | 120 | 订单状态 | `order_no` 订单号、`product_sku`、`status`、`tracking_no` |
| `shipments` | 111 | 快递物流 | `tracking_no` 物流单号、`order_no`、`track_detail`（JSON 轨迹） |
| `inventory` | 120 | 商品库存 | `sku`、`price`、`stock`、`restock_eta` |

三表通过三个关键字关联：

```
orders.order_no      ─────▶  shipments.order_no       （订单反查物流）
orders.tracking_no   ─────▶  shipments.tracking_no    （物流单号回填订单）
orders.product_sku   ─────▶  inventory.sku            （订单关联库存）
```

一条 SQL 把三张表串起来（订单 → 物流 → 库存）：

```sql
SELECT o.order_no, o.status, o.amount,
       s.tracking_no, s.carrier, s.status AS logistics_status,
       i.stock, i.warehouse
FROM orders o
LEFT JOIN shipments s ON o.tracking_no = s.tracking_no
LEFT JOIN inventory i ON o.product_sku = i.sku
WHERE o.order_no = 'SO20261101001';
```

数据相关文件：

- `data/schema.sql`：建表 DDL，含索引与外键约束
- `data/seed_data.sql`：纯 INSERT 脚本，可用 Navicat / DB Browser 直接导入查看
- `db/business_repo.py`：全部使用参数化 SQL，`apply_refund` 会真实 UPDATE 订单状态

> **为什么用数据库而不是写死字典**：字典改一条数据要改代码；换成 SQLite 后数据与代码解耦，并且能演示参数化查询、多表 JOIN、真实写操作与事务。接入真实后端时，只需替换 `db/business_repo.py` 的查询实现，工具层和 Agent 逻辑都不用动。

## 🔄 切换大模型

编辑 `.env`：

**用 Ollama 本地模型（默认）：**
```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3:4b
OLLAMA_EMBED_MODEL=qwen3-embedding:4b
OLLAMA_THINK=false        # Qwen3 关闭思考过程输出
OLLAMA_NUM_CTX=4096       # 上下文窗口，多轮对话被截断时调大
```

> 换 Qwen3 系列后注意两点：Qwen3 默认会输出思考块，本项目已通过 `OLLAMA_THINK=false` + prompt 中的 `/no_think` 关闭；换嵌入模型后维度变化（2560），必须执行 `python ingest.py --rebuild`。

**用 OpenAI / DeepSeek / 通义千问（OpenAI 兼容接口）：**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.deepseek.com/v1   # 或 DashScope / OneAPI 地址
OPENAI_MODEL=deepseek-chat
OPENAI_EMBED_MODEL=text-embedding-3-small
```

## 🧪 试试这些问题

- "帮我查一下订单 SO20261101001 到哪了？" → 自动调用 `query_order` + `query_logistics`
- "退换货政策是怎样的？运费谁出？" → 自动调用 `search_knowledge_base`
- "降噪耳机 Pro 现在有货吗？多少钱？" → 自动调用 `check_product_stock`
- "我要退掉订单 SO20261101003，不想要了" → 自动调用 `apply_refund`

## 🛠 扩展业务工具

在 `agent/tools.py` 里用 `@tool` 装饰器加新函数，然后把它加进 `ALL_TOOLS` 列表即可，Agent 会自动学会调用。

示例：
```python
@tool
def query_coupon(user_id: str) -> str:
    """查询用户可用优惠券。"""
    ...
```

## 📝 说明

- 订单/物流/库存存放在本地 SQLite（`data/ecommerce.db`），由 `db/seed_mock_data.py` 生成；接入真实业务系统时，只需替换 `db/business_repo.py` 的查询实现，工具层与 Agent 逻辑无需改动。
- 业务数据库连接使用进程级单例 + `check_same_thread=False`，原因和 ChromaDB 的单例改造一致：避免 Streamlit 反复重跑脚本时旧连接被 GC 关闭，抛 `Cannot operate on a closed database`。
- 记忆持久化用 LangGraph 的 `SqliteSaver`，重启 Streamlit 后同一会话的历史会自动恢复。
- 流式输出同时捕获工具调用事件，前端会显示 "🔧 已调用工具: xxx"。
- Qwen3 的思考内容做三层处理：模型侧 `OLLAMA_THINK=false` 尽量从源头关闭（依次尝试 `reasoning` / `think` / `model_kwargs` 三种参数）；输出侧 `core/think_filter.py` 负责清洗，兼容 `</think>`、`<|end_of_thinking|>`、Qwen3 特殊 token 三种收尾标记；前端流式过程中正常打字，**流结束后用 `st.empty()` 占位做一次整块覆盖**，页面上最终只保留回答结果。
