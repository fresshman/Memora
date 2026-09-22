"""解析器单元测试。"""
from __future__ import annotations

from memora.parsers import parse_file, Conversation, Message
from memora.parsers.wechat import parse_wechat
from memora.parsers.dingtalk import parse_dingtalk
from memora.parsers.feishu import parse_feishu


WECHAT_SAMPLE = (
    '"项目群" 的聊天记录\n'
    '==============\n'
    '"张三" 2024-01-01 10:00:00\n'
    '明天交付模块A\n'
    '"李四" 2024-01-01 10:01:00\n'
    '收到，我负责测试\n'
    '"张三" 2024-01-01 10:02:00\n'
    '报价 5 万元\n'
)

DINGTALK_SAMPLE = (
    "时间,发送人,内容\n"
    "2024-01-01 10:00,张三,明天交付\n"
    "2024-01-01 10:01,李四,收到\n"
)

FEISHU_SAMPLE = (
    "<html><body>\n"
    "2024-01-01 10:00:00 张三\n"
    "明天交付\n"
    "2024-01-01 10:01:00 李四\n"
    "收到\n"
    "</body></html>"
)


def test_wechat_parse(tmp_path):
    p = tmp_path / "wx.txt"
    p.write_text(WECHAT_SAMPLE, encoding="utf-8")
    conv = parse_wechat(str(p))
    assert conv.source == "wechat"
    assert len(conv) == 3
    assert conv.messages[0].speaker == "张三"
    assert "交付" in conv.messages[0].text


def test_dingtalk_parse(tmp_path):
    p = tmp_path / "dt.csv"
    p.write_text(DINGTALK_SAMPLE, encoding="utf-8")
    conv = parse_dingtalk(str(p))
    assert conv.source == "dingtalk"
    assert len(conv) == 2
    assert conv.messages[0].speaker == "张三"


def test_feishu_parse(tmp_path):
    p = tmp_path / "fs.html"
    p.write_text(FEISHU_SAMPLE, encoding="utf-8")
    conv = parse_feishu(str(p))
    assert conv.source == "feishu"
    assert len(conv) >= 1


def test_registry_by_suffix(tmp_path):
    p = tmp_path / "wx.txt"
    p.write_text(WECHAT_SAMPLE, encoding="utf-8")
    conv = parse_file(str(p))
    assert conv.source == "wechat"


def test_registry_fallback_plain(tmp_path):
    p = tmp_path / "unknown.txt"
    p.write_text("这是一段无法识别格式的纯文本内容", encoding="utf-8")
    conv = parse_file(str(p))
    assert conv.source == "plain"
    assert len(conv) == 1


def test_conversation_to_prompt_text():
    conv = Conversation(
        source="plain", title="t",
        messages=[Message(speaker="甲", time="10:00", text="你好"),
                  Message(speaker="乙", time="10:01", text="再见")],
    )
    text = conv.to_prompt_text()
    assert "甲" in text and "你好" in text
    assert "乙" in text and "再见" in text
    assert conv.char_count == 4
