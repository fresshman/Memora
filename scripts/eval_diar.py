"""说话人分离量化评估：RTTM 金标准，frame-level + Hungarian 最优映射，输出 DER。

用法：python scripts/eval_diar.py --rttm X.rttm --clip clip.wav --t0 30 --t1 210
"""
import argparse
import numpy as np
from memora.whisper import audio, transcribe, diarize
from scipy.optimize import linear_sum_assignment


def parse_rttm(path, t0, t1):
    out = []
    for line in open(path, encoding="utf-8"):
        p = line.split()
        if len(p) < 8 or p[0] != "SPEAKER":
            continue
        a = max(float(p[3]), t0)
        b = min(float(p[3]) + float(p[4]), t1)
        if b > a:
            out.append((a - t0, b - t0, p[7]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rttm", required=True)
    ap.add_argument("--clip", required=True)
    ap.add_argument("--t0", type=float, required=True)
    ap.add_argument("--t1", type=float, required=True)
    ap.add_argument("--lang", default="zh")
    a = ap.parse_args()
    HOP = 0.01
    pcm, sr = audio.decode(a.clip)
    segs = transcribe.transcribe_segments(pcm, sr, a.lang)
    segs, hk = diarize.diarize(pcm, segs, 0, sr)
    nfr = int((a.t1 - a.t0) / HOP)
    ref = np.full(nfr, "", dtype=object)
    hyp = np.full(nfr, "", dtype=object)
    for x, y, sp in parse_rttm(a.rttm, a.t0, a.t1):
        ref[int(x / HOP):int(y / HOP)] = sp
    for s in segs:
        hyp[int(s.start / HOP):int(s.end / HOP)] = s.speaker
    rf = np.where(ref != "")[0]
    rsp = sorted(set(ref[rf]))
    hsp = sorted(set(hyp[rf]) - {""})
    M = np.zeros((len(rsp), len(hsp)))
    for i, r in enumerate(rsp):
        for j, h in enumerate(hsp):
            M[i, j] = np.sum((ref[rf] == r) & (hyp[rf] == h))
    ri, hi = linear_sum_assignment(-M)
    rmap = {rsp[i]: hsp[j] for i, j in zip(ri, hi)}
    tot = len(rf)
    miss = conf = 0
    for f in rf:
        h = hyp[f]
        if h == "":
            miss += 1
        elif rmap.get(ref[f]) != h:
            conf += 1
    print(f"ref_speakers={len(rsp)} hyp_speakers={hk} "
          f"DER={(miss + conf) / tot:.3f} miss={miss / tot:.3f} conf={conf / tot:.3f}")


if __name__ == "__main__":
    main()