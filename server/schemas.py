"""FastAPI 请求/响应模型。"""
from __future__ import annotations

from pydantic import BaseModel


class PasteRequest(BaseModel):
    text: str


class ParseResponse(BaseModel):
    session_id: str
    source: str
    title: str
    msg_count: int
    char_count: int
    preview: str
    redacted: bool = False          # 是否已在本地脱敏
    pii_stats: dict[str, int] | None = None  # 各类脱敏数量


class ReviewRequest(BaseModel):
    session_id: str


class ReviewResponse(BaseModel):
    report: str
    sections: dict[str, str]


class QARequest(BaseModel):
    session_id: str
    question: str


class QAResponse(BaseModel):
    answer: str


class BatchReviewResponse(BaseModel):
    overview: str
    total: int
    success: int
    fail: int


class VoiceResponse(BaseModel):
    transcript: str
    report: str


class RecordOut(BaseModel):
    id: str
    name: str
    kind: str
    created: str


class SaveRecordRequest(BaseModel):
    name: str
    content: str
    kind: str = "report"


class SaveRecordResponse(BaseModel):
    id: str
    message: str


class ExportRequest(BaseModel):
    content: str
    name: str = "复盘报告"
    fmt: str = "md"


class ExportResponse(BaseModel):
    path: str
    message: str


class HealthResponse(BaseModel):
    backend: str
    status: str


class ModelInfo(BaseModel):
    id: str
    name: str
    params: str
    context: str
    size: str
    download_size: str = ""
    memory: str
    description: str
    recommended: bool
    selected: bool = False
    local_status: str           # ready / downloaded / missing
    local_dir: str | None = None
    gguf_path: str | None = None


class ModelConfigResponse(BaseModel):
    offline: bool               # ENFORCE_OFFLINE
    backend: str
    selected_model: str
    n_ctx: int
    kv_quant: str
    n_gpu_layers: int


class ModelIdRequest(BaseModel):
    model_id: str


class SelectModelResponse(BaseModel):
    model_id: str
    message: str


class DownloadStatusResponse(BaseModel):
    model_id: str
    status: str                 # idle / downloading / downloaded / converting / ready / completed / failed
    stage: str | None = None    # download / convert
    local_status: str = "missing"
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

class RedactRestoreRequest(BaseModel):
    session_id: str
    text: str


class RedactRestoreResponse(BaseModel):
    text: str
    restored: bool
