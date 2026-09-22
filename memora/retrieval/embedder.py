"""本地 embedding：复用本机 llama-server 跑 bge-m3 GGUF（OpenAI /v1/embeddings）。

- 按需懒启动一个独立的 llama-server 子进程（--embedding --pooling cls），
  与对话生成用的 llama-server 互不干扰、端口随机；
- 模型缺失/二进制缺失时抛 EmbedderUnavailable，由上层降级为规则压缩，
  绝不让超长对话直接报错或静默丢失前文；
- 测试可用 HashEmbedder（确定性词袋向量，无需模型）。
"""
from __future__ import annotations

import atexit
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

from .. import config
from ..log import get_logger
from ..backend.llamacpp_backend import (
    find_llama_server, pick_free_port, _assign_process_to_job,
)

log = get_logger(__name__)

_EXE = "llama-server.exe" if sys.platform == "win32" else "llama-server"


class EmbedderUnavailable(RuntimeError):
    pass


class LlamaServerEmbedder:
    """通过 llama-server 子进程提供文本向量。"""

    def __init__(self, gguf_path: str | Path, model_name: str = "bge-m3",
                 n_ctx: int = 8192, threads: int = 0,
                 boot_timeout: int | None = None) -> None:
        self.gguf = Path(gguf_path)
        self.model_name = model_name
        self.n_ctx = n_ctx
        self.threads = threads or config.LLAMACPP_N_THREADS
        self.boot_timeout = boot_timeout or config.SERVER_BOOT_TIMEOUT
        self._proc: subprocess.Popen | None = None
        self._port: int | None = None
        self._dim: int | None = None
        self._log_fh = None
        atexit.register(self.close)

    # ---- 子进程生命周期 ----
    def _build_cmd(self, exe: Path, port: int) -> list[str]:
        cmd = [
            str(exe), "-m", str(self.gguf),
            "--host", "127.0.0.1", "--port", str(port),
            "-c", str(self.n_ctx),
            "--embedding",            # 开启 /v1/embeddings
            "--pooling", "cls",       # bge 系列用 CLS 池化
            "--embd-normalize", "2",  # L2 归一化
            "-ngl", str(config.LLAMACPP_N_GPU_LAYERS),
        ]
        if self.threads:
            cmd += ["-t", str(self.threads)]
        if not config.LLAMACPP_VERBOSE:
            cmd += ["--log-disable"]
        return cmd

    def _wait_health(self, port: int, timeout: int) -> None:
        url = f"http://127.0.0.1:{port}/health"
        deadline = time.time() + timeout
        last = ""
        while time.time() < deadline:
            if self._proc and self._proc.poll() is not None:
                tail = self._read_log_tail()
                raise EmbedderUnavailable(f"embedding server 提前退出：{tail}")
            try:
                with urllib.request.urlopen(url, timeout=3) as r:
                    if r.status == 200:
                        body = json.loads(r.read().decode("utf-8"))
                        if body.get("status") == "ok":
                            return
            except Exception as e:  # noqa: BLE001
                last = str(e)
            time.sleep(1)
        raise EmbedderUnavailable(f"等待 embedding server 健康检查超时：{last}")

    def _read_log_tail(self, chars: int = 1500) -> str:
        try:
            if self._log_fh:
                self._log_fh.flush()
                with open(self._log_fh.name, "rb") as f:
                    f.seek(0, 2)
                    sz = f.tell()
                    f.seek(max(0, sz - chars))
                    return f.read().decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            pass
        return ""

    def _ensure(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        exe = find_llama_server(None)
        if exe is None:
            raise EmbedderUnavailable("未找到 llama-server，无法启动 embedding 服务")
        if not self.gguf.is_file():
            raise EmbedderUnavailable(f"embedding 模型不存在：{self.gguf}")
        port = pick_free_port()
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        log_path = config.DATA_DIR / "logs" / "llama-embed.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_fh = open(log_path, "ab")
        cmd = self._build_cmd(exe, port)
        creationflags = 0
        preexec_fn = None
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        log.info("启动 embedding server：%s -c %s（端口 %s）", exe.name, self.n_ctx, port)
        self._proc = subprocess.Popen(
            cmd, stdout=self._log_fh, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags, preexec_fn=preexec_fn)
        _assign_process_to_job(self._proc)
        self._wait_health(port, self.boot_timeout)
        self._port = port
        log.info("embedding server 就绪（端口 %s）", port)

    # ---- 向量 ----
    def embed(self, texts: list[str], batch_size: int = 8) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim or 1024), dtype="float32")
        self._ensure()
        url = f"http://127.0.0.1:{self._port}/v1/embeddings"
        out: list[list[float]] = []
        for s in range(0, len(texts), batch_size):
            batch = texts[s:s + batch_size]
            payload = json.dumps(
                {"model": self.model_name, "input": batch}).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8"))
            items = sorted(data["data"], key=lambda x: x["index"])
            for it in items:
                out.append(it["embedding"])
        vecs = np.asarray(out, dtype="float32")
        if self._dim is None:
            self._dim = vecs.shape[1]
        return vecs

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except Exception:  # noqa: BLE001
                    self._proc.kill()
            except Exception:  # noqa: BLE001
                pass
            log.info("embedding server 已关闭")
        self._proc = None
        self._port = None
        if self._log_fh:
            try:
                self._log_fh.close()
            except Exception:  # noqa: BLE001
                pass
            self._log_fh = None


class HashEmbedder:
    """确定性词袋哈希向量（仅用于离线单测，不依赖模型）。

    对中文按 2-gram、英文按词建立稀疏向量；共享词面的 query/块余弦相似度高。
    """

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    @staticmethod
    def _tokens(text: str) -> list[str]:
        import re
        text = text.lower()
        zh = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        grams: list[str] = []
        for w in zh:
            grams += [w[i:i + 2] for i in range(len(w) - 1)]
        grams += re.findall(r"[a-z0-9]+", text)
        return grams

    def embed(self, texts: list[str], batch_size: int = 8) -> np.ndarray:
        vecs = np.zeros((len(texts), self.dim), dtype="float32")
        for i, t in enumerate(texts):
            for tok in self._tokens(t):
                h = hash(tok) % self.dim
                vecs[i, h] += 1.0
            norm = np.linalg.norm(vecs[i])
            if norm > 0:
                vecs[i] /= norm
        return vecs

    def close(self) -> None:
        pass
