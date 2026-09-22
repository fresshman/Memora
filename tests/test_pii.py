# -*- coding: utf-8 -*-
"""PII 脱敏单元测试：强模式识别、误报控制、人名角色化、可逆还原。"""
from __future__ import annotations

from memora.parsers import Conversation, Message
from memora.pii import redact_conversation, restore_text_safe
from memora.pii.redactor import _idcard_ok, _luhn_ok


def _valid_idcard(body17: str) -> str:
    w = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    checks = "10X98765432"
    s = sum(int(body17[i]) * w[i] for i in range(17))
    return body17 + checks[s % 11]


def _conv():
    idc = _valid_idcard("11010119900307889")
    text = (
        "我手机号13812345678，备用也是13812345678。"
        f"邮箱 zhang.wei@example.com，身份证号{idc}，"
        "卡号4111111111111111，车牌京A·12345，护照E12345678，"
        "服务器地址10.0.0.5。张伟负责部署。"
    )
    return Conversation(
        source="wechat", title="项目群",
        messages=[
            Message(speaker="张伟", time="2024-03-04 10:00:00", text=text),
            Message(speaker="李娜", time="2024-03-04 10:01:00",
                    text="收到，张伟你先发我邮箱 li.na@test.cn"),
        ],
    ), idc


def test_strong_pii_detected_and_masked():
    conv, idc = _conv()
    redacted, red = redact_conversation(conv)
    joined = "\n".join(m.text for m in redacted.user_messages)

    # 明文 PII 不再出现
    assert "13812345678" not in joined
    assert "zhang.wei@example.com" not in joined
    assert idc not in joined
    assert "4111111111111111" not in joined
    assert "京A·12345" not in joined
    assert "E12345678" not in joined
    assert "10.0.0.5" not in joined

    # 占位符出现
    assert "【手机1】" in joined          # 同一号码两处 -> 同一占位
    assert joined.count("【手机1】") == 2
    assert "【邮箱1】" in joined and "【邮箱2】" in joined
    assert "【身份证1】" in joined
    assert "【银行卡1】" in joined
    assert "【车牌1】" in joined
    assert "【护照号1】" in joined
    assert "【IP地址1】" in joined

    stats = red.stats()
    assert stats["手机"] == 1 and stats["身份证"] == 1 and stats["银行卡"] == 1
    assert stats["邮箱"] == 2


def test_checksum_validators():
    assert _idcard_ok(_valid_idcard("11010119900307889"))
    assert not _idcard_ok("110101199003078890")  # 19 位
    assert not _idcard_ok("11010119900307888X")  # 校验位错
    assert _luhn_ok("4111111111111111")
    assert not _luhn_ok("1234567890123456")


def test_false_positive_control():
    conv = Conversation(
        source="plain", title="t",
        messages=[Message(
            speaker="甲", time=None,
            text="订单号2024030400001234567890（20位），编号1234567890123456，"
                 "版本 1.3.11，QQ群123456。")],
    )
    redacted, red = redact_conversation(conv)
    text = redacted.messages[0].text
    assert "银行卡" not in text     # 非 Luhn / 超长号不得误判
    assert "身份证" not in text
    assert "手机" not in text       # 123456 不是手机号
    # 三段版本号不是 IPv4
    assert "IP地址" not in text


def test_speaker_name_role_substitution():
    conv, _ = _conv()
    redacted, red = redact_conversation(conv)
    speakers = redacted.speakers
    assert speakers == ["成员A", "成员B"]
    joined = "\n".join(m.text for m in redacted.user_messages)
    assert "成员A" in joined   # 成员B（李娜）只作为发言人角色化，不在正文
    # 正文里的张伟被角色化（即便后接动词“负责”）
    assert "张伟负责" not in joined
    assert "成员A负责部署" in joined
    assert red.role_to_name["成员A"] == "张伟"
    assert red.n_names == 2


def test_long_name_first_avoids_split():
    # 两个发言人姓名互为前缀：三字名必须整体替换，不能被两字名拆散
    conv = Conversation(
        source="plain", title="t",
        messages=[
            Message(speaker="张伟", time=None, text="好的"),
            Message(speaker="张伟明", time=None, text="张伟明和张伟一起跟进"),
        ],
    )
    redacted, red = redact_conversation(conv)
    joined = "\n".join(m.text for m in redacted.user_messages)
    assert "张伟明" not in joined
    assert "成员B" in joined and "成员A" in joined
    assert red.role_to_name["成员B"] == "张伟明"


def test_original_conversation_unchanged():
    conv, idc = _conv()
    redact_conversation(conv)
    assert conv.messages[0].speaker == "张伟"
    assert idc in conv.messages[0].text
    assert getattr(conv, "redaction", None) is None


def test_restore_roundtrip():
    conv, idc = _conv()
    redacted, red = redact_conversation(conv)
    masked = redacted.to_prompt_text()
    assert "13812345678" not in masked
    restored = red.restore(masked)
    assert "13812345678" in restored
    assert idc in restored
    assert "张伟" in restored
    # restore_text_safe 对未脱敏会话原样返回
    plain = Conversation(source="plain", title="t",
                         messages=[Message(speaker="甲", time=None, text="无敏感信息")])
    assert restore_text_safe("无敏感信息", plain) == "无敏感信息"
