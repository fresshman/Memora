"""复盘路由：解析文件/粘贴、一键复盘、批量复盘。"""
from __future__ import annotations

import os
import tempfile

import json as _json

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

from ..deps import get_agent
from ..session import create, get
from ..schemas import (
    PasteRequest, ParseResponse, ReviewRequest, ReviewResponse,
    BatchReviewResponse, RedactRestoreRequest, RedactRestoreResponse,
)
from memora.parsers import parse_file, parse_text, Conversation, Message
from memora.agent import MemoraAgent
from memora.pii import redact_if_configured
from memora.batch import batch_review, summarize

router = APIRouter()


def _preview(conv: Conversation) -> str:
    head = conv.messages[:8]
    lines = [f"来源：{conv.source}　消息数：{len(conv)}　字数：{conv.char_count}"]
    for m in head:
        lines.append(f"[{m.time or '?'}] {m.speaker}：{m.text[:60]}")
    if len(conv) > 8:
        lines.append(f"…（共 {len(conv)} 条）")
    return "\n".join(lines)


@router.post("/conversations/parse", response_model=ParseResponse)
async def parse_upload(file: UploadFile = File(...)):
    content = await file.read()
    suffix = os.path.splitext(file.filename or ".txt")[1] or ".txt"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="wb") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        conv = parse_file(tmp_path)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"解析失败：{e}")
    finally:
        os.unlink(tmp_path)
    conv, red = redact_if_configured(conv)
    sid = create(conv)
    return ParseResponse(
        session_id=sid, source=conv.source, title=conv.title,
        msg_count=len(conv), char_count=conv.char_count,
        preview=_preview(conv),
        redacted=red is not None,
        pii_stats=red.stats() if red is not None else None,
    )


@router.post("/conversations/paste", response_model=ParseResponse)
async def paste(req: PasteRequest):
    if not req.text.strip():
        raise HTTPException(400, "内容为空")
    # 粘贴文本同样走平台嗅探（微信/飞书/钉钉），失败再按「发言人：内容」逐行兜底，
    # 避免把整段聊天记录当成一条消息。
    conv = parse_text(req.text, title="粘贴内容")
    conv, red = redact_if_configured(conv)
    sid = create(conv)
    return ParseResponse(
        session_id=sid, source=conv.source, title=conv.title,
        msg_count=len(conv), char_count=conv.char_count,
        preview=_preview(conv),
        redacted=red is not None,
        pii_stats=red.stats() if red is not None else None,
    )


@router.post("/review", response_model=ReviewResponse)
def review(req: ReviewRequest):
    conv = get(req.session_id)
    if conv is None:
        raise HTTPException(404, "会话不存在或已过期，请重新导入")
    try:
        report = get_agent().review(conv)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"复盘失败：{e}")
    sections = MemoraAgent.split_report(report)
    return ReviewResponse(report=report, sections=sections)


@router.post("/review/stream")
def review_stream(req: ReviewRequest):
    """SSE 流式复盘：事件 meta -> delta* -> done(含 sections) / error。"""
    conv = get(req.session_id)
    if conv is None:
        raise HTTPException(404, "会话不存在或已过期，请重新导入")
    agent = get_agent()

    def gen():
        try:
            for ev in agent.review_stream(conv):
                yield f"data: {_json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield (
                "data: "
                + _json.dumps({"type": "error", "message": f"复盘失败：{e}"},
                              ensure_ascii=False)
                + "\n\n"
            )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache",
                 "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/review/batch", response_model=BatchReviewResponse)
async def batch_review_endpoint(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "未选择文件")
    paths: list[str] = []
    tmp_files: list[str] = []
    try:
        for f in files:
            content = await f.read()
            suffix = os.path.splitext(f.filename or ".txt")[1] or ".txt"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="wb") as tmp:
                tmp.write(content)
                paths.append(tmp.name)
                tmp_files.append(tmp.name)
        results = batch_review(paths, get_agent())
        overview = summarize(results)
        return BatchReviewResponse(
            overview=overview, total=len(results),
            success=sum(1 for r in results if r.success),
            fail=sum(1 for r in results if not r.success),
        )
    finally:
        for p in tmp_files:
            os.unlink(p)

@router.post("/redact/restore", response_model=RedactRestoreResponse)
def redact_restore(req: RedactRestoreRequest):
    """在本机把脱敏后的报告/答案按会话映射还原为真实信息（本地授权操作）。"""
    conv = get(req.session_id)
    if conv is None:
        raise HTTPException(404, "会话不存在或已过期，请重新导入")
    red = getattr(conv, "redaction", None)
    if red is None:
        return RedactRestoreResponse(text=req.text, restored=False)
    return RedactRestoreResponse(text=red.restore(req.text), restored=True)
