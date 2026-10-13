"""诊断：真实会议上段文本 vs token 原始字节拼接的差异。

whisper.cpp 开启 token_timestamps 后，token 序列可能含时间戳对齐用的重复/
回退 token，而段文本是去重后的最终结果。本脚本逐段对比，定位差异类型。
"""
from __future__ import annotations

import numpy as np

from memora import config
from memora.whisper import audio as A
from memora.whisper.transcribe import build_initial_prompt, Segment


def main() -> None:
    path = r"data/voice_test/clip_8ch_30_210.wav"
    y, sr = A.decode(path)
    from pywhispercpp.model import Model
    mp = config.find_whisper_model(config.WHISPER_DEFAULT_MODEL)
    m = Model(model=str(mp), print_progress=False, print_realtime=False,
              print_timestamps=False, no_context=True,
              token_timestamps=True, split_on_word=True)
    raw = m.transcribe(np.ascontiguousarray(y, np.float32), language="zh",
                       initial_prompt=build_initial_prompt("zh", None))
    segs = [Segment(round(s.t0 * .01, 3), round(s.t1 * .01, 3),
                    s.text.strip()) for s in raw]
    import _pywhispercpp as pw
    ctx = m._ctx
    for si in range(pw.whisper_full_n_segments(ctx)):
        toks = []
        for j in range(pw.whisper_full_n_tokens(ctx, si)):
            d = pw.whisper_full_get_token_data(ctx, si, j)
            tid = int(d.id)
            b = pw.whisper_token_to_bytes(ctx, tid) if tid < 50257 else \
                f"[SPECIAL:{tid}]".encode()
            toks.append((tid, b, round(d.t0 * .01, 2),
                         round(d.t1 * .01, 2)))
        if si < 3:
            print(f"\n===== 段{si} [{segs[si].start:.1f}-{segs[si].end:.1f}] =====")
            print("段文本:", segs[si].text)
            print("token 序列:")
            for tid, b, a, z in toks:
                print(f"   {a:6.2f}-{z:6.2f} id={tid} {b!r}")
        # 整体对比
        jb = b"".join(t[1] for t in toks if t[0] < 50257)
        js = jb.decode("utf-8", errors="ignore").strip()
        if js.replace(" ", "") != segs[si].text.replace(" ", ""):
            print(f"!! 段{si} 不一致：段文本 {len(segs[si].text)} 字 vs "
                  f"token拼接 {len(js)} 字")


if __name__ == "__main__":
    main()
