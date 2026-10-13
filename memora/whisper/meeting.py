"""会议记录组装：把「时间戳 + 说话人 + 文本」的分段整理成标注清晰的记录。

产出：
  - 头部信息（音频名 / 总时长 / 说话人数 / 有效语音时长 / 语言）；
  - 逐行 `[HH:MM:SS] 说话人N：文本`，相邻同说话人短间隔自动合并；
  - 同时保留结构化分段（供前端渲染与 JSON 导出）；
  - SRT 字幕（带说话人前缀）。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, replace

from .transcribe import Segment


@dataclass
class MeetingMeta:
    audio_name: str
    duration_seconds: float
    num_speakers: int
    speech_seconds: float
    language: str


@dataclass
class SpeakerInfo:
    """说话人元信息：声纹原型（注册用）、是否从联系人库自动识别。"""
    name: str
    embedding: list[float] = field(default_factory=list)
    identified: bool = False
    contact_id: str = ""
    score: float = 0.0

    def to_dict(self) -> dict:
        return {"name": self.name, "embedding": self.embedding,
                "identified": self.identified,
                "contact_id": self.contact_id, "score": self.score}


@dataclass
class MeetingRecord:
    meta: MeetingMeta
    segments: list[Segment]
    text: str
    speakers: list[SpeakerInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "meta": asdict(self.meta),
            "segments": [s.to_dict() for s in self.segments],
            "text": self.text,
            "speakers": [s.to_dict() for s in self.speakers],
        }


def fmt_ts(seconds: float) -> str:
    """HH:MM:SS。"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _srt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def merge_adjacent(segments: list[Segment], max_gap: float = 0.6
                   ) -> list[Segment]:
    """合并相邻同一说话人且间隔 <= max_gap 的段（保留起始时间戳）。"""
    out: list[Segment] = []
    for seg in segments:
        if (out and out[-1].speaker == seg.speaker
                and seg.start - out[-1].end <= max_gap):
            out[-1].end = seg.end
            out[-1].text += seg.text
        else:
            out.append(replace(seg))
    return out


def build_meeting(audio_name: str, duration: float, speech_seconds: float,
                  language: str, segments: list[Segment],
                  merge_gap: float = 0.6,
                  speaker_infos: list[SpeakerInfo] | None = None) -> MeetingRecord:
    """组装完整会议记录。"""
    merged = merge_adjacent(segments, merge_gap)
    speakers = sorted({s.speaker for s in merged if s.speaker})
    meta = MeetingMeta(
        audio_name=audio_name,
        duration_seconds=round(duration, 1),
        num_speakers=max(1, len(speakers)),
        speech_seconds=round(speech_seconds, 1),
        language=language,
    )
    lines = [
        "# 会议记录",
        "",
        f"音频文件：{audio_name}",
        f"总时长：{fmt_ts(duration)}　识别说话人：{meta.num_speakers} 位"
        f"　有效语音：{fmt_ts(speech_seconds)}　语言：{language}",
        "",
        "=" * 48,
        "",
    ]
    for seg in merged:
        speaker = seg.speaker or "说话人1"
        lines.append(f"[{fmt_ts(seg.start)}] {speaker}：{seg.text}")
        lines.append("")
    return MeetingRecord(meta=meta, segments=merged, text="\n".join(lines).rstrip(),
                     speakers=speaker_infos or [])


def to_srt(segments: list[Segment]) -> str:
    """生成带说话人前缀的 SRT 字幕。"""
    out: list[str] = []
    for i, seg in enumerate(segments, 1):
        out.append(str(i))
        out.append(f"{_srt_ts(seg.start)} --> {_srt_ts(seg.end)}")
        prefix = f"[{seg.speaker}] " if seg.speaker else ""
        out.append(prefix + seg.text)
        out.append("")
    return "\n".join(out).rstrip() + "\n"
