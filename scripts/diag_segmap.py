"""诊断：段映射各环节的真实分布（whisper 段数 / 窗数 / k / 段映射 label）。"""
from __future__ import annotations

from collections import Counter

from memora.whisper import audio as A
from memora.whisper import diarize as D
from memora.whisper import transcribe as T


def main(path: str) -> None:
    y, sr = A.decode(path)
    segs = T.transcribe_segments(y, sr)
    print("whisper 段数:", len(segs))
    wins = D._spk_windows(y, sr)
    print("VAD 窗数:", len(wins))
    E = D._embed_windows(y, sr, wins)
    wl, k = D._cluster_neural(E, 0)
    print("聚类 k:", k)
    sl = D._assign_segments(segs, wins, wl)
    print("段映射 label 分布:", Counter(sl.tolist()))
    for lab in sorted(set(sl.tolist())):
        n = sum(1 for l in sl if l == lab)
        idxs = [i for i, l in enumerate(sl) if l == lab]
        span = []
        if idxs:
            span = [round(segs[idxs[0]].start, 1), round(segs[idxs[-1]].end, 1)]
        print(f"  label{lab}: {n} 段, 时间 {span}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else
         r"data/voice_test/clip_8ch_30_210.wav")
