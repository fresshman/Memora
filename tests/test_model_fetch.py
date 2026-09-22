"""model_fetch 单元测试（纯逻辑，不联网）。"""
from __future__ import annotations

import pytest

import memora.config as config
from memora.model_fetch import (
    find_llamacpp,
    ensure_gguf,
    ensure_whisper_model,
    check_model_local,
    get_model_meta,
    OfflineDownloadError,
)


def test_find_llamacpp_not_found(tmp_path, monkeypatch):
    # 显式路径不存在；同时把项目根指到临时目录，避免命中开发机上的同级 ../llama.cpp
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    assert find_llamacpp(str(tmp_path / "nope")) is None


def test_model_meta_has_official_gguf_repo():
    for mid in ("XHToken/Spark-X2.5-4B", "XHToken/Spark-X2.5-1.7B"):
        meta = get_model_meta(mid)
        assert meta["gguf_repo"].endswith("-GGUF")
        assert meta["gguf_filename"].endswith("-Q4_K_M.gguf")
        assert "*Q4_K_M*" in meta["gguf_pattern"]


def test_ensure_gguf_existing(tmp_path):
    model_dir = tmp_path / "spark"
    model_dir.mkdir()
    gguf = model_dir / "spark-x2-5-4b-q4_k_m.gguf"
    gguf.write_bytes(b"x")
    # 显式传 model_dir 时直接在该目录发现 GGUF，不做缓存布局解析
    result = ensure_gguf(model_id="XHToken/Spark-X2.5-4B", model_dir=model_dir)
    assert result == gguf


def test_check_model_local_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODELS_ROOT", tmp_path)
    st = check_model_local("XHToken/Spark-X2.5-4B")
    assert st["status"] == "missing"
    assert st["gguf"] is None


def test_check_model_local_modelscope_layout(tmp_path, monkeypatch):
    """HF 原始仓库 ModelScope 布局：只有 safetensors 时 downloaded。"""
    monkeypatch.setattr(config, "MODELS_ROOT", tmp_path)
    snap = tmp_path / "models" / "XHToken--Spark-X2.5-4B" / "snapshots" / "master"
    snap.mkdir(parents=True)
    (snap / "config.json").write_text("{}", encoding="utf-8")
    (snap / "model.safetensors").write_bytes(b"x")
    st = check_model_local("XHToken/Spark-X2.5-4B")
    assert st["status"] == "downloaded"
    assert st["dir"] == str(snap)

    # HF 目录里有本地转换的 GGUF 后应变 ready
    (snap / "spark-x2-5-4b-q4_k_m.gguf").write_bytes(b"g")
    st = check_model_local("XHToken/Spark-X2.5-4B")
    assert st["status"] == "ready"
    assert st["gguf"].endswith("spark-x2-5-4b-q4_k_m.gguf")


def test_check_model_local_official_gguf_repo(tmp_path, monkeypatch):
    """官方 GGUF 仓库布局：models/XHToken--Spark-X2.5-4B-GGUF/snapshots/master/*.gguf。"""
    monkeypatch.setattr(config, "MODELS_ROOT", tmp_path)
    snap = tmp_path / "models" / "XHToken--Spark-X2.5-4B-GGUF" / "snapshots" / "master"
    snap.mkdir(parents=True)
    (snap / "Spark-X2.5-4B-Q4_K_M.gguf").write_bytes(b"g")
    st = check_model_local("XHToken/Spark-X2.5-4B")
    assert st["status"] == "ready"
    assert st["source"] == "gguf"
    assert st["gguf"].endswith("Spark-X2.5-4B-Q4_K_M.gguf")


def test_check_model_local_gguf_repo_wins(tmp_path, monkeypatch):
    """GGUF 仓库与 HF 仓库同时存在时，优先使用官方 Q4_K_M GGUF。"""
    monkeypatch.setattr(config, "MODELS_ROOT", tmp_path)
    g_snap = tmp_path / "models" / "XHToken--Spark-X2.5-1.7B-GGUF" / "snapshots" / "master"
    g_snap.mkdir(parents=True)
    (g_snap / "Spark-X2.5-1.7B-Q4_K_M.gguf").write_bytes(b"g")
    h_snap = tmp_path / "models" / "XHToken--Spark-X2.5-1.7B" / "snapshots" / "master"
    h_snap.mkdir(parents=True)
    (h_snap / "model.safetensors").write_bytes(b"x")
    st = check_model_local("XHToken/Spark-X2.5-1.7B")
    assert st["status"] == "ready"
    assert "-GGUF" in st["dir"]


def test_offline_blocks_download(tmp_path, monkeypatch):
    """强制离线模式下，本地缺失时 ensure_gguf 不得联网，直接报错。"""
    monkeypatch.setattr(config, "MODELS_ROOT", tmp_path)
    monkeypatch.setattr(config, "ENFORCE_OFFLINE", True)
    with pytest.raises(RuntimeError):
        ensure_gguf(model_id="XHToken/Spark-X2.5-4B")


def test_offline_error_points_to_gguf_repo(tmp_path, monkeypatch):
    """离线报错指引应给出官方 GGUF 仓库命令。"""
    monkeypatch.setattr(config, "MODELS_ROOT", tmp_path)
    monkeypatch.setattr(config, "ENFORCE_OFFLINE", True)
    with pytest.raises(RuntimeError) as ei:
        ensure_gguf(model_id="XHToken/Spark-X2.5-4B")
    msg = str(ei.value)
    assert "Spark-X2.5-4B-GGUF" in msg
    assert "Q4_K_M" in msg


def test_ensure_whisper_existing(tmp_path, monkeypatch):
    whisper_dir = tmp_path / "whisper_models"
    whisper_dir.mkdir()
    (whisper_dir / "ggml-base.bin").write_bytes(b"x")
    monkeypatch.setattr(config, "WHISPER_MODEL_DIR", whisper_dir)
    result = ensure_whisper_model()
    assert result == whisper_dir / "ggml-base.bin"


def test_ensure_whisper_offline_missing(tmp_path, monkeypatch):
    whisper_dir = tmp_path / "whisper_models"
    whisper_dir.mkdir()
    monkeypatch.setattr(config, "WHISPER_MODEL_DIR", whisper_dir)
    monkeypatch.setattr(config, "ENFORCE_OFFLINE", True)
    with pytest.raises(RuntimeError):
        ensure_whisper_model()
