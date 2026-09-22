"""会话管理：内存存储已解析的 Conversation，前端用 session_id 引用。

简单实现：进程内 dict，重启丢失。离线单机工具够用。
"""
from __future__ import annotations

import hashlib
import time

from memora.parsers import Conversation

_sessions: dict[str, Conversation] = {}


def create(conv: Conversation) -> str:
    sid = hashlib.sha1(f"{time.time()}{id(conv)}".encode()).hexdigest()[:12]
    _sessions[sid] = conv
    return sid


def get(sid: str) -> Conversation | None:
    return _sessions.get(sid)


def remove(sid: str) -> None:
    _sessions.pop(sid, None)
