"""校准说话人分离：VAD 窗长 + AHC 聚类阈值（不依赖 whisper，快速）。

流程：decode -> 能量 VAD 短窗 -> CAM++ embedding -> 扫「窗长 × 相似度阈值」
组合，报告每个组合的聚类人数（已知真实 7 人），并打印每人段数。
"""
from __future__ import annotations

import sys

import numpy as np

from memora import config
from memora.whisper import diarize as D

REAL_K = 7


def main(path: str) -> None:
    y, sr = D.audio.decode(path)
    for win_s in (2.0, 2.5, 3.0, 3.5):
        wins = D._spk_windows(y, sr, win_s=win_s, max_s=win_s + 0.5)
        E = D._embed_windows(y, sr, wins)
        print(f"\n=== win_s={win_s}，{len(wins)} 个窗 ===")
        for thr in (0.45, 0.5, 0.55, 0.6):
            D._SIM_THR = thr
            labels, k = D._cluster_neural(E, 0)
            counts = [int(np.sum(np.asarray(labels) == l))
                      for l in sorted(set(labels))]
            small = sum(1 for c in counts if c == 1)
            mark = "  <== 7" if k == REAL_K else ""
            print(f"  thr={thr:.2f} -> k={k:2d}（单窗簇 {small}）{mark}")


if __name__ == "__main__":
    default = str(config.DATA_DIR / "voice_test" / "clip_8ch_30_210.wav")
    main(sys.argv[1] if len(sys.argv) > 1 else default)
