"""对话问答路由。"""
from __future__ import annotations

import json as _json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..deps import get_agent
from ..session import get
from ..schemas import QARequest, QAResponse

router = APIRouter()


@router.post("/qa", response_model=QAResponse)
def qa(req: QARequest):
    conv = get(req.session_id)
    if conv is None:
        raise HTTPException(404, "会话不存在或已过期，请重新导入")
    if not req.question.strip():
        raise HTTPException(400, "问题为空")
    try:
        answer = get_agent().answer(conv, req.question.strip())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"问答失败：{e}")
    return QAResponse(answer=answer)


@router.post("/qa/stream")
def qa_stream(req: QARequest):
    """SSE 流式问答：meta -> delta* -> done(answer) / error。"""
    conv = get(req.session_id)
    if conv is None:
        raise HTTPException(404, "会话不存在或已过期，请重新导入")
    if not req.question.strip():
        raise HTTPException(400, "问题为空")
    agent = get_agent()

    def gen():
        try:
            for ev in agent.answer_stream(conv, req.question.strip()):
                yield f"data: {_json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield (
                "data: "
                + _json.dumps({"type": "error", "message": f"问答失败：{e}"},
                              ensure_ascii=False)
                + "\n\n"
            )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache",
                 "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
