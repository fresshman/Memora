"""whisper.cpp 转写：通过 pywhispercpp 绑定（纯 CPU、本地离线）。

输入解码后的 16kHz float32 PCM，输出带时间戳的 Segment 列表。
模型为官方 whisper.cpp 的 ggml 格式（默认 ggml-small，远场实测可用；
追求质量可下 ggml-large-v3-turbo）。模型下载默认走 hf-mirror / ModelScope。

为何用 pywhispercpp 而非 whisper-cli 子进程：pip 即装（自带预编译 libwhisper，
Windows 友好），无需单独下载 CLI 二进制；同一套官方 ggml 模型，精度不变。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


HOTWORDS_FILE = Path(__file__).with_name("hotwords.txt")


def load_hotwords(path: str = "") -> str:
    """读取热词表，返回中文逗号分隔的热词串；# 注释 / 空行忽略。文件不存在返回空串。"""
    p = Path(path) if path else HOTWORDS_FILE
    if not p.exists():
        return ""
    words: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for w in line.split(","):
            w = w.strip()
            if w:
                words.append(w)
    return "，".join(words)


def _resolve_hotwords(hotwords) -> str:
    """归一化热词入参：
    None -> 自动加载内置热词表（默认开启）；
    ""   -> 显式关闭（返回空）；
    其他 -> 视为文件路径（存在则加载），否则当作热词字符串。
    """
    if hotwords is None:
        return load_hotwords()
    if hotwords == "":
        return ""
    cand = Path(hotwords)
    if cand.exists():
        return load_hotwords(str(cand))
    return hotwords


def build_initial_prompt(language: str, hotwords: str = "") -> str:
    """简体引导 + 热词（仅中文）。"""
    if language and not language.startswith("zh"):
        return ""
    prompt = "以下是普通话会议录音，请用简体汉字转写。"
    if hotwords:
        prompt += "涉及专有名词：" + hotwords + "。"
    return prompt


def transcribe_segments(
    pcm: np.ndarray,
    sr: int = 16000,
    language: str = "",
    hotwords=None,
) -> list["Segment"]:
    """转写 16kHz mono float32 PCM，返回 Segment（时间戳单位：秒）。

    hotwords: None=自动加载内置热词表（默认开启）；""=关闭热词；
              传文件路径则加载该表；传热词字符串则直接使用。
    """
    if sr != 16000:
        raise ValueError("whisper 需 16kHz 音频")
    pcm = np.ascontiguousarray(pcm, dtype=np.float32)
    model = _build_model()
    try:
        kw: dict = {}
        if language:
            kw["language"] = language
        # initial_prompt 引导简体（whisper 默认输出繁体）并注入热词
        prompt = build_initial_prompt(language, _resolve_hotwords(hotwords))
        if prompt:
            kw["initial_prompt"] = prompt
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


def transcribe_segments_hotwords(
    pcm: np.ndarray,
    sr: int = 16000,
    language: str = "",
    hotwords=None,
) -> list["Segment"]:
    """显式指定热词（文件路径 / 热词串；None=内置表，""=关闭）。"""
    return transcribe_segments(pcm, sr, language, hotwords=hotwords)


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
                      time_offset: float = 0.0,
                      hotwords=None) -> list["Segment"]:
    """转写一个短窗口（复用常驻模型），段时间戳叠加 time_offset（秒）。

    hotwords: None=自动加载内置热词表；""=关闭；路径/字符串=自定义。
    """
    model = get_stream_model()
    kw: dict = {}
    if language:
        kw["language"] = language
    prompt = build_initial_prompt(language, _resolve_hotwords(hotwords))
    if prompt:
        kw["initial_prompt"] = prompt
    raw = model.transcribe(np.ascontiguousarray(pcm, dtype=np.float32), **kw)
    out: list[Segment] = []
    for s in raw:
        text = (getattr(s, "text", "") or "").strip()
        if not text:
            continue
        out.append(Segment(round(s.t0 * 0.01 + time_offset, 3),
                           round(s.t1 * 0.01 + time_offset, 3), text))
    return out