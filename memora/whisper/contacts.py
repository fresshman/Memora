"""跨会话联系人声纹库：姓名 <-> 声纹 embedding 持久化，跨会议自动识别同一人。

纯本地 JSON（默认 data/contacts.json），数据不出设备，离线可用。

- 当用户在某场会议把「说话人1」重命名为「张三」，该说话人的聚类声纹被注册入库；
- 下一场会议聚类后，每个聚类声纹与联系人库比对，高相似度即自动认出「张三」。
一名联系人可累积多个声纹样本（不同会议 / 录音条件），识别取最高相似度，更稳健。
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .. import config


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class Contact:
    id: str
    name: str
    embeddings: list[list[float]] = field(default_factory=list)
    meetings: int = 1
    created_at: str = ""
    last_met: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = _now()
        if not self.last_met:
            self.last_met = _now()


def cosine(a, b) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def cluster_centroid(embeddings, labels, label) -> list[float]:
    """某聚类所有段 embedding 的平均质心（再做 L2 归一化）。"""
    E = np.asarray(embeddings, dtype=np.float32)
    m = E[np.asarray(labels) == label].mean(axis=0)
    n = np.linalg.norm(m)
    return (m / n if n > 1e-8 else m).tolist()


class ContactStore:
    def __init__(self, path: str = ""):
        self.path = Path(path) if path else config.CONTACTS_FILE
        self.contacts: list[Contact] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.contacts = []
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.contacts = [Contact(**c) for c in data.get("contacts", [])]
        except Exception:  # noqa: BLE001
            self.contacts = []

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "contacts": [asdict(c) for c in self.contacts]}
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(self.path)

    def find_by_name(self, name: str) -> Contact | None:
        name = name.strip()
        for c in self.contacts:
            if c.name == name:
                return c
        return None

    def find_by_id(self, cid: str) -> Contact | None:
        for c in self.contacts:
            if c.id == cid:
                return c
        return None

    def register(self, name: str, embedding, merge: bool = True) -> Contact:
        """注册（重命名）：同名联系人则追加声纹样本，否则新建。"""
        name = name.strip()
        emb = np.asarray(embedding, dtype=np.float32).tolist()
        c = self.find_by_name(name) if merge else None
        if c is not None:
            if all(cosine(emb, e) < 0.97 for e in c.embeddings):
                c.embeddings.append(emb)
            c.meetings += 1
            c.last_met = _now()
        else:
            c = Contact(id="c_" + uuid.uuid4().hex[:10],
                        name=name, embeddings=[emb])
            self.contacts.append(c)
        self.save()
        return c

    def identify(self, embedding, threshold: float | None = None):
        """与所有联系人的声纹质心比对，返回 (Contact 或 None, best_score)。

        用联系人全部样本的质心而非"单样本最高值"，避免个别噪声样本把声学
        相近但未注册的说话人拉高误认。
        """
        thr = config.CONTACT_MATCH_THRESHOLD if threshold is None else threshold
        best, best_score = None, -1.0
        for c in self.contacts:
            if not c.embeddings:
                continue
            m = np.asarray(c.embeddings, dtype=np.float32).mean(axis=0)
            nrm = np.linalg.norm(m)
            if nrm > 1e-8:
                m = m / nrm
            s = cosine(embedding, m)
            if s > best_score:
                best_score, best = s, c
        if best is not None and best_score >= thr:
            return best, best_score
        return None, best_score

    def rename(self, cid: str, new_name: str) -> Contact | None:
        c = self.find_by_id(cid)
        if c:
            c.name = new_name.strip()
            self.save()
        return c

    def delete(self, cid: str) -> bool:
        before = len(self.contacts)
        self.contacts = [c for c in self.contacts if c.id != cid]
        if len(self.contacts) < before:
            self.save()
            return True
        return False

    def summary(self) -> list[dict]:
        return [{"id": c.id, "name": c.name, "samples": len(c.embeddings),
                 "meetings": c.meetings, "created_at": c.created_at,
                 "last_met": c.last_met} for c in self.contacts]


def get_store(path: str = "") -> ContactStore:
    return ContactStore(path)
