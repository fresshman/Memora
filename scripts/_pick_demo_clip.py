# -*- coding: utf-8 -*-
"""解析 RTTM，找多说话人密集窗口，截取 16kHz 单声道演示音频。"""
import os, subprocess, sys

RTTM = r'E:\UNpress\train_L\TextGrid\20200706_L_R001S01C01.rttm'
SRC_FLAC = r'E:\UNpress\train_L\wav\20200706_L_R001S01C01.flac'
OUT = r'F:\python-exercise\Industrial_LLM\langchain-learn\Memora\data\_frames\demo_meeting.wav'

segs = []
with open(RTTM, encoding='utf-8') as f:
    for line in f:
        p = line.split()
        if len(p) >= 8 and p[0] == 'SPEAKER':
            segs.append((float(p[3]), float(p[4]), p[7]))
print("total segments:", len(segs), "duration ~",
      max(s+d for s, d, _ in segs), "speakers:",
      sorted(set(x[2] for x in segs)))

WIN, STEP = 40, 5
cands = []
tmax = max(s+d for s, d, _ in segs)
t = 0
while t < tmax - WIN:
    inside = [(s, d, sp) for s, d, sp in segs
              if s < t + WIN and s + d > t]
    spks = set(x[2] for x in inside)
    speech = sum(min(s+d, t+WIN) - max(s, t) for s, d, _ in inside)
    cands.append((len(spks), speech, t, sorted(spks)))
    t += STEP

# 优先：说话人数>=3，按语音占比排序
best = [c for c in cands if c[0] >= 3]
best.sort(key=lambda x: (-x[0], -x[1]))
print("=== top windows ===")
for nsp, speech, t0, spks in best[:8]:
    print("t=%d nspk=%d speech=%.1fs/40 spks=%s" % (t0, nsp, speech, spks))

nsp, speech, t0, spks = best[0]
print("chosen window start:", t0)

# ffmpeg 截取并转 16kHz mono
cmd = ['ffmpeg', '-y', '-ss', str(t0), '-t', str(WIN), '-i', SRC_FLAC,
       '-ar', '16000', '-ac', '1', OUT]
r = subprocess.run(cmd, capture_output=True, text=True)
print("ffmpeg rc:", r.returncode)
if r.returncode != 0:
    print(r.stderr[-1500:])
else:
    print("saved:", OUT, os.path.getsize(OUT), "bytes")
