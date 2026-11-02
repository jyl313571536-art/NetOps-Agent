"""RAG 服务：知识库索引与检索。

提供文档索引与 Top-K 知识检索能力，
引用校验保证回答中的引用可追溯到真实检索片段。
"""

import logging
import re
from pathlib import Path

from app.core.config import Settings, get_settings
from app.models.diagnosis import Citation
from app.rag.embeddings import BgeEmbedding, EmbeddingProvider
from app.rag.loaders import load_directory
from app.rag.models import RetrievedChunk
from app.rag.splitter import split_documents
from app.rag.store import VectorStore

logger = logging.getLogger(__name__)

CITATION_RE = re.compile(r"\[引用(\d+)\]")


class RagService:
    """RAG 服务，负责索引知识库与检索知识片段。"""

    def __init__(
        self,
        settings: Settings | None = None,
        embedding: EmbeddingProvider | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self._settings = cfg
        self._embedding = embedding or BgeEmbedding(cfg.rag_embedding_model)
        self._store = VectorStore(self._embedding, cfg.rag_persist_dir)

    def index_knowledge_base(self) -> int:
        """加载并索引整个知识库，返回写入的片段数量。"""
        directory = Path(self._settings.rag_kb_dir)
        documents = load_directory(directory)
        if not documents:
            logger.warning("知识库目录为空: %s", directory)
            return 0
        chunks = split_documents(
            documents,
            chunk_size=self._settings.rag_chunk_size,
            chunk_overlap=self._settings.rag_chunk_overlap,
        )
        return self._store.index_chunks(chunks)

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        """按查询检索 Top-K 知识片段。"""
        if not query.strip():
            return []
        return self._store.search(
            query, top_k=top_k or self._settings.rag_top_k
        )

    def count(self) -> int:
        """返回向量库中的片段数量。"""
        return self._store.count()


def extract_citations(
    answer: str, retrieved: list[RetrievedChunk]
) -> tuple[str, list[Citation], list[str]]:
    """从回答中提取引用并与真实检索片段比对。

    规则（对应 CLAUDE.md 第 7 节 Phase 3 验收）：
    1. [引用N] 按 N-1 映射到本次检索片段列表（1 起编号）。
    2. 编号越界的引用视为无效，从回答中剔除并单独标记。
    3. 有效引用必须来自真实检索结果，不允许编造来源。

    Args:
        answer: 模型生成的回答文本。
        retrieved: 本次真实检索到的片段列表。

    Returns:
        (清理后的回答, 有效引用列表, 无效引用编号列表)
    """
    valid: list[Citation] = []
    invalid: list[str] = []
    seen: set[int] = set()

    for match in CITATION_RE.finditer(answer):
        number = int(match.group(1))
        if number in seen:
            continue
        seen.add(number)
        if 1 <= number <= len(retrieved):
            chunk = retrieved[number - 1]
            valid.append(
                Citation(
                    marker=format_marker(number),
                    source=chunk.source,
                    snippet=chunk.content[:200],
                    score=chunk.score,
                    verified=True,
                )
            )
        else:
            invalid.append(format_marker(number))

    # 剔除无效引用标记，避免编造引用出现在最终回答中
    cleaned = answer
    for marker in invalid:
        cleaned = cleaned.replace(marker, "")
    return cleaned.strip(), valid, invalid


def format_marker(number: int) -> str:
    """引用标记的唯一格式源，与 CITATION_RE 配套使用。"""
    return f"[引用{number}]"


_rag_service: RagService | None = None


def get_rag_service() -> RagService:
    """获取 RAG 服务单例（FastAPI 依赖注入入口）。"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RagService()
    return _rag_service
