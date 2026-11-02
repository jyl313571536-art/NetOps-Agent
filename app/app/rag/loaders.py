"""知识库文档加载器。

支持 PDF / TXT / Markdown 三种格式，产出带来源信息的文档对象。
"""

import logging
from pathlib import Path

from pypdf import PdfReader

from app.rag.models import KnowledgeDocument

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".markdown"}


def load_document(path: Path) -> KnowledgeDocument:
    """加载单个知识文档，按扩展名分派解析器。

    Args:
        path: 文档路径。

    Returns:
        带来源信息的 KnowledgeDocument。

    Raises:
        ValueError: 不支持的文档格式。
        FileNotFoundError: 文件不存在。
    """
    if not path.is_file():
        raise FileNotFoundError(f"知识文档不存在: {path}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        content = _load_pdf(path)
        doc_type = "pdf"
    elif suffix in {".md", ".markdown"}:
        content = path.read_text(encoding="utf-8")
        doc_type = "markdown"
    elif suffix == ".txt":
        content = path.read_text(encoding="utf-8")
        doc_type = "txt"
    else:
        raise ValueError(f"不支持的文档格式: {suffix}")
    return KnowledgeDocument(
        doc_id=path.stem,
        source=path.name,
        doc_type=doc_type,
        content=content,
        metadata={"path": str(path), "suffix": suffix},
    )


def load_directory(directory: Path) -> list[KnowledgeDocument]:
    """加载目录下全部受支持的知识文档（按文件名排序）。"""
    if not directory.is_dir():
        logger.warning("知识库目录不存在: %s", directory)
        return []
    documents: list[KnowledgeDocument] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            documents.append(load_document(path))
        except (OSError, ValueError) as exc:
            logger.warning("跳过无法加载的文档 %s: %s", path.name, exc)
    return documents


def _load_pdf(path: Path) -> str:
    """提取 PDF 全文，逐页拼接。"""
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages)
