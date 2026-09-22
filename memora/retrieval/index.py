"""faiss 向量索引 + 块元数据，支持持久化缓存。"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .chunker import Chunk


class VectorStore:
    def __init__(self, chunks: list[Chunk], dim: int, index=None):
        self.chunks = chunks
        self.dim = dim
        if index is None:
            import faiss
            index = faiss.IndexFlatIP(dim)
        self.index = index

    # ---- 构建 ----
    @classmethod
    def build(cls, chunks: list[Chunk], embedder, batch_size: int = 8) -> "VectorStore":
        if not chunks:
            raise ValueError("没有可索引的块")
        vecs = embedder.embed([c.text for c in chunks], batch_size=batch_size)
        vecs = np.asarray(vecs, dtype="float32")
        import faiss
        faiss.normalize_L2(vecs)
        index = faiss.IndexFlatIP(vecs.shape[1])
        index.add(vecs)
        return cls(chunks, vecs.shape[1], index)

    # ---- 检索 ----
    def _search_one(self, qvec, k: int) -> list[tuple[Chunk, float]]:
        import faiss
        q = np.asarray(qvec, dtype="float32").reshape(1, -1)
        faiss.normalize_L2(q)
        k = min(k, self.index.ntotal)
        if k == 0:
            return []
        scores, ids = self.index.search(q, k)
        out = []
        for rank, idx in enumerate(ids[0]):
            if idx >= 0:
                out.append((self.chunks[int(idx)], float(scores[0][rank])))
        return out

    def search(self, qvec, k: int = 8) -> list[tuple[Chunk, float]]:
        return self._search_one(qvec, k)

    def search_many(self, qvecs, k_per_query: int = 6) -> list[tuple[Chunk, float]]:
        """多路 query 召回，按块取最高分合并去重，降序返回。"""
        best: dict[str, tuple[Chunk, float]] = {}
        for qv in qvecs:
            for ch, sc in self._search_one(qv, k_per_query):
                cur = best.get(ch.chunk_id)
                if cur is None or sc > cur[1]:
                    best[ch.chunk_id] = (ch, sc)
        return sorted(best.values(), key=lambda x: -x[1])

    # ---- 持久化 ----
    def save(self, dir_path: str | Path) -> None:
        d = Path(dir_path)
        d.mkdir(parents=True, exist_ok=True)
        import faiss
        faiss.write_index(self.index, str(d / "vec.index"))
        (d / "chunks.json").write_text(
            json.dumps({"dim": self.dim,
                        "chunks": [c.to_dict() for c in self.chunks]},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")

    @classmethod
    def load(cls, dir_path: str | Path) -> "VectorStore":
        import faiss
        d = Path(dir_path)
        index = faiss.read_index(str(d / "vec.index"))
        meta = json.loads((d / "chunks.json").read_text(encoding="utf-8"))
        chunks = [Chunk.from_dict(c) for c in meta["chunks"]]
        return cls(chunks, meta["dim"], index)
