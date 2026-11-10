"""
知识库入库脚本：把 data/knowledge_base/ 下的文档切分后写入 ChromaDB。
用法：
    python ingest.py            # 增量入库
    python ingest.py --rebuild  # 清空后重新入库
"""
import sys

from rag.document_loader import load_documents, split_documents
from rag.vector_store import add_documents, delete_collection, get_vector_store


def main(rebuild: bool = False):
    if rebuild:
        print(">>> 重建模式：先清空旧向量库 ...")
        try:
            delete_collection()
        except Exception as e:
            print(f"[warn] 清空失败（可能本来就没有）: {e}")

    print(">>> 加载文档 ...")
    docs = load_documents()
    if not docs:
        print("未加载到任何文档，请把 .md/.pdf/.docx 放到 data/knowledge_base/ 目录。")
        return

    print(">>> 切分文本 ...")
    splits = split_documents(docs)
    print(f"    共切出 {len(splits)} 个文本块。")

    print(">>> 写入 ChromaDB ...")
    add_documents(splits)

    # 验证（用公开 API 计数，避免不同 Chroma 版本私有属性差异）
    vs = get_vector_store()
    try:
        cnt = len(vs.get(include=[])["ids"])
    except Exception:
        cnt = vs._collection.count()
    print(f">>> 完成！当前向量库共 {cnt} 个文本块。")


if __name__ == "__main__":
    rebuild_flag = "--rebuild" in sys.argv
    main(rebuild=rebuild_flag)
