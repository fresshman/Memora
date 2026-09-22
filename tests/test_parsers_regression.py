"""多平台真实样本解析回归测试（golden 驱动）。

样本与标注见 samples/ 与 samples/manifest.json。覆盖：
- 微信（带引号/无引号消息头、GBK、系统消息、多媒体占位、跨天分隔）
- 钉钉（标准列/媒体与系统行/GBK）
- 飞书（时间独占行、发言人在前、时间在前、系统消息）
- 粘贴文本嗅探、系统消息不进模型、编码无乱码
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from memora.parsers import parse_file, parse_text

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"


def _load_golden():
    data = json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))
    return data["samples"]


GOLDEN = _load_golden()


@pytest.mark.parametrize("golden", GOLDEN,
                         ids=[g["path"] for g in GOLDEN])
def test_sample_matches_golden(golden):
    conv = parse_file(str(SAMPLES / golden["path"]))
    assert conv.source == golden["source"], golden["path"]
    assert conv.title == golden["title"], golden["path"]
    assert len(conv) == golden["user_count"], (
        f"{golden['path']} 真人消息数 {len(conv)} != {golden['user_count']}")
    assert len(conv.system_messages) == golden["system_count"], (
        f"{golden['path']} 系统消息数 {len(conv.system_messages)} "
        f"!= {golden['system_count']}")
    assert conv.speakers == golden["speakers"], (
        f"{golden['path']} 发言人 {conv.speakers} != {golden['speakers']}")
    first, last = conv.time_range
    assert first == golden["first_time"], f"{golden['path']} 起始时间 {first}"
    assert last == golden["last_time"], f"{golden['path']} 结束时间 {last}"

    joined = "\n".join(m.text for m in conv.user_messages)
    for kw in golden["must_contain"]:
        assert kw in joined, f"{golden['path']} 缺少关键内容：{kw}"


@pytest.mark.parametrize("golden", GOLDEN)
def test_system_messages_excluded_from_prompt(golden):
    """群系统消息不得进入喂给模型的文本。"""
    conv = parse_file(str(SAMPLES / golden["path"]))
    prompt = conv.to_prompt_text(limit_chars=10**9)
    for sm in conv.system_messages:
        head = sm.text.strip().splitlines()[0][:12]
        # 系统行特征（撤回/入群/打招呼/日期分隔/导出说明）不应出现在模型文本里
        if any(k in head for k in ("撤回", "加入了群", "打招呼", "消息记录",
                                   "邀请", "发起了审批", "修改了群聊")):
            assert head not in prompt, f"{golden['path']} 系统消息泄漏：{head}"


def test_gbk_samples_no_mojibake():
    """GBK 编码样本必须正确解码，中文不得乱码。"""
    expect = {
        "wechat/03_gbk.txt": "报价单",
        "dingtalk/03_gbk.csv": "毛利",
    }
    for rel, kw in expect.items():
        conv = parse_file(str(SAMPLES / rel))
        joined = "\n".join(m.text for m in conv.user_messages)
        assert "\ufffd" not in joined
        assert kw in joined  # 专属中文词正常解码（乱码时必丢失）


def test_paste_wechat_format_sniffed():
    paste = (
        '"蒋睿" 2024-03-10 08:00:00\n'
        "早会挪到会议室B\n"
        '"许诺" 2024-03-10 08:05:00\n'
        "收到\n"
    )
    conv = parse_text(paste)
    assert conv.source == "wechat"
    assert len(conv) == 2
    assert conv.speakers == ["蒋睿", "许诺"]


def test_paste_plain_colon_split_into_messages():
    paste = "刘洋：记得把测试报告发我\n陈晨：好的，下班前给你\n"
    conv = parse_text(paste)
    assert conv.source == "plain"
    assert len(conv) == 2
    assert conv.speakers == ["刘洋", "陈晨"]
    assert "测试报告" in conv.user_messages[0].text


def test_paste_single_paragraph_one_message():
    conv = parse_text("这是一整段没有任何格式特征的普通文本，没有发言人前缀。")
    assert conv.source == "plain"
    assert len(conv) == 1


def test_multiline_message_merged():
    """同一发言人连续多行应合并为一条消息。"""
    conv = parse_file(str(SAMPLES / "wechat" / "01_basic_group.txt"))
    wang = [m for m in conv.user_messages if m.speaker == "王强"][0]
    assert "接口联调" in wang.text and "限流" in wang.text
