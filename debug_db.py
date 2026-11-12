"""
一键自检：定位 "Cannot operate on a closed database" 到底来自 Chroma 还是 SQLite 记忆。
用法：python debug_db.py
"""
import os
import sys
import traceback

print("=" * 60)
print("Python:", sys.version.split()[0])
try:
    import chromadb
    print("chromadb:", chromadb.__version__)
except Exception as e:
    print("chromadb 版本读取失败:", e)

# ---------- 1. 确认加载的是单例版代码 ----------
print("\n[1] 检查 vector_store 是否为单例版")
import rag.vector_store as v
has_singleton = hasattr(v, "_VECTOR_STORE")
print("    存在 _VECTOR_STORE 全局变量:", has_singleton)
print("    模块文件:", v.__file__)
if not has_singleton:
    print("    ❌ 仍是旧版！请替换 rag/vector_store.py")

# ---------- 2. 连续检索两次（模拟 Agent 两次调用知识库工具） ----------
print("\n[2] 连续检索两次")
try:
    r1 = v.similarity_search("退货运费谁出", k=2)
    print("    第1次 OK, 命中", len(r1), "条")
    r2 = v.similarity_search("保修多久", k=2)
    print("    第2次 OK, 命中", len(r2), "条")
    print("    两次是否同一实例:", v.get_vector_store() is v.get_vector_store())
except Exception:
    print("    ❌ 检索失败，堆栈如下：")
    traceback.print_exc()

# ---------- 3. checkpointer 单例 ----------
print("\n[3] 检查 checkpointer 单例与连接可用性")
try:
    from agent.memory import get_checkpointer
    c1 = get_checkpointer()
    c2 = get_checkpointer()
    print("    两次是否同一实例:", c1 is c2)
    n = len(list(c1.list({"configurable": {"thread_id": "debug-thread"}})))
    print("    list 查询 OK, 已有记录:", n)
except Exception:
    print("    ❌ checkpointer 失败，堆栈如下：")
    traceback.print_exc()

# ---------- 4. 业务数据库（订单/物流/库存） ----------
print("\n[4] 业务数据库三表 JOIN 与连接单例")
try:
    from db.connection import get_business_conn
    from db.business_repo import get_order_detail, get_stats

    c1 = get_business_conn()
    c2 = get_business_conn()
    print("    两次是否同一连接:", c1 is c2)
    print("    三表行数:", get_stats())
    o = get_order_detail("SO20261101001")
    print(f"    订单 JOIN: {o['order_no']} / {o['status']} / {o['carrier']} / 库存 {o['stock']}")
except Exception:
    print("    ❌ 业务数据库失败，堆栈如下：")
    traceback.print_exc()

# ---------- 5. 真正跑一轮 Agent（最容易复现的场景） ----------
print("\n[5] 走一轮完整 Agent 对话")
try:
    from agent.react_agent import CustomerServiceAgent
    a = CustomerServiceAgent(thread_id="debug-run")
    ans = a.chat("退货运费谁出？")
    print("    ✅ 回复:", ans[:100], "...")
    ans2 = a.chat("那质量问题退换货呢？")
    print("    ✅ 第二轮回复:", ans2[:100], "...")
except Exception:
    print("    ❌ 对话失败，堆栈如下：")
    traceback.print_exc()

print("\n" + "=" * 60)
print("自检结束。哪一步报错，问题就在那一步对应的模块。")
