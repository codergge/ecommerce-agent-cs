"""
ChromaDB 向量库封装：持久化到本地磁盘，支持增量入库与相似检索。

【重要】Chroma 实例必须进程内单例。
每次 new 一个 Chroma，底层 PersistentClient 的 sqlite 连接会被旧实例的 GC 关闭，
随后再访问就会报 "Cannot operate on a closed database"。
"""
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document

from config.settings import settings
from core.embeddings import get_embeddings

_VECTOR_STORE: Optional[Chroma] = None


def get_vector_store() -> Chroma:
    """返回进程内唯一的 Chroma 实例（懒加载单例）。"""
    global _VECTOR_STORE
    if _VECTOR_STORE is None:
        _VECTOR_STORE = Chroma(
            collection_name=settings.COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=settings.CHROMA_DIR,
        )
    return _VECTOR_STORE


def reset_vector_store() -> None:
    """丢弃当前单例，下次调用时重新打开（集合被删除后必须调用）。"""
    global _VECTOR_STORE
    _VECTOR_STORE = None


def add_documents(docs: List[Document]) -> None:
    """把切分好的文档写入向量库（增量）。"""
    if not docs:
        print("[chroma] 没有可入库的文档。")
        return
    vs = get_vector_store()
    vs.add_documents(docs)
    print(f"[chroma] 已写入 {len(docs)} 个文本块 -> {settings.CHROMA_DIR}")


def similarity_search(query: str, k: Optional[int] = None) -> List[Document]:
    """Top-K 相似检索。"""
    k = k or settings.TOP_K
    vs = get_vector_store()
    return vs.similarity_search(query, k=k)


def delete_collection() -> None:
    """清空整个集合（重建知识库时用）。"""
    vs = get_vector_store()
    try:
        vs.delete_collection()
        print("[chroma] 集合已删除。")
    finally:
        # 集合对象已失效，必须重开，否则后续写入会踩到已关闭的连接
        reset_vector_store()
