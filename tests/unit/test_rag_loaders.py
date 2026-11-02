"""RAG 加载器与切分器单元测试。"""

from pathlib import Path

import pytest

from app.rag.loaders import load_directory, load_document
from app.rag.splitter import split_document, split_documents

KB_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge_base"


def test_load_markdown() -> None:
    """加载 Markdown 文档并保留来源。"""
    doc = load_document(KB_DIR / "dns_troubleshooting.md")
    assert doc.doc_id == "dns_troubleshooting"
    assert doc.source == "dns_troubleshooting.md"
    assert doc.doc_type == "markdown"
    assert "DNS" in doc.content


def test_load_txt(tmp_path: Path) -> None:
    """加载 TXT 文档。"""
    path = tmp_path / "note.txt"
    path.write_text("这是一段纯文本知识", encoding="utf-8")
    doc = load_document(path)
    assert doc.doc_type == "txt"
    assert doc.content == "这是一段纯文本知识"


def test_load_pdf(tmp_path: Path) -> None:
    """加载 PDF 文档（用 pypdf 生成的最小 PDF）。"""
    from pypdf import PdfWriter

    path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as fp:
        writer.write(fp)
    doc = load_document(path)
    assert doc.doc_type == "pdf"
    assert doc.source == "sample.pdf"


def test_load_unsupported_format(tmp_path: Path) -> None:
    """不支持的格式抛出 ValueError。"""
    path = tmp_path / "image.png"
    path.write_bytes(b"fake")
    with pytest.raises(ValueError):
        load_document(path)


def test_load_missing_file(tmp_path: Path) -> None:
    """文件不存在抛出 FileNotFoundError。"""
    with pytest.raises(FileNotFoundError):
        load_document(tmp_path / "missing.md")


def test_load_directory_skips_unknown(tmp_path: Path) -> None:
    """目录加载跳过不支持的文件。"""
    (tmp_path / "a.md").write_text("内容 A", encoding="utf-8")
    (tmp_path / "b.png").write_bytes(b"fake")
    docs = load_directory(tmp_path)
    assert len(docs) == 1
    assert docs[0].source == "a.md"


def test_load_real_knowledge_base() -> None:
    """真实知识库目录可加载出多篇文档。"""
    docs = load_directory(KB_DIR)
    assert len(docs) >= 4
    sources = {d.source for d in docs}
    assert "dns_troubleshooting.md" in sources


def test_split_document_keeps_source() -> None:
    """切分后片段保留来源与顺序编号。"""
    doc = load_document(KB_DIR / "network_connectivity.md")
    chunks = split_document(doc, chunk_size=200, chunk_overlap=20)
    assert chunks
    for index, chunk in enumerate(chunks):
        assert chunk.chunk_index == index
        assert chunk.source == "network_connectivity.md"
        assert chunk.doc_id == "network_connectivity"
        assert chunk.content


def test_split_long_document_produces_multiple_chunks() -> None:
    """长文档按 chunk_size 切分出多个片段。"""
    doc = load_document(KB_DIR / "network_connectivity.md")
    chunks = split_document(doc, chunk_size=100, chunk_overlap=10)
    assert len(chunks) > 1


def test_split_documents_batch() -> None:
    """批量切分保留全部来源。"""
    docs = load_directory(KB_DIR)
    chunks = split_documents(docs, chunk_size=300, chunk_overlap=30)
    sources = {c.source for c in chunks}
    assert len(sources) >= 4
