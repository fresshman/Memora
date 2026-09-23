"""说话人分离（diarization，本地离线，纯 CPU，不依赖 torch / librosa）。

两级方案：
  A. 神经声纹（推荐）：用 speakeronnx 的 CAM++ / ERes2Net ONNX 提取说话人
     embedding（onnxruntime，pip 即装，不引 torch）。对 whisper.cpp 的每个
     句子段（数秒、相对稳定）提一个 embedding，再以「平均链接凝聚聚类
     （AHC）+ cosine 相似度阈值」自动定人数（用户已知人数时直接指定）。
     句子段比 1.5s 短窗 embedding 更稳定（远场实测：段级 DER 明显更低）。
  B. 轻量降级：无 speakeronnx 时，用 numpy/scipy 自实现 MFCC 段向量 + KMeans
     （轮廓系数 + 簇间质心间距双重门控）。

实测边界（8 通道远场小阵列）：轮流发言、低重叠、句间有停顿 → 正确识别 7 人、
DER≈0.12；快速抢话、高重叠、无停顿 → 小孔径阵列（通道时延 ±0.12ms）无法
空间分人、混响污染声纹，DER 偏高，属硬件性难题。近场 / 会议平台导出音频效果
更好。标签按首次出现顺序命名「说话人N」。
"""
from __future__ import annotations

import numpy as np
from scipy.fft import dct
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score

from .. import config
from ..log import get_logger
from .transcribe import Segment

log = get_logger(__name__)

_SPK_ALIAS = getattr(config, "SPEAKER_EMBED_MODEL", "campplus-zh-en")
_SIM_THR = float(getattr(config, "SPEAKER_SIM_THRESHOLD", 0.6))

# MFCC 降级参数
_N_FFT = 400          # 25ms
_HOP = 160            # 10ms
_N_MELS = 26


# ---------------------------------------------------------------------------
# MFCC（numpy + scipy）——降级路径
# ---------------------------------------------------------------------------
def _hz2mel(h: np.ndarray) -> np.ndarray:
    return 2595.0 * np.log10(1.0 + h / 700.0)


def _mel2hz(m: np.ndarray) -> np.ndarray:
    return 700.0 * (10.0 ** (m / 2595.0) - 1.0)


def _mel_filterbank(n_mels: int, n_fft: int, sr: int) -> np.ndarray:
    bins = np.floor((n_fft + 1) *
                    _mel2hz(np.linspace(_hz2mel(0), _hz2mel(sr / 2),
                                        n_mels + 2)) / sr).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1))
    for m in range(1, n_mels + 1):
        l, c, r = bins[m - 1], bins[m], bins[m + 1]
        if c > l:
            fb[m - 1, l:c] = (np.arange(l, c) - l) / (c - l)
        if r > c:
            fb[m - 1, c:r] = (r - np.arange(c, r)) / (r - c)
    return fb


_FBANK = _mel_filterbank(_N_MELS, _N_FFT, 16000)


def mfcc(y: np.ndarray, sr: int = 16000, n_mfcc: int = 20) -> np.ndarray:
    """返回 (帧数, n_mfcc) 的 MFCC。"""
    y = np.append(y[0], y[1:] - 0.97 * y[:-1])      # 预加重
    if len(y) < _N_FFT:
        y = np.pad(y, (0, _N_FFT - len(y)))
    n = 1 + (len(y) - _N_FFT) // _HOP
    idx = np.arange(_N_FFT)[None, :] + _HOP * np.arange(n)[:, None]
    frames = y[idx] * np.hamming(_N_FFT)
    spec = np.fft.rfft(frames, _N_FFT)
    pow_spec = (np.abs(spec) ** 2) / _N_FFT
    ffeat = np.maximum(pow_spec @ _FBANK.T, np.finfo(float).eps)
    return dct(np.log(ffeat), type=2, axis=1, norm="ortho")[:, :n_mfcc]


def _segment_vector(clip: np.ndarray, n_mfcc: int) -> np.ndarray:
    m = mfcc(clip, n_mfcc=n_mfcc)
    return np.concatenate([m.mean(axis=0), m.std(axis=0)])


def _choose_k_mfcc(X: np.ndarray, num_speakers: int, n_seg: int) -> int:
    from scipy.spatial.distance import pdist
    if num_speakers and num_speakers > 0:
        return max(1, min(num_speakers, n_seg))
    if n_seg < 3:
        return 1
    upper = min(config.DIAR_MAX_SPEAKERS, n_seg - 1)
    best_k, best_sil, best_gap = 1, -1.0, 0.0
    for k in range(2, upper + 1):
        km = KMeans(n_clusters=k, n_init=10, random_state=0)
        lab = km.fit_predict(X)
        if len(set(lab)) < 2:
            continue
        s = float(silhouette_score(X, lab))
        gap = float(pdist(km.cluster_centers_).min())
        if s > best_sil:
            best_sil, best_k, best_gap = s, k, gap
    if best_sil < 0.20 or best_gap < 1.0:
        return 1
    return best_k


# ---------------------------------------------------------------------------
# 神经声纹 embedding（CAM++ / ERes2Net ONNX，懒加载单例）
# ---------------------------------------------------------------------------
_EMBEDDER = None


def _get_embedder():
    global _EMBEDDER
    if _EMBEDDER is None:
        from speakeronnx import SpeakerEmbedder
        _EMBEDDER = SpeakerEmbedder(model=_SPK_ALIAS)
    return _EMBEDDER


def _neural_embeddings(y: np.ndarray, segments: list[Segment],
                       sr: int) -> np.ndarray:
    emb = _get_embedder()
    dim = int(getattr(emb, "embed_dim", 192) or 192)
    E = np.zeros((len(segments), dim), dtype=np.float32)
    for i, seg in enumerate(segments):
        a, b = int(seg.start * sr), int(seg.end * sr)
        clip = y[a:b]
        if len(clip) < int(0.3 * sr):                 # 过短则向两侧扩窗
            clip = y[max(0, a - int(0.2 * sr)):
                     min(len(y), b + int(0.2 * sr))]
        E[i] = emb.embed(clip)
    return E


def _cluster_neural(E: np.ndarray, num_speakers: int
                    ) -> tuple[np.ndarray, int]:
    """AHC（average，cosine）；num_speakers=0 按相似度阈值自动定 k。"""
    n = len(E)
    if num_speakers and num_speakers > 0:
        k = max(1, min(num_speakers, n))
        if k == 1:
            return np.zeros(n, dtype=int), 1
        ac = AgglomerativeClustering(n_clusters=k, metric="cosine",
                                     linkage="average")
        return ac.fit_predict(E), k
    ac = AgglomerativeClustering(n_clusters=None, metric="cosine",
                                 linkage="average",
                                 distance_threshold=1.0 - _SIM_THR)
    labels = ac.fit_predict(E)
    return labels, int(len(set(labels)))


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def diarize(y: np.ndarray, segments: list[Segment],
            num_speakers: int = 0, sr: int = 16000
            ) -> tuple[list[Segment], int]:
    """给 segments 填充 speaker，返回 (segments, 识别出的说话人数)。

    优先 CAM++ 神经声纹 + AHC；speakeronnx 不可用时降级 MFCC + KMeans。
    num_speakers=0 自动估计；>0 表示用户已知参会人数。
    """
    if not segments:
        return segments, 1
    try:
        E = _neural_embeddings(y, segments, sr)
        labels, k = _cluster_neural(E, num_speakers)
        log.info("说话人分离（神经声纹 %s）：识别出 %d 位说话人", _SPK_ALIAS, k)
    except Exception as exc:  # noqa: BLE001
        log.warning("神经声纹不可用（%s），降级为 MFCC + KMeans", exc)
        n_mfcc = config.DIAR_MFCC_N
        X = np.zeros((len(segments), n_mfcc * 2))
        for i, seg in enumerate(segments):
            a, b = int(seg.start * sr), int(seg.end * sr)
            clip = y[a:b]
            if len(clip) < int(0.1 * sr):
                clip = y[max(0, a - int(0.2 * sr)):
                         min(len(y), b + int(0.2 * sr))]
            X[i] = _segment_vector(clip, n_mfcc)
        sd = X.std(axis=0)
        sd[sd < 1e-3] = 1.0
        X = (X - X.mean(axis=0)) / sd
        k = _choose_k_mfcc(X, num_speakers, len(segments))
        if k == 1:
            for seg in segments:
                seg.speaker = "说话人1"
            log.info("说话人分离（MFCC）：判定为单人")
            return segments, 1
        labels = KMeans(n_clusters=k, n_init=10,
                        random_state=0).fit_predict(X)
    order: list[int] = []
    for lab in labels:
        if int(lab) not in order:
            order.append(int(lab))
    nm = {l: f"说话人{i + 1}" for i, l in enumerate(order)}
    for seg, lab in zip(segments, labels):
        seg.speaker = nm[int(lab)]
    return segments, k