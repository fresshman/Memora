"""本地加密存储（隐私核心）。

所有导入的对话记录与生成的纪要，均以 Fernet（AES-128 + HMAC）加密保存在本机，
密钥仅存于本机 vault.key。无任何上传、无遥测。
「一键清空」会删除全部加密碎片与密钥，数据不可恢复 —— 这正是隐私设计目标。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from cryptography.fernet import Fernet

from .. import config
from ..log import get_logger

log = get_logger(__name__)


class Vault:
    def __init__(self) -> None:
        config.ensure_dirs()
        self._key = self._load_or_create_key()
        self._fernet = Fernet(self._key)

    # ------------------------------------------------------------------
    def _load_or_create_key(self) -> bytes:
        if config.VAULT_KEY_FILE.exists():
            return config.VAULT_KEY_FILE.read_bytes()
        key = Fernet.generate_key()
        config.VAULT_KEY_FILE.write_bytes(key)
        return key

    def _index(self) -> dict:
        if config.VAULT_INDEX.exists():
            try:
                return json.loads(config.VAULT_INDEX.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_index(self, idx: dict) -> None:
        config.VAULT_INDEX.write_text(
            json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    def save(self, name: str, content: str, kind: str = "report") -> str:
        """保存一条加密记录，返回记录 id。"""
        rid = hashlib.sha1(f"{name}{time.time()}".encode()).hexdigest()[:12]
        log.info("加密保存记录：id=%s，名称=%s，类型=%s", rid, name, kind)
        blob = self._fernet.encrypt(content.encode("utf-8"))
        (config.VAULT_DIR / f"{rid}.enc").write_bytes(blob)

        idx = self._index()
        idx[rid] = {
            "id": rid,
            "name": name,
            "kind": kind,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._save_index(idx)
        return rid

    def list_records(self) -> list[dict]:
        return list(self._index().values())

    def load(self, rid: str) -> str | None:
        path = config.VAULT_DIR / f"{rid}.enc"
        if not path.exists():
            return None
        return self._fernet.decrypt(path.read_bytes()).decode("utf-8")

    def delete(self, rid: str) -> bool:
        path = config.VAULT_DIR / f"{rid}.enc"
        if path.exists():
            path.unlink()
        idx = self._index()
        if rid in idx:
            del idx[rid]
            self._save_index(idx)
            return True
        return False

    def wipe_all(self) -> None:
        """一键清空：删除全部加密碎片与密钥，数据不可恢复。"""
        log.warning("执行一键清空：将删除全部加密记录与密钥，不可恢复")
        for f in config.VAULT_DIR.glob("*.enc"):
            f.unlink()
        if config.VAULT_INDEX.exists():
            config.VAULT_INDEX.unlink()
        if config.VAULT_KEY_FILE.exists():
            config.VAULT_KEY_FILE.unlink()
