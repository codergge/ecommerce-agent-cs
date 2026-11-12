"""
Streamlit 主应用：电商智能客服前端。
运行：streamlit run app.py
"""
import os
import streamlit as st

from agent.react_agent import CustomerServiceAgent
from agent.memory import new_thread_id
from agent.tools import query_order
from core.llm import get_llm_name
from core.think_filter import strip_think
from db.business_repo import get_stats
from rag.retriever import retrieve_with_meta

# ============ 页面配置 ============
st.set_page_config(
    page_title="星辰商城 · 智能客服",
    page_icon="🤖",
    layout="wide",
)

# ============ 会话状态初始化 ============
if "thread_id" not in st.session_state:
    st.session_state.thread_id = new_thread_id()
if "agent" not in st.session_state:
    st.session_state.agent = CustomerServiceAgent(thread_id=st.session_state.thread_id)
if "messages" not in st.session_state:
    st.session_state.messages = []  # 仅用于前端展示，真实历史在 SQLite 里

# ============ 侧边栏 ============
with st.sidebar:
    st.header("⚙️ 系统状态")
    st.markdown(f"**当前模型**: `{get_llm_name()}`")
    st.markdown(f"**会话 ID**: `{st.session_state.thread_id}`")

    st.divider()
    if st.button("🆕 开启新会话", use_container_width=True):
        st.session_state.thread_id = new_thread_id()
        st.session_state.agent = CustomerServiceAgent(thread_id=st.session_state.thread_id)
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.subheader("🗄 业务数据（SQLite）")
    try:
        stats = get_stats()
        st.caption(
            f"订单 {stats['orders']} 条 ｜ 物流 {stats['shipments']} 条 ｜ 库存 {stats['inventory']} 条"
        )
    except Exception as e:
        st.caption(f"业务库未就绪：{e}")

    demo_order = st.text_input("订单号快速查询", value="SO20261101001")
    if st.button("查询订单详情", use_container_width=True):
        st.code(query_order.invoke({"order_id": demo_order}), language="text")

    st.divider()
    st.subheader("🔍 知识库检索测试")
    test_q = st.text_input("输入测试问题", placeholder="例如：退货运费谁出？")
    if st.button("检索") and test_q:
        with st.spinner("检索中..."):
            hits = retrieve_with_meta(test_q, k=3)
            for h in hits:
                with st.expander(f"片段 {h['index']} · {os.path.basename(h['source'])}"):
                    st.write(h["content"])

    st.divider()
    st.caption("💡 提示：可先运行 `python ingest.py` 入库知识库")

# ============ 主聊天区 ============
st.title("🤖 星辰商城 · 智能客服")
st.caption("我是小星，可帮你查订单、查物流、申请退款、解答平台规则。试试问我：")

# 示例提示
example_cols = st.columns(3)
examples = [
    "帮我查一下订单 SO20261101001 到哪了？",
    "你们退换货政策是怎样的？",
    "降噪耳机 Pro 现在有货吗？",
]
for col, ex in zip(example_cols, examples):
    if col.button(ex, use_container_width=True):
        st.session_state.pending_input = ex

# 渲染历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 用户输入
user_input = st.chat_input("请输入你的问题...")
if "pending_input" in st.session_state:
    user_input = st.session_state.pending_input
    del st.session_state.pending_input

if user_input:
    # 展示用户消息
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 流式展示回复
    with st.chat_message("assistant"):
        full_answer = ""

        try:
            # 用官方 st.write_stream 做增量追加，避免每 token 重绘整块 markdown
            # 导致前端 React 反复卸载/挂载 DOM 节点（典型报错：removeChild ... not a child of this node）
            holder = {}
            stream_box = st.empty()   # 占位：流式期间在这里打字，结束后整块替换

            def _stream():
                for event_type, payload in st.session_state.agent.chat_stream(user_input):
                    if event_type == "tool_event":
                        # 工具提示走 toast 浮层，不占用主内容区的节点树
                        st.toast(payload, icon="🔧")
                    elif event_type == "token":
                        yield payload
                    elif event_type == "done":
                        # done 里是已剔除思考块的完整文本，用于覆盖渲染与写入历史
                        holder["text"] = payload

            streamed = stream_box.write_stream(_stream()) or ""

            # 关键一步：流结束时做一次整块覆盖
            # - 流式过程中显示过的 Qwen3 思考内容会被清除
            # - 页面最终只保留 done 事件给出的最终回答
            # 这里是单次替换（不是每 token 重绘），不会触发前端 removeChild 报错
            full_answer = holder.get("text") or strip_think(streamed)
            stream_box.markdown(full_answer or "（本次没有生成内容）")
        except Exception as e:
            # 打印完整堆栈到终端，便于定位是 Chroma 还是 SQLite 记忆的连接问题
            import traceback
            traceback.print_exc()
            full_answer = f"⚠️ 调用出错：{e}"
            st.error(full_answer)
            with st.expander("查看完整报错栈"):
                st.code(traceback.format_exc())

    st.session_state.messages.append({"role": "assistant", "content": full_answer})
