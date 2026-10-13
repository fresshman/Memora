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


class VoiceMeetingResponse(BaseModel):
    meta: dict
    segments: list[dict]
    speakers: list[dict] = []
    text: str


class VoiceStatusResponse(BaseModel):
    ffmpeg: bool
    asr_engine: bool
    asr_model: bool
    speaker: bool
    asr_model_name: str
    message: str = ""


class VoiceMinutesRequest(BaseModel):
    record_text: str


class VoiceExportRequest(BaseModel):
    record: dict
    fmt: str = "md"
    name: str | None = None


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


# ---------------------------------------------------------------------------
# 跨会议行动项
# ---------------------------------------------------------------------------
class ActionItemOut(BaseModel):
    id: str
    title: str
    owner: str = ""
    contact_id: str = ""
    due: str = ""
    status: str
    status_label: str = ""
    overdue: bool = False
    source_meeting: str = ""
    source_kind: str = "chat"
    source_session: str = ""
    created_at: str = ""
    updated_at: str = ""
    history: list[dict] = []


class ActionListResponse(BaseModel):
    items: list[ActionItemOut]
    summary: dict
    owners: list[str] = []


class ActionStatusRequest(BaseModel):
    id: str
    status: str
    note: str = ""


# 跨会议进展回顾：用会话 id（复盘）或直接传会议文本
class TrackProgressRequest(BaseModel):
    session_id: str = ""
    meeting_text: str = ""
    source_meeting: str = ""
    source_kind: str = "chat"


class ThinkingModeRequest(BaseModel):
    mode: str               # fast / deep


class ThinkingModeResponse(BaseModel):
    mode: str


class PackageRequest(BaseModel):
    title: str = "项目复盘包"
    session_id: str = ""
    report: str = ""
    qa: list[dict] = []
    record_text: str = ""
    raw_text: str = ""
    include_raw: bool = True
