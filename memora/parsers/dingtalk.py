"""钉钉聊天记录解析（.csv 导出）。

钉钉导出 CSV 常见列：消息时间 / 发送人昵称 / 消息类型 / 消息内容（列名随版本
变化，可能带 BOM、GBK 编码）。用统一编码探测读取后交给 pandas，按列名关键词
匹配；系统消息（消息类型非文本、发送人为空）标记为 kind="system"。
"""
from __future__ import annotations

import io

import pandas as pd

from .base import Conversation, Message
from .encoding import read_text

_TIME_KEYS = ("时间", "日期", "time", "timestamp")
_SENDER_KEYS = ("发送人昵称", "发送人姓名", "发送人", "姓名", "昵称",
                "sender", "user", "成员", "发言人")
_TEXT_KEYS = ("消息内容", "内容", "消息", "文本", "正文", "text",
              "content", "message")
_TYPE_KEYS = ("消息类型", "类型", "type", "msg_type")

# 钉钉消息类型中视为系统/非文本的取值
_NON_TEXT_TYPES = {
    "system", "notice", "picture", "image", "audio", "voice", "video", "file",
    "richtext", "calendar", "meeting", "red_envelope", "robot",
}
_SYSTEM_SENDER_HINTS = ("系统", "system", "小助手", "助手", "机器人", "通知")


def _pick(df: "pd.DataFrame", keys: tuple[str, ...]) -> str | None:
    cols = {str(c).strip().lstrip("\ufeff").lower(): c for c in df.columns}
    for k in keys:
        for low, orig in cols.items():
            if k.lower() in low:
                return orig
    return None


def parse_dingtalk_text(text: str) -> Conversation:
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    if df.empty or df.shape[1] == 0:
        raise ValueError("CSV 为空或无法解析")
    tcol = _pick(df, _TIME_KEYS)
    scol = _pick(df, _SENDER_KEYS)
    mcol = _pick(df, _TEXT_KEYS)
    typecol = _pick(df, _TYPE_KEYS)
    if mcol is None:
        raise ValueError("CSV 中未找到内容列")

    messages: list[Message] = []
    for _, row in df.iterrows():
        body = str(row[mcol]).strip()
        if not body:
            continue
        speaker = str(row[scol]).strip() if scol else ""
        t = str(row[tcol]).strip() if tcol else None
        mtype = str(row[typecol]).strip().lower() if typecol else ""

        is_system = (
            mtype in _NON_TEXT_TYPES
            or (not speaker)
            or any(h in speaker for h in _SYSTEM_SENDER_HINTS)
        )
        if is_system:
            # 图片/文件等非文本占位仍保留其内容描述，但标记为系统
            messages.append(Message(speaker=speaker or "系统", time=t,
                                    text=body, kind="system"))
        else:
            messages.append(Message(speaker=speaker or "未知成员", time=t,
                                    text=body, kind="msg"))

    if not messages:
        raise ValueError("CSV 中未解析到任何消息")
    user = [m for m in messages if m.kind != "system"]
    if not user:
        raise ValueError("CSV 中仅有系统消息，无真人发言")

    return Conversation(source="dingtalk", title="钉钉聊天记录",
                        messages=messages, raw_text=text)


def parse_dingtalk(path: str) -> Conversation:
    text, _enc = read_text(path)
    return parse_dingtalk_text(text)
