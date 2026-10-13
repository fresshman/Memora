"""诊断：短窗聚类 7 人但段映射只覆盖 6 人——找出"消失"的少言者。

列出每个聚类的短窗、对应 whisper 段文本与段内投票，定位第 7 人为什么没
独立段。
"""
from __future__ import annotations

import numpy as np
from pywhispercpp.model import Model

from memora import config
from memora.whisper import audio as A
from memora.whisper import diarize as D
from memora.whisper.transcribe import build_initial_prompt, Segment


def main() -> None:
    path = r"data/voice_test/clip_8ch_30_210.wav"
    y, sr = A.decode(path)
    mp = config.find_whisper_model(config.WHISPER_DEFAULT_MODEL)
    m = Model(model=str(mp), print_progress=False, print_realtime=False,
              print_timestamps=False, no_context=True,
              token_timestamps=True, split_on_word=True)
    raw = m.transcribe(np.ascontiguousarray(y, np.float32), language="zh",
                       initial_prompt=build_initial_prompt("zh", None))
    segs = [Segment(round(s.t0 * .01, 3), round(s.t1 * .01, 3),
                    s.text.strip()) for s in raw if s.text.strip()]
    wins = D._spk_windows(y, sr)
    E = D._embed_windows(y, sr, wins)
    lab, k = D._cluster_neural(E, 0)

    # 每聚类短窗数
    win_of: dict[int, list[tuple]] = {}
    for w, l in zip(wins, lab):
        win_of.setdefault(int(l), []).append(w)
    # 每段归属（加权投票）
    seg_lab = D._assign_segments(segs, wins, lab)
    covered = {int(l) for l in seg_lab if int(l) >= 0}

    for c in sorted(win_of, key=lambda c: -len(win_of[c])):
        ws_ = win_of[c]
        t0 = min(w[0] for w in ws_); t1 = max(w[1] for w in ws_)
        mark = "有独立段" if c in covered else ">>> 无独立段"
        print(f"\n聚类{c}（{len(ws_)} 窗 {t0:.1f}-{t1:.1f}s）{mark}")
        if c in covered:
            continue
        # 该聚类短窗落在哪些段，段内各聚类重叠
        for (a, b) in ws_:
            for i, seg in enumerate(segs):
                ov = min(seg.end, b) - max(seg.start, a)
                if ov > 0:
                    # 该段各聚类重叠
                    votes = {}
                    for (x, z), l2 in zip(wins, lab):
                        v = min(seg.end, z) - max(seg.start, x)
                        if v > 0:
                            v = int(l2)
                            votes[v] = votes.get(v, 0) + v
                    top = max(votes, key=votes.get)
                    print(f"  窗{a:.1f}-{b:.1f} → 段{i}"
                          f"[{seg.start:.1f}-{seg.end:.1f}] 归属聚类{top}"
                          f"  文本：{seg.text}")
                    break  # 每窗只看首个重叠段


if __name__ == "__main__":
    main()
