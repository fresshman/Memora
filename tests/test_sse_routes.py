# -*- coding: utf-8 -*-
"""SSE 流式路由集成测试（FastAPI TestClient + 注入 Fake agent，不加载模型）。"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from memora.agent import MemoraAgent
from memora.backend.base import MemoraLLM
from memora.parsers import Conversation, Message
from server.main import app
from server import routes
from server.session import create

REPORT = (
    "## 一、本次沟通核心结论\n确定上线窗口为 3 月 18 日。\n\n"
    "## 二、待办任务清单\n- [ ] 部署 ｜ 责任人：陈静 ｜ 时间节点：本周四\n\n"
    "## 三、关键信息提取\n联系人：张伟。\n\n"
    "## 四、沟通风险提示\n证书下周到期。\n"
)


class FakeStreamingLLM(MemoraLLM):
    name = "fake-stream"
    model_id = "fake/model"

    def complete(self, prompt, *, max_tokens=None, temperature=None):
        return REPORT

    def stream_complete(self, prompt, *, max_tokens=None, temperature=None):
        for piece in (REPORT[:10], REPORT[10:30], REPORT[30:]):
            yield piece


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        if line.startswith("data:"):
            events.append(json.loads(line[5:].strip()))
    return events


def _make_session() -> str:
    conv = Conversation(
        source="test", title="t",
        messages=[Message(speaker="甲", time="2024-03-04 10:00:00",
                          text="上线窗口定在3月18日，张伟值守。")],
    )
    return create(conv)


def test_review_stream_endpoint(monkeypatch):
    fake_agent = MemoraAgent(FakeStreamingLLM())
    monkeypatch.setattr(routes.review, "get_agent", lambda: fake_agent)
    sid = _make_session()
    with TestClient(app) as client:
        resp = client.post("/api/review/stream", json={"session_id": sid})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.text)
    assert events[0]["type"] == "meta"
    assert events[-1]["type"] == "done"
    assert "".join(e.get("text", "") for e in events if e["type"] == "delta") == REPORT
    assert events[-1]["report"] == REPORT.strip()
    assert events[-1]["sections"]


def test_qa_stream_endpoint(monkeypatch):
    fake_agent = MemoraAgent(FakeStreamingLLM())
    monkeypatch.setattr(routes.qa, "get_agent", lambda: fake_agent)
    sid = _make_session()
    with TestClient(app) as client:
        resp = client.post("/api/qa/stream",
                           json={"session_id": sid, "question": "什么时候上线？"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.text)
    assert events[0]["type"] == "meta"
    assert events[-1]["type"] == "done"
    assert events[-1]["answer"] == REPORT.strip()


def test_review_stream_missing_session(monkeypatch):
    fake_agent = MemoraAgent(FakeStreamingLLM())
    monkeypatch.setattr(routes.review, "get_agent", lambda: fake_agent)
    with TestClient(app) as client:
        resp = client.post("/api/review/stream", json={"session_id": "nope"})
    assert resp.status_code == 404
