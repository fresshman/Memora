# -*- coding: utf-8 -*-
"""流式复盘 / 流式问答的事件序列测试（Fake 后端，不加载模型）。"""
from __future__ import annotations

from memora.agent import MemoraAgent
from memora.backend.base import MemoraLLM
from memora.parsers import Conversation, Message

REPORT = (
    "## 一、本次沟通核心结论\n"
    "确定供应商为华东，单价 120 元。\n\n"
    "## 二、待办任务清单\n"
    "- [ ] 撰写安全审计报告 ｜ 责任人：王强 ｜ 时间节点：下周五\n\n"
    "## 三、关键信息提取\n"
    "联系人：王强。\n\n"
    "## 四、沟通风险提示\n"
    "生产服务器证书下周到期。\n"
)


class FakeStreamingLLM(MemoraLLM):
    name = "fake-stream"
    model_id = "fake/model"

    def complete(self, prompt, *, max_tokens=None, temperature=None):
        return REPORT

    def stream_complete(self, prompt, *, max_tokens=None, temperature=None):
        # 模拟逐 token / 逐句到达
        for piece in (REPORT[:12], REPORT[12:40], REPORT[40:]):
            yield piece


def _agent():
    return MemoraAgent(FakeStreamingLLM())


def _conv():
    return Conversation(
        source="test", title="t",
        messages=[
            Message(speaker="甲", time="2024-03-04 10:00:00", text="我们确定供应商为华东，单价120元。"),
            Message(speaker="乙", time="2024-03-04 10:01:00", text="安全审计报告我负责，下周五前给。"),
        ],
    )


def test_review_stream_event_sequence():
    events = list(_agent().review_stream(_conv()))
    assert events[0]["type"] == "meta"
    assert events[0]["context_mode"] == "full"
    assert events[-1]["type"] == "done"
    deltas = "".join(e["text"] for e in events if e["type"] == "delta")
    assert deltas == REPORT
    done = events[-1]
    assert done["report"] == REPORT.strip()
    # 四段都被切出
    joined = "".join(done["sections"].keys())
    assert "核心结论" in joined and "待办" in joined and "风险" in joined


def test_answer_stream_event_sequence():
    events = list(_agent().answer_stream(_conv(), "供应商单价多少？"))
    assert events[0]["type"] == "meta"
    assert events[-1]["type"] == "done"
    deltas = "".join(e["text"] for e in events if e["type"] == "delta")
    assert deltas == REPORT
    assert events[-1]["answer"] == REPORT.strip()


def test_default_stream_complete_falls_back_to_complete():
    class OnlyComplete(MemoraLLM):
        name = "one-shot"
        def complete(self, prompt, *, max_tokens=None, temperature=None,
                     **kwargs):
            return "完整回答"
    out = list(OnlyComplete().stream_complete("hi"))
    assert out == ["完整回答"]
