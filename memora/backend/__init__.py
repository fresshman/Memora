"""推理后端工厂。"""
from __future__ import annotations

from .base import MemoraLLM, ModelNotReadyError, strip_thinking
from .llamacpp_backend import LlamaCppBackend
from .sglang_backend import SGLangBackend
from .. import config


def build_backend(backend: str | None = None,
                  model_id: str | None = None) -> MemoraLLM:
    """根据配置构造推理后端。

    backend 为 None 时读取 config.INFERENCE_BACKEND；
    model_id 为 None 时读取用户选中的模型（data/settings.json）。
    """
    backend = (backend or config.INFERENCE_BACKEND).lower()
    model_id = model_id or config.get_selected_model_id()
    if backend == "sglang":
        return SGLangBackend(model_id)
    if backend == "llamacpp":
        return LlamaCppBackend(model_id)
    raise ValueError(f"未知推理后端：{backend!r}（可选 llamacpp / sglang）")


__all__ = [
    "MemoraLLM",
    "ModelNotReadyError",
    "strip_thinking",
    "LlamaCppBackend",
    "SGLangBackend",
    "build_backend",
]
