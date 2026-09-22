"""M2 评测指标单元测试（不依赖模型，构造报告与 golden 验证口径）。"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from evals.metrics import (  # noqa: E402
    norm, point_hit, parse_sections, extract_items,
    score_facet, score_qa, score_case, aggregate,
)

GOOD_REPORT = """## 一、本次沟通核心结论
1. 安全审计报告由王强负责编写，截止下周五下午六点前交付。
2. 正式上线窗口确定为3月18日凌晨两点，由张伟负责值守。

## 二、待办任务清单
- [ ] 安全审计报告 ｜ 责任人：王强 ｜ 时间节点：下周五18:00前
- [ ] 合同盖章 ｜ 责任人：赵敏 ｜ 时间节点：下周一前

## 三、关键信息提取
1. 人员：王强、赵敏、张伟。

## 四、沟通风险提示
1. 第三方支付接口限流额度未确认，可能导致上线延期。
2. 供应商核心物料缺货，硬件交付可能推迟。
"""

GOLD = {
    "todos": [
        {"terms_all": ["安全审计", "王强"], "terms_any": ["下周五"], "owner": "王强"},
        {"terms_all": ["合同", "赵敏"], "terms_any": ["下周一", "周一"], "owner": "赵敏"},
    ],
    "risks": [
        {"terms_all": ["限流"], "terms_any": ["延期", "上线"], "owner": None},
        {"terms_all": ["物料"], "terms_any": ["缺货", "推迟", "交付"], "owner": None},
    ],
    "decisions": [
        {"terms_all": ["3月18", "张伟"], "terms_any": ["上线", "凌晨"], "owner": "张伟"},
    ],
    "qa": [
        {"q": "安全审计谁负责？", "answerable": True, "all": ["王强"], "any": ["下周五"]},
        {"q": "结算金额多少？", "answerable": False,
         "hedge": ["未提及", "没有提到", "无法确定", "不清楚", "不知道"]},
    ],
}


def test_norm_strips_punct_and_space():
    assert norm("  下周五 18:00 前！") == "下周五1800前"
    assert norm("3月18日，凌晨。") == "3月18日凌晨"
    assert norm("") == ""


def test_point_hit_all_and_any_logic():
    sec = "安全审计报告由王强负责，下周五交付"
    assert point_hit({"terms_all": ["安全审计", "王强"], "terms_any": ["下周五"]}, sec)
    # 缺一个必含短语
    assert not point_hit({"terms_all": ["安全审计", "赵敏"], "terms_any": []}, sec)
    # any 一个都不中
    assert not point_hit({"terms_all": ["安全审计"], "terms_any": ["下周二"]}, sec)
    # 空 any 不约束
    assert point_hit({"terms_all": ["王强"], "terms_any": []}, sec)


def test_parse_sections_maps_three_facets():
    secs = parse_sections(GOOD_REPORT)
    assert "todos" in secs and "risks" in secs and "decisions" in secs
    assert "王强" in secs["todos"]
    assert "限流" in secs["risks"]
    assert "3月18" in secs["decisions"]


def test_extract_items_checkbox_and_numbered():
    secs = parse_sections(GOOD_REPORT)
    todo_items = extract_items(secs["todos"])
    risk_items = extract_items(secs["risks"])
    assert len(todo_items) == 2
    assert any("安全审计" in x for x in todo_items)
    assert len(risk_items) == 2


def test_perfect_report_scores_full():
    card = score_case(GOOD_REPORT, ["由王强负责，下周五下午六点前", "对话中未提及结算金额"], GOLD)
    for facet in ("todos", "risks", "decisions"):
        assert card[facet]["recall"] == 1.0, facet
        assert card[facet]["precision"] == 1.0, facet
        assert card[facet]["f1"] == 1.0, facet
    assert card["todos"]["owner_accuracy"] == 1.0
    assert card["todos"]["deadline_recall"] == 1.0


def test_missing_todo_lowers_recall():
    secs = parse_sections(GOOD_REPORT)
    # 报告待办段只保留第一条
    partial_todos = "- [ ] 安全审计报告 ｜ 责任人：王强 ｜ 时间节点：下周五18:00前\n"
    r = score_facet(GOLD["todos"], partial_todos, with_owner=True)
    assert r["recall"] == 0.5
    assert r["tp_gold"] == 1


def test_spurious_item_lowers_precision():
    secs = parse_sections(GOOD_REPORT)
    noisy = secs["todos"] + "\n- [ ] 给全组订珍珠奶茶 ｜ 责任人：行政 ｜ 时间：周五"
    r = score_facet(GOLD["todos"], noisy, with_owner=True)
    assert r["fp_item"] == 1
    assert r["precision"] < 1.0
    assert r["recall"] == 1.0  # 召回不受误报影响


def test_qa_evidence_and_hallucination():
    # 可答命中 + 无答案正确拒答
    good = score_qa(GOLD["qa"], ["王强负责，下周五前", "对话里没有提到结算金额，无法确定"])
    assert good["evidence_recall"] == 1.0
    assert good["hallucination_rate"] == 0.0
    assert good["hedge_correct"] == 1
    # 无答案却编造 -> 幻觉
    bad = score_qa(GOLD["qa"], ["王强负责，下周五前", "结算金额是八万元，已经批了"])
    assert bad["hallucination_rate"] == 1.0
    # 可答问题答错 -> 证据未命中
    miss = score_qa(GOLD["qa"], ["好像是李娜负责", "未提及"])
    assert miss["evidence_recall"] == 0.0


def test_aggregate_micro_average():
    c1 = score_case(GOOD_REPORT, ["王强 下周五", "未提及金额"], GOLD)
    # 第二张卡：风险全漏
    report2 = GOOD_REPORT.split("## 四、沟通风险提示")[0] + "## 四、沟通风险提示\n"
    c2 = score_case(report2, ["王强", "未提及"], GOLD)
    agg = aggregate([c1, c2])
    # c1 风险召回 1（2/2），c2 风险召回 0（0/2）-> 微平均 0.5
    assert agg["risk_completeness"] == 0.5
    assert agg["n_cases"] == 2
    assert 0.0 <= agg["hallucination_rate"] <= 1.0
