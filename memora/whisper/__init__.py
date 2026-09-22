"""语音转写包。"""
from __future__ import annotations

from .transcribe import WhisperNotReadyError, transcribe, ensure_model

__all__ = ["WhisperNotReadyError", "transcribe", "ensure_model"]
