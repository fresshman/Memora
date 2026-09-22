"""llama-server 子进程后端的纯逻辑测试（不真正拉起进程）。"""
from __future__ import annotations

import sys

import memora.config as config
from memora.backend.llamacpp_backend import (
    LlamaCppBackend,
    find_llama_server,
    pick_free_port,
)

_EXE = "llama-server.exe" if sys.platform == "win32" else "llama-server"


def test_find_server_explicit(tmp_path):
    exe = tmp_path / "bin" / _EXE
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"x")
    assert find_llama_server(str(exe)) == exe


def test_find_server_tools_dir(tmp_path, monkeypatch):
    """离线包布局：Memora/tools/llamacpp/bin/llama-server(.exe)。"""
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "LLAMACPP_SERVER_PATH", "")
    monkeypatch.setattr(config, "LLAMACPP_PATH", "")
    assert find_llama_server() is None
    exe = tmp_path / "tools" / "llamacpp" / "bin" / _EXE
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"x")
    assert find_llama_server() == exe


def test_build_cmd_contents(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LLAMACPP_N_CTX", 32768)
    monkeypatch.setattr(config, "LLAMACPP_N_GPU_LAYERS", 0)
    monkeypatch.setattr(config, "LLAMACPP_KV_QUANT", "q8_0")
    monkeypatch.setattr(config, "LLAMACPP_N_THREADS", 0)
    monkeypatch.setattr(config, "LLAMACPP_VERBOSE", False)
    b = LlamaCppBackend("XHToken/Spark-X2.5-4B")
    exe = tmp_path / _EXE
    gguf = tmp_path / "model.gguf"
    cmd = b._build_cmd(exe, gguf, 8765)
    joined = " ".join(cmd)
    assert cmd[0] == str(exe)
    assert "-m" in cmd and str(gguf) in cmd
    assert "--host" in cmd and "127.0.0.1" in cmd
    assert "--port" in cmd and "8765" in cmd
    assert "-c" in cmd and "32768" in cmd
    assert "-ngl" in cmd and "0" in cmd
    assert "--cache-type-k" in cmd and "q8_0" in cmd
    # threads=0 时不传 -t（交给 llama-server 自动决定）
    assert "-t" not in cmd
    assert "--verbose" not in joined


def test_build_cmd_with_threads_and_gpu(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LLAMACPP_N_THREADS", 6)
    monkeypatch.setattr(config, "LLAMACPP_N_GPU_LAYERS", 99)
    monkeypatch.setattr(config, "LLAMACPP_VERBOSE", True)
    b = LlamaCppBackend("XHToken/Spark-X2.5-1.7B")
    cmd = b._build_cmd(tmp_path / _EXE, tmp_path / "m.gguf", 1)
    assert "-t" in cmd and "6" in cmd
    assert "-ngl" in cmd and "99" in cmd
    assert "--verbose" in cmd


def test_pick_free_port_auto(monkeypatch):
    monkeypatch.setattr(config, "LLAMACPP_SERVER_PORT", 0)
    p1 = pick_free_port()
    assert isinstance(p1, int) and 1024 < p1 < 65536


def test_pick_free_port_fixed(monkeypatch):
    monkeypatch.setattr(config, "LLAMACPP_SERVER_PORT", 18999)
    assert pick_free_port() == 18999


def test_close_without_start_is_noop():
    b = LlamaCppBackend("XHToken/Spark-X2.5-4B")
    b.close()  # 未启动时 close 不应报错
