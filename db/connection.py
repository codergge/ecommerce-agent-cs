"""
业务数据库连接管理（SQLite 进程级单例）

为什么必须是单例：
    Streamlit 每次交互都会重跑一遍脚本。如果每次调用都 sqlite3.connect() 新建连接，
    旧连接被 Python 垃圾回收时会把底层文件句柄关掉，后续查询就会抛
    "Cannot operate on a closed database"。
    因此这里和 rag/vector_store.py、agent/memory.py 保持一致，统一用进程级单例。

check_same_thread=False：
    Streamlit 会把请求分发到不同线程，SQLite 默认禁止跨线程使用同一连接，
    关掉该限制并由单例统一管理读写。当前场景为单用户演示，够用；
    生产多用户应改为连接池或 Postgres。
"""
import os
import sqlite3
import threading

from config.settings import settings

_CONN = None
_LOCK = threading.RLock()


def ensure_database() -> bool:
    """
    确保业务数据库存在。不存在则自动生成（首次 clone 项目后直接运行即可）。

    Returns:
        True 表示本次新建了数据库，False 表示已存在。
    """
    if os.path.exists(settings.BUSINESS_DB_PATH):
        return False

    # 延迟导入，避免模块循环依赖
    from db.seed_mock_data import create_database

    print("[DB] 未检测到业务数据库，正在自动生成模拟数据...")
    create_database(rebuild=True, verbose=True)
    return True


def get_business_conn() -> sqlite3.Connection:
    """获取业务数据库连接（进程级单例，线程安全创建）"""
    global _CONN
    if _CONN is None:
        with _LOCK:
            if _CONN is None:
                ensure_database()
                conn = sqlite3.connect(
                    settings.BUSINESS_DB_PATH,
                    check_same_thread=False,
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                _CONN = conn
    return _CONN


def reset_business_conn() -> None:
    """关闭并重置单例连接（重建数据库后必须调用，否则旧连接指向已删除的文件）"""
    global _CONN
    with _LOCK:
        if _CONN is not None:
            try:
                _CONN.close()
            except Exception:
                pass
            _CONN = None
