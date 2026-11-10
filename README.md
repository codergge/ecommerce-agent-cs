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
| 🖥 **Streamlit 界面** | 流式输出、工具调用可视化、侧边栏知识库测试、一键开新会话 |

## 📁 项目结构

```
ecommerce_agent_cs/
├── app.py                  # Streamlit 主应用
├── ingest.py               # 知识库入库脚本
├── requirements.txt
├── .env.example            # 环境变量模板
├── config/
│   └── settings.py          # 全局配置
├── core/
│   ├── llm.py              # LLM 统一封装（Ollama/OpenAI 切换）
│   ├── embeddings.py       # Embedding 统一封装
│   └── prompts.py          # 系统提示词
├── rag/
│   ├── document_loader.py  # 文档加载与切分
│   ├── vector_store.py     # ChromaDB 封装
│   └── retriever.py         # 检索器
├── agent/
│   ├── tools.py            # Agent 工具集（订单/物流/退款/库存/知识库）
│   ├── memory.py           # SQLite 记忆持久化
│   └── react_agent.py     # ReAct Agent 封装
└── data/
    ├── knowledge_base/     # 知识库文档（放这里）
    ├── chroma_db/           # ChromaDB 持久化（自动生成）
    └── conversations/       # 对话记忆 SQLite（自动生成）
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

### 3. 入库知识库

把你的产品文档、退换货政策、FAQ 等放到 `data/knowledge_base/`，然后：

```bash
python ingest.py            # 首次或增量入库
python ingest.py --rebuild  # 清空重建
```

### 4. 启动应用

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501` 即可。

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

- 订单/物流/库存目前是**模拟数据**（写在 `agent/tools.py`），实际使用时替换成真实后端 API 即可。
- 记忆持久化用 LangGraph 的 `SqliteSaver`，重启 Streamlit 后同一会话的历史会自动恢复。
- 流式输出同时捕获工具调用事件，前端会显示 "🔧 已调用工具: xxx"。
