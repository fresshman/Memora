"""热词 + max_len 强制切短：能否同时保留热词准确率和短段分离。"""
from __future__ import annotations

import numpy as np
from pywhispercpp.model import Model

from memora import config
from memora.whisper import audio as A
from memora.whisper.transcribe import build_initial_prompt, load_hotwords


def main(path: str) -> None:
    y, sr = A.decode(path)
    mp = config.find_whisper_model(config.WHISPER_DEFAULT_MODEL)
    m = Model(model=str(mp), print_progress=False, print_realtime=False,
              print_timestamps=False, no_context=True)
    hot = load_hotwords()
    p = build_initial_prompt("zh", hot)
    yy = np.ascontiguousarray(y, np.float32)
    for ml in [0, 24, 40, 60, 80]:
        kw = dict(initial_prompt=p, language="zh",
                  token_timestamps=True, split_on_word=True)
        if ml:
            kw["max_len"] = ml
        raw = m.transcribe(yy, **kw)
        lens = [round((s.t1 - s.t0) * .01, 1) for s in raw
                if (s.text or "").strip()]
        print(f"热词 +max_len={ml}: {len(lens)} 段, 最长 {max(lens)}s, "
              f"前8={lens[:8]}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else
         r"data/voice_test/clip_8ch_30_210.wav")
