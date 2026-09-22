# -*- coding: utf-8 -*-
"""报告结构化与「会议决定归位」后处理的单元测试（纯函数，不依赖模型/网络）。"""
from __future__ import annotations

from memora.report import (
    structure_report,
    meeting_decisions_rehomed,
    parse_standard_sections,
)


def _report(info_block: str, conclusion: str = "上线窗口确定为3月18日凌晨两点。") -> str:
    return f"""## 一、本次沟通核心结论
1. {conclusion}

## 二、待办任务清单
- [ ] 值守正式上线发布 ｜ 责任人：张伟 ｜ 时间节点：3月18日凌晨

## 三、关键信息提取
{info_block}

## 四、沟通风险提示
- 生产服务器 SSL 证书下周到期，不续会导致网站打不开。
"""


def test_meeting_time_venue_aggregated_chinese_clock():
    rep = _report(
        "1. 时间节点：3月18日凌晨两点（正式上线窗口）、上午十点（季度复盘会议）\n"
        "2. 地点：三楼星河厅（季度复盘会议地点）")
    rehomed = meeting_decisions_rehomed(rep)
    assert len(rehomed) == 1
    sent = rehomed[0]
    assert "季度复盘会议" in sent and "上午十点" in sent and "三楼星河厅" in sent


def test_launch_window_time_not_misassigned_to_meeting():
    # 凌晨两点属于上线窗口，会议是上午十点；不得把凌晨两点配给会议
    rep = _report(
        "1. 时间节点：3月18日凌晨两点（上线窗口）、上午十点（季度复盘会议）\n"
        "2. 地点：三楼星河厅（季度复盘会议地点）")
    sent = meeting_decisions_rehomed(rep)[0]
    assert "凌晨" not in sent
    assert "上午十点" in sent


def test_venue_residual_cleaned():
    # "会议室三楼星河厅" 不得截出残字"议室"
    rep = _report(
        "1. 时间节点：季度复盘会议时间为3月7日上午十点。\n"
        "2. 地点：会议室三楼星河厅（季度复盘会议地点）。")
    sent = meeting_decisions_rehomed(rep)[0]
    assert "三楼星河厅" in sent and "议室三楼" not in sent


def test_venue_only_emits_place_decision():
    rep = _report("1. 地点：季度复盘会议地点为三楼星河厅。\n2. 联系人：周婷。")
    rehomed = meeting_decisions_rehomed(rep)
    assert len(rehomed) == 1
    assert "地点确定为三楼星河厅" in rehomed[0]


def test_cancelled_or_postponed_event_skipped():
    # 发布会推迟且无确定会场，不得归位
    rep = _report(
        "1. 时间节点：发布会推迟至下下月十号。\n"
        "2. 其他：暂无确定场地。")
    assert meeting_decisions_rehomed(rep) == []


def test_already_in_conclusion_not_duplicated():
    rep = _report(
        "1. 时间节点：上午十点（季度复盘会议）\n"
        "2. 地点：三楼星河厅（季度复盘会议地点）",
        conclusion="季度复盘会议定于上午十点在三楼星河厅举行。")
    assert meeting_decisions_rehomed(rep) == []


def test_non_venue_excluded():
    # 前台 / 停车场不是会场
    rep = _report(
        "1. 时间节点：上午十点（季度复盘会议）\n"
        "2. 地点：下午茶放前台旁边，停车场侧门为施工入口。")
    assert meeting_decisions_rehomed(rep) == []


def test_todos_and_risks_untouched():
    # 归位是复制式补全：待办段、风险段文本必须原样保留
    rep = _report(
        "1. 时间节点：上午十点（季度复盘会议）\n"
        "2. 地点：三楼星河厅（季度复盘会议地点）")
    secs = structure_report(rep)
    assert "值守正式上线发布" in secs["todos"]
    assert "SSL 证书下周到期" in secs["risks"]
    # 决定面追加了归位句
    assert "三楼星河厅" in secs["decisions"]


def test_no_info_section_returns_empty():
    rep = ("## 一、本次沟通核心结论\n1. 预算五万。\n\n"
           "## 二、待办任务清单\n- [ ] 签合同\n")
    assert meeting_decisions_rehomed(rep) == []
    secs = parse_standard_sections(rep)
    assert "decisions" in secs and "todos" in secs


def test_ui_split_report_appends_rehome_block():
    """前端分段：核心结论段末尾透明追加归位安排，关键信息段原样保留（只复制不移动）。"""
    from memora.agent.review_agent import MemoraAgent
    rep = _report(
        "1. 时间节点：3月18日凌晨两点（上线窗口）、上午十点（季度复盘会议）\n"
        "2. 地点：三楼星河厅（季度复盘会议地点）")
    ui = MemoraAgent.split_report(rep)
    conclusion = next(v for k, v in ui.items() if "结论" in k)
    info = next(v for k, v in ui.items() if "关键信息" in k)
    assert "系统从关键信息归位" in conclusion
    assert "季度复盘会议定于上午十点在三楼星河厅举行" in conclusion
    # 关键信息段原样保留（未被移动/删除）
    assert "三楼星河厅" in info and "季度复盘会议地点" in info
