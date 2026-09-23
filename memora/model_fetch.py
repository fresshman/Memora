"""统一模型获取策略：有就用 → ModelScope 下载官方 GGUF → （兜底）safetensors 转 GGUF。

默认下载路径（推荐，零工具链）：
    官方在 ModelScope 提供了已转换/量化好的 GGUF 仓库，直接下载 Q4_K_M 单文件即可推理：
        from modelscope import snapshot_download
        snapshot_download("XHToken/Spark-X2.5-4B-GGUF", allow_file_pattern=["*Q4_K_M*"])

兜底路径（高级用户，仅当拿到的是 safetensors 原始仓库时）：
    convert_hf_to_gguf.py 转 f16 → llama-quantize 量化 Q4_K_M，需要本机有 llama.cpp。

状态机（check_model_local / 后台任务状态）：
    missing     本地没有
    downloading 正在下载（官方 GGUF 或 safetensors）
    downloaded  已下载 safetensors，尚需转 GGUF
    converting  正在转换 GGUF + INT4 量化（兜底路径）
    ready       已有 GGUF，可直接推理
    failed      下载/转换失败（error 字段带原因）

离线红线：config.ENFORCE_OFFLINE=1 时，本模块绝不发起下载，直接报错并给手动指引。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from . import config
from .log import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# 推荐模型列表（首页 / 模型配置页显式推荐）
# gguf_repo：官方已量化 GGUF 仓库；gguf_pattern：只拉取 Q4_K_M 单文件
# ---------------------------------------------------------------------------
AVAILABLE_MODELS = [
    {
        "id": "XHToken/Spark-X2.5-4B",
        "name": "Spark-X2.5-4B",
        "params": "40亿参数",
        "context": "1M 上下文",
        "size": "Q4_K_M 量化约 2.5GB（官方 GGUF，下载即用）",
        "download_size": "约 2.5GB",
        "memory": "8GB+ 内存（n_ctx=32768 + KV q8）",
        "description": "推荐主力模型，长上下文复盘能力强，复盘/纪要/问答效果最佳",
        "recommended": True,
        "gguf_repo": "XHToken/Spark-X2.5-4B-GGUF",
        "gguf_filename": "Spark-X2.5-4B-Q4_K_M.gguf",
        "gguf_pattern": ["*Q4_K_M*"],
    },
    {
        "id": "XHToken/Spark-X2.5-1.7B",
        "name": "Spark-X2.5-1.7B",
        "params": "17亿参数",
        "context": "1M 上下文",
        "size": "Q4_K_M 量化约 1.1GB（官方 GGUF，下载即用）",
        "download_size": "约 1.1GB",
        "memory": "4GB+ 内存",
        "description": "轻量替代，低配设备友好，加载与推理更快",
        "recommended": False,
        "gguf_repo": "XHToken/Spark-X2.5-1.7B-GGUF",
        "gguf_filename": "Spark-X2.5-1.7B-Q4_K_M.gguf",
        "gguf_pattern": ["*Q4_K_M*"],
    },
]

MODEL_IDS = [m["id"] for m in AVAILABLE_MODELS]
_MODELS_BY_ID = {m["id"]: m for m in AVAILABLE_MODELS}


def get_model_meta(model_id: str) -> dict:
    """返回模型元数据；未知 id 抛 KeyError。"""
    return _MODELS_BY_ID[model_id]


class OfflineDownloadError(RuntimeError):
    """强制离线模式下请求联网下载时抛出。"""


def get_model_dir(model_id: str) -> Path | None:
    """返回模型本地 snapshot 目录（优先官方 GGUF 仓库，其次 HF 仓库），不存在返回 None。"""
    meta = _MODELS_BY_ID.get(model_id)
    if meta:
        d = config.find_model_dir(model_id, repo_id=meta["gguf_repo"])
        if d:
            return d
    return config.find_model_dir(model_id)


def check_model_local(model_id: str) -> dict:
    """检查模型本地状态。

    返回 {"status": "ready"|"downloaded"|"missing", "dir": str|None, "gguf": str|None,
          "source": "gguf"|"safetensors"|None}
    - ready:      已有 GGUF（官方 GGUF 仓库或本地转换产物），可直接推理
    - downloaded: 已有 safetensors，需转 GGUF（兜底路径）
    - missing:    未下载
    """
    meta = _MODELS_BY_ID.get(model_id)

    # 1) 官方 GGUF 仓库（XHToken--Spark-X2.5-4B-GGUF/snapshots/.../*.gguf）
    if meta:
        gdir = config.find_model_dir(model_id, repo_id=meta["gguf_repo"])
        if gdir:
            gguf = config.discover_gguf(gdir, model_id=meta["gguf_repo"])
            if gguf:
                return {"status": "ready", "dir": str(gdir), "gguf": str(gguf),
                        "source": "gguf"}

    # 2) HF 原始仓库：可能已有本地转换的 GGUF，或只有 safetensors
    hdir = config.find_model_dir(model_id)
    if hdir is None:
        return {"status": "missing", "dir": None, "gguf": None, "source": None}
    gguf = config.discover_gguf(hdir, model_id=(meta["gguf_repo"] if meta else model_id))
    if gguf:
        return {"status": "ready", "dir": str(hdir), "gguf": str(gguf), "source": "gguf"}
    if config.has_safetensors(hdir, model_id=model_id):
        return {"status": "downloaded", "dir": str(hdir), "gguf": None,
                "source": "safetensors"}
    return {"status": "missing", "dir": None, "gguf": None, "source": None}


# ---------------------------------------------------------------------------
# 后台任务状态（下载 / 转换），进程内
# ---------------------------------------------------------------------------
_task_status: dict[str, dict] = {}
_task_lock = threading.Lock()


def _set_status(model_id: str, **fields) -> None:
    with _task_lock:
        st = _task_status.setdefault(model_id, {
            "model_id": model_id, "status": "idle", "stage": None,
            "error": None, "started_at": None, "finished_at": None,
        })
        st.update(fields)


def get_task_status(model_id: str) -> dict:
    """查询某模型的下载/转换任务状态，未发起过返回 idle。"""
    with _task_lock:
        st = _task_status.get(model_id)
        if st is None:
            return {
                "model_id": model_id, "status": "idle", "stage": None,
                "error": None, "started_at": None, "finished_at": None,
            }
        return dict(st)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# ModelScope 下载
# ---------------------------------------------------------------------------
def _offline_guard() -> None:
    if config.ENFORCE_OFFLINE:
        raise OfflineDownloadError(
            "当前为强制离线模式（MEMORA_ENFORCE_OFFLINE=1），禁止联网下载模型。\n"
            "请在可联网的安装阶段关闭离线模式（MEMORA_ENFORCE_OFFLINE=0）后在「模型管理」页下载，\n"
            "或在联网机器手动下载官方 GGUF 后拷贝到本机模型目录。"
        )


def _import_snapshot_download():
    try:
        from modelscope import snapshot_download
        return snapshot_download
    except ImportError as e:
        raise RuntimeError(
            "未安装 modelscope，请先执行：pip install modelscope"
        ) from e


def fetch_modelscope(model_id: str, cache_dir: Path | None = None,
                     repo_id: str | None = None,
                     allow_file_pattern: list[str] | None = None) -> Path:
    """从 ModelScope 下载指定仓库，返回本地 snapshot 目录。

    ENFORCE_OFFLINE=1 时直接抛 OfflineDownloadError，绝不联网。
    repo_id 可指定与模型 id 不同的仓库（官方 GGUF 仓库）。
    allow_file_pattern 用于只拉取需要的文件（如仅 Q4_K_M 量化版）。
    """
    _offline_guard()
    snapshot_download = _import_snapshot_download()
    target_repo = repo_id or model_id
    cache_dir = cache_dir or config.MODELS_ROOT
    cache_dir.mkdir(parents=True, exist_ok=True)
    log.info("从 ModelScope 下载：%s（缓存目录=%s，文件过滤=%s）",
             target_repo, cache_dir, allow_file_pattern or "全部")
    try:
        kwargs = {"cache_dir": str(cache_dir)}
        if allow_file_pattern:
            kwargs["allow_file_pattern"] = list(allow_file_pattern)
        path = Path(snapshot_download(target_repo, **kwargs))
        log.info("ModelScope 下载完成：%s", path)
        return path
    except OfflineDownloadError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"从 ModelScope 下载失败：{target_repo}\n"
            f"错误：{e}\n"
            "请检查网络，或手动执行官方命令下载：\n"
            "  from modelscope import snapshot_download\n"
            f"  snapshot_download('{target_repo}')"
        ) from e


def fetch_official_gguf(model_id: str, cache_dir: Path | None = None) -> Path:
    """下载官方已量化的 Q4_K_M GGUF（默认路径，无需任何转换工具）。"""
    meta = _MODELS_BY_ID[model_id]
    return fetch_modelscope(
        model_id,
        cache_dir=cache_dir or config.MODELS_ROOT,
        repo_id=meta["gguf_repo"],
        allow_file_pattern=meta["gguf_pattern"],
    )


def start_download(model_id: str, auto_convert: bool = True) -> None:
    """后台线程：默认下载官方 Q4_K_M GGUF，完成即可用。

    若拿到的是 safetensors（老路径/手动放置），且本机有 llama.cpp，则自动续接转换。
    """
    st = get_task_status(model_id)
    if st["status"] in ("downloading", "converting"):
        return

    def _worker():
        _set_status(model_id, status="downloading", stage="download",
                    error=None, started_at=_now(), finished_at=None)
        try:
            path = fetch_official_gguf(model_id, config.MODELS_ROOT)
            log.info("官方 GGUF 下载完成：%s -> %s", model_id, path)
        except Exception as e:
            _set_status(model_id, status="failed", stage="download",
                        error=str(e), finished_at=_now())
            log.error("模型下载失败：%s -> %s", model_id, e)
            return

        # 官方 GGUF 仓库里已有量化文件 → 直接就绪
        meta = _MODELS_BY_ID[model_id]
        if config.discover_gguf(path, model_id=meta["gguf_repo"]):
            _set_status(model_id, status="ready", stage=None,
                        error=None, finished_at=_now())
            log.info("模型 %s 已就绪（官方 GGUF）", model_id)
            return

        # 兜底：目录里只有 safetensors 时尝试本地转换
        if config.has_safetensors(path, model_id=model_id):
            lcp = find_llamacpp(config.LLAMACPP_PATH or None)
            if auto_convert and lcp is not None:
                _run_convert(model_id, path, lcp)
                return
        _set_status(
            model_id, status="failed", stage="download",
            error="下载完成但未在仓库中找到可用 GGUF，请检查仓库内容或手动转换。",
            finished_at=_now(),
        )

    threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# llama.cpp 工具定位 + GGUF 转换（兜底路径，仅 safetensors 需要）
# ---------------------------------------------------------------------------
def find_llamacpp(explicit: str | None = None) -> Path | None:
    """查找 llama.cpp 仓库路径（需含 convert_hf_to_gguf.py），找不到返回 None。"""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(config.PROJECT_ROOT.parent / "llama.cpp")
    candidates.append(config.PROJECT_ROOT / "llama.cpp")
    for p in candidates:
        if p.exists() and (p / "convert_hf_to_gguf.py").exists():
            return p
    return None


def _find_quantize_bin(llamacpp: Path) -> Path | None:
    """定位 llama-quantize 可执行文件（兼容不同构建布局与平台）。"""
    exe = "llama-quantize.exe" if sys.platform == "win32" else "llama-quantize"
    for rel in (f"build/bin/{exe}", f"build/{exe}", exe, f"bin/{exe}"):
        p = llamacpp / rel
        if p.exists():
            return p
    return None


def convert_to_gguf(model_dir: Path, llamacpp: Path, model_id: str,
                    quant: str = "Q4_K_M") -> Path:
    """把 safetensors 模型转成 GGUF(INT4)，返回 GGUF 路径。失败抛 RuntimeError。"""
    convert_py = llamacpp / "convert_hf_to_gguf.py"
    quant_bin = _find_quantize_bin(llamacpp)
    if not convert_py.exists():
        raise RuntimeError(f"缺少 llama.cpp 转换脚本：{convert_py}")
    if quant_bin is None:
        raise RuntimeError(
            "缺少 llama-quantize（请使用含 Spark2_5 支持的 llama.cpp，2026-09-07 后版本）：\n"
            "  cmake -B build && cmake --build build --config Release\n"
            "或直接下载官方已量化 GGUF（推荐，无需转换）。"
        )
    # 输出文件名与 config.gguf_filename_hints 对齐
    base_name = model_id.split("/")[-1].lower().replace(".", "-")
    fp16 = model_dir / f"{base_name}-f16.gguf"
    out = model_dir / f"{base_name}-{quant.lower()}.gguf"
    if out.exists():
        log.info("GGUF 已存在，跳过转换：%s", out)
        return out
    log.info("[1/2] 转换 safetensors → GGUF(f16)：%s", model_dir)
    subprocess.run(
        [sys.executable, str(convert_py), str(model_dir), "--outfile", str(fp16)],
        check=True,
    )
    log.info("[2/2] 量化 → %s：%s", quant, out)
    subprocess.run([str(quant_bin), str(fp16), str(out), quant], check=True)
    try:
        fp16.unlink()   # 转换成功后删除体积巨大的 f16 中间产物
    except OSError:
        pass
    log.info("GGUF 转换完成：%s", out)
    return out


def start_conversion(model_id: str) -> None:
    """后台线程：把已下载的 safetensors 转成 GGUF（兜底路径）。"""
    st = get_task_status(model_id)
    if st["status"] in ("downloading", "converting"):
        return

    def _worker():
        local = check_model_local(model_id)
        if local["status"] == "ready":
            _set_status(model_id, status="ready", stage=None,
                        error=None, finished_at=_now())
            return
        if local["status"] == "missing" or local["dir"] is None:
            _set_status(model_id, status="missing", stage="convert",
                        error="本地未找到模型文件，请先下载", finished_at=_now())
            return
        model_dir = Path(local["dir"])
        lcp = find_llamacpp(config.LLAMACPP_PATH or None)
        if lcp is None:
            _set_status(
                model_id, status="downloaded", stage="convert",
                error=(
                    "已下载 safetensors，但未找到 llama.cpp 转换工具"
                    "（Spark2_5 架构需 2026-09-07 后版本）。\n"
                    "推荐改下载官方已量化 GGUF（删除本地 safetensors 后重新点下载），\n"
                    "或 clone 并编译最新 llama.cpp，在 .env 设置 MEMORA_LLAMACPP_PATH。"
                ),
                finished_at=_now(),
            )
            return
        _run_convert(model_id, model_dir, lcp)

    threading.Thread(target=_worker, daemon=True).start()


def _run_convert(model_id: str, model_dir: Path, lcp: Path) -> None:
    _set_status(model_id, status="converting", stage="convert",
                error=None, started_at=_now(), finished_at=None)
    try:
        convert_to_gguf(model_dir, lcp, model_id)
        _set_status(model_id, status="ready", stage=None,
                    error=None, finished_at=_now())
        log.info("模型 %s 已就绪（GGUF）", model_id)
    except Exception as e:  # noqa: BLE001
        _set_status(model_id, status="failed", stage="convert",
                    error=str(e), finished_at=_now())
        log.error("GGUF 转换失败：%s -> %s", model_id, e)


def ensure_gguf(
    model_id: str | None = None,
    model_dir: Path | None = None,
    quant: str = "Q4_K_M",
    llamacpp_path: str | None = None,
) -> Path:
    """确保模型有可用 GGUF，返回路径。

    流程：
      1. 已有 GGUF（官方仓库/本地转换/显式目录）→ 直接用
      2. 本地缺失：非离线模式下载官方 Q4_K_M GGUF（推荐，无需工具链）
      3. 只有 safetensors：用 llama.cpp 本地转换（兜底）
    model_dir 显式传入时（测试/脚本）直接使用，不做缓存布局解析。
    """
    model_id = model_id or config.get_selected_model_id()
    meta = _MODELS_BY_ID.get(model_id)

    # 1) 已有 GGUF
    if model_dir is not None:
        gguf = config.discover_gguf(model_dir, model_id=model_id)
        if gguf:
            log.info("已找到 GGUF，直接使用：%s", gguf)
            return gguf
    else:
        local = check_model_local(model_id)
        if local["status"] == "ready":
            log.info("已找到 GGUF，直接使用：%s", local["gguf"])
            return Path(local["gguf"])
        gguf = config.discover_gguf(model_id=model_id)
        if gguf:
            log.info("已找到 GGUF，直接使用：%s", gguf)
            return gguf

    # 2) 本地缺失 → 下载官方 GGUF（非离线）
    local = check_model_local(model_id) if model_dir is None else {"status": "missing"}
    if local["status"] == "missing":
        if model_dir is None:
            if config.ENFORCE_OFFLINE:
                repo = meta["gguf_repo"] if meta else model_id
                raise RuntimeError(
                    f"本地未找到模型 {model_id}，且当前为强制离线模式，无法下载。\n"
                    f"请在联网环境执行官方命令下载 Q4_K_M 量化版 GGUF：\n"
                    f"  from modelscope import snapshot_download\n"
                    f"  snapshot_download('{repo}', allow_file_pattern=['*Q4_K_M*'])\n"
                    f"缓存目录设置为 MEMORA_MODELS_ROOT 指向的目录；"
                    f"或在「模型管理」页关闭离线模式后下载。"
                )
            log.info("本地无模型，下载官方 Q4_K_M GGUF：%s", model_id)
            path = fetch_official_gguf(model_id, config.MODELS_ROOT)
            gguf = config.discover_gguf(path, model_id=meta["gguf_repo"] if meta else model_id)
            if gguf:
                return gguf
            raise RuntimeError(f"官方 GGUF 下载完成但未找到 .gguf 文件：{path}")
        # 显式传入 model_dir 但里面什么都没有
        raise RuntimeError(f"模型目录中未找到任何模型文件：{model_dir}")

    # 3) 只有 safetensors → 本地转换（兜底）
    model_dir = Path(local["dir"]) if model_dir is None else Path(model_dir)
    if not config.has_safetensors(model_dir, model_id=model_id):
        raise RuntimeError(f"模型目录中未找到 safetensors/GGUF：{model_dir}")
    lcp = find_llamacpp(llamacpp_path)
    if lcp is None:
        repo = meta["gguf_repo"] if meta else None
        tip = (
            f"或直接下载官方已量化 GGUF（推荐）：snapshot_download('{repo}', "
            f"allow_file_pattern=['*Q4_K_M*'])\n" if repo else ""
        )
        raise RuntimeError(
            "本地只有 safetensors，而 llama.cpp 只能加载 GGUF，需要转换工具。\n"
            "Spark2_5 架构需 2026-09-07 之后合入的 llama.cpp：\n"
            "  git clone https://github.com/ggml-org/llama.cpp.git ../llama.cpp\n"
            "  cd ../llama.cpp && cmake -B build && cmake --build build --config Release\n"
            f"{tip}"
            "也可在「模型管理」页点击「转换为 GGUF」（工具就位后）。"
        )
    return convert_to_gguf(model_dir, lcp, model_id, quant)


# ---------------------------------------------------------------------------
# ASR（whisper.cpp）模型获取
# ---------------------------------------------------------------------------
_ASR_REPO = "ggerganov/whisper.cpp"


def _asr_base_url() -> str:
    """whisper ggml 模型官方托管在 HuggingFace；国内经 HF_ENDPOINT（hf-mirror）。"""
    import os
    ep = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com").rstrip("/")
    return f"{ep}/{_ASR_REPO}/resolve/main"


def _http_download(url: str, target: Path) -> None:
    """流式下载到 .part 再原子改名，按 ~10% 打进度日志。"""
    import urllib.request
    tmp = target.with_name(target.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "memora"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        got = 0
        next_pct = 10
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if total and 100 * got / total >= next_pct:
                log.info("ASR 下载进度：%d%%", next_pct)
                next_pct += 10
    tmp.replace(target)


def ensure_asr_model(model_name: str) -> Path:
    """确保指定 whisper.cpp ASR 模型（ggml-*.bin）存在。

    有就用 → 强制离线模式报错并给手动指引 → 否则从 hf-mirror 直接下载
    （ggml 官方仓库在 HuggingFace；设 HF_ENDPOINT=https://hf-mirror.com 国内可达）。
    """
    target_dir = config.WHISPER_MODEL_DIR
    target = target_dir / model_name
    if target.exists():
        log.debug("ASR 模型已存在：%s", target)
        return target

    if config.ENFORCE_OFFLINE:
        raise RuntimeError(
            f"ASR 模型 {model_name} 缺失且处于强制离线模式，无法下载。\n"
            f"请在联网环境下载后手动放置到：{target}\n"
            f"下载地址：{_asr_base_url()}/{model_name}"
        )

    url = f"{_asr_base_url()}/{model_name}"
    target_dir.mkdir(parents=True, exist_ok=True)
    log.info("ASR 模型缺失，开始下载：%s", url)
    try:
        _http_download(url, target)
        log.info("ASR 模型已就绪：%s", target)
        return target
    except Exception as e:  # noqa: BLE001
        part = target.with_name(target.name + ".part")
        try:
            part.unlink()
        except OSError:
            pass
        raise RuntimeError(
            f"ASR 模型自动下载失败：{url}\n错误：{e}\n"
            f"请手动下载 {model_name} 并放置到：{target}"
        ) from e


def ensure_whisper_model() -> Path:
    """向后兼容：确保 ggml-base.bin。"""
    return ensure_asr_model("ggml-base.bin")