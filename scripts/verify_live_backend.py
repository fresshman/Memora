# -*- coding: utf-8 -*-
"""真实模型集成验证：clear_zh.wav 经 WS 实时转写，验证 delta 与 final（需模型，较慢）。"""
from __future__ import annotations

import base64

import numpy as np
import soundfile as sf

from fastapi.testclient import TestClient

from server.main import app

y, sr = sf.read("data/voice_test/clear_zh.wav", dtype="float32")
if y.ndim > 1:
    y = y.mean(1)
if sr != 16000:
    n = int(len(y) * 16000 / sr)
    y = np.interp(np.linspace(0, len(y) - 1, n), np.arange(len(y)),
                  y).astype(np.float32)
i16 = (y * 32767).astype(np.int16)
chunk = 16000  # 1s 一块

deltas = []
with TestClient(app) as c:
    with c.websocket_connect("/api/voice/stream") as ws:
        ws.send_json({"type": "start", "language": "zh"})
        print("ready:", ws.receive_json())
        for i in range(0, len(i16), chunk):
            ws.send_json({
                "type": "chunk",
                "data": base64.b64encode(i16[i:i + chunk].tobytes()).decode(),
            })
        ws.send_json({"type": "stop"})
        while True:
            m = ws.receive_json()
            t = m["type"]
            if t == "delta":
                for s in m["segments"]:
                    deltas.append(s)
                    print(f"[delta {s['start']:5.1f}-{s['end']:5.1f}] "
                          f"{s['speaker']}: {s['text']}")
            elif t == "final":
                print("\n=== FINAL ===")
                print("meta:", m["meta"])
                print("num segments:", len(m["segments"]))
                for s in m["segments"]:
                    print(f"  {s['speaker']} [{s['start']:.1f}-"
                          f"{s['end']:.1f}]: {s['text']}")
                print("text len:", len(m["text"]))
                break
            elif t == "error":
                print("ERROR:", m["message"])
                break

print("\nreal-time delta count:", len(deltas))
