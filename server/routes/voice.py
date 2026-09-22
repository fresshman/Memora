"""语音转写路由。"""
from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, UploadFile, File, HTTPException

from ..deps import get_agent
from ..schemas import VoiceResponse
from memora.whisper import transcribe, WhisperNotReadyError
from memora.backend.base import ModelNotReadyError

router = APIRouter()


@router.post("/voice/transcribe", response_model=VoiceResponse)
async def voice_transcribe(file: UploadFile = File(...)):
    content = await file.read()
    suffix = os.path.splitext(file.filename or ".wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="wb") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        transcript = transcribe(tmp_path)
    except WhisperNotReadyError as e:
        raise HTTPException(503, f"语音模块未就绪：{e}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"转写失败：{e}")
    finally:
        os.unlink(tmp_path)
    try:
        report = get_agent().review_transcript(transcript)
    except ModelNotReadyError as e:
        return VoiceResponse(transcript=transcript,
                             report=f"模型未就绪，仅返回转写文本：\n{e}")
    return VoiceResponse(transcript=transcript, report=report)
