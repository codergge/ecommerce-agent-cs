"""
统一封装大模型：通过 settings.LLM_PROVIDER 在 ollama / openai 之间切换。
对外暴露一个 get_chat_llm() 工厂函数，Agent 层无需关心底层是哪家模型。
"""
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from config.settings import settings


def _make_ollama(streaming: bool) -> BaseChatModel:
    """
    构造 ChatOllama，并在 OLLAMA_THINK=false 时尽量从源头关闭 Qwen3 的思考输出。

    不同版本的开关位置不同，按优先级依次尝试：
      1. ChatOllama(reasoning=False)     —— langchain-ollama 新版字段
      2. ChatOllama(think=False)         —— 部分版本直接透传
      3. model_kwargs={"think": False}   —— 兜底：Ollama 原生 /api/chat 支持 think 字段
    都不支持时退回普通构造，由 core/think_filter.py 在输出层兜底过滤，保证界面干净。
    """
    kwargs = dict(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=settings.TEMPERATURE,
        streaming=streaming,
        timeout=settings.REQUEST_TIMEOUT,
        num_ctx=settings.OLLAMA_NUM_CTX,
    )

    if settings.OLLAMA_THINK:
        return ChatOllama(**kwargs)

    fields = getattr(ChatOllama, "model_fields", {}) or {}
    for name in ("reasoning", "think"):
        if name in fields:
            try:
                return ChatOllama(**kwargs, **{name: False})
            except Exception:
                continue

    try:
        return ChatOllama(**kwargs, model_kwargs={"think": False})
    except Exception:
        return ChatOllama(**kwargs)


def get_chat_llm(streaming: bool = False) -> BaseChatModel:
    """
    根据配置返回一个 ChatModel 实例。
    所有下游（Agent、RAG chain）都通过这个入口拿模型，切换模型只改 .env。
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "ollama":
        return _make_ollama(streaming)

    elif provider in ("openai", "dashscope", "deepseek"):
        # 任何 OpenAI 兼容接口都走这里，靠 OPENAI_BASE_URL 区分
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                f"当前 LLM_PROVIDER={provider}，但未配置 OPENAI_API_KEY，"
                f"请在 .env 中填写或切换为 ollama。"
            )
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            temperature=settings.TEMPERATURE,
            streaming=streaming,
            timeout=settings.REQUEST_TIMEOUT,
        )

    else:
        raise ValueError(
            f"未知的 LLM_PROVIDER={provider}，可选: ollama / openai / dashscope / deepseek"
        )


def get_llm_name() -> str:
    """返回当前模型名，用于界面展示。"""
    if settings.LLM_PROVIDER.lower() == "ollama":
        return f"Ollama / {settings.OLLAMA_MODEL}"
    return f"{settings.LLM_PROVIDER.title()} / {settings.OPENAI_MODEL}"
