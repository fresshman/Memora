"""会议记录组装与 SRT 单元测试。"""
from __future__ import annotations

from memora.whisper.meeting import build_meeting, merge_adjacent, to_srt
from memora.whisper.transcribe import Segment


def _segs():
    return [
        Segment(0, 1, "你好", speaker="说话人1"),
        Segment(1.2, 2, "早上好", speaker="说话人2"),
        Segment(2.1, 3, "我们开会吧", speaker="说话人2"),
    ]


def test_merge_adjacent():
    merged = merge_adjacent(_segs())
    # 后两段同说话人且间隔 0.1s < 0.6s，应合并
    assert len(merged) == 2
    assert "早上好我们开会吧" in merged[1].text
    assert merged[1].end == 3


def test_build_meeting_text():
    r = build_meeting("a.mp3", 60.0, 30.0, "zh", _segs())
    assert "会议记录" in r.text
    assert "a.mp3" in r.text
    assert "说话人1" in r.text and "说话人2" in r.text
    assert "[00:00:00]" in r.text
    assert r.meta.num_speakers == 2


def test_to_srt():
    s = to_srt(_segs())
    lines = s.splitlines()
    assert lines[0] == "1"
    assert "-->" in s
    assert "[说话人1]" in s
    assert ",000" in s
