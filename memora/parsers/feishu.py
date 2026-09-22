"""飞书（Lark）聊天记录解析（.html / .htm 导出）。

飞书导出 HTML 结构随版本变化，采用「先取文本、再按时间锚点切分」的稳健策略：
- 兼容 "时间 发言人"、"发言人 时间"、时间与发言人不同行 三种排版；
- 时间戳之间为一个消息块，首行短且像人名则作为发言人，其余为正文；
- 入群 / 撤回 / 会议卡片等标记为 kind="system"。
失败时由 registry 回退纯文本。
"""
from __future__ import annotations

import re

from .base import Conversation, Message
from .encoding import read_text

TS = r"\d{4}-\d{1,2}-\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?"
TS_RE = re.compile(TS)
HEAD_TS_FIRST = re.compile(r"^(" + TS + r")\s+(.+?)\s*$")
HEAD_NAME_FIRST = re.compile(r"^(.+?)\s+(" + TS + r")\s*$")

# 人名行启发：短、无句末标点、无大段空格
_SENTENCE_PUNCT = "。！？!?；;，,…"

SYSTEM_PATTERNS = [
    re.compile(p) for p in (
        r"加入了群(组|聊)", r"退出了群(组|聊)", r"被移出|移出群",
        r"撤回了一条消息", r"已加入(群|群组|会议)", r"创建了群(组|聊)",
        r"修改了群(名|名称|公告|头像)", r"视频会议|语音会议|飞书会议",
        r"消息已读", r"^\[系统", r"机器人|应用机器人",
        r"分享了(日程|会议|文档|链接)", r"发起了(投票|接龙|会议)",
    )
]


def _looks_like_speaker(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 20:
        return False
    if any(ch in s for ch in _SENTENCE_PUNCT):
        return False
    if "\t" in s or "  " in s:
        return False
    return True


def _is_system(body: str, speaker: str) -> bool:
    head = body.strip().splitlines()[0] if body.strip() else ""
    if head and any(rx.search(head) for rx in SYSTEM_PATTERNS):
        return True
    if speaker and any(k in speaker for k in ("系统", "机器人", "助手", "通知")):
        return True
    return False


def parse_feishu_text(text: str) -> Conversation:
    # 若传入的是 HTML，先抽文本；纯文本也能直接处理
    low = text[:3000].lower()
    if "<" in text and ">" in text and any(
            t in low for t in ("<html", "<body", "<table", "<div", "<!doctype", "<p")):
        try:
            from bs4 import BeautifulSoup
            text = BeautifulSoup(text, "html.parser").get_text(separator="\n")
        except Exception:  # noqa: BLE001
            pass

    # 压缩为非空行（HTML 抽取会产生大量空行）
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    anchors = [(i, TS_RE.search(ln).group(0)) for i, ln in enumerate(lines)
               if TS_RE.search(ln)]

    messages: list[Message] = []
    for idx, (line_i, ts) in enumerate(anchors):
        end = anchors[idx + 1][0] if idx + 1 < len(anchors) else len(lines)
        block = lines[line_i:end]
        if not block:
            continue
        speaker = "未知成员"
        body_lines: list[str] = []

        first = block[0]
        m1 = HEAD_TS_FIRST.match(first)
        m2 = HEAD_NAME_FIRST.match(first)
        if m1 and _looks_like_speaker(m1.group(2)):
            speaker = m1.group(2).strip()
            body_lines = block[1:]
        elif m2 and _looks_like_speaker(m2.group(1)):
            speaker = m2.group(1).strip()
            body_lines = block[1:]
        else:
            # 时间独占一行：下一个非空行若像人名则取作发言人
            rest = block[1:]
            if rest and _looks_like_speaker(rest[0]):
                speaker = rest[0].strip()
                body_lines = rest[1:]
            else:
                body_lines = rest
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        kind = "system" if _is_system(body, speaker) else "msg"
        messages.append(Message(speaker=speaker, time=ts.replace("/", "-"),
                                text=body, kind=kind))

    user = [m for m in messages if m.kind != "system"]
    if not user:
        raise ValueError("未从飞书记录中切分出真人消息")
    return Conversation(source="feishu", title="飞书聊天记录",
                        messages=messages, raw_text=text)


def parse_feishu(path: str) -> Conversation:
    text, _enc = read_text(path)
    return parse_feishu_text(text)
