"""dump whisper 完整转写段（不做分离），看清录音真实内容结构。"""
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
              print_timestamps=False, no_context=True,
              token_timestamps=True, split_on_word=True)
    raw = m.transcribe(np.ascontiguousarray(y, np.float32), language="zh",
                       initial_prompt=build_initial_prompt("zh", None))
    for i, s in enumerate(raw):
        t = (s.text or "").strip()
        if t:
            print(f"{i:3d} [{s.t0*.01:6.1f}-{s.t1*.01:6.1f}] {t}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else
         r"data/voice_test/clip_8ch_30_210.wav")
