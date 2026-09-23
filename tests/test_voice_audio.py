"""音频预处理与轻量能量 VAD 单元测试。"""
from __future__ import annotations

import numpy as np

from memora.whisper import audio


def test_energy_vad_silence():
    y = np.zeros(16000, dtype=np.float32)
    voiced, _ = audio.energy_vad(y)
    assert not voiced.any()


def test_energy_vad_loud_signal():
    t = np.arange(16000) / 16000
    y = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    voiced, _ = audio.energy_vad(y)
    assert voiced.mean() > 0.5


def test_speech_regions_split_two():
    # 语音 40 帧、静音 40 帧（400ms > 300ms）、语音 40 帧
    voiced = np.array([True] * 40 + [False] * 40 + [True] * 40)
    regs = audio.speech_regions(voiced, hop_ms=10,
                                min_speech_ms=250, min_silence_ms=300)
    assert len(regs) == 2
    assert abs(regs[0][0]) < 0.01
    assert abs(regs[1][1] - 1.2) < 0.05


def test_speech_regions_drop_short():
    voiced = np.array([True] * 10 + [False] * 50)   # 仅 100ms，短于 250ms
    assert audio.speech_regions(voiced, hop_ms=10) == []


def test_save_wav_and_probe(tmp_path):
    t = np.arange(16000) / 16000
    y = (0.2 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    wav = audio.save_wav(y, tmp_path / "a.wav")
    assert wav.exists()
    info = audio.probe(wav)
    assert abs(info.duration - 1.0) < 0.1


def test_speech_duration():
    t = np.arange(16000 * 2) / 16000
    y = np.zeros(16000 * 2, dtype=np.float32)
    y[:16000] = (0.3 * np.sin(2 * np.pi * 200 * t[:16000])).astype(np.float32)
    d = audio.speech_duration(y)
    assert 0.5 < d < 1.5
