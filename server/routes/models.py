"""模型管理路由：推荐列表 / 本地检测 / 下载 / 转换 / 选择 / 任务状态。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from memora import model_fetch, config

from ..deps import get_agent, select_model
from ..schemas import (
    DownloadStatusResponse, ModelInfo, ModelConfigResponse,
    ModelIdRequest, SelectModelResponse,
)

router = APIRouter()

_VALID_IDS = set(model_fetch.MODEL_IDS)


@router.get("/models/config", response_model=ModelConfigResponse)
def model_config():
    """返回离线开关、后端与当前选中模型等配置（前端据此决定下载交互）。"""
    return ModelConfigResponse(
        offline=config.ENFORCE_OFFLINE,
        backend=config.INFERENCE_BACKEND,
        selected_model=config.get_selected_model_id(),
        n_ctx=config.LLAMACPP_N_CTX,
        kv_quant=config.LLAMACPP_KV_QUANT,
        n_gpu_layers=config.LLAMACPP_N_GPU_LAYERS,
    )


@router.get("/models", response_model=list[ModelInfo])
def list_models():
    """列出推荐模型及其本地状态、选中标记。"""
    selected = config.get_selected_model_id()
    result = []
    for m in model_fetch.AVAILABLE_MODELS:
        local = model_fetch.check_model_local(m["id"])
        result.append(ModelInfo(
            id=m["id"],
            name=m["name"],
            params=m["params"],
            context=m["context"],
            size=m["size"],
            download_size=m.get("download_size", ""),
            memory=m["memory"],
            description=m["description"],
            recommended=m["recommended"],
            selected=(m["id"] == selected),
            local_status=local["status"],
            local_dir=local["dir"],
            gguf_path=local["gguf"],
        ))
    return result


@router.post("/models/download", response_model=DownloadStatusResponse)
def download_model(req: ModelIdRequest):
    """触发模型下载（后台异步，ModelScope）。离线模式直接拒绝并给指引。"""
    model_id = req.model_id
    if model_id not in _VALID_IDS:
        raise HTTPException(status_code=400, detail=f"不支持的模型 ID：{model_id}")
    local = model_fetch.check_model_local(model_id)
    if local["status"] == "ready":
        raise HTTPException(status_code=400, detail="该模型 GGUF 已就绪，无需下载")
    # 离线红线前置拦截：直接给出 409 与操作指引，不进入后台下载线程
    if config.ENFORCE_OFFLINE:
        gguf_repo = model_fetch.get_model_meta(model_id)["gguf_repo"]
        raise HTTPException(
            status_code=409,
            detail=(
                "当前为强制离线模式（MEMORA_ENFORCE_OFFLINE=1），无法下载模型。\n"
                "请在联网的安装阶段设置 MEMORA_ENFORCE_OFFLINE=0 后重启后端再下载，\n"
                "或在联网机器手动执行官方命令下载 Q4_K_M 量化版 GGUF 后拷贝到模型目录：\n"
                "  from modelscope import snapshot_download\n"
                f"  snapshot_download('{gguf_repo}', allow_file_pattern=['*Q4_K_M*'])"
            ),
        )
    st = model_fetch.get_task_status(model_id)
    if st["status"] in ("downloading", "converting"):
        return _status_response(model_id)
    model_fetch.start_download(model_id)
    return _status_response(model_id)


@router.post("/models/convert", response_model=DownloadStatusResponse)
def convert_model(req: ModelIdRequest):
    """对已下载的 safetensors 后台转换 GGUF（需本机有 llama.cpp 工具）。"""
    model_id = req.model_id
    if model_id not in _VALID_IDS:
        raise HTTPException(status_code=400, detail=f"不支持的模型 ID：{model_id}")
    local = model_fetch.check_model_local(model_id)
    st = model_fetch.get_task_status(model_id)
    if st["status"] in ("downloading", "converting"):
        raise HTTPException(status_code=409, detail="该模型正在下载/转换中，请等待完成")
    if local["status"] == "missing":
        raise HTTPException(status_code=400, detail="本地没有该模型文件，请先下载")
    if local["status"] == "ready":
        return _status_response(model_id)
    model_fetch.start_conversion(model_id)
    return _status_response(model_id)


@router.post("/models/select", response_model=SelectModelResponse)
def select(req: ModelIdRequest):
    """选择当前使用的模型（持久化并重建 agent）。仅 ready 模型可被选中。"""
    model_id = req.model_id
    if model_id not in _VALID_IDS:
        raise HTTPException(status_code=400, detail=f"不支持的模型 ID：{model_id}")
    local = model_fetch.check_model_local(model_id)
    if local["status"] != "ready":
        tip = {"missing": "请先在本页下载官方 GGUF",
               "downloaded": "本地只有 safetensors，请转换为 GGUF 或改下载官方 GGUF"}.get(
            local["status"], "请先完成模型下载")
        raise HTTPException(
            status_code=409,
            detail=f"模型尚未就绪（当前状态：{local['status']}），{tip}",
        )
    select_model(model_id)
    # 预触发健康描述（不加载模型，仅文件级检查）
    get_agent()
    return SelectModelResponse(
        model_id=model_id, message=f"已切换到 {model_id}，将在下次推理时加载"
    )


@router.get("/models/status", response_model=DownloadStatusResponse)
def download_status(model_id: str):
    """查询下载/转换任务状态，并合并最新本地检测结果。"""
    if model_id not in _VALID_IDS:
        raise HTTPException(status_code=400, detail=f"不支持的模型 ID：{model_id}")
    return _status_response(model_id)


def _status_response(model_id: str) -> DownloadStatusResponse:
    st = model_fetch.get_task_status(model_id)
    local = model_fetch.check_model_local(model_id)
    # 任务状态与磁盘状态合并：磁盘已 ready 时以 ready 为准
    status = st["status"]
    if local["status"] == "ready" and status not in ("downloading", "converting"):
        status = "ready"
    elif local["status"] == "downloaded" and status in ("idle", "failed", "downloaded"):
        # 保留 failed（带错误信息）但更新 local_status
        pass
    return DownloadStatusResponse(
        model_id=model_id,
        status=status,
        stage=st.get("stage"),
        local_status=local["status"],
        error=st.get("error"),
        started_at=st.get("started_at"),
        finished_at=st.get("finished_at"),
    )
