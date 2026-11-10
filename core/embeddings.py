"""
统一封装 Embedding 模型：同样支持 Ollama 本地嵌入 / OpenAI 嵌入切换。
"""
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings

from config.settings import settings


def get_embeddings() -> Embeddings:
    provider = settings.EMBEDDING_PROVIDER.lower()

    if provider == "ollama":
        return OllamaEmbeddings(
            model=settings.OLLAMA_EMBED_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )

    elif provider in ("openai", "dashscope", "deepseek"):
        if not settings.OPENAI_API_KEY:
            raise ValueError("未配置 OPENAI_API_KEY，无法使用 OpenAI 嵌入。")
        return OpenAIEmbeddings(
            model=settings.OPENAI_EMBED_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )

    else:
        raise ValueError(f"未知 EMBEDDING_PROVIDER={provider}")
