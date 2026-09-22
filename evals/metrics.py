# -*- coding: utf-8 -*-
"""M2 评测指标（纯函数，不依赖模型，便于单元测试）。

口径：
- 报告按 Markdown/中文序号标题分段，映射到 待办 / 风险 / 结论(决定)；
- golden 点命中（召回）：该点 terms_all 短语在对应段落全部出现，且 terms_any 至少一个出现；
- 精确率：从段落抽取列表/编号条目，条目含任一 golden 实体短语算命中(TP)，否则误报(FP)；
- 字段级：待办责任人 owner、截止时间在段落中的覆盖率；
- QA：可回答问题看证据短语命中（evidence recall）；无答案问题看是否正确拒答，
  未拒答即记为幻觉（hallucination）。
所有匹配在归一化（去空白/标点、小写）后的子串上进行，对表述差异鲁棒。
"""
from __future__ import annotations

import re

# 报告切段/条目抽取/归一化/决定归位统一以 memora.report 为单一事实源，
# 保证「评测口径 == 产品结构化口径」。
from memora.report.sections import (
    norm,
    structure_report,
    extract_list_items,
)

# 段落标题关键词 -> 标准段
_SECTION_RULES = (
    ("todos", ("待办", "任务清单", "行动项", "todo")),
    ("risks", ("风险", "隐患", "问题提示")),
    ("decisions", ("结论", "决定", "共识", "拍板")),
)

_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s*(?:\[[ xX]\]\s*)?|\d+\s*[.、)]\s*)")


def point_hit(point: dict, section_text: str) -> bool:
    """golden 点是否在段落文本中命中：terms_all 全中 且 terms_any 至少一中。"""
    t = norm(section_text)
    if not t:
        return False
    for term in point.get("terms_all", []):
        if norm(term) not in t:
            return False
    any_terms = point.get("terms_any") or []
    if any_terms and not any(norm(term) in t for term in any_terms):
        return False
    return True


def parse_sections(report_md: str) -> dict[str, str]:
    """切成标准段（含决定归位）；实现统一在 memora.report，评测=产品口径。"""
    return structure_report(report_md)


def extract_items(section_text: str) -> list[str]:
    """从段落抽取列表 / 编号条目（统一用 memora.report 实现）。"""
    return extract_list_items(section_text)


def _entity_terms(point: dict) -> list[str]:
    return point.get("terms_all", []) + (point.get("terms_any") or [])


def score_facet(gold_points: list[dict], section_text: str,
                with_owner: bool = False, global_entities: list[str] | None = None,
                whole_text: str | None = None) -> dict:
    """计算一个面（待办/风险/决定）的 P/R/F1 与字段级准确率。

    召回按本面 golden 点计算；精确率的“有据可查”用全局实体集判定——模型在
    「结论」段复述待办/风险属于合理跨段陈述，不应算误报，只有关联不到任何
    golden 实体的条目才算 FP（无中生有）。
    """
    n_gold = len(gold_points)
    items = extract_items(section_text)
    n_items = len(items)
    n_section = norm(section_text)

    # 召回：golden 点命中
    hit_idx = [i for i, g in enumerate(gold_points) if point_hit(g, section_text)]
    tp_gold = len(hit_idx)

    # 精确率：抽取条目是否能关联到某个 golden 实体（默认用本面，可传全局集）
    tp_item = 0
    fp_item = 0
    source = global_entities if global_entities is not None else gold_points
    all_entities = [norm(x) for g in source for x in _entity_terms(g) if norm(x)] \
        if global_entities is None else [norm(x) for x in source if norm(x)]
    for it in items:
        nit = norm(it)
        if any(ent and ent in nit for ent in all_entities):
            tp_item += 1
        else:
            fp_item += 1

    precision = (tp_item / (tp_item + fp_item)) if (tp_item + fp_item) else None
    recall = (tp_gold / n_gold) if n_gold else None
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)

    out = {
        "n_gold": n_gold, "n_items": n_items,
        "tp_gold": tp_gold, "tp_item": tp_item, "fp_item": fp_item,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
    }

    # 全文提取召回：golden 点在整篇报告任意位置命中即算“提取到”，
    # 与段内 recall（结构归位）区分，避免“写进了结论段但没进待办段”被记为完全丢失。
    if whole_text is not None and n_gold:
        extracted = sum(1 for g in gold_points if point_hit(g, whole_text))
        out["extracted"] = extracted
        out["extraction_recall"] = round(extracted / n_gold, 4)
    else:
        out["extracted"] = tp_gold
        out["extraction_recall"] = out["recall"]

    if with_owner:
        owners = [g.get("owner") for g in gold_points if g.get("owner")]
        owner_hit = sum(1 for g in gold_points
                        if g.get("owner") and norm(g["owner"]) in n_section
                        and point_hit(g, section_text))
        out["owner_accuracy"] = round(owner_hit / len(owners), 4) if owners else None
        out["n_owner"] = len(owners)
        # 截止时间：terms_any 命中（待办的日期多为多写法）
        dl_total = sum(1 for g in gold_points if g.get("terms_any"))
        dl_hit = sum(1 for g in gold_points
                     if g.get("terms_any") and point_hit(g, section_text))
        out["deadline_recall"] = round(dl_hit / dl_total, 4) if dl_total else None
    return out


def score_qa(gold_qa: list[dict], answers: list[str]) -> dict:
    """QA 证据命中率 + 无答案问题的幻觉率。answers 与 gold_qa 等长、同序。"""
    answerable_hit = 0
    answerable_total = 0
    hedge_correct = 0
    un_total = 0
    per_q = []
    for g, ans in zip(gold_qa, answers):
        na = norm(ans)
        if g.get("answerable", True):
            answerable_total += 1
            ok = all(norm(t) in na for t in g.get("all", []))
            if ok and g.get("any"):
                ok = any(norm(t) in na for t in g["any"])
            answerable_hit += int(ok)
            per_q.append({"q": g["q"], "answerable": True, "hit": bool(ok)})
        else:
            un_total += 1
            hedged = any(norm(h) in na for h in g.get("hedge", []))
            hedge_correct += int(hedged)
            per_q.append({"q": g["q"], "answerable": False,
                          "hedged": bool(hedged), "hallucinated": not hedged})
    return {
        "evidence_recall": round(answerable_hit / answerable_total, 4) if answerable_total else None,
        "n_answerable": answerable_total, "answerable_hit": answerable_hit,
        "hallucination_rate": round(1 - hedge_correct / un_total, 4) if un_total else None,
        "n_unanswerable": un_total, "hedge_correct": hedge_correct,
        "per_q": per_q,
    }


def score_case(report_md: str, qa_answers: list[str], gold: dict) -> dict:
    """单个 case 的完整评分卡。"""
    sections = parse_sections(report_md)
    # 全局实体集（跨 todo/risk/decision），用于精确率时判定条目是否“有据可查”
    global_entities = sorted({
        norm(x)
        for facet in ("todos", "risks", "decisions")
        for g in gold.get(facet, []) for x in _entity_terms(g) if norm(x)
    })
    result = {
        "todos": score_facet(gold.get("todos", []), sections.get("todos", ""),
                             with_owner=True, global_entities=global_entities,
                             whole_text=report_md),
        "risks": score_facet(gold.get("risks", []), sections.get("risks", ""),
                             global_entities=global_entities, whole_text=report_md),
        "decisions": score_facet(gold.get("decisions", []), sections.get("decisions", ""),
                                 global_entities=global_entities, whole_text=report_md),
        "qa": score_qa(gold.get("qa", []), qa_answers),
        "sections_found": sorted(sections.keys()),
    }
    return result


def aggregate(cards: list[dict]) -> dict:
    """把多个 case 评分卡聚合成微平均 / 宏平均指标。"""
    def micro(key):
        tp_gold = sum(c[key]["tp_gold"] for c in cards)
        n_gold = sum(c[key]["n_gold"] for c in cards)
        tp_item = sum(c[key]["tp_item"] for c in cards)
        fp_item = sum(c[key]["fp_item"] for c in cards)
        p = tp_item / (tp_item + fp_item) if (tp_item + fp_item) else None
        r = tp_gold / n_gold if n_gold else None
        f = 2 * p * r / (p + r) if (p is not None and r is not None and p + r > 0) else None
        return {"precision": round(p, 4) if p is not None else None,
                "recall": round(r, 4) if r is not None else None,
                "f1": round(f, 4) if f is not None else None,
                "tp_gold": tp_gold, "n_gold": n_gold,
                "tp_item": tp_item, "fp_item": fp_item}

    def macro(key, field):
        vals = [c[key][field] for c in cards if c[key].get(field) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    def extraction(key):
        hit = sum(c[key].get("extracted", 0) for c in cards)
        n = sum(c[key]["n_gold"] for c in cards)
        return round(hit / n, 4) if n else None

    ext_total_hit = sum(c[k].get("extracted", 0) for c in cards for k in ("todos", "risks", "decisions"))
    ext_total_n = sum(c[k]["n_gold"] for c in cards for k in ("todos", "risks", "decisions"))

    qa_hit = sum(c["qa"]["answerable_hit"] for c in cards)
    qa_tot = sum(c["qa"]["n_answerable"] for c in cards)
    un_tot = sum(c["qa"]["n_unanswerable"] for c in cards)
    hedge = sum(c["qa"]["hedge_correct"] for c in cards)
    return {
        "n_cases": len(cards),
        "todos": micro("todos"),
        "risks": micro("risks"),
        "decisions": micro("decisions"),
        "todo_extraction_recall": extraction("todos"),
        "risk_extraction_recall": extraction("risks"),
        "decision_extraction_recall": extraction("decisions"),
        "extraction_recall": round(ext_total_hit / ext_total_n, 4) if ext_total_n else None,
        "owner_accuracy": macro("todos", "owner_accuracy"),
        "deadline_recall": macro("todos", "deadline_recall"),
        "qa_evidence_recall": round(qa_hit / qa_tot, 4) if qa_tot else None,
        "hallucination_rate": round(1 - hedge / un_tot, 4) if un_tot else None,
        # 风险完整度按“全文是否提到”计（跨段提及也算覆盖）
        "risk_completeness": extraction("risks"),
    }
