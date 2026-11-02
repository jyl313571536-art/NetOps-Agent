"""Chroma 向量库封装。

负责知识片段的向量化写入与 Top-K 相似度检索，
检索结果保留来源信息与相似度分数。
"""

import logging
from pathlib import Path

from app.rag.embeddings import EmbeddingProvider
from app.rag.models import KnowledgeChunk, RetrievedChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "netops_knowledge"


class VectorStore:
    """基于 Chroma 的向量存储。"""

    def __init__(
        self,
        embedding: EmbeddingProvider,
        persist_dir: str = "data/chroma_db",
    ) -> None:
        self._embedding = embedding
        self._persist_dir = persist_dir
        self._collection = None

    def _ensure_collection(self):
        """惰性创建 Chroma 持久化客户端与集合。"""
        if self._collection is None:
            import chromadb

            Path(self._persist_dir).mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def index_chunks(self, chunks: list[KnowledgeChunk]) -> int:
        """把知识片段向量化写入向量库，返回写入数量。

        已存在且内容未变的片段跳过，避免重复索引全量重跑 Embedding。
        """
        if not chunks:
            return 0
        collection = self._ensure_collection()
        # 查询已有片段的内容，用于变更检测
        fetched = collection.get(ids=[c.chunk_id for c in chunks])
        existing_docs = dict(
            zip(fetched.get("ids") or [], fetched.get("documents") or [])
        )
        to_index = [
            c for c in chunks if existing_docs.get(c.chunk_id) != c.content
        ]
        if not to_index:
            logger.info("知识片段无变化，跳过索引")
            return 0
        embeddings = self._embedding.embed_documents(
            [c.content for c in to_index]
        )
        collection.upsert(
            ids=[c.chunk_id for c in to_index],
            embeddings=embeddings,
            documents=[c.content for c in to_index],
            metadatas=[
                {
                    "source": c.source,
                    "doc_id": c.doc_id,
                    "chunk_index": c.chunk_index,
                }
                for c in to_index
            ],
        )
        logger.info(
            "已写入 %s 个知识片段到 %s", len(to_index), self._persist_dir
        )
        return len(to_index)

    def search(self, query: str, top_k: int = 4) -> list[RetrievedChunk]:
        """Top-K 相似度检索，返回带来源与分数的片段。"""
        collection = self._ensure_collection()
        total = collection.count()
        if total == 0:
            return []
        query_embedding = self._embedding.embed_query(query)
        rows = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, total),
            include=["documents", "metadatas", "distances"],
        )
        results: list[RetrievedChunk] = []
        ids = rows.get("ids", [[]])[0]
        documents = rows.get("documents", [[]])[0]
        metadatas = rows.get("metadatas", [[]])[0]
        distances = rows.get("distances", [[]])[0]
        for i, chunk_id in enumerate(ids):
            metadata = metadatas[i] if i < len(metadatas) else {}
            distance = distances[i] if i < len(distances) else 1.0
            # Chroma cosine 距离转相似度分数：1 - distance
            score = max(0.0, 1.0 - float(distance))
            results.append(
                RetrievedChunk(
                    chunk_id=str(chunk_id),
                    source=str(metadata.get("source", "unknown")),
                    content=documents[i] if i < len(documents) else "",
                    score=round(score, 4),
                    chunk_index=int(metadata.get("chunk_index", 0)),
                )
            )
        return results

    def count(self) -> int:
        """返回向量库中的片段数量。"""
        return self._ensure_collection().count()
