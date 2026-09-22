"""报告导出路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import ExportRequest, ExportResponse
from memora.exporter import export

router = APIRouter()


@router.post("/export", response_model=ExportResponse)
def export_report(req: ExportRequest):
    try:
        path = export(req.content, req.name, req.fmt)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"导出失败：{e}")
    return ExportResponse(path=str(path), message=f"已导出：{path}")
