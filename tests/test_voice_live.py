# -*- coding: utf-8 -*-
"""实时录音 WebSocket 流式转写测试（Fake whisper / embedder，不加载真实模型）。"""
from __future__ import annotations

import base64

import numpy as np
import pytest

from fastapi.testclient import TestClient

from memora.whisper.transcribe import Segment
from server.main import app
from server.routes import live


class FakeEmbedder:
    embed_dim = 4

    def __init__(self, vec: np.ndarray):
        self.vec = vec

    def embed(self, clip) -> np.ndarray:
        return self.vec


def test_assign_speaker_merge_and_new():
    sess = live.LiveSession("zh")
    v1 = np.array([1, 0, 0, 0], dtype=np.float32)
    v2 = np.array([0, 1, 0, 0], dtype=np.float32)
    # 首段注册为说话人1
    assert sess._assign(v1) == "说话人1"
    # 差异大的新声纹 → 说话人2
    assert sess._assign(v2) == "说话人2"
    # 与 v1 相同 → 归并回说话人1（不新建）
    assert sess._assign(v1) == "说话人1"
    assert len(sess.centroids) == 2


def test_process_window_offsets_and_speaker(monkeypatch):
    monkeypatch.setattr(
        live, "transcribe_window",
        lambda pcm, lang, off: [Segment(0, 1, "你好"), Segment(1, 2, "世界")])
    monkeypatch.setattr(live.diarize, "_get_embedder",
                        lambda: FakeEmbedder(np.array([1, 0, 0, 0], np.float32)))
    sess = live.LiveSession("zh")
    assert sess.feed(np.zeros(3 * 16000, np.float32)) is True
    out = sess.process_window()
    assert len(out) == 2
    assert out[0].start == 0 and out[0].end == 1
    assert out[1].start == 1 and out[1].end == 2
    assert all(s.speaker == "说话人1" for s in out)
    # 第二个窗口的全局偏移应为 3s
    assert sess.processed_s == pytest.approx(3.0)


def test_ws_handshake():
    with TestClient(app) as c:
        with c.websocket_connect("/api/voice/stream") as ws:
            ws.send_json({"type": "start", "language": "zh"})
            assert ws.receive_json() == {"type": "ready"}


def test_ws_end_to_end(monkeypatch):
    monkeypatch.setattr(
        live, "transcribe_window",
        lambda pcm, lang, off: [Segment(0, 1, "你好")])
    monkeypatch.setattr(live.diarize, "_get_embedder", lambda: None)

    def _fake_diarize(y, segs, num_speakers, sr):
        for s in segs:
            s.speaker = "说话人1"
        return segs, 1

    monkeypatch.setattr(live.diarize, "diarize", _fake_diarize)
    monkeypatch.setattr(live.audio, "speech_duration", lambda y: 1.0)

    with TestClient(app) as c:
        with c.websocket_connect("/api/voice/stream") as ws:
            ws.send_json({"type": "start", "language": "zh"})
            assert ws.receive_json() == {"type": "ready"}

            # 4s 静音（一次喂入即触发 3s 窗口）
            i16 = np.zeros(4 * 16000, dtype=np.int16)
            ws.send_json({
                "type": "chunk",
                "data": base64.b64encode(i16.tobytes()).decode(),
            })
            delta = ws.receive_json()
            assert delta["type"] == "delta"
            assert delta["segments"][0]["text"] == "你好"

            ws.send_json({"type": "stop"})
            final = ws.receive_json()
            assert final["type"] == "final"
            assert final["meta"]["audio_name"].startswith("实时录音")
            assert final["segments"]
            assert final["text"]
