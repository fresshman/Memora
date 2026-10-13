"""整合验证：voice._process 的 VAD 短窗 5 元组 + 注册→自动识别（一次 whisper）。

1) 前 90s 独立聚类，把主导者（≥4 窗）注册到临时库（模拟"会议1已重命名"）；
2) patch contacts.get_store 指向临时库；
3) 对完整音频调用 _process（whisper 转写 + 分离 + 识别），检查已注册者
   identified=True，其余 identified=False；全程零误认。
"""
from __future__ import annotations

import os
import sys
import tempfile

from memora.whisper import contacts, diarize, audio
from server.routes.voice import _process

CLIP = r"data/voice_test/clip_8ch_30_210.wav"


def main(path: str) -> None:
    y, sr = audio.decode(path)
    y1 = y[: int(90 * sr)]
    wins1 = diarize._spk_windows(y1, sr)
    E1 = diarize._embed_windows(y1, sr, wins1)
    lab1, _k1 = diarize._cluster_neural(E1, 0)

    tmp = os.path.join(tempfile.gettempdir(), "memora_verify_process.json")
    if os.path.exists(tmp):
        os.remove(tmp)
    store = contacts.get_store(path=tmp)
    registered = {}
    for l in sorted(set(int(x) for x in lab1)):
        rows = [i for i in range(len(E1)) if int(lab1[i]) == l]
        if len(rows) >= 4:
            name = f"测试人{l}"
            store.register(name, contacts.cluster_centroid(E1, lab1, l))
            registered[l] = name
    print(f"前半段注册 {len(registered)} 位主导者：{registered}")

    # _process 内部从模块取 get_store
    contacts.get_store = lambda path="": store

    record = _process(path, "整合测试会议", "zh", 0)
    d = record.to_dict()
    print(f"\n完整 _process：{len(d['segments'])} 段、"
          f"{len(d['speakers'])} 位说话人")
    hit = miss = 0
    for sp in d["speakers"]:
        flag = "已识别" if sp["identified"] else "未识别"
        if sp["identified"]:
            hit += 1
        else:
            miss += 1
        print(f"  {sp['name']}：{flag}（score={sp['score']}，"
              f"contact={sp['contact_id'] or '-'}）")
    print(f"\n结果：自动识别 {hit} 人，未识别 {miss} 人；零误认="
          f"{all(sp['name'] in registered.values() for sp in d['speakers'] if sp['identified'])}")

    from collections import Counter
    cnt = Counter(s["speaker"] for s in d["segments"])
    print("\n每位说话人段数（少言者应有独立段）：")
    for name, n in cnt.most_common():
        print(f"  {name}: {n} 段")

    print("\n前 12 段（检查文本完整、边界在说话人切换处）：")
    for s in d["segments"][:12]:
        def ts(x):
            return f"{int(x // 60)}:{x % 60:04.1f}"
        print(f"  [{ts(s['start'])}] {s['speaker']}：{s['text']}")
    total = sum(len(s["text"]) for s in d["segments"])
    print(f"\n重建记录总字数：{total}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else CLIP)
