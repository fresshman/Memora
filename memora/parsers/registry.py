"""解析器注册表：根据文件后缀 + 内容嗅探，自动选择解析器。

调用入口：
- 文件：`from memora.parsers import parse_file; conv = parse_file(path)`
- 粘贴文本：`parse_text(text)`，会依次嗅探微信/飞书/钉钉格式，失败再按
  「发言人：内容」逐行兜底，避免把整段粘贴当成一条消息。
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import Conversation, Message
from .encoding import read_text
from .wechat import parse_wechat, parse_wechat_text
from .dingtalk import parse_dingtalk, parse_dingtalk_text
from .feishu import parse_feishu, parse_feishu_text
from ..log import get_logger

log = get_logger(__name__)

# 兜底逐行：[时间] 发言人：内容 / 发言人：内容
_PLAIN_LINE_RE = re.compile(
    r'^\s*(?:\[?(\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?)\]?\s*)?'
    r'([^\s：:【】\[\]@]{1,30}?)\s*[：:]\s*(.+)$'
)


def parse_file(path: str) -> Conversation:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在：{path}")

    log.info("解析文件：%s（后缀=%s）", p.name, p.suffix)
    suffix = p.suffix.lower()
    if suffix == ".csv":
        try:
            return parse_dingtalk(str(p))
        except Exception:  # noqa: BLE001
            pass
    elif suffix in (".html", ".htm"):
        try:
            return parse_feishu(str(p))
        except Exception:  # noqa: BLE001
            pass
    elif suffix == ".txt":
        try:
            return parse_wechat(str(p))
        except Exception:  # noqa: BLE001
            pass

    for parser in (parse_wechat, parse_feishu, parse_dingtalk):
        try:
            return parser(str(p))
        except Exception:  # noqa: BLE001
            continue

    log.warning("所有解析器均失败，使用纯文本兜底：%s", p.name)
    text, _enc = read_text(p)
    return parse_plain_text(text, title=p.name, source="plain")


def _looks_html(text: str) -> bool:
    head = text[:2000].lower()
    return any(tok in head for tok in ("<html", "<body", "<table", "<div", "<!doctype"))


def _looks_csv(text: str) -> bool:
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return False
    # 前两行都含逗号且列数一致，疑似表格
    def cols(s: str) -> int:
        return s.count(",") + s.count("，")
    return cols(lines[0]) >= 2 and cols(lines[0]) == cols(lines[1])


def parse_plain_text(text: str, title: str = "粘贴内容",
                     source: str = "plain") -> Conversation:
    """无平台特征时的逐行兜底：识别 '发言人：内容'，识别不出则整体一条。"""
    messages: list[Message] = []
    cur: Message | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        m = _PLAIN_LINE_RE.match(line)
        if m and _reasonable_speaker(m.group(2)):
            cur = Message(speaker=m.group(2).strip(),
                          time=(m.group(1).replace("/", "-") if m.group(1) else None),
                          text=m.group(3).strip(), kind="msg")
            messages.append(cur)
        elif cur is not None:
            cur.text = (cur.text + "\n" + line.strip()).strip()
        else:
            cur = Message(speaker="对话内容", time=None, text=line.strip(),
                          kind="msg")
            messages.append(cur)
    messages = [m for m in messages if m.text.strip()]
    if not messages:
        messages = [Message(speaker="对话内容", time=None,
                            text=text.strip(), kind="msg")]
    return Conversation(source=source, title=title,
                        messages=messages, raw_text=text)


def _reasonable_speaker(name: str) -> bool:
    s = name.strip()
    if not s or len(s) > 30:
        return False
    # 排除把整句长文本误当发言人
    if any(ch in s for ch in "。！？!?；;，,"):
        return False
    return True


def parse_text(text: str, title: str = "粘贴内容") -> Conversation:
    """解析粘贴/上传的纯文本内容，自动嗅探平台格式。"""
    text = text.strip()
    if not text:
        raise ValueError("内容为空")

    candidates = []
    if _looks_html(text):
        candidates.append(parse_feishu_text)
    if _looks_csv(text):
        candidates.append(parse_dingtalk_text)
    # 微信格式最常见（带引号消息头），优先；飞书时间锚点次之
    candidates += [parse_wechat_text, parse_feishu_text]

    for fn in candidates:
        try:
            conv = fn(text)
            if len(conv) >= 1:
                log.info("粘贴文本命中解析器：%s（真人消息 %d 条）",
                         fn.__name__, len(conv))
                return conv
        except Exception:  # noqa: BLE001
            continue

    return parse_plain_text(text, title=title)
