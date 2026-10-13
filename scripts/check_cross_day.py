"""跨日期会议验证（真正的"不同会议"）：7月6日注册主导者 → 7月7日自动识别。
金标准说话人编号跨日期一致（001-007 是同一批人）。
"""
from __future__ import annotations

import os
import tempfile
from collections import Counter

from memora.whisper import audio as A
from memora.whisper import contacts, diarize as D

W1 = r"E:\UNpress\train_L\wav\20200706_L_R001S01C01.flac"
R1 = r"E:\UNpress\train_L\TextGrid\20200706_L_R001S01C01.rttm"
W2 = r"E:\UNpress\train_L\wav\20200707_L_R001S01C01.flac"
R2 = r"E:\UNpress\train_L\TextGrid\20200707_L_R001S01C01.rttm"


def rttm_segs(path, t0, t1):
    out = []
    for line in open(path, encoding="utf-8"):
        p = line.split()
        if p[0] != "SPEAKER":
            continue
        st, du, sp = float(p[3]), float(p[4]), p[7]
        if st + du > t0 and st < t1:
            out.append((max(st, t0), min(st + du, t1), sp))
    return out


def gt_at(t, seg):
    for s, e, sp in seg:
        if s <= t < e:
            return sp
    return None


def cluster(y, sr, t0, t1, rttm):
    seg = y[int(t0 * sr):int(t1 * sr)]
    wins = D._spk_windows(seg, sr)
    E = D._embed_windows(seg, sr, wins)
    lab, k = D._cluster_neural(E, 0)
    gt = rttm_segs(rttm, t0, t1)
    c2gt = {}
    for (ws, we), l in zip(wins, lab):
        g = gt_at((ws + we) / 2 + t0, gt)
        if g:
            c2gt.setdefault(int(l), Counter())[g] += 1
    return wins, lab, E, {l: c.most_common(1)[0][0]
                         for l, c in c2gt.items()}, k, c2gt


def main():
    y1, sr1 = A.decode(W1)
    y2, sr2 = A.decode(W2)
    tmp = os.path.join(tempfile.gettempdir(), "memora_crossday.json")
    if os.path.exists(tmp):
        os.remove(tmp)
    store = contacts.get_store(path=tmp)

    # 会议1（7月6日 33-260）
    wA, lA, EA, idA, kA, cA = cluster(y1, sr1, 33, 400, R1)
    print(f"会议1 聚类 k={kA}，每簇金标准：{idA}")
    for l, c in cA.items():
        if sum(c.values()) >= 4:
            store.register(idA[l], contacts.cluster_centroid(EA, lA, l))
    print(f"已注册：{[c.name for c in store.contacts]}")

    # 会议2（7月7日 71-300）
    wB, lB, EB, idB, kB, cB = cluster(y2, sr2, 71, 500, R2)
    print(f"\n会议2 聚类 k={kB}，每簇金标准：{idB}")
    ok = wrong = missed = 0
    for l, c in sorted(cB.items()):
        if sum(c.values()) < 2:
            continue
        cen = contacts.cluster_centroid(EB, lB, l)
        hit, score = store.identify(cen)
        true = idB[l]
        if hit is None:
            missed += 1
            print(f"  簇{l}（真实 {true}，{sum(c.values())}窗）：漏认 {score:.3f}")
        elif hit.name == true:
            ok += 1
            print(f"  簇{l}（真实 {true}）：正确 {score:.3f}")
        else:
            wrong += 1
            print(f"  簇{l}（真实 {true}）：误认成 {hit.name} {score:.3f}")
    print(f"\n跨日期会议：正确 {ok}，误认 {wrong}，漏认 {missed}")


if __name__ == "__main__":
    main()
