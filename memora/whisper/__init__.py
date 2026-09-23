"""语音转写与会议记录包（本地离线，纯 CPU）。

模块布局（包属性指向子模块，便于 memora.whisper.transcribe.xxx）：
  audio      解码 / 响度归一 / 轻量能量 VAD
  transcribe whisper.cpp 转写（内置 VAD + JSON 时间戳）
  diarize    MFCC + KMeans 说话人分离
  meeting    会议记录组装与 SRT
"""
from __future__ import annotations

# 1) 先导入子模块，保证包属性 transcribe / diarize 指向模块而非同名函数
from . import audio, transcribe, diarize, meeting

# 2) 常用函数 / 类（便捷函数用别名，避免与模块名冲突）
from .transcribe import (
    WhisperNotReadyError, Segment, transcribe_segments, ensure_model,
    transcribe as run_transcribe,
)
from .audio import energy_vad, speech_regions, speech_duration
from .diarize import diarize as run_diarize
from .meeting import build_meeting, to_srt, MeetingRecord, MeetingMeta

__all__ = [
    "audio", "transcribe", "diarize", "meeting",
    "WhisperNotReadyError", "Segment", "transcribe_segments", "ensure_model",
    "run_transcribe", "energy_vad", "speech_regions", "speech_duration",
    "run_diarize", "build_meeting", "to_srt", "MeetingRecord", "MeetingMeta",
]
