"""批量复盘纯函数单元测试。"""
from __future__ import annotations

from memora.batch import BatchResult, summarize


def test_summarize_mixed():
    results = [
        BatchResult(file="a.txt", success=True, report="## 结论\nA",
                    source="wechat", msg_count=3),
        BatchResult(file="b.txt", success=False, error="解析失败"),
    ]
    overview = summarize(results)
    assert "共 2 份" in overview
    assert "成功 1 份" in overview
    assert "失败 1 份" in overview
    assert "a.txt" in overview
    assert "解析失败" in overview


def test_summarize_empty():
    overview = summarize([])
    assert "共 0 份" in overview
