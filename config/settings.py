"""
全局配置：通过 .env 或环境变量覆盖。
统一在这里集中管理 LLM 提供商、模型名、向量库路径等，便于灵活切换。
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _get_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # ---------- 大模型提供商 ----------
    # 可选: ollama / openai / dashscope(通义千问, OpenAI 兼容)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")

    # Ollama 本地部署
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:4b")
    # Qwen3 默认会输出思考过程，关掉可省 token、避免污染前端流式输出
    OLLAMA_THINK: bool = _get_bool("OLLAMA_THINK", False)
    # 上下文窗口：Ollama 默认常常只有 2048/4096，多轮对话容易被截断
    OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "4096"))

    # OpenAI / 兼容接口（如 Dashscope、DeepSeek、OneAPI 等）
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # ---------- 嵌入模型 ----------
    # Ollama 嵌入（推荐 qwen3-embedding:4b / bge-m3 / nomic-embed-text）
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "ollama")
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:4b")
    OPENAI_EMBED_MODEL: str = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

    # ---------- 向量库 ----------
    CHROMA_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "chroma_db"
    )
    COLLECTION_NAME: str = "ecommerce_kb"

    # ---------- 知识库 ----------
    KB_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "knowledge_base"
    )
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "80"))
    TOP_K: int = int(os.getenv("TOP_K", "4"))

    # ---------- 记忆 ----------
    CONV_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "conversations"
    )
    MEMORY_WINDOW: int = int(os.getenv("MEMORY_WINDOW", "10"))  # 保留最近 N 轮

    # ---------- 生成参数 ----------
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.3"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "120"))


settings = Settings()

# 确保目录存在
for _d in (settings.CHROMA_DIR, settings.KB_DIR, settings.CONV_DIR):
    os.makedirs(_d, exist_ok=True)
