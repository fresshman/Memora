"""全局依赖：agent 与 vault 单例（避免循环导入，独立于 main）。"""
from __future__ import annotations

import threading

from memora.agent import MemoraAgent
from memora.storage import Vault
from memora import config

_agent: MemoraAgent | None = None
_vault = Vault()
_lock = threading.Lock()


def get_agent() -> MemoraAgent:
    global _agent
    if _agent is None:
        with _lock:
            if _agent is None:
                _agent = MemoraAgent.from_config()
    return _agent


def reset_agent() -> MemoraAgent:
    """丢弃当前 agent 单例（切换模型/后端后调用，下次请求按新配置重建）。"""
    global _agent
    with _lock:
        old, _agent = _agent, None
    if old is not None:
        close = getattr(getattr(old, "backend", None), "close", None)
        if callable(close):
            try:
                close()   # 终止旧模型的 llama-server 子进程
            except Exception:  # noqa: BLE001
                pass
    return get_agent()


def select_model(model_id: str) -> MemoraAgent:
    """持久化选中模型并重建 agent。"""
    config.set_selected_model_id(model_id)
    return reset_agent()


def get_vault() -> Vault:
    return _vault
