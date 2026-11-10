"""
文档加载与切分：支持 txt / md / pdf / docx 格式的知识库文档。
"""
import os
from typing import List

from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    DirectoryLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config.settings import settings


def _build_loader(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return PyPDFLoader(file_path)
    if ext in (".docx", ".doc"):
        return Docx2txtLoader(file_path)
    if ext in (".txt", ".md"):
        return TextLoader(file_path, encoding="utf-8")
    return None


def load_documents(kb_dir: str = None) -> List[Document]:
    """加载知识库目录下所有支持的文档。"""
    kb_dir = kb_dir or settings.KB_DIR
    docs: List[Document] = []

    for fname in os.listdir(kb_dir):
        fpath = os.path.join(kb_dir, fname)
        if not os.path.isfile(fpath):
            continue
        loader = _build_loader(fpath)
        if loader is None:
            print(f"[skip] 不支持的文件类型: {fname}")
            continue
        try:
            loaded = loader.load()
            docs.extend(loaded)
            print(f"[load] {fname} -> {len(loaded)} 页/段")
        except Exception as e:
            print(f"[warn] 加载 {fname} 失败: {e}")

    return docs


def split_documents(docs: List[Document]) -> List[Document]:
    """递归切分文本，保留语义边界。"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n## ", "\n### ", "\n\n", "\n", "。", "！", "？", ";", " ", ""],
    )
    return splitter.split_documents(docs)
