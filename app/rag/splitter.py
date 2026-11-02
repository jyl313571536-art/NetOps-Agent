"""知识文本切分。

使用 RecursiveCharacterTextSplitter 切分文档，
每个片段保留来源信息，便于引用追溯。
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.models import KnowledgeChunk, KnowledgeDocument


def split_document(
    document: KnowledgeDocument,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[KnowledgeChunk]:
    """把文档切分为带来源的知识片段。

    Args:
        document: 已加载的知识文档。
        chunk_size: 片段最大字符数。
        chunk_overlap: 片段重叠字符数。

    Returns:
        按顺序编号的 KnowledgeChunk 列表。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "；", " ", ""],
    )
    texts = splitter.split_text(document.content)
    chunks: list[KnowledgeChunk] = []
    for index, text in enumerate(texts):
        stripped = text.strip()
        if not stripped:
            continue
        chunks.append(
            KnowledgeChunk(
                chunk_id=f"{document.doc_id}#{index}",
                doc_id=document.doc_id,
                source=document.source,
                content=stripped,
                chunk_index=index,
                metadata=dict(document.metadata),
            )
        )
    return chunks


def split_documents(
    documents: list[KnowledgeDocument],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[KnowledgeChunk]:
    """批量切分文档。"""
    result: list[KnowledgeChunk] = []
    for document in documents:
        result.extend(
            split_document(
                document, chunk_size=chunk_size, chunk_overlap=chunk_overlap
            )
        )
    return result
