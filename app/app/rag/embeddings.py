"""BGE Embedding 封装。

使用 fastembed 本地推理 BGE 系列模型，无需 torch。
测试时可注入 Mock Embedding，不影响离线测试。
"""

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Embedding 协议：离线测试可注入 Mock 实现。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量向量化文档片段。"""
        ...

    def embed_query(self, text: str) -> list[float]:
        """向量化查询文本。"""
        ...


class BgeEmbedding:
    """BGE Embedding 提供者（fastembed 本地推理）。"""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5") -> None:
        """初始化时才加载模型，避免 import 副作用。"""
        self._model_name = model_name
        self._model = None

    def _ensure_model(self):
        """惰性加载 fastembed 模型。"""
        if self._model is None:
            from fastembed import TextEmbedding

            logger.info("加载 Embedding 模型: %s", self._model_name)
            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量向量化文档片段，返回纯 Python float 列表。"""
        model = self._ensure_model()
        embeddings = model.embed(texts)
        # fastembed 返回 numpy.float32，需转为纯 Python float 供 Chroma 使用
        return [[float(value) for value in vector] for vector in embeddings]

    def embed_query(self, text: str) -> list[float]:
        """向量化查询文本（BGE 查询前缀按模型约定处理）。"""
        model = self._ensure_model()
        # BGE 系列推荐查询侧加前缀以对齐检索效果
        query = text
        if "bge" in self._model_name.lower():
            query = f"为这个句子生成表示以用于检索相关文章：{text}"
        embeddings = list(model.embed([query]))
        return [float(value) for value in embeddings[0]]
