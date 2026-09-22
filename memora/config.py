"""Memora 集中配置。

所有路径、后端选择、推理参数、存储路径都集中在这里，方便比赛演示时一处修改。
离线安全红线：ENFORCE_OFFLINE=1（默认）时，本程序任何模块都不得发起对外网络请求。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent          # .../Memora

# 从 .env 加载配置（找不到 .env 或未装 python-dotenv 时静默跳过，沿用系统环境变量）
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

# 模型根目录（ModelScope cache_dir）：snapshot_download 会在其下生成
#   models/{组织}--{模型名}/snapshots/{版本}/...
# 优先环境变量，否则默认放到项目同级 ../root/models（不写死盘符）
MODELS_ROOT = Path(
    os.environ.get("MEMORA_MODELS_ROOT", str(PROJECT_ROOT.parent / "root" / "models"))
)

# 推荐模型（与 model_fetch.AVAILABLE_MODELS 的 id 保持一致）
DEFAULT_MODEL_ID = "XHToken/Spark-X2.5-4B"
MODEL_IDS = ["XHToken/Spark-X2.5-4B", "XHToken/Spark-X2.5-1.7B"]

# 本地数据（导入记录 + 加密产出）全部落在本项目 data/ 下
DATA_DIR = PROJECT_ROOT / "data"
VAULT_DIR = DATA_DIR / "vault"        # 加密碎片
VAULT_KEY_FILE = DATA_DIR / "vault.key"
VAULT_INDEX = DATA_DIR / "vault_index.json"
SETTINGS_FILE = DATA_DIR / "settings.json"   # 用户偏好（当前选中模型等）

# Whisper.cpp（语音转写，可选模块）
WHISPER_CPP_DIR = PROJECT_ROOT / "whisper.cpp"
_EXE_SUFFIX = ".exe" if sys.platform == "win32" else ""
WHISPER_BIN = WHISPER_CPP_DIR / "build" / "bin" / f"whisper-cli{_EXE_SUFFIX}"
WHISPER_MODEL_DIR = WHISPER_CPP_DIR / "models"
# Whisper 模型的 ModelScope 仓库 ID（优先从 ModelScope 下载；失败则报错附手动指引）
WHISPER_MODELSCOPE_ID = os.environ.get("MEMORA_WHISPER_MS_ID", "AI-ModelScope/whisper.cpp")

# ---------------------------------------------------------------------------
# 推理后端选择
#   "llamacpp" -> 默认，进程内推理，零外部依赖，匹配 8GB 内存
#   "sglang"   -> 可选，连接本机已启动的 sglang server（OpenAI 兼容端点）
# ---------------------------------------------------------------------------
INFERENCE_BACKEND = os.environ.get("MEMORA_BACKEND", "llamacpp").lower()

# SGLang server 配置（仅 server 模式使用）
SGLANG_BASE_URL = os.environ.get("MEMORA_SGLANG_URL", "http://127.0.0.1:30000/v1")
SGLANG_API_KEY = os.environ.get("MEMORA_SGLANG_KEY", "EMPTY")
SGLANG_MODEL_NAME = os.environ.get("MEMORA_SGLANG_MODEL", "")  # 空=跟随选中模型

# ---------------------------------------------------------------------------
# llama.cpp 推理参数
#   n_ctx：上下文窗口。8GB 内存机器默认 32768 + KV q8 量化（约 3.5GB 总占用）；
#          高端机器可调大（65536 / 196608 / 1048576），但 fp16 KV 下
#          196608 仅 KV 缓存就约 6.75GB，8GB 机器会爆内存。
#   n_gpu_layers：0 = 全 CPU（无显卡也能跑）；有显卡填层数可加速，-1 = 全部上 GPU。
#   kv_quant：KV cache 量化（q8_0 / q4_0 / f16），端侧建议 q8_0。
# ---------------------------------------------------------------------------
LLAMACPP_N_CTX = int(os.environ.get("MEMORA_N_CTX", "32768"))
LLAMACPP_N_GPU_LAYERS = int(os.environ.get("MEMORA_N_GPU", "0"))
LLAMACPP_N_THREADS = int(os.environ.get("MEMORA_THREADS", "0"))  # 0 = 自动
LLAMACPP_KV_QUANT = os.environ.get("MEMORA_KV_QUANT", "q8_0").lower()
LLAMACPP_VERBOSE = os.environ.get("MEMORA_LLAMACPP_VERBOSE", "0") in ("1", "true", "yes")
# llama.cpp 仓库路径（safetensors→GGUF 转换用）；空则自动找项目同级 ../llama.cpp
LLAMACPP_PATH = os.environ.get("MEMORA_LLAMACPP_PATH", "")
# 默认推理后端通过本机 llama-server 子进程提供 OpenAI 兼容服务：
#   - 免编译、免 Python 绑定（PyPI 的 llama-cpp-python 可能尚未合入 Spark2_5）
#   - 可直接随离线包分发官方每日构建二进制（含 llama-server 的 zip 解压即可）
# 显式指定 llama-server 可执行文件路径；空则按 LLAMACPP_PATH / 同级 llama.cpp /
# 项目内 tools/llamacpp/bin 自动查找
LLAMACPP_SERVER_PATH = os.environ.get("MEMORA_LLAMASERVER_PATH", "")
# server 启动（模型加载）超时秒数，CPU + 4B 一般 10~60s
SERVER_BOOT_TIMEOUT = int(os.environ.get("MEMORA_SERVER_BOOT_TIMEOUT", "300"))
# server 固定端口；0 = 每次自动挑选空闲端口（默认）
LLAMACPP_SERVER_PORT = int(os.environ.get("MEMORA_LLAMASERVER_PORT", "0"))

# 生成参数
TEMPERATURE = float(os.environ.get("MEMORA_TEMP", "0.3"))
MAX_TOKENS_REVIEW = int(os.environ.get("MEMORA_MAX_REVIEW", "4096"))
MAX_TOKENS_QA = int(os.environ.get("MEMORA_MAX_QA", "1024"))

# 喂给模型的最大输入字符数。中文约 1 字 ≈ 1.2-1.5 token，按 1.35 估算，
# 并为 prompt 模板与输出预留 (MAX_TOKENS_REVIEW + 1536) token。
# 可由 MEMORA_MAX_INPUT_CHARS 覆盖；n_ctx 调大时此处默认值自动跟随。
MAX_INPUT_CHARS = int(os.environ.get(
    "MEMORA_MAX_INPUT_CHARS",
    str(max(8000, int((LLAMACPP_N_CTX - MAX_TOKENS_REVIEW - 1536) / 1.35))),
))


# ---------------------------------------------------------------------------
# RAG 检索增强（超长对话）
#   短对话（<= RAG_TRIGGER_CHARS）仍全量直喂，零损耗；
#   超长对话启用本地 embedding + faiss 混合检索，避免旧版直接砍掉最旧记录。
# ---------------------------------------------------------------------------
RAG_ENABLE = os.environ.get("MEMORA_RAG_ENABLE", "1").lower() in ("1", "true", "yes", "on")
# embedding 模型（ModelScope GGUF 仓库，免转换；bge-m3 中文检索，Q4 约 438MB）
EMBED_REPO = os.environ.get("MEMORA_EMBED_REPO", "gpustack/bge-m3-GGUF")
EMBED_FILE_PATTERN = os.environ.get("MEMORA_EMBED_PATTERN", "*Q4_K_M*")
EMBED_CTX = int(os.environ.get("MEMORA_EMBED_CTX", "8192"))
EMBED_DIM = int(os.environ.get("MEMORA_EMBED_DIM", "1024"))
# 分块：每块字符预算（约 512 token / 1.35）、相邻块回带消息数、话题切分时间间隔（分钟）
RAG_CHUNK_CHARS = int(os.environ.get("MEMORA_RAG_CHUNK_CHARS", "420"))
RAG_CHUNK_OVERLAP = int(os.environ.get("MEMORA_RAG_CHUNK_OVERLAP", "2"))
RAG_TOPIC_GAP_MIN = int(os.environ.get("MEMORA_RAG_GAP_MIN", "30"))
# 检索：每路 query 召回数、合并后送入模型的块上限
RAG_FACET_TOPK = int(os.environ.get("MEMORA_RAG_FACET_TOPK", "6"))
RAG_TOP_K = int(os.environ.get("MEMORA_RAG_TOPK", "20"))
# 超过该字符数才启用 RAG（默认放得下就全量；调小可用于演示/测试）
# RAG 检索后送入模型的上下文目标字符数（收紧以聚焦关键信息、降低 CPU 耗时）
RAG_CONTEXT_CHARS = int(os.environ.get("MEMORA_RAG_CONTEXT_CHARS", "7600"))
RAG_TRIGGER_CHARS = int(
    os.environ.get("MEMORA_RAG_TRIGGER_CHARS", str(MAX_INPUT_CHARS)))
# 向量索引持久化目录
RAG_INDEX_DIR = DATA_DIR / "index"

# ---------------------------------------------------------------------------
# PII 本地脱敏（端侧隐私）
#   解析后、送入模型 / 建立向量索引前，对手机 / 身份证 / 银行卡 / 邮箱 /
#   IPv4 / 车牌 / 护照等强模式 PII 占位脱敏，发言人统一角色化为成员A/B…。
#   占位与角色映射仅保存在会话内存中、不落盘，重启即销毁（最小留存）。
# ---------------------------------------------------------------------------
PII_REDACT_ENABLE = os.environ.get("MEMORA_PII_REDACT", "1").lower() in ("1", "true", "yes", "on")
PII_REDACT_NAMES = os.environ.get("MEMORA_PII_REDACT_NAMES", "1").lower() in ("1", "true", "yes", "on")

# 离线安全红线
#   True  -> 模型缺失时不联网下载，只报错指引（比赛演示断网场景）
#   False -> 模型缺失时允许从 ModelScope 下载（安装阶段用网）
ENFORCE_OFFLINE = os.environ.get("MEMORA_ENFORCE_OFFLINE", "1").lower() in ("1", "true", "yes", "on")
if ENFORCE_OFFLINE:
    # 同步约束 huggingface_hub / transformers / modelscope 的在线行为
    for _k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "MODELSCOPE_OFFLINE"):
        os.environ.setdefault(_k, "1")

# GGUF 文件名候选（小写匹配），按模型名动态生成，另保留通用兜底
_GENERIC_GGUF_HINTS = ["model-q4_k_m.gguf", "model.gguf"]


def gguf_filename_hints(model_id: str) -> list[str]:
    """模型对应的 GGUF 约定文件名。

    覆盖三种来源：
      - 官方 ModelScope GGUF 仓库：Spark-X2.5-4B-Q4_K_M.gguf
      - 本项目转换脚本输出：    spark-x2-5-4b-q4_k_m.gguf
      - 通用兜底
    """
    raw = model_id.split("/")[-1]                 # Spark-X2.5-4B / Spark-X2.5-4B-GGUF
    name = raw.lower().replace(".", "-")          # spark-x2-5-4b / spark-x2-5-4b-gguf
    stem = name.removesuffix("-gguf")
    official = raw.removesuffix("-GGUF")          # Spark-X2.5-4B
    return [
        f"{official}-Q4_K_M.gguf",                # 官方 GGUF 仓库命名
        f"{official}-Q8_0.gguf",
        f"{official}.gguf",                       # 官方 BF16 原版
        f"{stem}-q4_k_m.gguf",                    # 本项目转换命名
        f"{stem}_q4_k_m.gguf",
        f"{stem}.gguf",
        *_GENERIC_GGUF_HINTS,
    ]


# ---------------------------------------------------------------------------
# ModelScope 缓存布局解析
#   snapshot_download(cache_dir=MODELS_ROOT) 实际落盘：
#     MODELS_ROOT/models/{Org}--{Name}/snapshots/{rev}/config.json ...
#   同时兼容：旧扁平布局 MODELS_ROOT/{Org}/{Name}、用户默认缓存 ~/.cache/modelscope
# ---------------------------------------------------------------------------
def _cache_repo_dirs(model_id: str) -> list[Path]:
    repo = model_id.replace("/", "--")
    org, name = model_id.split("/", 1)
    home_cache = Path.home() / ".cache" / "modelscope" / "hub" / "models" / repo
    return [
        MODELS_ROOT / "models" / repo,        # ModelScope cache_dir 布局（当前默认）
        MODELS_ROOT / org / name,             # 旧扁平布局
        MODELS_ROOT / repo,                   # 直接平铺
        home_cache,                           # 用户主目录默认缓存
    ]


def find_model_dir(model_id: str, repo_id: str | None = None) -> Path | None:
    """返回模型实际所在目录（snapshot 版本目录或平铺目录），找不到返回 None。

    repo_id 可指定实际要查找的仓库（如模型 id 为 XHToken/Spark-X2.5-4B，
    但 GGUF 在独立仓库 XHToken/Spark-X2.5-4B-GGUF）。
    """
    for base in _cache_repo_dirs(repo_id or model_id):
        snap = base / "snapshots"
        if snap.is_dir():
            kids = sorted(
                (p for p in snap.iterdir() if p.is_dir()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for k in kids:
                if (k / "config.json").exists() or any(k.glob("*.gguf")):
                    return k
        if (base / "config.json").exists() or any(base.glob("*.gguf")):
            return base
    return None


def discover_gguf(model_dir: Path | str | None = None, model_id: str | None = None) -> Path | None:
    """在模型目录里查找已转换好的 GGUF。

    llama.cpp 只能加载 GGUF；若下载到的是 HuggingFace safetensors，
    需先用 scripts/prepare_model.py 转换为 GGUF + INT4 量化。
    """
    if model_dir is None:
        model_dir = find_model_dir(model_id or DEFAULT_MODEL_ID)
        if model_dir is None:
            return None
    model_dir = Path(model_dir)
    if not model_dir.exists():
        return None
    # 1) 优先按约定文件名
    hints = gguf_filename_hints(model_id or DEFAULT_MODEL_ID)
    for hint in hints:
        p = model_dir / hint
        if p.exists():
            return p
    # 2) 退而求其次：目录内任意 .gguf（含子目录一层）
    matches = sorted(model_dir.glob("*.gguf")) or sorted(model_dir.glob("*/*.gguf"))
    if matches:
        return matches[0]
    return None


def discover_embedding_gguf() -> Path | None:
    """查找本地 embedding GGUF（bge-m3），找不到返回 None（RAG 降级为规则压缩）。"""
    model_dir = find_model_dir(EMBED_REPO)
    if model_dir is None:
        return None
    import fnmatch
    # 优先配置的量化档（默认 Q4_K_M）
    for pat in (EMBED_FILE_PATTERN, "*.gguf"):
        hits = [q for q in model_dir.rglob("*.gguf")
                if fnmatch.fnmatch(q.name, pat) and ".incomplete" not in q.name]
        if hits:
            return sorted(hits, key=lambda q: q.stat().st_size)[-1]                 if pat == "*.gguf" else hits[0]
    return None


def has_safetensors(model_dir: Path | str | None = None, model_id: str | None = None) -> bool:
    """判断模型目录是否已完整下载权重（safetensors/pytorch bin）。

    注意：ModelScope 下载中的临时文件为 *.safetensors.incomplete，
    不能仅凭 config.json 判定（小文件先于权重落盘）。
    """
    if model_dir is None:
        model_dir = find_model_dir(model_id or DEFAULT_MODEL_ID)
        if model_dir is None:
            return False
    model_dir = Path(model_dir)
    if not model_dir.exists():
        return False
    # ModelScope 下载中会留下 *.incomplete（含 .safetensors.incomplete），
    # 只要存在未完成分片就不能视为权重完整（兼容子目录一层）。
    incomplete = list(model_dir.rglob("*.incomplete"))
    if incomplete:
        return False
    return (
        any(model_dir.glob("*.safetensors"))
        or any(model_dir.glob("*.bin"))
    )


# ---------------------------------------------------------------------------
# 用户偏好（当前选中模型）—— data/settings.json
# ---------------------------------------------------------------------------
def get_selected_model_id() -> str:
    """读取用户选中的模型 id；损坏/缺失时回落到默认模型或环境变量。"""
    env_id = os.environ.get("MEMORA_MODEL_ID")
    if env_id:
        return env_id
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            mid = data.get("selected_model")
            if mid:
                return mid
    except Exception:
        pass
    return DEFAULT_MODEL_ID


def set_selected_model_id(model_id: str) -> None:
    """持久化用户选中的模型 id。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["selected_model"] = model_id
    SETTINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def ensure_dirs() -> None:
    """创建本地数据目录（首次运行调用）。"""
    for d in (DATA_DIR, VAULT_DIR, WHISPER_MODEL_DIR):
        d.mkdir(parents=True, exist_ok=True)
