"""说话人分离单元测试（神经声纹段级 AHC + MFCC 降级）。"""
from __future__ import annotations

import numpy as np

from memora.whisper import diarize as dm
from memora.whisper.transcribe import Segment


def _tone(freq, dur=1.0, sr=16000, amp=0.4):
    t = np.arange(int(sr * dur)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)
            + 0.2 * amp * np.sin(4 * np.pi * freq * t)).astype(np.float32)


# ---- MFCC 基础 ----
def test_mfcc_shape():
    m = dm.mfcc(_tone(200))
    assert m.shape[1] == 20 and m.shape[0] > 50


def test_mfcc_distinguishes_pitch():
    a = dm.mfcc(_tone(120)).mean(axis=0)
    b = dm.mfcc(_tone(400)).mean(axis=0)
    assert not np.allclose(a, b)


def test_choose_k_mfcc_forced():
    X = np.random.RandomState(0).randn(10, 5)
    assert dm._choose_k_mfcc(X, 3, 10) == 3
    assert dm._choose_k_mfcc(X, 0, 1) == 1


# ---- 神经聚类（受控单位向量）----
def test_cluster_neural_forced():
    E = np.array([[1, 0, 0, 0], [0, 1, 0, 0],
                  [1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
    lab, k = dm._cluster_neural(E, 2)
    assert k == 2 and lab[0] == lab[2] and lab[1] == lab[3]


def test_cluster_neural_auto_two():
    E = np.array([[1, 0], [1, 0], [1, 0], [0, 1]], np.float32)
    lab, k = dm._cluster_neural(E, 0)
    assert k == 2


def test_cluster_neural_auto_single():
    E = np.repeat([[1.0, 0.0]], 4, axis=0).astype(np.float32)
    lab, k = dm._cluster_neural(E, 0)
    assert k == 1


# ---- diarize 端到端（mock VAD 短窗与 embedding）----
def test_diarize_neural_end2end(monkeypatch):
    segs = [Segment(0, 1, "a"), Segment(1, 2, "b"),
            Segment(2, 3, "c"), Segment(3, 4, "d")]
    vA = np.array([1, 0, 0, 0], np.float32)
    vB = np.array([0, 1, 0, 0], np.float32)
    wins = [(0, 1), (1, 2), (2, 3), (3, 4)]
    monkeypatch.setattr(dm, "_spk_windows", lambda y, sr: wins)
    monkeypatch.setattr(dm, "_embed_windows",
                        lambda y, sr, w: np.array([vA, vB, vA, vB]))
    out, k = dm.diarize(np.zeros(64000, np.float32), segs, 0, 16000)
    assert k == 2
    assert out[0].speaker == out[2].speaker
    assert out[0].speaker != out[1].speaker
    assert out[0].speaker == "说话人1"


def test_diarize_forced(monkeypatch):
    segs = [Segment(0, 1, "a"), Segment(1, 2, "b")]
    wins = [(0, 1), (1, 2)]
    monkeypatch.setattr(dm, "_spk_windows", lambda y, sr: wins)
    monkeypatch.setattr(dm, "_embed_windows",
                        lambda y, sr, w: np.random.RandomState(1).randn(2, 4))
    out, k = dm.diarize(np.zeros(32000, np.float32), segs, 2, 16000)
    assert k == 2 and out[0].speaker != out[1].speaker


def test_diarize_fallback_mfcc(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no onnx")
    monkeypatch.setattr(dm, "_spk_windows",
                        lambda y, sr: [(0, 1), (1, 2)])
    monkeypatch.setattr(dm, "_embed_windows", boom)
    y = np.concatenate([_tone(120), _tone(420)])
    segs = [Segment(0, 1, "a"), Segment(1, 2, "b")]
    out, k = dm.diarize(y, segs, 2, 16000)
    assert k == 2 and out[0].speaker != out[1].speaker


def test_diarize_empty():
    out, k = dm.diarize(np.zeros(100, np.float32), [], 0, 16000)
    assert out == [] and k == 1