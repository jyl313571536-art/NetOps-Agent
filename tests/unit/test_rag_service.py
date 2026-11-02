"""RAG 服务与引用校验单元测试（Mock Embedding，离线）。"""

from app.rag.models import RetrievedChunk
from app.rag.service import extract_citations


class FakeEmbedding:
    """离线 Mock Embedding：确定性向量，不依赖模型下载。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    @staticmethod
    def _vec(text: str) -> list[float]:
        # 简单确定性映射：按字符码生成固定维度向量
        base = [0.0] * 8
        for index, ch in enumerate(text[:8]):
            base[index % 8] += (ord(ch) % 13) / 13.0
        return base


def _chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id="dns_troubleshooting.md#0",
            source="dns_troubleshooting.md",
            content="DNS 故障排查第一步是确认本机 DNS 配置。",
            score=0.92,
            chunk_index=0,
        ),
        RetrievedChunk(
            chunk_id="network_connectivity.md#1",
            source="network_connectivity.md",
            content="能 Ping 通网关但无法上网，最常见原因是 DNS 解析故障。",
            score=0.88,
            chunk_index=1,
        ),
    ]


def test_extract_valid_citations() -> None:
    """合法引用被正确提取并保留来源。"""
    answer = "建议检查 DNS 配置 [引用1]，这是常见原因 [引用2]。"
    cleaned, citations, invalid = extract_citations(answer, _chunks())
    assert len(citations) == 2
    assert invalid == []
    assert citations[0].marker == "[引用1]"
    assert citations[0].source == "dns_troubleshooting.md"
    assert citations[0].verified is True
    assert citations[1].source == "network_connectivity.md"
    assert "[引用1]" in cleaned


def test_extract_removes_fabricated_citations() -> None:
    """编造的引用（编号越界）被剔除，不允许通过。"""
    answer = "根据资料 [引用9]，故障原因是 DNS。"
    cleaned, citations, invalid = extract_citations(answer, _chunks())
    assert citations == []
    assert invalid == ["[引用9]"]
    assert "[引用9]" not in cleaned


def test_extract_mixed_valid_and_invalid() -> None:
    """混合引用：合法保留、非法剔除。"""
    answer = "参见 [引用1] 与 [引用42]。"
    cleaned, citations, invalid = extract_citations(answer, _chunks())
    assert len(citations) == 1
    assert invalid == ["[引用42]"]
    assert "[引用1]" in cleaned
    assert "[引用42]" not in cleaned


def test_extract_without_citations() -> None:
    """无引用标记时不产生引用。"""
    answer = "这是纯推断的结论。"
    cleaned, citations, invalid = extract_citations(answer, _chunks())
    assert citations == []
    assert invalid == []
    assert cleaned == answer


def test_extract_deduplicates_markers() -> None:
    """同一编号重复出现只计一次。"""
    answer = "[引用1] 与 [引用1] 是同一来源。"
    _, citations, _ = extract_citations(answer, _chunks())
    assert len(citations) == 1


def test_extract_handles_empty_retrieval() -> None:
    """检索为空时任何引用都被视为无效。"""
    answer = "参见 [引用1]。"
    cleaned, citations, invalid = extract_citations(answer, [])
    assert citations == []
    assert invalid == ["[引用1]"]
    assert "[引用1]" not in cleaned


def test_rag_service_search_with_fake_embedding(tmp_path) -> None:
    """RAG 服务可用 Mock Embedding 完成索引与检索。"""
    from app.core.config import Settings
    from app.rag.service import RagService

    settings = Settings(
        _env_file=None,
        mimo_api_key="",
        rag_kb_dir="data/knowledge_base",
        rag_persist_dir=str(tmp_path / "chroma"),
    )
    service = RagService(settings=settings, embedding=FakeEmbedding())
    indexed = service.index_knowledge_base()
    assert indexed > 0
    assert service.count() == indexed
    results = service.search("DNS 解析失败怎么办")
    assert results
    for item in results:
        assert item.source.endswith(".md")
        assert item.content
        assert 0.0 <= item.score <= 1.0


def test_rag_service_search_empty_query(tmp_path) -> None:
    """空查询返回空列表。"""
    from app.core.config import Settings
    from app.rag.service import RagService

    settings = Settings(
        _env_file=None,
        mimo_api_key="",
        rag_persist_dir=str(tmp_path / "chroma"),
    )
    service = RagService(settings=settings, embedding=FakeEmbedding())
    assert service.search("   ") == []
