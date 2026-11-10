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
    构造 ChatOllama。
    Qwen3 系列默认会输出思考块（thinking），这里按 OLLAMA_THINK 配置尽量关闭：
    新版 langchain-ollama 用 reasoning=False，老版本不认这个参数就退回普通构造。
    """
    kwargs = dict(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=settings.TEMPERATURE,
        streaming=streaming,
        timeout=settings.REQUEST_TIMEOUT,
        num_ctx=settings.OLLAMA_NUM_CTX,
    )

    if not settings.OLLAMA_THINK:
        try:
            return ChatOllama(**kwargs, reasoning=False)
        except TypeError:
            # 老版本不支持 reasoning 参数，靠 prompt 里的 /no_think 兜底
            pass

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
