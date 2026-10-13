"""近场聚类验证：S01 片段 VAD 窗聚类，直接与 rttm 金标准对比（不转写）。"""
from __future__ import annotations

from collections import Counter

import numpy as np
from sklearn.cluster import SpectralClustering

from memora.whisper import audio as A
from memora.whisper import diarize as D


def rttm_map(path, t0, t1):
    out = []
    for line in open(path, encoding="utf-8"):
        p = line.split()
        if p[0] != "SPEAKER":
            continue
        st, du, sp = float(p[3]), float(p[4]), p[7]
        if st + du > t0 and st < t1:
            out.append((max(st, t0), min(st + du, t1), sp))
    return out


def main(t0=33.0, t1=333.0) -> None:
    audio = r"E:\UNpress\train_L\wav\20200706_L_R001S01C01.flac"
    rttm = r"E:\UNpress\train_L\TextGrid\20200706_L_R001S01C01.rttm"
    y, sr = A.decode(audio)
    seg = y[int(t0 * sr):int(t1 * sr)]
    wins = D._spk_windows(seg, sr)
    wins_abs = [(s + t0, e + t0) for s, e in wins]
    E = D._embed_windows(seg, sr, wins)
    S = np.clip(E @ E.T, 0, 1)
    d = S.sum(1)
    D2 = np.diag(1 / np.sqrt(d))
    L = np.eye(len(S)) - D2 @ S @ D2
    ev = np.linalg.eigvalsh(L)
    print("特征值:", [round(x, 2) for x in ev[:10]])
    gt = rttm_map(rttm, t0, t1)

    def gt_at(t):
        for s, e, sp in gt:
            if s <= t < e:
                return sp
        return None

    print("金标准说话人:", sorted({sp for _, _, sp in gt}))
    for k in [5, 6, 7]:
        lab = SpectralClustering(n_clusters=k, affinity="precomputed",
                                 random_state=0, n_init=10).fit_predict(S)
        pairs = []
        for (ws, we), l in zip(wins_abs, lab):
            g = gt_at((ws + we) / 2)
            if g:
                pairs.append((int(l), g))
        c2g = {}
        for l, g in pairs:
            c2g.setdefault(l, Counter())[g] += 1
        mapping = {l: c.most_common(1)[0][0] for l, c in c2g.items()}
        correct = sum(1 for l, g in pairs if mapping[l] == g)
        print(f"谱聚类 k={k}: 窗准确率 {correct}/{len(pairs)}="
              f"{correct/max(1,len(pairs)):.3f}, 覆盖 {len(c2g)} 簇")
        if k == 5:
            for l in sorted(c2g):
                print(f"    簇{l}: {dict(c2g[l])}")


if __name__ == "__main__":
    main()
