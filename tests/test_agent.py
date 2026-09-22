"""智能体纯函数单元测试（不依赖模型加载）。"""
from __future__ import annotations

from memora.agent import MemoraAgent


def test_split_report_with_sections():
    report = "## 一、核心结论\n要点A\n\n## 二、待办\n- 任务1\n"
    parts = MemoraAgent.split_report(report)
    assert "一、核心结论" in parts
    assert "二、待办" in parts
    assert "要点A" in parts["一、核心结论"]


def test_split_report_no_sections():
    report = "这是一段没有标题的报告内容"
    parts = MemoraAgent.split_report(report)
    assert "报告" in parts
    assert "没有标题" in parts["报告"]
