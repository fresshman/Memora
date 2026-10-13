"""跨会议行动项路由：列表 / 手动改状态 / 进展回顾 / 思考档位 / 项目复盘包。

全部数据在本地处理，数据不出设备。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..deps import get_agent
from ..session import get
from ..schemas import (
    ActionItemOut, ActionListResponse, ActionStatusRequest,
    TrackProgressRequest, ThinkingModeRequest, ThinkingModeResponse,
    PackageRequest,
)
from memora import action_items as action_mod, exporter
from memora.action_items import STATUSES, is_overdue

router = APIRouter()


def _to_out(it) -> ActionItemOut:
    return ActionItemOut(
        id=it.id, title=it.title, owner=it.owner, contact_id=it.contact_id,
        due=it.due, status=it.status, status_label=STATUSES.get(it.status, it.status),
        overdue=is_overdue(it), source_meeting=it.source_meeting,
        source_kind=it.source_kind, source_session=it.source_session,
        created_at=it.created_at, updated_at=it.updated_at, history=it.history,
    )


@router.get("/actions", response_model=ActionListResponse)
def list_actions(status: str = "", owner: str = ""):
    store = action_mod.get_store()
    items = store.list(status=status or None, owner=owner or None)
    return ActionListResponse(
        items=[_to_out(it) for it in items],
        summary=store.summary(), owners=store.owners(),
    )


@router.post("/actions/status", response_model=ActionItemOut)
def set_action_status(req: ActionStatusRequest):
    if req.status not in STATUSES:
        raise HTTPException(400, f"未知状态：{req.status}")
    it = action_mod.get_store().set_status(req.id, req.status, req.note,
                                           source="手动")
    if it is None:
        raise HTTPException(404, "行动项不存在")
    return _to_out(it)


@router.post("/actions/track")
def track_progress(req: TrackProgressRequest):
    """跨会议进展回顾：用会话 id 或直接传会议文本。"""
    agent = get_agent()
    meeting_text = req.meeting_text
    source_meeting = req.source_meeting
    if req.session_id:
        conv = get(req.session_id)
        if conv is None:
            raise HTTPException(404, "会话不存在或已过期，请重新导入")
        meeting_text = conv.to_prompt_text()
        source_meeting = source_meeting or conv.title
    if not meeting_text.strip():
        raise HTTPException(400, "会议内容为空")
    try:
        return agent.track_progress(
            meeting_text, source_meeting=source_meeting or "本次会议",
            source_kind=req.source_kind,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"进展回顾失败：{e}")


# ---------------------------------------------------------------------------
# 思考档位
# ---------------------------------------------------------------------------
@router.get("/actions/thinking", response_model=ThinkingModeResponse)
def get_thinking():
    return ThinkingModeResponse(mode=get_agent().get_thinking_mode())


@router.post("/actions/thinking", response_model=ThinkingModeResponse)
def set_thinking(req: ThinkingModeRequest):
    if req.mode not in ("fast", "deep"):
        raise HTTPException(400, f"未知思考档位：{req.mode}")
    try:
        get_agent().set_thinking_mode(req.mode)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ThinkingModeResponse(mode=req.mode)


# ---------------------------------------------------------------------------
# 项目复盘包（zip）
# ---------------------------------------------------------------------------
@router.post("/export/package")
def export_package(req: PackageRequest):
    title = req.title
    raw_text = req.raw_text
    if req.session_id:
        conv = get(req.session_id)
        if conv is not None:
            raw_text = conv.to_prompt_text()
            if not title or title == "项目复盘包":
                title = conv.title or title
    try:
        path = exporter.export_package(
            title=title, report=req.report, qa=req.qa,
            record_text=req.record_text, raw_text=raw_text,
            include_raw=req.include_raw,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"复盘包导出失败：{e}")
    return FileResponse(
        str(path), filename=path.name,
        media_type="application/zip",
    )
