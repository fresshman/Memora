# -*- coding: utf-8 -*-
"""本地 PII（个人敏感信息）检测与可逆脱敏。

设计目标（端侧隐私闭环）：
- 在「解析之后、送入模型 / 建立向量索引之前」统一脱敏，模型与本地索引都不接触明文 PII；
- 强模式 PII 用正则识别，并对身份证做校验位、银行卡做 Luhn 校验以压低误报；
- 人名按发言人角色化（成员A/B…），正文中 @ 到的同一姓名同步替换；
- 维护「占位符 -> 原文」映射，可在本机授权后还原；映射本身交由 Vault 加密保存。

不在能力范围内（避免误伤，明确边界）：
- 不是发言人、且不以强模式出现的真实姓名，需要中文 NER 才能可靠识别，本模块不臆测；
- 自由文本住址没有稳定模式，不做通用脱敏。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..parsers.base import Conversation, Message

# ---------------------------------------------------------------------------
# 强模式 PII 正则
# ---------------------------------------------------------------------------
_RE_MOBILE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_RE_IDCARD = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")
_RE_BANKCARD = re.compile(r"(?<!\d)(\d{16,19})(?!\d)")
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_RE_IPV4 = re.compile(r"(?<!\d)((?:\d{1,3}\.){3}\d{1,3})(?!\d)")
_RE_PLATE = re.compile(
    r"[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤川青藏琼宁]"
    r"[A-Z][·\-]?[A-HJ-NP-Z0-9]{5,6}(?![A-Z0-9])"
)
_RE_PASSPORT = re.compile(r"(?<![A-Za-z0-9])[EeKkGgDdSsPpHh]\d{8}(?!\d)")

_CJK = r"一-鿿"
# 占位符标签
LBL_MOBILE = "手机"
LBL_IDCARD = "身份证"
LBL_BANK = "银行卡"
LBL_EMAIL = "邮箱"
LBL_IP = "IP地址"
LBL_PLATE = "车牌"
LBL_PASSPORT = "护照号"


def _luhn_ok(num: str) -> bool:
    """银行卡 Luhn 校验。"""
    digits = [int(c) for c in num if c.isdigit()]
    if len(digits) < 16:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _idcard_ok(num: str) -> bool:
    """18 位身份证校验位验证（GB 11643-1999）。"""
    if len(num) != 18:
        return False
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    checks = "10X98765432"
    try:
        total = sum(int(num[i]) * weights[i] for i in range(17))
    except ValueError:
        return False
    return checks[total % 11] == num[17].upper()


def _valid_ipv4(s: str) -> bool:
    parts = s.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


@dataclass
class Redaction:
    """一次脱敏的结果与可逆映射。"""

    enabled: bool = True
    names_enabled: bool = True
    # 角色名 -> 原发言人（如 成员A -> 张伟）
    role_to_name: dict[str, str] = field(default_factory=dict)
    # 占位符 -> 原文（如 【手机1】 -> 13812345678）
    placeholder_to_value: dict[str, str] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    n_names: int = 0

    def stats(self) -> dict[str, int]:
        """各类脱敏数量（含人名角色化数量）。"""
        out = dict(self.counters)
        if self.names_enabled:
            out["人名"] = self.n_names
        return out

    # ------------------------------------------------------------------
    def restore(self, text: str) -> str:
        """把脱敏文本（含模型报告）中的占位符/角色名还原为原文。"""
        if not text:
            return text
        # 先还原带括号的占位符
        for ph, val in self.placeholder_to_value.items():
            text = text.replace(ph, val)
        # 再还原角色名（长的先还原，避免前缀问题）
        for role in sorted(self.role_to_name, key=len, reverse=True):
            text = text.replace(role, self.role_to_name[role])
        return text


class _RedactorState:
    """单次脱敏过程的可变状态（跨多条消息复用，保证同值同占位）。"""

    def __init__(self, redaction: Redaction):
        self.r = redaction
        self.value_to_placeholder: dict[str, str] = {}

    def _placeholder(self, label: str, value: str) -> str:
        if value in self.value_to_placeholder:
            return self.value_to_placeholder[value]
        n = self.r.counters.get(label, 0) + 1
        self.r.counters[label] = n
        ph = f"【{label}{n}】"
        self.value_to_placeholder[value] = ph
        self.r.placeholder_to_value[ph] = value
        return ph

    def redact_text(self, text: str) -> str:
        if not text:
            return text
        # 1) 收集所有强模式匹配，按起始位置排序、去重叠
        spans: list[tuple[int, int, str]] = []

        def collect(regex, label, validator=None):
            for m in regex.finditer(text):
                val = m.group(0)
                if validator and not validator(val):
                    continue
                spans.append((m.start(), m.end(), self._placeholder(label, val)))

        collect(_RE_EMAIL, LBL_EMAIL)
        collect(_RE_PLATE, LBL_PLATE)
        collect(_RE_PASSPORT, LBL_PASSPORT)
        collect(_RE_MOBILE, LBL_MOBILE)
        collect(_RE_IDCARD, LBL_IDCARD, _idcard_ok)
        collect(_RE_BANKCARD, LBL_BANK, _luhn_ok)
        # IPv4 需要逐段校验
        for m in _RE_IPV4.finditer(text):
            val = m.group(1)
            if _valid_ipv4(val):
                spans.append((m.start(1), m.end(1),
                              self._placeholder(LBL_IP, val)))

        # 去重叠（保留更靠前、更长的）
        spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        merged: list[tuple[int, int, str]] = []
        occupied_end = -1
        for st, en, ph in spans:
            if st >= occupied_end:
                merged.append((st, en, ph))
                occupied_end = en
        for st, en, ph in sorted(merged, key=lambda x: -x[0]):
            text = text[:st] + ph + text[en:]
        return text


def _role_name(index: int) -> str:
    """0 -> 成员A，25 -> 成员Z，26 -> 成员AA。"""
    name = ""
    i = index
    while True:
        name = chr(ord("A") + i % 26) + name
        i = i // 26 - 1
        if i < 0:
            break
    return f"成员{name}"


def redact_conversation(
    conv: Conversation,
    *,
    redact_names: bool = True,
) -> tuple[Conversation, Redaction]:
    """返回脱敏后的新 Conversation（不改原对象）与 Redaction 映射。

    发言人统一角色化；消息正文先做角色名替换，再做强模式 PII 脱敏。
    """
    red = Redaction(names_enabled=redact_names)
    state = _RedactorState(red)

    # 发言人 -> 角色（按首次出现）
    speaker_to_role: dict[str, str] = {}
    for sp in conv.speakers:
        if not sp:
            continue
        role = _role_name(len(speaker_to_role))
        speaker_to_role[sp] = role
        red.role_to_name[role] = sp
    red.n_names = len(speaker_to_role)

    # 姓名替换正则（长名优先，要求姓名独立成词，避免误伤“张伟明”）
    name_roles: list[tuple[str, str]] = []
    if redact_names:
        for name in sorted(speaker_to_role, key=len, reverse=True):
            name_roles.append((name, speaker_to_role[name]))

    new_msgs: list[Message] = []
    for m in conv.messages:
        text = m.text
        for name, role in name_roles:
            text = text.replace(name, role)
        text = state.redact_text(text)
        new_speaker = speaker_to_role.get(m.speaker, m.speaker)
        new_msgs.append(Message(speaker=new_speaker, time=m.time,
                                text=text, kind=m.kind))

    title = state.redact_text(conv.title or "")
    for name, role in name_roles:
        title = title.replace(name, role)

    new_conv = Conversation(
        source=conv.source, title=title, messages=new_msgs,
        raw_text=state.redact_text(conv.raw_text or ""),
    )
    new_conv.redaction = red
    return new_conv, red

def redact_if_configured(conv: Conversation):
    """按 config 开关脱敏；关闭时原样返回、redaction 为 None。"""
    from .. import config
    if not getattr(config, "PII_REDACT_ENABLE", False):
        return conv, None
    return redact_conversation(
        conv, redact_names=getattr(config, "PII_REDACT_NAMES", True))
