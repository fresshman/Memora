# -*- coding: utf-8 -*-
"""本地 PII 脱敏（端侧隐私）：解析后、入模型/索引前完成，可逆。"""
from .redactor import Redaction, redact_conversation, redact_if_configured

__all__ = ["Redaction", "redact_conversation", "redact_if_configured", "restore_text_safe"]


def restore_text_safe(text: str, conv) -> str:
    """若会话带脱敏映射则还原，否则原样返回（路由兜底用）。"""
    red = getattr(conv, "redaction", None)
    if red is None:
        return text
    return red.restore(text)
