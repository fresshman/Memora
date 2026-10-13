"""近场跨会话验证（train_L S01，金标准 rttm）：
片段A 按金标准真实身份注册主导者（模拟"会议1已重命名"）；
片段B 聚类后自动识别，核对 正确识别 / 误认 / 漏认。
"""
from __future__ import annotations

import os
import tempfile
from collections import Counter

from memora.whisper import audio as A
from memora.whisper import contacts, diarize as D

AUDIO = r"E:\UNpress\train_L\wav\20200706_L_R001S01C01.flac"
RTTM = r"E:\UNpress\train_L\TextGrid\20200706_L_R001S01C01.rttm"


def rttm_segs(t0, t1):
    out = []
    for line in open(RTTM, encoding="utf-8"):
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


def cluster_true(y, sr, t0, t1):
    """返回 (wins, lab, E, 每簇金标准身份)。"""
    seg = y[int(t0 * sr):int(t1 * sr)]
    wins = D._spk_windows(seg, sr)
    E = D._embed_windows(seg, sr, wins)
    lab, k = D._cluster_neural(E, 0)
    gt = rttm_segs(t0, t1)
    c2gt = {}
    for (ws, we), l in zip(wins, lab):
        g = gt_at((ws + we) / 2 + t0, gt)
        if g:
            c2gt.setdefault(int(l), Counter())[g] += 1
    true_id = {l: c.most_common(1)[0][0] for l, c in c2gt.items()}
    return wins, lab, E, true_id, k


def main():
    y, sr = A.decode(AUDIO)
    tmp = os.path.join(tempfile.gettempdir(), "memora_cross.json")
    if os.path.exists(tmp):
        os.remove(tmp)
    store = contacts.get_store(path=tmp)

    # 片段A（33-200）：注册金标准主导者（>=4 窗）
    wA, lA, EA, idA, kA = cluster_true(y, sr, 33, 200)
    print(f"片段A 聚类 k={kA}，每簇金标准：{idA}")
    for l, true in idA.items():
        rows = [i for i in range(len(EA)) if int(lA[i]) == l]
        if len(rows) >= 4:
            store.register(true, contacts.cluster_centroid(EA, lA, l))
    print(f"已注册：{[c.name for c in store.contacts]}")

    # 片段B（400-600）：聚类 + identify
    wB, lB, EB, idB, kB = cluster_true(y, sr, 400, 600)
    print(f"\n片段B 聚类 k={kB}，每簇金标准：{idB}")
    ok = wrong = missed = 0
    for l, true in sorted(idB.items()):
        rows = [i for i in range(len(EB)) if int(lB[i]) == l]
        if len(rows) < 2:
            continue
        cen = contacts.cluster_centroid(EB, lB, l)
        c, score = store.identify(cen)
        if c is None:
            missed += 1
            print(f"  簇{l}（真实 {true}）：漏认 score={score:.3f}")
        elif c.name == true:
            ok += 1
            print(f"  簇{l}（真实 {true}）：正确 score={score:.3f}")
        else:
            wrong += 1
            print(f"  簇{l}（真实 {true}）：误认成 {c.name} score={score:.3f}")
    print(f"\n近场跨会话：正确 {ok}，误认 {wrong}，漏认 {missed}")


if __name__ == "__main__":
    main()
