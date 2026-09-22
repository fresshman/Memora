"""RAG 检索增强子系统（本地离线）。

- chunker：话题时间窗 + 字符预算 + 滑窗分块
- embedder：本机 llama-server 跑 bge-m3 GGUF（/v1/embeddings）
- index：faiss 向量索引 + 元数据，按会话指纹持久化
- retriever：多路语义召回 + 规则时间线骨架 + 无向量降级
"""
from .chunker import Chunk, chunk_conversation
from .index import VectorStore
from .embedder import LlamaServerEmbedder, HashEmbedder, EmbedderUnavailable
from .retriever import (
    Retriever, RagContext, build_retriever, build_embedder,
    compress_conversation,
)

__all__ = [
    "Chunk", "chunk_conversation", "VectorStore",
    "LlamaServerEmbedder", "HashEmbedder", "EmbedderUnavailable",
    "Retriever", "RagContext", "build_retriever", "build_embedder",
    "compress_conversation",
]
