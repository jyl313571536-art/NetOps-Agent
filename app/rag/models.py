"""RAG 数据模型：文档与知识片段。

Citation 为领域共享模型，唯一定义在 app.models.diagnosis。
"""

from typing import Any

from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    """加载后的知识文档，保留来源信息。"""

    doc_id: str
    source: str
    doc_type: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeChunk(BaseModel):
    """切分后的知识片段，来源可追溯。"""

    chunk_id: str
    doc_id: str
    source: str
    content: str
    chunk_index: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    """检索命中的知识片段，带相似度分数。"""

    chunk_id: str
    source: str
    content: str
    score: float
    chunk_index: int = 0
