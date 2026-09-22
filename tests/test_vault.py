"""加密存储单元测试（用 tmp_path 隔离，不污染真实数据）。"""
from __future__ import annotations

import memora.config as config
from memora.storage import Vault


def _patch_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "VAULT_DIR", tmp_path / "vault")
    monkeypatch.setattr(config, "VAULT_KEY_FILE", tmp_path / "vault.key")
    monkeypatch.setattr(config, "VAULT_INDEX", tmp_path / "vault_index.json")
    (tmp_path / "vault").mkdir()


def test_vault_save_load(tmp_path, monkeypatch):
    _patch_vault(tmp_path, monkeypatch)
    v = Vault()
    rid = v.save("测试纪要", "报告内容")
    assert v.load(rid) == "报告内容"
    assert any(r["id"] == rid for r in v.list_records())
    v.delete(rid)
    assert v.load(rid) is None


def test_vault_wipe(tmp_path, monkeypatch):
    _patch_vault(tmp_path, monkeypatch)
    v = Vault()
    v.save("a", "内容1")
    v.save("b", "内容2")
    assert len(v.list_records()) == 2
    v.wipe_all()
    assert v.list_records() == []
