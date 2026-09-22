"""系统路由：健康检查。"""
from __future__ import annotations

from fastapi import APIRouter

from ..deps import get_agent
from ..schemas import HealthResponse
from memora import config

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    try:
        status = get_agent().backend.health_check()
    except Exception as e:  # noqa: BLE001
        status = f"未就绪：{e}"
    return HealthResponse(backend=config.INFERENCE_BACKEND, status=status)
