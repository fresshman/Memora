# -*- coding: utf-8 -*-
"""PII 脱敏接入路由测试：粘贴即脱敏（模型/索引只见占位），支持本地还原。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from server.main import app
from server.session import get as get_session

CLIENT = TestClient(app)

PASTE = "张伟：我手机号13812345678，邮箱 zhang.wei@example.com，这周部署\n李娜：收到"


def test_paste_is_redacted_before_model():
    resp = CLIENT.post("/api/conversations/paste", json={"text": PASTE})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["redacted"] is True
    stats = data["pii_stats"]
    assert stats["手机"] == 1
    assert stats["邮箱"] == 1
    assert stats["人名"] == 2

    # 会话内保存的对话已是脱敏文本，不含任何明文 PII / 真名
    conv = get_session(data["session_id"])
    blob = "\n".join(m.text for m in conv.user_messages)
    speakers = conv.speakers
    assert "13812345678" not in blob
    assert "zhang.wei@example.com" not in blob
    assert "张伟" not in blob and "李娜" not in blob
    assert speakers == ["成员A", "成员B"]
    assert conv.redaction is not None


def test_restore_endpoint_roundtrip():
    data = CLIENT.post("/api/conversations/paste", json={"text": PASTE}).json()
    sid = data["session_id"]
    masked = "请【手机1】持有人成员A本周完成，联系邮箱见上。"
    resp = CLIENT.post("/api/redact/restore",
                       json={"session_id": sid, "text": masked})
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert out["restored"] is True
    assert "13812345678" in out["text"]
    assert "张伟" in out["text"]
    assert "【手机1】" not in out["text"]


def test_restore_unknown_session_404():
    resp = CLIENT.post("/api/redact/restore",
                       json={"session_id": "nope", "text": "x"})
    assert resp.status_code == 404
