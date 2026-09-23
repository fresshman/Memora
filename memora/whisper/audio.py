"""音频解码与轻量预处理（本地离线，纯 CPU，不依赖 torch）。

职责：
  1) 常见格式（mp3 / m4a / aac / wav / flac / ogg / wma / opus …）统一解码为
     16kHz 单声道 PCM；
  2) ffmpeg 缺失时用 soundfile（libsndfile）兜底；
  3) 轻量能量 VAD：自适应阈值标记语音帧、合并语音区间、统计有效语音时长；
  4) 写出 whisper.cpp 最稳定的 16kHz / mono / 16bit WAV。

轻量过滤刻意不引入额外神经网络与 torch：ffmpeg 动态响度归一 + 自研短时能量
VAD + whisper.cpp 内置 VAD（转写阶段）三道轻量处理，已能去除绝大多数静音 /
噪声 / 非语音段，并显著降低转写幻觉与耗时。
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import config
from ..log import get_logger

log = get_logger(__name__)

SAMPLE_RATE = 16000

# 支持的常见音频 / 含音轨容器（交给 ffmpeg 解码）
SUPPORTED_EXTS = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".oga", ".wma",
    ".opus", ".mp4", ".webm", ".amr", ".aiff", ".aif", ".mka", ".3gp",
}


class AudioDecodeError(RuntimeError):
    pass


@dataclass
class AudioInfo:
    duration: float
    sample_rate: int
    channels: int


# ---------------------------------------------------------------------------
# 元信息
# ---------------------------------------------------------------------------
def probe(path: str | Path) -> AudioInfo:
    """读取时长 / 采样率 / 声道；无 ffprobe 时解码后按长度估算。"""
    path = Path(path)
    fp = config.find_ffprobe()
    if fp is not None:
        cmd = [
            str(fp), "-v", "error",
            "-show_entries", "format=duration:stream=sample_rate,channels",
            "-of", "json", str(path),
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            try:
                data = json.loads(p.stdout)
                dur = float(data.get("format", {}).get("duration") or 0.0)
                sr, ch = SAMPLE_RATE, 1
                for s in data.get("stream", []):
                    if "sample_rate" in s:
                        sr = int(s["sample_rate"])
                        ch = int(s.get("channels") or 1)
                        break
                if dur > 0:
                    return AudioInfo(dur, sr, ch)
            except (json.JSONDecodeError, ValueError):
                pass
    y, sr = decode(path)
    return AudioInfo(len(y) / sr, sr, 1)


# ---------------------------------------------------------------------------
# 解码：ffmpeg 主力，soundfile 兜底
# ---------------------------------------------------------------------------
def _decode_ffmpeg(path: Path) -> np.ndarray:
    ff = config.find_ffmpeg()
    if ff is None:
        raise FileNotFoundError("ffmpeg")
    # afftdn 频域降噪（远场麦克风底噪）+ dynaudnorm 动态响度归一（会议音量
    # 不一致，比 loudnorm 稳健）
    cmd = [
        str(ff), "-nostdin", "-v", "error", "-i", str(path),
        "-vn",
        "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-af", "afftdn,dynaudnorm=f=200:g=15",
        "-f", "f32le", "-acodec", "pcm_f32le", "-",
    ]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        msg = p.stderr.decode("utf-8", "ignore")[-500:]
        raise AudioDecodeError(f"ffmpeg 解码失败：{msg}")
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def _decode_soundfile(path: Path) -> np.ndarray:
    import soundfile as sf
    y, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if getattr(y, "ndim", 1) > 1:
        y = y.mean(axis=1)
    if sr != SAMPLE_RATE:
        n = int(len(y) * SAMPLE_RATE / sr)
        idx = np.linspace(0, len(y) - 1, n)
        y = np.interp(idx, np.arange(len(y)), y).astype(np.float32)
    return y


def decode(path: str | Path) -> tuple[np.ndarray, int]:
    """解码为 (float32 一维 PCM, 16000)。失败抛 AudioDecodeError 并给指引。"""
    path = Path(path)
    try:
        return _decode_ffmpeg(path), SAMPLE_RATE
    except FileNotFoundError as e:
        log.debug("ffmpeg 不可用（%s），尝试 soundfile", e)
    except AudioDecodeError as e:
        log.debug("ffmpeg 解码失败，尝试 soundfile：%s", e)
    try:
        return _decode_soundfile(path), SAMPLE_RATE
    except Exception as e:  # noqa: BLE001
        raise AudioDecodeError(
            f"无法解码音频 {path.name}：{e}\n"
            "请安装 ffmpeg（下载 Windows 静态构建解压到 tools/ffmpeg），"
            "或执行 pip install soundfile。"
        ) from e


def save_wav(y: np.ndarray, out_path: str | Path) -> Path:
    """写出 16kHz / mono / 16bit PCM WAV（whisper.cpp 最稳输入）。"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ff = config.find_ffmpeg()
    if ff is not None:
        cmd = [
            str(ff), "-nostdin", "-v", "error",
            "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", "-",
            "-c:a", "pcm_s16le", "-y", str(out_path),
        ]
        p = subprocess.run(cmd, input=y.astype(np.float32).tobytes(),
                           capture_output=True)
        if p.returncode == 0:
            return out_path
        log.warning("ffmpeg 写 WAV 失败，改用 soundfile：%s",
                    p.stderr.decode("utf-8", "ignore")[-300:])
    import soundfile as sf
    sf.write(str(out_path), y, SAMPLE_RATE, subtype="PCM_16")
    return out_path


# ---------------------------------------------------------------------------
# 轻量能量 VAD（零模型）
# ---------------------------------------------------------------------------
def energy_vad(y: np.ndarray, frame_ms: int = 30, hop_ms: int = 10,
               rel_thr: float = 0.02, abs_thr: float = 1e-3
               ) -> tuple[np.ndarray, int]:
    """短时能量 VAD，返回 (每帧是否语音, hop 毫秒)。

    阈值自适应：以 20% 分位为噪声底、95% 分位为高能量参考，取
    noise + rel_thr*(high-noise)，并设绝对下限，避免纯噪声误判。
    """
    fl = int(SAMPLE_RATE * frame_ms / 1000)
    hop = int(SAMPLE_RATE * hop_ms / 1000)
    if len(y) < fl:
        rms = float(np.sqrt(np.mean(y ** 2) + 1e-12))
        return np.array([rms > abs_thr]), hop_ms
    n = 1 + (len(y) - fl) // hop
    rms = np.empty(n)
    for i in range(n):
        seg = y[i * hop:i * hop + fl]
        rms[i] = np.sqrt(np.mean(seg ** 2) + 1e-12)
    noise = float(np.percentile(rms, 20))
    high = float(np.percentile(rms, 95))
    thr = max(noise + rel_thr * (high - noise), abs_thr)
    return rms > thr, hop_ms


def speech_regions(voiced: np.ndarray, hop_ms: int = 10,
                   min_speech_ms: int = 250,
                   min_silence_ms: int = 300) -> list[tuple[float, float]]:
    """把语音帧合并为 (start_s, end_s) 区间：平滑短停顿、丢弃过短语音。"""
    min_sil = max(1, min_silence_ms // hop_ms)
    min_sp = min_speech_ms // hop_ms
    regions: list[tuple[float, float]] = []
    seg_start: int | None = None
    sil = 0
    last_voiced = 0
    for i, v in enumerate(voiced):
        if v:
            if seg_start is None:
                seg_start = i
            sil = 0
            last_voiced = i
        elif seg_start is not None:
            sil += 1
            if sil >= min_sil:
                end = last_voiced + 1
                if end - seg_start >= min_sp:
                    regions.append((seg_start * hop_ms / 1000,
                                    end * hop_ms / 1000))
                seg_start = None
                sil = 0
    if seg_start is not None:
        end = last_voiced + 1
        if end - seg_start >= min_sp:
            regions.append((seg_start * hop_ms / 1000,
                            end * hop_ms / 1000))
    return regions


def speech_duration(y: np.ndarray) -> float:
    """统计有效语音总时长（秒）。"""
    voiced, hop = energy_vad(y)
    return sum(e - s for s, e in speech_regions(voiced, hop))

def gate_by_vad(y, frame_ms: int = 30, hop_ms: int = 10,
               pad_ms: int = 150) -> np.ndarray:
    """能量 VAD 门控：非语音帧置零（保留时间轴），词头词尾加 padding。

    whisper 内置 VAD 不可用时的轻量替代：抑制静音 / 噪声段以降低转写幻觉，
    不删除时间轴（时间戳仍准确）。返回与输入等长的 float32 PCM。
    """
    y = np.asarray(y, dtype=np.float32)
    voiced, hopm = energy_vad(y, frame_ms, hop_ms)
    hop = int(SAMPLE_RATE * hopm / 1000)
    fl = int(SAMPLE_RATE * frame_ms / 1000)
    pad = int(SAMPLE_RATE * pad_ms / 1000)
    mask = np.zeros(len(y), dtype=np.float32)
    for i, v in enumerate(voiced):
        if v:
            a = max(0, i * hop - pad)
            b = min(len(y), i * hop + fl + pad)
            mask[a:b] = 1.0
    return y * mask
