"""对照实验：language / max_len / split_on_word 对 whisper 段数的影响（模型只加载一次）。"""
from __future__ import annotations

import numpy as np
from pywhispercpp.model import Model

from memora import config
from memora.whisper import audio as A
from memora.whisper.transcribe import build_initial_prompt


def main(path: str) -> None:
    y, sr = A.decode(path)
    mp = config.find_whisper_model(config.WHISPER_DEFAULT_MODEL)
    m = Model(model=str(mp), print_progress=False, print_realtime=False,
              print_timestamps=False, no_context=True)
    prompt = build_initial_prompt("zh", None)
    yy = np.ascontiguousarray(y, np.float32)

    def run(tag: str, **kw) -> None:
        raw = m.transcribe(yy, **kw)
        lens = [round((s.t1 - s.t0) * .01, 1) for s in raw
                if (s.text or "").strip()]
        print(f"{tag}: {len(lens)} 段, 段长前10={lens[:10]}")

    base = dict(initial_prompt=prompt, token_timestamps=True)
    run("zh +split(无maxlen)", language="zh", split_on_word=True, **base)
    run("auto +split(无maxlen)", split_on_word=True, **base)
    run("zh +maxlen40 +split", language="zh", max_len=40,
        split_on_word=True, **base)
    run("zh +maxlen40 无split", language="zh", max_len=40, **base)
    run("zh 无任何切分", language="zh", **base)


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else
         r"data/voice_test/clip_8ch_30_210.wav")
