# -*- coding: utf-8 -*-
"""M2 评测集合成生成器（确定性、可复现、零隐私）。

产出 evals/cases.jsonl：
- 30 个短/中对话（全量上下文即可处理）；
- 20 个超长对话（>RAG 触发阈值，约 2.2 万字），关键事实强制锚定在
  开头 / 中间 / 结尾，用于检验 RAG 是否能召回被大量噪声淹没的信息；
- 每个 case 带 golden：todos / risks / decisions / qa（含无答案问题测幻觉）。

运行：python evals/generator.py
"""
from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

try:  # 兼容「python evals/generator.py」与包内 import 两种方式
    from .facts import TODOS, RISKS, DECISIONS, UNANSWERABLE_QA, FILLER, PROCESS
except ImportError:  # pragma: no cover
    from facts import TODOS, RISKS, DECISIONS, UNANSWERABLE_QA, FILLER, PROCESS

HERE = Path(__file__).resolve().parent
OUT = HERE / "cases.jsonl"

FILLER_SPEAKERS = ["甲", "乙", "丙", "丁", "戊"]
BASE_TIME = dt.datetime(2024, 3, 4, 9, 0)
LONG_TARGET_CHARS = 21800   # 略高于默认触发阈值 20100，确保走 RAG


def _msg(t: dt.datetime, speaker: str, text: str) -> dict:
    return {"speaker": speaker, "time": t.strftime("%Y-%m-%d %H:%M:%S"), "text": text}


def _gold_point(card: dict) -> dict:
    return {
        "terms_all": list(card["terms_all"]),
        "terms_any": list(card.get("terms_any") or []),
        "owner": card.get("owner"),
    }


def _qa_points(card: dict) -> dict:
    qa = card["qa"]
    return {"q": qa["q"], "answerable": True,
            "all": list(qa.get("all") or []), "any": list(qa.get("any") or [])}


def _pick_facts(rng: random.Random, n_todo: int, n_risk: int, n_decision: int):
    todos = rng.sample(TODOS, n_todo)
    risks = rng.sample(RISKS, n_risk)
    decisions = rng.sample(DECISIONS, n_decision)
    facts = todos + risks + decisions
    rng.shuffle(facts)
    return facts, todos, risks, decisions


def _build_gold(todos, risks, decisions, rng) -> dict:
    qa = [_qa_points(c) for c in todos + risks + decisions]
    # 每个 case 抽 1 个无答案问题测幻觉/拒答
    un = rng.sample(UNANSWERABLE_QA, 1)[0]
    qa.append({"q": un["q"], "answerable": False, "hedge": list(un["hedge"])})
    return {
        "todos": [_gold_point(c) for c in todos],
        "risks": [_gold_point(c) for c in risks],
        "decisions": [_gold_point(c) for c in decisions],
        "qa": qa,
    }


def _fill_stream(rng: random.Random, n: int) -> list[str]:
    """生成 n 条噪声文本（filler 与 process 混合，确定性）。"""
    pool = FILLER + PROCESS
    out = []
    for i in range(n):
        # 约 70% 纯寒暄，30% 模糊过程讨论（后者用于检验精确率）
        if rng.random() < 0.3:
            out.append(rng.choice(PROCESS))
        else:
            out.append(rng.choice(FILLER))
    return out


def build_short(case_id: str, rng: random.Random) -> dict:
    n_todo = rng.randint(1, 3)
    n_risk = rng.randint(1, 2)
    n_decision = rng.randint(1, 2)
    facts, todos, risks, decisions = _pick_facts(rng, n_todo, n_risk, n_decision)
    n_noise = rng.randint(4, 10)
    noise = _fill_stream(rng, n_noise)

    # 事实与噪声交错：把事实随机插入
    slots = list(range(len(facts) + len(noise)))
    rng.shuffle(slots)
    seq: list[tuple[str, str]] = [None] * (len(facts) + len(noise))  # type: ignore
    fact_positions = sorted(slots[: len(facts)])
    for pos, card in zip(fact_positions, facts):
        seq[pos] = (card["speaker"], card["say"])
    ni = 0
    for i in range(len(seq)):
        if seq[i] is None:
            seq[i] = (rng.choice(FILLER_SPEAKERS), noise[ni]); ni += 1

    msgs = []
    t = BASE_TIME + dt.timedelta(minutes=rng.randint(0, 60))
    for speaker, text in seq:
        t += dt.timedelta(minutes=rng.randint(2, 25))
        msgs.append(_msg(t, speaker, text))
    gold = _build_gold(todos, risks, decisions, rng)
    probe_qa = rng.choice([q for q in gold["qa"] if q.get("answerable", True)])
    return _case_dict(case_id, "short", msgs, gold, probe_qa=probe_qa)


def build_long(case_id: str, rng: random.Random) -> dict:
    n_todo = rng.randint(2, 3)
    n_risk = rng.randint(2, 3)
    n_decision = rng.randint(2, 3)
    facts, todos, risks, decisions = _pick_facts(rng, n_todo, n_risk, n_decision)

    # 估算需要的噪声条数使总字数越过阈值
    fact_chars = sum(len(c["say"]) for c in facts)
    avg_noise = sum(len(x) for x in FILLER + PROCESS) / len(FILLER + PROCESS)
    n_noise = int((LONG_TARGET_CHARS - fact_chars) / avg_noise) + 20
    noise = _fill_stream(rng, n_noise)
    total = n_noise + len(facts)

    # 至少把一个 todo/risk/decision 锚定到 head，一个 mid，一个 tail
    anchors = []
    head_idx = int(total * rng.uniform(0.01, 0.06))
    mid_idx = int(total * rng.uniform(0.46, 0.54))
    tail_idx = int(total * rng.uniform(0.93, 0.98))
    ordered = list(facts)
    rng.shuffle(ordered)
    slots = {"head": head_idx, "mid": mid_idx, "tail": tail_idx}
    placed: dict[int, dict] = {}
    keys = list(slots.keys())
    head_card = None
    for k in keys:
        if ordered:
            card = ordered.pop()
            placed[min(slots[k], total - 1)] = card
            if k == "head":
                head_card = card
    # 其余事实随机散布
    free = [i for i in range(total) if i not in placed]
    rng.shuffle(free)
    for card in ordered:
        placed[free.pop()] = card

    seq: list[tuple[str, str]] = []
    ni = 0
    for i in range(total):
        if i in placed:
            c = placed[i]
            seq.append((c["speaker"], c["say"]))
        else:
            seq.append((rng.choice(FILLER_SPEAKERS), noise[ni])); ni += 1

    msgs = []
    t = BASE_TIME + dt.timedelta(minutes=rng.randint(0, 30))
    for speaker, text in seq:
        t += dt.timedelta(minutes=rng.randint(3, 8))
        msgs.append(_msg(t, speaker, text))
    gold = _build_gold(todos, risks, decisions, rng)
    # 超长 case 的可答探针问题固定指向锚定在“开头”的事实，专测 RAG 头部召回
    probe_qa = _qa_points(head_card) if head_card else \
        next(q for q in gold["qa"] if q.get("answerable", True))
    return _case_dict(case_id, "long", msgs, gold, probe_qa=probe_qa)


def _case_dict(case_id, category, msgs, gold, probe_qa=None) -> dict:
    char_count = sum(len(m["text"]) for m in msgs)
    un = next((q for q in gold["qa"] if not q.get("answerable", True)), None)
    return {
        "id": case_id,
        "category": category,
        "is_long": category == "long",
        "title": f"评测会话 {case_id}",
        "char_count": char_count,
        "messages": msgs,
        "gold": gold,
        # 评测实际追问的两个问题：一个可答（超长 case 锚定开头事实）+ 一个无答案
        "probe_qa": probe_qa,
        "probe_unanswerable": un,
    }


def generate(n_short: int = 30, n_long: int = 20, seed_base: int = 20240304):
    cases = []
    for i in range(n_short):
        rng = random.Random(seed_base + i)
        cases.append(build_short(f"short_{i + 1:03d}", rng))
    for j in range(n_long):
        rng = random.Random(seed_base + 10000 + j)
        cases.append(build_long(f"long_{j + 1:03d}", rng))
    return cases


def main() -> None:
    cases = generate()
    with open(OUT, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    n_long = sum(1 for c in cases if c["is_long"])
    chars = [c["char_count"] for c in cases]
    n_todo = sum(len(c["gold"]["todos"]) for c in cases)
    n_risk = sum(len(c["gold"]["risks"]) for c in cases)
    n_dec = sum(len(c["gold"]["decisions"]) for c in cases)
    n_qa = sum(len(c["gold"]["qa"]) for c in cases)
    over = sum(1 for c in cases if c["is_long"] and c["char_count"] >= LONG_TARGET_CHARS)
    print(f"已生成 {len(cases)} 个 case（短/中 {len(cases) - n_long}，超长 {n_long}）")
    print(f"  超长 case 字数达标(>={LONG_TARGET_CHARS})：{over}/{n_long}")
    print(f"  字数范围：{min(chars)} ~ {max(chars)}")
    print(f"  golden：待办 {n_todo}、风险 {n_risk}、决定 {n_dec}、QA {n_qa}")
    print(f"  输出：{OUT}")


if __name__ == "__main__":
    main()
