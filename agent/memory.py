"""
记忆持久化：基于 LangGraph 的 SqliteSaver，把对话状态（消息历史）落到 SQLite 文件。
每个会话一个 thread_id，重启程序后历史自动恢复。

注意：SqliteSaver 来自独立包 langgraph-checkpoint-sqlite，不在 langgraph 主包里。
"""
import os
import sqlite3
from typing import Optional

from langgraph.checkpoint.sqlite import SqliteSaver

from config.settings import settings

# 全局单例：SQLite 连接复用，避免 Streamlit 每次 rerun 都新建连接导致写锁冲突
_CHECKPOINTER: Optional[SqliteSaver] = None
_DB_PATH: Optional[str] = None


def get_checkpointer(db_path: Optional[str] = None) -> SqliteSaver:
    """
    返回一个 SQLite checkpointer（进程内单例）。
    用法：agent.invoke({"messages": [...]}, config={"configurable": {"thread_id": "xxx"}})
    """
    global _CHECKPOINTER, _DB_PATH

    db_path = db_path or os.path.join(settings.CONV_DIR, "memory.sqlite")

    # 同一个库路径已初始化过，直接复用
    if _CHECKPOINTER is not None and _DB_PATH == db_path:
        return _CHECKPOINTER

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # check_same_thread=False 必须开启：
    # Streamlit 的每次 rerun 可能落在不同线程上，不放开会报
    # "SQLite objects created in a thread can only be used in that same thread"
    conn = sqlite3.connect(db_path, check_same_thread=False)
    _CHECKPOINTER = SqliteSaver(conn)
    _DB_PATH = db_path
    return _CHECKPOINTER


def new_thread_id() -> str:
    """生成一个新的会话 ID。"""
    import uuid
    return uuid.uuid4().hex[:12]
