"""语音会议链路路由：就绪状态 / 转写会议记录 / 流式纪要 / 多格式导出。

整条链路（本地离线、纯 CPU、不依赖 torch）：
    上传音频
      -> ffmpeg 解码为 16kHz mono（soundfile 兜底）+ 降噪 / 动态响度归一
      -> 轻量能量 VAD 统计有效语音时长
      -> pywhispercpp（whisper.cpp 进程内绑定）转写，输出带时间戳句子段
      -> CAM++ 神经声纹 embedding + AHC 说话人分离（人数自动 / 手填，MFCC 降级）
      -> 组装标注清晰（说话人 + 时间戳）的会议记录
      -> 一键导出 MD/TXT/SRT/PDF，或流式提炼结构化会议纪要
"""
from __future__ import annotations

import json as _json
import os
import tempfile

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse

from ..deps import get_agent
from ..schemas import (
    VoiceMeetingResponse, VoiceStatusResponse,
    VoiceMinutesRequest, VoiceExportRequest,
)
from memora import config, exporter
from memora.whisper import audio
from memora.whisper import transcribe as asr_mod
from memora.whisper import diarize as diar_mod
from memora.whisper.meeting import build_meeting
from memora.whisper.transcribe import WhisperNotReadyError

router = APIRouter()


def _unlink(p: str) -> None:
    try:
        os.unlink(p)
    except OSError:
        pass


def _module_ready(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# 就绪状态
# ---------------------------------------------------------------------------
@router.get("/voice/status", response_model=VoiceStatusResponse)
def voice_status():
    ff = config.find_ffmpeg()
    engine = _module_ready("pywhispercpp")
    speaker = _module_ready("speakeronnx")
    model = config.find_whisper_model(config.WHISPER_DEFAULT_MODEL)
    missing = []
    if ff is None:
        missing.append("缺少 ffmpeg（音频解码）")
    if not engine:
        missing.append("缺少 pywhispercpp（转写引擎：pip install pywhispercpp）")
    if model is None:
        missing.append(f"缺少 ASR 模型 {config.WHISPER_DEFAULT_MODEL}")
    if not speaker:
        missing.append("缺少 speakeronnx（说话人识别：pip install speakeronnx；无则降级 MFCC）")
    return VoiceStatusResponse(
        ffmpeg=ff is not None,
        asr_engine=engine,
        asr_model=model is not None,
        speaker=speaker,
        asr_model_name=config.WHISPER_DEFAULT_MODEL,
        message="；".join(missing),
    )


# ---------------------------------------------------------------------------
# 转写 -> 会议记录（重活放线程池，不阻塞事件循环）
# ---------------------------------------------------------------------------
def _process(audio_path: str, name: str, language: str,
             num_speakers: int):
    info = audio.probe(audio_path)
    y, sr = audio.decode(audio_path)
    speech_s = audio.speech_duration(y)
    lang = "" if language in ("", "auto") else language

    segs = asr_mod.transcribe_segments(y, sr=sr, language=lang)

    speaker_infos = []
    if config.DIAR_ENABLE and segs:
        from memora.whisper import contacts as contacts_mod
        from memora.whisper.meeting import SpeakerInfo
        segs, _k, E, win_labels, name_map = diar_mod.diarize_full(
            y, segs, num_speakers=num_speakers, sr=sr)
        if E is not None and win_labels is not None:
            store = contacts_mod.get_store()
            speaker_rename: dict[str, str] = {}
            for lab, generic in name_map.items():
                cen = contacts_mod.cluster_centroid(E, win_labels, lab)
                contact, score = store.identify(cen)
                if contact is not None:
                    speaker_rename[generic] = contact.name
                    speaker_infos.append(SpeakerInfo(
                        name=contact.name, embedding=cen,
                        identified=True, contact_id=contact.id,
                        score=round(score, 3)))
                else:
                    speaker_infos.append(SpeakerInfo(
                        name=generic, embedding=cen,
                        identified=False, score=round(score, 3)))
            if speaker_rename:
                for seg in segs:
                    if seg.speaker in speaker_rename:
                        seg.speaker = speaker_rename[seg.speaker]
    else:
        for s in segs:
            if not s.speaker:
                s.speaker = "说话人1"

    # diarize_full 已按 generic 合并；此处禁用再合并，避免不同 generic 被误认
    # 为同一联系人后、相邻段被 merge_adjacent 错误并成一段。
    mg = -1.0 if (config.DIAR_ENABLE and segs) else 0.6
    return build_meeting(name, info.duration, speech_s, language, segs,
                         merge_gap=mg, speaker_infos=speaker_infos)


@router.post("/voice/transcribe", response_model=VoiceMeetingResponse)
async def voice_transcribe(
    file: UploadFile = File(...),
    language: str = Form("zh"),
    num_speakers: int = Form(0),
):
    content = await file.read()
    if not content:
        raise HTTPException(400, "上传文件为空")
    suffix = os.path.splitext(file.filename or ".wav")[1] or ".wav"
    src = tempfile.NamedTemporaryFile(suffix=suffix, delete=False,
                                      mode="wb").name
    with open(src, "wb") as f:
        f.write(content)
    try:
        try:
            record = await run_in_threadpool(
                _process, src, file.filename or "audio" + suffix,
                language, num_speakers)
        except WhisperNotReadyError as e:
            raise HTTPException(503, f"语音模块未就绪：{e}")
        except audio.AudioDecodeError as e:
            raise HTTPException(400, str(e))
        except Exception as e:  # noqa: BLE001
            raise HTTPException(500, f"语音处理失败：{e}")
    finally:
        _unlink(src)
    d = record.to_dict()
    return VoiceMeetingResponse(meta=d["meta"], segments=d["segments"],
                                text=d["text"], speakers=d.get("speakers", []))


# ---------------------------------------------------------------------------
# 流式会议纪要
# ---------------------------------------------------------------------------
@router.post("/voice/minutes/stream")
def voice_minutes_stream(req: VoiceMinutesRequest):
    if not req.record_text.strip():
        raise HTTPException(400, "会议记录为空")
    agent = get_agent()

    def gen():
        try:
            for ev in agent.review_transcript_stream(req.record_text):
                yield f"data: {_json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield (
                "data: "
                + _json.dumps({"type": "error",
                               "message": f"纪要生成失败：{e}"},
                              ensure_ascii=False)
                + "\n\n"
            )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache",
                 "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# 多格式导出
# ---------------------------------------------------------------------------
def _record_from_dict(data: dict):
    from memora.whisper.transcribe import Segment
    from memora.whisper.meeting import MeetingMeta, MeetingRecord
    m = data["meta"]
    meta = MeetingMeta(
        audio_name=m["audio_name"],
        duration_seconds=m["duration_seconds"],
        num_speakers=m["num_speakers"],
        speech_seconds=m["speech_seconds"],
        language=m["language"],
    )
    segs = [Segment(start=s["start"], end=s["end"], text=s["text"],
                    speaker=s.get("speaker"))
            for s in data["segments"]]
    return MeetingRecord(meta=meta, segments=segs,
                         text=data.get("text", ""))


_MEDIA = {
    "md": "text/markdown; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
    "srt": "text/plain; charset=utf-8",
    "pdf": "application/pdf",
}


@router.post("/voice/export")
def voice_export(req: VoiceExportRequest):
    fmt = req.fmt.lower()
    if fmt not in _MEDIA:
        raise HTTPException(400, f"不支持的导出格式：{req.fmt}")
    try:
        record = _record_from_dict(req.record)
        path = exporter.export_meeting(record, fmt=fmt, name=req.name)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"导出失败：{e}")
    return FileResponse(str(path), filename=path.name,
                        media_type=_MEDIA[fmt])


# ---------------------------------------------------------------------------
# 跨会话联系人声纹库（纯本地，数据不出设备）
# ---------------------------------------------------------------------------
from pydantic import BaseModel as _BM


class _ContactRegister(_BM):
    name: str
    embedding: list[float]


class _ContactRename(_BM):
    id: str
    name: str


@router.post("/voice/contact/register")
def voice_contact_register(req: _ContactRegister):
    """重命名即注册：把说话人声纹原型存入联系人库。"""
    from memora.whisper import contacts as contacts_mod
    if not req.name.strip():
        raise HTTPException(400, "联系人姓名为空")
    if not req.embedding:
        raise HTTPException(400, "缺少声纹 embedding")
    c = contacts_mod.get_store().register(req.name, req.embedding)
    return {"id": c.id, "name": c.name, "samples": len(c.embeddings)}


@router.get("/voice/contacts")
def voice_contacts_list():
    from memora.whisper import contacts as contacts_mod
    return {"contacts": contacts_mod.get_store().summary()}


@router.post("/voice/contact/rename")
def voice_contact_rename(req: _ContactRename):
    from memora.whisper import contacts as contacts_mod
    c = contacts_mod.get_store().rename(req.id, req.name)
    if c is None:
        raise HTTPException(404, "联系人不存在")
    return {"id": c.id, "name": c.name}


@router.delete("/voice/contact/{cid}")
def voice_contact_delete(cid: str):
    from memora.whisper import contacts as contacts_mod
    ok = contacts_mod.get_store().delete(cid)
    if not ok:
        raise HTTPException(404, "联系人不存在")
    return {"deleted": cid}