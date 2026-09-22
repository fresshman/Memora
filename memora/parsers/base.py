"""对话记录统一数据结构。

所有解析器（微信 / 钉钉 / 飞书）都产出 `Conversation`，
上层智能体只消费 `Conversation.to_prompt_text()` 还原的纯文本对话。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Message:
    speaker: str
    time: str | None
    text: str
    # 消息类型："msg"=真人发言（默认，进模型）；"system"=群系统提示
    # （撤回、入群、打招呼、日期分隔等，默认不进模型，仅用于统计/过滤）
    kind: str = "msg"


@dataclass
class Conversation:
    source: str                       # wechat / dingtalk / feishu / plain
    title: str
    messages: list[Message] = field(default_factory=list)
    raw_text: str = ""                # 原始未解析文本（兜底）
    # PII 脱敏结果（含可逆映射）；未脱敏时为 None。不参与 prompt 文本拼装。
    redaction: object | None = None

    @property
    def char_count(self) -> int:
        return sum(len(m.text) for m in self.user_messages)

    @property
    def user_messages(self) -> list[Message]:
        """真人发言（剔除群系统消息）。"""
        return [m for m in self.messages if m.kind != "system"]

    @property
    def system_messages(self) -> list[Message]:
        return [m for m in self.messages if m.kind == "system"]

    @property
    def speakers(self) -> list[str]:
        """参与发言的人（按首次出现顺序去重）。"""
        seen: list[str] = []
        for m in self.user_messages:
            if m.speaker and m.speaker not in seen:
                seen.append(m.speaker)
        return seen

    @property
    def time_range(self) -> tuple[str | None, str | None]:
        """返回 (最早时间, 最晚时间)，无法识别则为 None。"""
        times = [m.time for m in self.user_messages if m.time]
        return (times[0] if times else None, times[-1] if times else None)

    def to_prompt_text(self, limit_chars: int | None = None) -> str:
        """还原「发言人 + 时间 + 内容」的对话时序文本，供模型全局理解。

        只包含真人发言（kind="msg"），系统消息不喂给模型。
        超过 limit_chars 时，保留最新部分并在开头标注截断。默认上限取
        config.MAX_INPUT_CHARS（随 n_ctx 自动换算，可用 MEMORA_MAX_INPUT_CHARS 覆盖）。
        """
        if limit_chars is None:
            from .. import config
            limit_chars = config.MAX_INPUT_CHARS
        lines: list[str] = []
        total = 0
        msgs = self.user_messages
        # 从新到旧累加，超出后截断最旧部分
        for m in reversed(msgs):
            line = f"[{m.time or '时间未知'}] {m.speaker}：{m.text}"
            if total + len(line) > limit_chars:
                break
            lines.append(line)
            total += len(line)
        lines.reverse()
        body = "\n".join(lines)
        if len(lines) < len(msgs):
            dropped = len(msgs) - len(lines)
            return (
                f"（以下为最近 {len(lines)} 条记录，较早的 {dropped} 条因长度限制未载入）\n"
                + body
            )
        return body

    def __len__(self) -> int:
        return len(self.user_messages)
