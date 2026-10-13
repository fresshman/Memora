"""跨会话联系人声纹库单测（不加载模型）。"""
from __future__ import annotations

import numpy as np

from memora.whisper import contacts as C

DIM = 16


def _vec(base, noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    v = (np.array(base, dtype=np.float32)
         + rng.normal(0, noise, len(base)).astype(np.float32))
    v = v / np.linalg.norm(v)
    return v.tolist()


A = [1] + [0] * (DIM - 1)
B = [0, 1] + [0] * (DIM - 2)


def test_register_new(tmp_path):
    store = C.ContactStore(str(tmp_path / "c.json"))
    c = store.register("张三", _vec(A))
    assert c.name == "张三" and len(c.embeddings) == 1 and c.id


def test_same_name_appends(tmp_path):
    store = C.ContactStore(str(tmp_path / "c.json"))
    c1 = store.register("张三", _vec(A))
    c2 = store.register("张三", _vec(A, noise=0.15, seed=1))
    assert c2.id == c1.id
    assert len(c2.embeddings) == 2
    assert c2.meetings == 2


def test_identify_hit(tmp_path):
    store = C.ContactStore(str(tmp_path / "c.json"))
    store.register("张三", _vec(A))
    hit, score = store.identify(_vec(A, noise=0.05, seed=3), threshold=0.7)
    assert hit is not None and hit.name == "张三" and score >= 0.7


def test_identify_miss(tmp_path):
    store = C.ContactStore(str(tmp_path / "c.json"))
    store.register("张三", _vec(A))
    hit, _ = store.identify(_vec(B), threshold=0.7)
    assert hit is None


def test_persistence(tmp_path):
    p = str(tmp_path / "c.json")
    C.ContactStore(p).register("张三", _vec(A))
    store2 = C.ContactStore(p)
    assert len(store2.contacts) == 1
    assert store2.contacts[0].name == "张三"
    assert len(store2.contacts[0].embeddings) == 1


def test_rename_and_delete(tmp_path):
    p = str(tmp_path / "c.json")
    store = C.ContactStore(p)
    c = store.register("张三", _vec(A))
    assert store.rename(c.id, "张三经理") is not None
    assert store.find_by_name("张三经理") is not None
    assert store.delete(c.id) is True
    assert store.find_by_id(c.id) is None


def test_cluster_centroid():
    E = np.array([[1, 0], [1, 0], [0, 1]], dtype=np.float32)
    labels = np.array([0, 0, 1])
    cen = C.cluster_centroid(E, labels, 0)
    assert np.allclose(cen, [1.0, 0.0])
