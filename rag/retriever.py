"""
检索器封装：对外提供一个 retriever 对象和一个带引用的检索函数。
"""
from typing import List, Dict

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from config.settings import settings
from rag.vector_store import get_vector_store, similarity_search


def get_retriever(k: int = None) -> BaseRetriever:
    """返回 LangChain Retriever 对象，可直接接到 chain / agent 中。"""
    vs = get_vector_store()
    return vs.as_retriever(search_kwargs={"k": k or settings.TOP_K})


def retrieve_with_meta(query: str, k: int = None) -> List[Dict]:
    """
    检索并返回带元信息的结果，便于在前端展示引用来源。
    """
    docs: List[Document] = similarity_search(query, k=k)
    results = []
    for i, d in enumerate(docs, 1):
        results.append({
            "index": i,
            "content": d.page_content,
            "source": d.metadata.get("source", "未知来源"),
            "metadata": d.metadata,
        })
    return results


def format_docs(docs: List[Document]) -> str:
    """把检索结果拼成上下文字符串，喂给 LLM。"""
    return "\n\n---\n\n".join(
        f"[来源: {d.metadata.get('source', '未知')}]\n{d.page_content}" for d in docs
    )
