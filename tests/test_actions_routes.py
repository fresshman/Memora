# -*- coding: utf-8 -*-
"""行动项 / 思考档位 / 复盘包路由集成测试（TestClient，不加载模型）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from urllib.parse import quote

from server.main import app
from memora import action_items as A
from server.routes import actions as actions_route

CLIENT = TestClient(app)


class FakeAgent:
    """不加载模型的最小 agent，覆盖档位与进展回顾。"""
    def __init__(self):
        self.mode = "fast"

    def get_thinking_mode(self):
        return self.mode

    def set_thinking_mode(self, mode):
        self.mode = mode
        return mode

    def track_progress(self, text, *, source_meeting, source_kind):
        return {"checked": 2, "updates": [
            {"changed": True, "title": "任务A", "status": "done"},
            {"changed": False, "title": "任务B", "status": "open"},
        ]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    store = A.ActionItemStore(str(tmp_path / "a.json"))
    store.ingest([
        {"title": "任务A", "owner": "张三", "due": "2026-10-01"},
        {"title": "任务B", "owner": "李四"},
    ], source_meeting="群1")
    fake = FakeAgent()
    # 让路由与 exporter 都用临时 store / fake agent
    monkeypatch.setattr(A, "get_store", lambda path="": store)
    monkeypatch.setattr(actions_route, "get_agent", lambda: fake)
    return store, fake


# ---------------------------------------------------------------------------
# 列表
# ---------------------------------------------------------------------------
def test_list_actions(env):
    r = CLIENT.get("/api/actions")
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["items"]) == 2
    assert d["summary"]["total"] == 2
    assert d["owners"] == ["张三", "李四"]


def test_list_actions_filter_status(env):
    r = CLIENT.get("/api/actions?status=open")
    assert len(r.json()["items"]) == 2


# ---------------------------------------------------------------------------
# 改状态
# ---------------------------------------------------------------------------
def test_set_status_ok(env):
    store = env[0]
    aid = store.items[0].id
    r = CLIENT.post("/api/actions/status",
                    json={"id": aid, "status": "done", "note": "已交付"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done"
    assert r.json()["status_label"] == "已完成"
    assert store.items[0].status == "done"
    assert len(store.items[0].history) == 1


def test_set_status_unknown_id_404(env):
    r = CLIENT.post("/api/actions/status",
                    json={"id": "nope", "status": "done"})
    assert r.status_code == 404


def test_set_status_bad_status_400(env):
    aid = env[0].items[0].id
    r = CLIENT.post("/api/actions/status",
                    json={"id": aid, "status": "bogus"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 删除
# ---------------------------------------------------------------------------
def test_delete_action_ok(env):
    store = env[0]
    aid = store.items[0].id
    r = CLIENT.delete(f"/api/actions/{aid}")
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] == aid
    assert store.find_by_id(aid) is None
    assert len(store.items) == 1


def test_delete_action_unknown_id_404(env):
    r = CLIENT.delete("/api/actions/nope")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 思考档位
# ---------------------------------------------------------------------------
def test_thinking_get_set(env):
    assert CLIENT.get("/api/actions/thinking").json()["mode"] == "fast"
    r = CLIENT.post("/api/actions/thinking", json={"mode": "deep"})
    assert r.json()["mode"] == "deep"
    assert env[1].mode == "deep"


def test_thinking_bad_mode_400(env):
    r = CLIENT.post("/api/actions/thinking", json={"mode": "x"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 进展回顾
# ---------------------------------------------------------------------------
def test_track_with_text(env):
    r = CLIENT.post("/api/actions/track",
                    json={"meeting_text": "任务A已经完成", "source_meeting": "群2"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["checked"] == 2 and len(d["updates"]) == 2


def test_track_empty_text_400(env):
    r = CLIENT.post("/api/actions/track", json={"meeting_text": "   "})
    assert r.status_code == 400


def test_track_unknown_session_404(env):
    r = CLIENT.post("/api/actions/track", json={"session_id": "nope"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 复盘包
# ---------------------------------------------------------------------------
def test_export_package_zip(env):
    r = CLIENT.post("/api/export/package", json={
        "title": "测试项目", "report": "## 一、结论\n- 完成",
        "include_raw": False,
    })
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert r.content[:2] == b"PK"           # zip 魔数
    # 中文文件名按 RFC 5987 百分号编码（filename*=utf-8''…）
    assert quote("复盘包") in r.headers["content-disposition"]
