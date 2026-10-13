"""ASR 转写质量量化评估：TextGrid 人工转写为参考，输出 CER / WER（纯 CPU、不引 torch）。

参考文本：从 TextGrid 全部说话人 IntervalTier 中提取与 [t0,t1] 重叠的非空 text，
按 xmin 时间排序拼接（人工金标准）。
假设文本：对切片音频做整条转写链路（ffmpeg 解码/降噪 → whisper.cpp）。
归一化：去 <sil>/<$> 等标记与所有标点空白，只保留汉字/字母/数字。
  - CER：逐字符编辑距离（中文 ASR 标准指标）
  - WER：jieba 分词后词级编辑距离（jieba 缺失则降级，仅报告 CER）

用法：
  python scripts/eval_asr.py --textgrid E:/UNpress/train_L/TextGrid/xxx.TextGrid \
      --clip data/voice_test/clip_8ch_30_210.wav --t0 30 --t1 210
  # 热词表（见 memora/whisper/hotwords.txt）
  python scripts/eval_asr.py ... --hotwords memora/whisper/hotwords.txt
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from memora.whisper import audio, transcribe

_INTERVAL = re.compile(
    r'xmin\s*=\s*([\d.]+)\s*\n\s*xmax\s*=\s*([\d.]+)\s*\n'
    r'\s*text\s*=\s*"(.*?)"\s*\n', re.DOTALL)


def parse_textgrid(path: str, t0: float, t1: float) -> str:
    raw = Path(path).read_text(encoding="utf-8")
    items = []
    for m in _INTERVAL.finditer(raw):
        xmin = float(m.group(1))
        xmax = float(m.group(2))
        text = m.group(3).strip()
        if xmax <= t0 or xmin >= t1 or not text:
            continue
        items.append((xmin, text))
    items.sort(key=lambda x: x[0])
    return "".join(t for _, t in items)


def norm_chars(text: str) -> str:
    """去 <...> 标记与标点空白，只保留汉字 / 字母 / 数字。"""
    text = re.sub(r"<[^>]*>", "", text)
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]", "", text)


def levenshtein(a, b) -> int:
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        ai = a[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ai == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[m]


def cer(ref: str, hyp: str):
    r, h = norm_chars(ref), norm_chars(hyp)
    d = levenshtein(r, h)
    return d, len(r), (d / len(r) if r else 0.0)


def wer(ref: str, hyp: str):
    try:
        import jieba
    except ImportError:
        return None
    r, h = norm_chars(ref), norm_chars(hyp)
    rw, hw = list(jieba.cut(r)), list(jieba.cut(h))
    d = levenshtein(rw, hw)
    return d, len(rw), (d / len(rw) if rw else 0.0)


def run_hypothesis(clip: str, lang: str, hotwords: str):
    pcm, sr = audio.decode(clip)
    # 显式传热词：""=关闭（基线）；路径=加载；auto=内置热词表
    hw = None if hotwords == "auto" else (hotwords or "")
    segs = transcribe.transcribe_segments_hotwords(pcm, sr, lang, hw)
    return "".join(s.text for s in segs), segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--textgrid", required=True)
    ap.add_argument("--clip", required=True)
    ap.add_argument("--t0", type=float, required=True)
    ap.add_argument("--t1", type=float, required=True)
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--hotwords", default="",
                    help="热词表：文件路径；auto=内置热词表；不传=关闭")
    ap.add_argument("--out", default="", help="可选：保存 JSON 结果")
    a = ap.parse_args()

    ref = parse_textgrid(a.textgrid, a.t0, a.t1)
    t0 = time.time()
    hyp, segs = run_hypothesis(a.clip, a.lang, a.hotwords)
    elapsed = time.time() - t0

    cd, cn, crate = cer(ref, hyp)
    w = wer(ref, hyp)
    print(f"segments={len(segs)} audio={a.t1-a.t0:.0f}s "
          f"wall={elapsed:.1f}s hotwords={a.hotwords or 'off'}")
    print(f"CER={crate*100:.2f}%  (edits={cd} / ref_chars={cn})")
    if w:
        print(f"WER={w[2]*100:.2f}%  (edits={w[0]} / ref_words={w[1]})")
    print("--- reference ---")
    print(norm_chars(ref))
    print("--- hypothesis ---")
    print(norm_chars(hyp))

    if a.out:
        result = {
            "clip": a.clip, "t0": a.t0, "t1": a.t1,
            "hotwords": a.hotwords, "segments": len(segs),
            "wall_s": round(elapsed, 1),
            "cer": round(crate, 4), "cer_edits": cd, "ref_chars": cn,
            "wer": round(w[2], 4) if w else None,
            "wer_edits": w[0] if w else None,
            "ref_words": w[1] if w else None,
        }
        Path(a.out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("saved", a.out)


if __name__ == "__main__":
    main()
