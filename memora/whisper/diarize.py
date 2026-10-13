"""说话人分离（diarization，本地离线，纯 CPU，不依赖 torch / librosa）。

两级方案：
  A. 神经声纹（推荐）：speakeronnx 的 CAM++ ONNX 提取说话人 embedding
     （onnxruntime，pip 即装，不引 torch）。关键：声纹与 whisper 句子分段
     解耦——先用能量 VAD 把语音切成约 2.5s 短窗（跳过静音、长度均匀），
     对每个短窗提 embedding，再以「平均链接凝聚聚类（AHC）+ cosine 阈值
     0.5」自动定人数，最后把聚类标签按时间重叠加权投票映射回 whisper 句子段。
     短窗解耦避免了热词 initial_prompt 让 whisper 长句合并（实测可达 29s、
     混合多人）造成的段级 embedding 平均化、聚类退化（7 人曾退化为 2 人）。
  B. 轻量降级：无 speakeronnx 时，对同一批 VAD 短窗用 numpy/scipy 自实现
     MFCC 向量 + KMeans（轮廓系数 + 簇间质心间距双重门控）。

跨会议声纹：聚类 centroid 作为说话人样本，重命名即注册（contacts.json），
新会议聚类后按 0.72 阈值自动识别已知联系人（远场实测：主导发言者识别 100%、
零误认；少言者样本不足宁可漏认，重命名补样本后改善）。

实测边界（8 通道远场小阵列）：轮流发言、低重叠、句间有停顿 → 正确 7 人、
DER≈0.12；快速抢话、高重叠、无停顿 → 小孔径阵列（通道时延 ±0.12ms）无法
空间分人、混响污染声纹，DER 偏高，属硬件性难题。近场 / 会议平台导出音频
效果更好。标签按首次出现顺序命名「说话人N」。
"""
from __future__ import annotations

import numpy as np
from scipy.fft import dct
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score

from .. import config
from ..log import get_logger
from . import audio
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


def _spk_windows(y: np.ndarray, sr: int, win_s: float = 2.5,
                 max_s: float = 3.0, min_s: float = 0.6):
    """能量 VAD 得语音区域，切成约 win_s 的短窗（跳过静音、不超长混合多人）。"""
    voiced, hop_ms = audio.energy_vad(y)
    regions = audio.speech_regions(voiced, hop_ms,
                                   min_speech_ms=300, min_silence_ms=300)
    wins: list[tuple[float, float]] = []
    for s, e in regions:
        if e - s <= max_s:
            wins.append((s, e))
            continue
        t = s
        while t < e:
            wb = t + win_s
            if wb >= e:
                wins.append((t, e))
                break
            wins.append((t, wb))
            t = wb
    return [(s, e) for s, e in wins if e - s >= min_s]


def _token_windows(segments: list[Segment], win_s: float = 2.0,
                   max_gap: float = 0.5, min_s: float = 0.6):
    """按 whisper token 边界把语音组合成 ~win_s 伪窗。

    与 VAD 窗相比，伪窗边界对齐 token（不劈词、不跨长停顿），聚类后 token
    能无歧义归到所属伪窗，避免窗边界与词边界错位。
    """
    toks = [t for seg in segments for t in getattr(seg, "tokens", [])]
    toks.sort(key=lambda t: t.start)
    wins: list[tuple[float, float]] = []
    ws = we = None
    for t in toks:
        if ws is None:
            ws, we = t.start, t.end
        elif t.start - we > max_gap or t.end - ws >= win_s:
            wins.append((ws, we))
            ws, we = t.start, t.end
        else:
            we = t.end
    if ws is not None:
        wins.append((ws, we))
    return [(s, e) for s, e in wins if e - s >= min_s]


def _embed_windows(y: np.ndarray, sr: int,
                   wins: list[tuple[float, float]]) -> np.ndarray:
    emb = _get_embedder()
    dim = int(getattr(emb, "embed_dim", 192) or 192)
    E = np.zeros((len(wins), dim), dtype=np.float32)
    for i, (s, e) in enumerate(wins):
        a, b = int(s * sr), int(e * sr)
        clip = y[a:b]
        if len(clip) < int(0.6 * sr):
            clip = y[max(0, a - int(0.2 * sr)):
                     min(len(y), b + int(0.2 * sr))]
        E[i] = emb.embed(clip)
    return E


def _mfcc_windows(y: np.ndarray, sr: int,
                  wins: list[tuple[float, float]], n_mfcc: int) -> np.ndarray:
    X = np.zeros((len(wins), n_mfcc * 2))
    for i, (s, e) in enumerate(wins):
        a, b = int(s * sr), int(e * sr)
        clip = y[a:b]
        if len(clip) < int(0.1 * sr):
            clip = y[max(0, a - int(0.2 * sr)):
                     min(len(y), b + int(0.2 * sr))]
        X[i] = _segment_vector(clip, n_mfcc)
    sd = X.std(axis=0)
    sd[sd < 1e-3] = 1.0
    return (X - X.mean(axis=0)) / sd


def _cluster_neural(E: np.ndarray, num_speakers: int
                    ) -> tuple[np.ndarray, int]:
    """平均链接凝聚聚类（AHC，CAM++ embedding）；num_speakers=0 按相似度阈值。

    声纹与 whisper 句子段解耦：先按 VAD 短窗提 embedding，再 AHC + cosine
    阈值自动定人数。选 AHC 而非谱聚类：真实近场会议中，谱聚类在"快速轮流"
    段（大量混合窗）会退化到 k=1、信息丢失；AHC 宁可过分割（每位主导者保留
    独立簇，用户可在界面合并），也不把不同人并成一人。
    """
    n = len(E)
    if n < 2:
        return np.zeros(n, dtype=int), 1
    if num_speakers and num_speakers > 0:
        k = max(1, min(num_speakers, n))
        if k == 1:
            return np.zeros(n, dtype=int), 1
        lab = AgglomerativeClustering(n_clusters=k, metric="cosine",
                                      linkage="average").fit_predict(E)
        return lab, k
    # 自动 k：平均链接 + cosine 相似度阈值
    ac = AgglomerativeClustering(
        n_clusters=None, metric="cosine", linkage="average",
        distance_threshold=1.0 - config.SPEAKER_SIM_THRESHOLD)
    lab = ac.fit_predict(E)
    return lab, len(set(lab.tolist()))


def _assign_segments(segments: list[Segment],
                     wins: list[tuple[float, float]],
                     win_labels: np.ndarray) -> np.ndarray:
    """每个 whisper 段按时间重叠窗加权投票，返回聚类标签（-1=无覆盖）。"""
    out = np.full(len(segments), -1, dtype=int)
    for i, seg in enumerate(segments):
        votes: dict[int, float] = {}
        for (ws, we), lab in zip(wins, win_labels):
            ov = min(seg.end, we) - max(seg.start, ws)
            if ov > 0:
                v = int(lab)
                votes[v] = votes.get(v, 0.0) + ov
        if votes:
            out[i] = max(votes, key=votes.get)
    return out


def rebuild_segments(segments: list[Segment],
                     wins: list[tuple[float, float]],
                     win_labels: np.ndarray,
                     name_map: dict[int, str]) -> list[Segment]:
    """用聚类窗 + token 字节重建记录段。

    每个 token 按时间重叠最大的窗归入聚类；相邻同聚类 token 的原始字节拼接，
    段边界 UTF-8 解码（中文 BPE 字节跨 token 还原汉字）。记录段边界落在说话
    人切换处，少言者不再被长段吞掉。
    """
    def lab_at(tk) -> int:
        best, best_ov = -1, 0.0
        for (ws, we), l in zip(wins, win_labels):
            ov = min(tk.end, we) - max(tk.start, ws)
            if ov > best_ov:
                best_ov, best = ov, int(l)
        return best

    def emit(bs: bytes, a: float, b: float, lab: int):
        text = bs.decode("utf-8", errors="ignore").strip()
        if not text:
            return None
        return Segment(a, b, text, name_map.get(lab, "说话人1"))

    all_tk = [tk for seg in segments for tk in getattr(seg, "tokens", [])]
    all_tk.sort(key=lambda t: t.start)
    out: list[Segment] = []
    cur_lab, cur_b, cur_s, cur_e = None, None, 0.0, 0.0
    for tk in all_tk:
        lab = lab_at(tk)
        if cur_b is None or lab != cur_lab:
            if cur_b is not None:
                seg = emit(cur_b, cur_s, cur_e, cur_lab)
                if seg is not None:
                    out.append(seg)
            cur_b, cur_lab = tk.data, lab
            cur_s, cur_e = tk.start, tk.end
        else:
            cur_b += tk.data
            cur_e = max(cur_e, tk.end)
    if cur_b is not None:
        seg = emit(cur_b, cur_s, cur_e, cur_lab)
        if seg is not None:
            out.append(seg)
    return out


def diarize_full(y: np.ndarray, segments: list[Segment],
                 num_speakers: int = 0, sr: int = 16000):
    """返回 (segments, k, E, win_labels, name_map)。

    E：神经声纹路径为窗 embedding（声纹注册/识别用）；MFCC 降级为 None。
    name_map：聚类标签 -> 「说话人N」。
    """
    if not segments:
        return segments, 1, None, None, {}
    wins = _spk_windows(y, sr)
    E, win_labels = None, None
    if not wins:
        for seg in segments:
            seg.speaker = "说话人1"
        return segments, 1, None, None, {0: "说话人1"}
    try:
        E = _embed_windows(y, sr, wins)
        win_labels, k = _cluster_neural(E, num_speakers)
        log.info("说话人分离（神经声纹 %s，%d 个短窗）：识别出 %d 位说话人",
                 _SPK_ALIAS, len(wins), k)
    except Exception as exc:  # noqa: BLE001
        log.warning("神经声纹不可用（%s），降级 MFCC + KMeans", exc)
        E = None
        n_mfcc = config.DIAR_MFCC_N
        X = _mfcc_windows(y, sr, wins, n_mfcc)
        k = _choose_k_mfcc(X, num_speakers, len(wins))
        if k == 1:
            for seg in segments:
                seg.speaker = "说话人1"
            log.info("说话人分离（MFCC）：判定单人")
            return segments, 1, None, None, {0: "说话人1"}
        win_labels = KMeans(n_clusters=k, n_init=10,
                            random_state=0).fit_predict(X)
    # 按聚类最早出现时间（窗）命名
    first_time: dict[int, float] = {}
    for (ws, we), l in zip(wins, win_labels):
        l = int(l)
        if l not in first_time or ws < first_time[l]:
            first_time[l] = ws
    order = sorted(first_time, key=lambda l: first_time[l])
    name_map = {int(l): f"说话人{i + 1}" for i, l in enumerate(order)}
    seg_lab = _assign_segments(segments, wins, win_labels)
    for seg, lab in zip(segments, seg_lab):
        seg.speaker = name_map.get(int(lab), "说话人1")
    from .meeting import merge_adjacent
    segments = merge_adjacent(segments, 0.6)
    return segments, k, E, win_labels, name_map


def diarize(y: np.ndarray, segments: list[Segment],
            num_speakers: int = 0, sr: int = 16000
            ) -> tuple[list[Segment], int]:
    """给 segments 填充 speaker，返回 (segments, 识别出的说话人数)。

    优先 CAM++ 神经声纹 + AHC；speakeronnx 不可用时降级 MFCC + KMeans。
    num_speakers=0 自动估计；>0 表示用户已知参会人数。
    """
    segments, k, _E, _l, _nm = diarize_full(
        y, segments, num_speakers=num_speakers, sr=sr)
    return segments, k
