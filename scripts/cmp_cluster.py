"""聚类方法系统对比：多片段 × AHC阈值 × 谱聚类核，找稳健配置。
输出每段的自动 k 与金标准窗准确率。
"""
from __future__ import annotations

from collections import Counter

import numpy as np
from sklearn.cluster import AgglomerativeClustering, SpectralClustering
from sklearn.metrics import silhouette_score

from memora.whisper import audio as A
from memora.whisper import diarize as D
from scripts.check_cross_day import rttm_segs, gt_at

SEGS = [
    (r"E:\UNpress\train_L\wav\20200706_L_R001S01C01.flac",
     r"E:\UNpress\train_L\TextGrid\20200706_L_R001S01C01.rttm", 33, 333),
    (r"E:\UNpress\train_L\wav\20200706_L_R001S01C01.flac",
     r"E:\UNpress\train_L\TextGrid\20200706_L_R001S01C01.rttm", 33, 400),
    (r"E:\UNpress\train_L\wav\20200707_L_R001S01C01.flac",
     r"E:\UNpress\train_L\TextGrid\20200707_L_R001S01C01.rttm", 71, 300),
    (r"E:\UNpress\train_L\wav\20200707_L_R001S01C01.flac",
     r"E:\UNpress\train_L\TextGrid\20200707_L_R001S01C01.rttm", 71, 500),
]


def auto_ahc(E, thr):
    ac = AgglomerativeClustering(n_clusters=None, metric="cosine",
                                 linkage="average",
                                 distance_threshold=1.0 - thr)
    lab = ac.fit_predict(E)
    return lab, len(set(lab.tolist()))


def auto_spectral(S):
    bestk, bestsc = 1, -1.0
    for k in range(2, min(9, len(S))):
        try:
            lab = SpectralClustering(n_clusters=k, affinity="precomputed",
                                     random_state=0, n_init=10).fit_predict(S)
        except Exception:  # noqa: BLE001
            continue
        if len(set(lab.tolist())) < k:
            continue
        d = 1 - S
        np.fill_diagonal(d, 0)
        sc = silhouette_score(d, lab, metric="precomputed")
        if sc > bestsc:
            bestsc, bestk = sc, k
    if bestsc < 0.04:
        return np.zeros(len(S), int), 1
    return SpectralClustering(n_clusters=bestk, affinity="precomputed",
                              random_state=0, n_init=10).fit_predict(S), bestk


def acc(wins, lab, gt, t0):
    c2g = {}
    for (ws, we), l in zip(wins, lab):
        g = gt_at((ws + we) / 2 + t0, gt)
        if g:
            c2g.setdefault(int(l), Counter())[g] += 1
    m = {l: c.most_common(1)[0][0] for l, c in c2g.items()}
    cor = sum(1 for (ws, we), l in zip(wins, lab)
              if gt_at((ws + we) / 2 + t0, gt) == m.get(int(l)))
    tot = sum(1 for ws, we in wins if gt_at((ws + we) / 2 + t0, gt))
    return cor / max(1, tot)


def main():
    # 缓存各段 embedding
    cache = []
    for w, r, t0, t1 in SEGS:
        y, sr = A.decode(w)
        seg = y[int(t0 * sr):int(t1 * sr)]
        wins = D._spk_windows(seg, sr)
        E = D._embed_windows(seg, sr, wins)
        gt = rttm_segs(r, t0, t1)
        cache.append((f"{w[15:23]} {t0}-{t1}", wins, E, gt, t0))
        print(f"段 {t0}-{t1}: {len(wins)}窗, 金标准 {len(set(g for _,_,g in gt))}人")

    print("\n=== AHC 阈值 ===")
    for thr in [0.5, 0.55, 0.6, 0.65]:
        row = []
        for name, wins, E, gt, t0 in cache:
            lab, k = auto_ahc(E, thr)
            row.append(f"{name}:k{k}/{acc(wins,lab,gt,t0):.2f}")
        print(f"thr={thr}: " + "  ".join(row))

    print("\n=== 谱聚类核 ===")
    for sigma in [0.08, 0.12, 0.18, 0.25]:
        row = []
        for name, wins, E, gt, t0 in cache:
            C = E @ E.T
            S = np.exp(-np.clip(1 - C, 0, None) / sigma)
            np.fill_diagonal(S, 1)
            lab, k = auto_spectral(S)
            row.append(f"{name}:k{k}/{acc(wins,lab,gt,t0):.2f}")
        print(f"sigma={sigma}: " + "  ".join(row))


if __name__ == "__main__":
    main()
