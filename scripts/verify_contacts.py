"""跨会话联系人声纹：真机闭环验证（同一人不同片段 vs 不同人）。

对一场真实会议的每个说话人：
  把该说话人的语音段切成两半，half1 注册、half2 再识别，统计「同一人相似度」；
  同时计算不同说话人之间的「异人相似度」，用于校准匹配阈值。

用法：python scripts/verify_contacts.py [音频路径]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from memora import config
from memora.whisper import contacts as C
from memora.whisper import diarize as diar_mod
from memora.whisper import audio, transcribe as asr_mod


def _centroid(E: np.ndarray, rows: list[int]) -> np.ndarray:
    m = E[rows].mean(axis=0)
    n = np.linalg.norm(m)
    return m / n if n > 1e-8 else m


def main(path: str) -> None:
    print(f"加载音频：{path}")
    y, sr = audio.decode(path)
    print("转写中（whisper.cpp）…")
    segs = asr_mod.transcribe_segments(y, sr=sr)
    segs, k, E, labels, _nm = diar_mod.diarize_full(y, segs)
    if E is None:
        print("声纹模块降级为 MFCC，无法做声纹验证。")
        return
    order: list[int] = []
    for lab in labels:
        if int(lab) not in order:
            order.append(int(lab))
    print(f"识别出 {k} 位说话人。")

    half: dict[int, tuple[np.ndarray, np.ndarray] | None] = {}
    for lab in order:
        rows = [i for i, l in enumerate(labels) if int(l) == lab]
        if len(rows) < 2:
            half[lab] = None
            continue
        mid = max(1, len(rows) // 2)
        half[lab] = (_centroid(E, rows[:mid]), _centroid(E, rows[mid:]))

    print("\n[同一人] 跨片段 cosine：")
    same = []
    for lab in order:
        if half[lab] is None:
            print(f"  说话人{lab}: 段太少，跳过")
            continue
        s = C.cosine(half[lab][0], half[lab][1])
        same.append(s)
        print(f"  说话人{lab}: {s:.3f}")

    print("\n[不同人] 跨片段 cosine：")
    cross = []
    for a in order:
        for b in order:
            if b <= a or half[a] is None or half[b] is None:
                continue
            s = C.cosine(half[a][0], half[b][1])
            cross.append(s)
            print(f"  说话人{a} vs 说话人{b}: {s:.3f}")

    print("\n=== 阈值校准 ===")
    if same:
        print(f"同一人相似度 min / mean：{min(same):.3f} / {np.mean(same):.3f}")
    if cross:
        print(f"异人相似度 max / mean：{max(cross):.3f} / {np.mean(cross):.3f}")
    print(f"当前匹配阈值：{config.CONTACT_MATCH_THRESHOLD}")


if __name__ == "__main__":
    default = str(Path(config.DATA_DIR) / "voice_test" / "clip_8ch_30_210.wav")
    main(sys.argv[1] if len(sys.argv) > 1 else default)
