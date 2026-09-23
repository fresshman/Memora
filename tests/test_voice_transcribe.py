"""whisper 转写（pywhispercpp 进程内绑定）单元测试。"""
from __future__ import annotations

import sys
import types

import numpy as np

from memora.whisper import transcribe as ts


class _Raw:
    def __init__(self, t0, t1, text):
        self.t0, self.t1, self.text = t0, t1, text


def _patch(monkeypatch, raw, captured=None):
    monkeypatch.setattr(ts.config, "find_whisper_model",
                        lambda n=None: "m.bin")

    class FakeModel:
        def __init__(self, **kw):
            if captured is not None:
                captured["init"] = kw

        def transcribe(self, pcm, **kw):
            if captured is not None:
                captured["tr"] = kw
            return raw

    parent = types.ModuleType("pywhispercpp")
    child = types.ModuleType("pywhispercpp.model")
    child.Model = FakeModel
    parent.model = child
    monkeypatch.setitem(sys.modules, "pywhispercpp", parent)
    monkeypatch.setitem(sys.modules, "pywhispercpp.model", child)


def test_segment_to_dict():
    d = ts.Segment(0, 1, "你好").to_dict()
    assert d == {"start": 0, "end": 1, "text": "你好", "speaker": ""}


def test_transcribe_basic(monkeypatch):
    cap = {}
    raw = [_Raw(0, 150, "你好"), _Raw(150, 300, "世界"), _Raw(300, 310, "")]
    _patch(monkeypatch, raw, cap)
    segs = ts.transcribe_segments(np.zeros(16000, np.float32), 16000, "zh")
    assert len(segs) == 2
    assert segs[0].start == 0 and segs[0].end == 1.5 and segs[0].text == "你好"
    assert segs[1].text == "世界"
    assert cap["tr"]["language"] == "zh"
    assert "initial_prompt" in cap["tr"]


def test_transcribe_no_lang(monkeypatch):
    cap = {}
    _patch(monkeypatch, [_Raw(0, 100, "hi")], cap)
    ts.transcribe_segments(np.zeros(16000, np.float32))
    assert "language" not in cap["tr"]


def test_build_model_missing(monkeypatch):
    monkeypatch.setattr(ts.config, "find_whisper_model", lambda n=None: None)
    parent = types.ModuleType("pywhispercpp")
    child = types.ModuleType("pywhispercpp.model")
    child.Model = object
    parent.model = child
    monkeypatch.setitem(sys.modules, "pywhispercpp", parent)
    monkeypatch.setitem(sys.modules, "pywhispercpp.model", child)
    try:
        ts._build_model()
        assert False
    except ts.WhisperNotReadyError:
        pass


def test_transcribe_convenience(monkeypatch):
    monkeypatch.setattr(
        ts, "transcribe_segments",
        lambda pcm, sr, language="": [ts.Segment(0, 1, "x")])
    import memora.whisper.audio as audio_mod
    monkeypatch.setattr(audio_mod, "decode",
                        lambda p: (np.zeros(16000, np.float32), 16000))
    out = ts.transcribe("a.wav")
    assert len(out) == 1


def test_transcribe_wrong_sr():
    try:
        ts.transcribe_segments(np.zeros(100, np.float32), 8000)
        assert False
    except ValueError:
        pass