"""聊天记录文件的统一编码读取。

微信导出常见 GBK/GB18030，钉钉/飞书多为 UTF-8（可能带 BOM）。
优先用 chardet/charset_normalizer 探测，失败再按常见编码回退，
避免中文聊天记录在解析阶段乱码。
"""
from __future__ import annotations

from pathlib import Path

from ..log import get_logger

log = get_logger(__name__)

# 中文聊天记录常见编码回退顺序
_FALLBACK_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "latin-1")


def _detect_encoding(raw: bytes) -> str | None:
    """用 chardet / charset_normalizer 探测编码，返回编码名或 None。"""
    # chardet
    try:
        import chardet  # type: ignore

        guess = chardet.detect(raw)
        enc = (guess or {}).get("encoding")
        if enc and (guess or {}).get("confidence", 0) >= 0.5:
            return enc
    except Exception:  # noqa: BLE001
        pass
    # charset_normalizer（requests 自带，多数环境有）
    try:
        from charset_normalizer import from_bytes  # type: ignore

        best = from_bytes(raw).best()
        if best is not None and best.encoding:
            return best.encoding
    except Exception:  # noqa: BLE001
        pass
    return None


def read_text(path: str | Path) -> tuple[str, str]:
    """读取文本文件，返回 (文本, 实际使用编码)。

    永远不抛 UnicodeDecodeError：最后以 utf-8 errors=ignore 兜底。
    """
    p = Path(path)
    raw = p.read_bytes()
    if not raw:
        return "", "utf-8"

    # 1) BOM 直判
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="ignore"), "utf-16"
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="ignore"), "utf-8-sig"

    # 2) 探测
    detected = _detect_encoding(raw)
    candidates: list[str] = []
    if detected:
        candidates.append(detected)
    for enc in _FALLBACK_ENCODINGS:
        if enc not in candidates:
            candidates.append(enc)

    for enc in candidates:
        try:
            text = raw.decode(enc)
            # 简单质量校验：中文文本不应出现大量替换符
            if text.count("\ufffd") <= max(2, len(text) // 500):
                return text, enc
        except (UnicodeDecodeError, LookupError):
            continue

    return raw.decode("utf-8", errors="ignore"), "utf-8"


def decode_bytes(raw: bytes) -> tuple[str, str]:
    """与 read_text 相同的策略，但输入是字节串（用于粘贴/上传内容）。"""
    if not raw:
        return "", "utf-8"
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="ignore"), "utf-16"
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="ignore"), "utf-8-sig"
    detected = _detect_encoding(raw)
    candidates: list[str] = []
    if detected:
        candidates.append(detected)
    for enc in _FALLBACK_ENCODINGS:
        if enc not in candidates:
            candidates.append(enc)
    for enc in candidates:
        try:
            text = raw.decode(enc)
            if text.count("\ufffd") <= max(2, len(text) // 500):
                return text, enc
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="ignore"), "utf-8"
