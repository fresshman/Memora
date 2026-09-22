"""配置单元测试。"""
from __future__ import annotations

from memora import config


def test_ensure_dirs():
    config.ensure_dirs()
    assert config.DATA_DIR.exists()
    assert config.VAULT_DIR.exists()


def test_discover_gguf_empty(tmp_path):
    assert config.discover_gguf(tmp_path) is None


def test_discover_gguf_found(tmp_path):
    gguf = tmp_path / "spark-x2-5-4b-q4_k_m.gguf"
    gguf.write_bytes(b"x")
    assert config.discover_gguf(tmp_path, model_id="XHToken/Spark-X2.5-4B") == gguf


def test_has_safetensors(tmp_path):
    assert config.has_safetensors(tmp_path) is False
    (tmp_path / "model.safetensors").write_bytes(b"x")
    assert config.has_safetensors(tmp_path) is True


def test_has_safetensors_ignores_incomplete(tmp_path):
    """存在 *.incomplete 分片时视为下载未完成，不得判定为完整。"""
    (tmp_path / "model-00002-of-00002.safetensors").write_bytes(b"x")
    (tmp_path / "model-00001-of-00002.safetensors.incomplete").write_bytes(b"x")
    assert config.has_safetensors(tmp_path) is False
    (tmp_path / "model-00001-of-00002.safetensors.incomplete").unlink()
    (tmp_path / "model-00001-of-00002.safetensors").write_bytes(b"x")
    assert config.has_safetensors(tmp_path) is True


def test_enforce_offline_default():
    assert isinstance(config.ENFORCE_OFFLINE, bool)


def test_find_model_dir_modelscope_layout(tmp_path, monkeypatch):
    """ModelScope cache 布局：models/{Org}--{Name}/snapshots/{rev}/。"""
    monkeypatch.setattr(config, "MODELS_ROOT", tmp_path)
    snap = tmp_path / "models" / "XHToken--Spark-X2.5-1.7B" / "snapshots" / "master"
    snap.mkdir(parents=True)
    (snap / "config.json").write_text("{}", encoding="utf-8")
    found = config.find_model_dir("XHToken/Spark-X2.5-1.7B")
    assert found == snap


def test_find_model_dir_flat_layout(tmp_path, monkeypatch):
    """兼容旧扁平布局：MODELS_ROOT/{Org}/{Name}/。"""
    monkeypatch.setattr(config, "MODELS_ROOT", tmp_path)
    flat = tmp_path / "XHToken" / "Spark-X2.5-4B"
    flat.mkdir(parents=True)
    (flat / "config.json").write_text("{}", encoding="utf-8")
    found = config.find_model_dir("XHToken/Spark-X2.5-4B")
    assert found == flat


def test_gguf_filename_hints():
    hints = config.gguf_filename_hints("XHToken/Spark-X2.5-4B")
    assert "spark-x2-5-4b-q4_k_m.gguf" in hints


def test_selected_model_persistence(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.delenv("MEMORA_MODEL_ID", raising=False)
    assert config.get_selected_model_id() == config.DEFAULT_MODEL_ID
    config.set_selected_model_id("XHToken/Spark-X2.5-1.7B")
    assert config.get_selected_model_id() == "XHToken/Spark-X2.5-1.7B"


def test_gpu_default_is_cpu():
    # 0 = 全 CPU；-1 是全部上 GPU（历史版本曾写反）
    assert config.LLAMACPP_N_GPU_LAYERS in (0, -1)
