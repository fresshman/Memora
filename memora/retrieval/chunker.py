"""对话分块：话题时间窗 + 字符预算 + 滑窗 overlap。

不按字符硬切（会切断语境），而是：
1. 按相邻消息时间间隔（默认 >30 分钟）切「话题段(topic)」；
2. 每个话题段内按字符预算打包成块，相邻块回带 overlap 条消息保持上下文；
3. 超长单条消息按句读切分；每块带元数据（起止消息索引/时间/参与者）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

_TS_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M",
)


def parse_time(t: str | None) -> datetime | None:
    """解析常见时间戳；仅 HH:MM 或无法识别时返回 None。"""
    if not t:
        return None
    s = t.strip().replace("年", "-").replace("月", "-").replace("日", "")
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _line(time: str | None, speaker: str, text: str) -> str:
    return f"[{time or '时间未知'}] {speaker}：{text}"


@dataclass
class Chunk:
    chunk_id: str
    topic_id: int
    text: str
    start_idx: int          # 在 Conversation.user_messages 中的起止索引（含）
    end_idx: int
    start_time: str | None
    end_time: str | None
    speakers: list[str] = field(default_factory=list)
    n_msgs: int = 0

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id, "topic_id": self.topic_id,
            "text": self.text, "start_idx": self.start_idx,
            "end_idx": self.end_idx, "start_time": self.start_time,
            "end_time": self.end_time, "speakers": self.speakers,
            "n_msgs": self.n_msgs,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        return cls(**d)


def _split_long(text: str, max_chars: int) -> list[str]:
    """把超长单条消息按句读/换行切成不超过 max_chars 的段。"""
    if len(text) <= max_chars:
        return [text]
    units = re.split(r"(?<=[。！？!?\n；;])", text)
    parts: list[str] = []
    buf = ""
    for u in units:
        if len(buf) + len(u) <= max_chars:
            buf += u
        else:
            if buf:
                parts.append(buf)
            while len(u) > max_chars:
                parts.append(u[:max_chars])
                u = u[max_chars:]
            buf = u
    if buf:
        parts.append(buf)
    return [p for p in parts if p.strip()]


def chunk_conversation(conv, max_chars: int = 420, overlap_msgs: int = 2,
                       gap_minutes: int = 30) -> list[Chunk]:
    """把 Conversation 切成 Chunk 列表（只含真人消息）。"""
    msgs = conv.user_messages
    if not msgs:
        return []

    # 1) 展开为虚拟行（超长消息切段），记录所属原消息索引
    lines: list[tuple[int, str, str | None, str]] = []
    for i, m in enumerate(msgs):
        base = _line(m.time, m.speaker, m.text)
        for seg in _split_long(base, max_chars):
            lines.append((i, seg, m.time, m.speaker))

    # 2) 话题段编号（时间间隔 > gap 则新话题）
    topics = [0] * len(lines)
    cur_topic = 0
    last_dt = None
    for k, (_, _, t, _) in enumerate(lines):
        dt = parse_time(t)
        if last_dt is not None and dt is not None \
                and (dt - last_dt).total_seconds() > gap_minutes * 60:
            cur_topic += 1
        topics[k] = cur_topic
        if dt is not None:
            last_dt = dt

    # 3) 话题内按字符预算打包，相邻块滑窗 overlap
    chunks: list[Chunk] = []
    i = 0
    cid = 0
    n = len(lines)
    while i < n:
        topic = topics[i]
        j = i
        body: list[str] = []
        size = 0
        while j < n and topics[j] == topic:
            seg_len = len(lines[j][1])
            if body and size + seg_len > max_chars:
                break
            body.append(lines[j][1])
            size += seg_len + 1
            j += 1

        idxs = [lines[x][0] for x in range(i, j)]
        speakers: list[str] = []
        for x in range(i, j):
            sp = lines[x][3]
            if sp not in speakers:
                speakers.append(sp)
        chunks.append(Chunk(
            chunk_id=f"c{cid:04d}", topic_id=topic, text="\n".join(body),
            start_idx=min(idxs), end_idx=max(idxs),
            start_time=lines[i][2], end_time=lines[j - 1][2],
            speakers=speakers, n_msgs=len(set(idxs)),
        ))
        cid += 1
        if j >= n:
            break
        # 跨话题不回退；同话题回带 overlap 条「原消息」
        if topics[j] != topic:
            i = j
        else:
            ni = max(j - overlap_msgs, i + 1)
            i = ni
    return chunks
