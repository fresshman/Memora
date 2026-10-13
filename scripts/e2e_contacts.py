"""端到端：声纹注册→自动识别，两种评估（纯 VAD 聚类，不依赖 whisper）。

以完整音频聚类为 ground truth（真实 7 人）：
  A. 分层切半：每人一半窗注册、另一半窗识别（充足样本，测识别能力上限）；
  B. 时间切半：前 90s 注册、后 90s 识别（含冷启动，测真实首场/次场）。
用临时库，不污染真实 contacts。
"""
from __future__ import annotations

import os
import tempfile

import numpy as np

from memora.whisper import contacts as C
from memora.whisper import diarize as D


def centroid(E: np.ndarray, rows: list[int]) -> list[float]:
    v = E[rows].mean(axis=0)
    return (v / (np.linalg.norm(v) + 1e-9)).tolist()


def score(store: C.ContactStore, E: np.ndarray, expect: str,
          rows: list[int]) -> tuple[str, object, float]:
    contact, sc = store.identify(centroid(E, rows))
    if contact is not None and contact.name == expect:
        return "ok", contact, sc
    if contact is None:
        return "miss", None, sc
    return "wrong", contact, sc


def main(path: str, split: float = 90.0) -> None:
    y, sr = D.audio.decode(path)
    wins = D._spk_windows(y, sr)
    E = D._embed_windows(y, sr, wins)
    full_lab, fk = D._cluster_neural(E, 0)
    full_lab = np.asarray(full_lab)
    people = sorted(set(int(l) for l in full_lab))
    print(f"完整音频：{len(wins)} 窗、{fk} 人")

    # A. 分层切半
    tmp = os.path.join(tempfile.gettempdir(), "memora_e2e_strat.json")
    if os.path.exists(tmp):
        os.remove(tmp)
    st = C.get_store(path=tmp)
    win_of = {p: [i for i in range(len(E)) if full_lab[i] == p]
              for p in people}
    for p in people:
        r = win_of[p][0::2]
        if r:
            st.register(f"P{p}", centroid(E, r))
    print("\n[A] 分层切半（充足样本）：")
    ok = miss = wrong = 0
    for p in people:
        r = win_of[p][1::2]
        if not r:
            continue
        res, c, scv = score(st, E, f"P{p}", r)
        if res == "ok":
            ok += 1
            print(f"  P{p}: 正确（{scv:.3f}，{len(win_of[p])} 窗）")
        elif res == "miss":
            miss += 1
            print(f"  P{p}: 漏认（{scv:.3f}）")
        else:
            wrong += 1
            print(f"  P{p}: 误认 {c.name}（{scv:.3f}）")
    print(f"  => 正确 {ok}/{ok + miss + wrong}，漏 {miss}，误 {wrong}")

    # B. 时间切半
    first = [i for i, (s, e) in enumerate(wins) if e <= split]
    second = [i for i, (s, e) in enumerate(wins) if s >= split]
    tmp2 = os.path.join(tempfile.gettempdir(), "memora_e2e_time.json")
    if os.path.exists(tmp2):
        os.remove(tmp2)
    st2 = C.get_store(path=tmp2)
    for i in first:
        st2.register(f"P{int(full_lab[i])}", E[i].tolist())  # 单窗注册(冷启动)
    print(f"\n[B] 时间切半（前{split:.0f}s 注册、后{split:.0f}s 识别）：")
    ok = miss = wrong = 0
    # 后半按人聚合识别
    second_people = {}
    for i in second:
        second_people.setdefault(int(full_lab[i]), []).append(i)
    for p, rows in second_people.items():
        res, c, scv = score(st2, E, f"P{p}", rows)
        if res == "ok":
            ok += 1
            print(f"  P{p}: 正确（{scv:.3f}，后半 {len(rows)} 窗）")
        elif res == "miss":
            miss += 1
            print(f"  P{p}: 漏认（{scv:.3f}）")
        else:
            wrong += 1
            print(f"  P{p}: 误认 {c.name}（{scv:.3f}）")
    print(f"  => 正确 {ok}/{ok + miss + wrong}，漏 {miss}，误 {wrong}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else
         r"data/voice_test/clip_8ch_30_210.wav")
