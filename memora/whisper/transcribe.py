"""whisper.cpp 转写：通过 pywhispercpp 绑定（纯 CPU、本地离线）。

输入解码后的 16kHz float32 PCM，输出带时间戳的 Segment 列表。
模型为官方 whisper.cpp 的 ggml 格式（默认 ggml-small，远场实测可用；
追求质量可下 ggml-large-v3-turbo）。模型下载默认走 hf-mirror / ModelScope。

为何用 pywhispercpp 而非 whisper-cli 子进程：pip 即装（自带预编译 libwhisper，
Windows 友好），无需单独下载 CLI 二进制；同一套官方 ggml 模型，精度不变。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import config


@dataclass
class Segment:
    """一句话分段：起止时间（秒）与文本；speaker 在说话人分离阶段填充。"""
    start: float
    end: float
    text: str
    speaker: str = ""

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end,
                "text": self.text, "speaker": self.speaker}


class WhisperNotReadyError(RuntimeError):
    """缺少 pywhispercpp 运行库或 ASR 模型。"""


def _build_model():
    try:
        from pywhispercpp.model import Model
    except Exception as exc:  # noqa: BLE001
        raise WhisperNotReadyError(
            "未安装 pywhispercpp，请运行：pip install pywhispercpp"
        ) from exc
    model_path = config.find_whisper_model(config.WHISPER_DEFAULT_MODEL)
    if not model_path:
        raise WhisperNotReadyError(
            f"未找到 ASR 模型 {config.WHISPER_DEFAULT_MODEL}，请在“语音复盘”页点击下载，"
            f"或运行：python -m memora.model_fetch --asr"
        )
    params = dict(
        print_progress=False,
        print_realtime=False,
        print_timestamps=False,
        no_context=True,
        vad=bool(config.WHISPER_USE_VAD),
    )
    if int(config.LLAMACPP_N_THREADS) > 0:
        params["n_threads"] = int(config.LLAMACPP_N_THREADS)
    return Model(model=str(model_path), **params)


_STREAM_MODEL = None


def get_stream_model():
    """流式专用常驻 whisper 模型（懒加载，避免每个窗口重复加载）。"""
    global _STREAM_MODEL
    if _STREAM_MODEL is None:
        _STREAM_MODEL = _build_model()
    return _STREAM_MODEL


def transcribe_segments(
    pcm: np.ndarray,
    sr: int = 16000,
    language: str = "",
) -> list["Segment"]:
    """转写 16kHz mono float32 PCM，返回 Segment（时间戳单位：秒）。"""
    if sr != 16000:
        raise ValueError("whisper 需 16kHz 音频")
    pcm = np.ascontiguousarray(pcm, dtype=np.float32)
    model = _build_model()
    try:
        kw: dict = {}
        if language:
            kw["language"] = language
        # whisper 默认输出繁体中文，用 initial_prompt 引导简体
        if not language or language.startswith("zh"):
            kw["initial_prompt"] = "以下是普通话会议录音，请用简体汉字转写。"
        raw = model.transcribe(pcm, **kw)
    finally:
        try:
            del model
        except Exception:  # noqa: BLE001
            pass
    segs: list[Segment] = []
    for s in raw:
        text = (getattr(s, "text", "") or "").strip()
        if not text:
            continue
        # t0 / t1 为 10ms（centiseconds）→ 秒
        segs.append(Segment(round(s.t0 * 0.01, 3), round(s.t1 * 0.01, 3), text))
    return segs


def ensure_model(model_name: str = "") -> str:
    """确保 ASR 模型已下载（经 model_fetch）。"""
    from ..model_fetch import ensure_asr_model
    return ensure_asr_model(model_name or config.WHISPER_DEFAULT_MODEL)


def transcribe(path, language: str = "") -> list["Segment"]:
    """便捷入口：任意常见格式音频文件 → 带时间戳分段。"""
    from .audio import decode
    pcm, sr = decode(str(path))
    return transcribe_segments(pcm, sr, language=language)

def transcribe_window(pcm: np.ndarray, language: str = "",
                      time_offset: float = 0.0) -> list["Segment"]:
    """转写一个短窗口（复用常驻模型），段时间戳叠加 time_offset（秒）。"""
    model = get_stream_model()
    kw: dict = {}
    if language:
        kw["language"] = language
    if not language or language.startswith("zh"):
        kw["initial_prompt"] = "以下是普通话会议录音，请用简体汉字转写。"
    raw = model.transcribe(np.ascontiguousarray(pcm, dtype=np.float32), **kw)
    out: list[Segment] = []
    for s in raw:
        text = (getattr(s, "text", "") or "").strip()
        if not text:
            continue
        out.append(Segment(round(s.t0 * 0.01 + time_offset, 3),
                           round(s.t1 * 0.01 + time_offset, 3), text))
    return out