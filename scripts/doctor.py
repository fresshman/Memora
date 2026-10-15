"""Memora 环境自检（doctor）：逐项检查离线部署所需条件并给出修复指引。

用法：
    python scripts/doctor.py
退出码：全部关键项通过为 0，否则为 1（语音等可选项不影响退出码）。
"""
from __future__ import annotations

import importlib
import platform
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memora import config, model_fetch  # noqa: E402
from memora.backend.llamacpp_backend import find_llama_server  # noqa: E402

OK = "通过"
WARN = "警告"
FAIL = "缺失"

results: list[tuple[str, str, str, str]] = []   # (级别, 项目, 现状, 建议)


def check(level: str, item: str, status: str, advice: str = "") -> None:
    results.append((level, item, status, advice))


def _linux_distro() -> str:
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def _llama_pkg_tag(system: str, machine: str) -> str:
    if system == "Windows":
        return "llama-b*-bin-win-cpu-x64.zip"
    if system == "Darwin":
        return ("llama-b*-bin-macos-arm64.zip" if machine == "arm64"
                else "llama-b*-bin-macos-x64.zip")
    if machine in ("aarch64", "arm64"):
        return "llama-b*-bin-ubuntu-arm64.zip"
    return "llama-b*-bin-ubuntu-x64.zip"


def main() -> int:
    print("=" * 68)
    print("Memora 环境自检" + ("（强制离线模式）" if config.ENFORCE_OFFLINE else "（允许联网下载）"))
    print("=" * 68)

    # 0) 平台 / 架构（端侧关键，决定该用哪个 llama.cpp 二进制）
    sysname = platform.system()
    machine = platform.machine()
    distro = _linux_distro() if sysname == "Linux" else ""
    print(f"操作系统：{sysname} {distro}".rstrip())
    print(f"体系架构：{machine}（x86_64 含海光/兆芯；aarch64 为 ARM 端侧）")
    print(f"匹配二进制：{_llama_pkg_tag(sysname, machine)}")
    print("-" * 68)

    # 1) Python 版本
    pyver = platform.python_version()
    ok = sys.version_info >= (3, 10)
    check(OK if ok else FAIL, "Python 版本", pyver + ("（≥3.10）" if ok else "，需 3.10+"),
          "" if ok else "请升级到 Python 3.10+")

    # 2) 核心依赖
    for mod, pip_name in (
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn[standard]"),
        ("langchain_core", "langchain-core"),
        ("langchain_openai", "langchain-openai"),
        ("modelscope", "modelscope"),
        ("cryptography", "cryptography"),
        ("pandas", "pandas"),
        ("bs4", "beautifulsoup4"),
        ("dotenv", "python-dotenv"),
        ("reportlab", "reportlab"),
        ("faiss", "faiss-cpu"),
        ("numpy", "numpy"),
        ("chardet", "chardet"),
        ("scipy", "scipy"),
        ("sklearn", "scikit-learn"),
        ("soundfile", "soundfile"),
        ("pywhispercpp", "pywhispercpp"),
        ("speakeronnx", "speakeronnx"),
        ("onnxruntime", "onnxruntime"),
    ):
        try:
            m = importlib.import_module(mod)
            check(OK, f"依赖 {pip_name}", getattr(m, "__version__", "已安装"))
        except ImportError:
            check(FAIL, f"依赖 {pip_name}", "未安装", f"pip install {pip_name}")

    # 3) llama-server 推理引擎
    exe = find_llama_server()
    if exe is not None:
        check(OK, "llama-server 推理引擎", str(exe))
    else:
        check(FAIL, "llama-server 推理引擎", "未找到",
              "下载含 Spark2_5 的 llama.cpp 每日构建 zip，解压到 tools/llamacpp/bin；"
              "或设置 MEMORA_LLAMASERVER_PATH")

    # 4) 推荐模型状态
    for mid in model_fetch.MODEL_IDS:
        st = model_fetch.check_model_local(mid)
        name = mid.split("/")[-1]
        if st["status"] == "ready":
            gguf = Path(st["gguf"])
            size_gb = gguf.stat().st_size / 1024**3
            check(OK, f"模型 {name}", f"就绪（{gguf.name}，{size_gb:.2f}GB）")
        elif st["status"] == "downloaded":
            check(WARN, f"模型 {name}", "仅有 safetensors，需 GGUF",
                  "模型管理页转换，或删除后改下载官方 GGUF")
        else:
            advice = ("模型管理页点「下载此模型」（需 MEMORA_ENFORCE_OFFLINE=0），"
                      "或运行 python scripts/prepare_model.py")
            check(WARN if config.ENFORCE_OFFLINE else WARN, f"模型 {name}", "未下载", advice)


    # 4b) RAG 检索增强（超长对话）：faiss + 本地 embedding 模型
    try:
        importlib.import_module("faiss")
        faiss_ok = True
    except ImportError:
        faiss_ok = False
        check(WARN, "RAG 向量库 faiss", "未安装", "pip install faiss-cpu")
    if faiss_ok and config.RAG_ENABLE:
        emb = config.discover_embedding_gguf()
        if emb is not None:
            mb = emb.stat().st_size / 1024**2
            check(OK, "RAG embedding 模型", f"就绪（{emb.name}，{mb:.0f}MB）")
        else:
            check(WARN, "RAG embedding 模型",
                  "未下载（超长对话将降级为规则压缩，仍可用但检索质量下降）",
                  f"模型管理页下载，或 snapshot_download('{config.EMBED_REPO}') "
                  f"（默认取 {config.EMBED_FILE_PATTERN} 量化档）")
    elif not config.RAG_ENABLE:
        check(WARN, "RAG 检索增强", "已关闭（MEMORA_RAG_ENABLE=0），超长对话将截断最旧记录")

    # 4c) PII 本地脱敏（端侧隐私）
    if config.PII_REDACT_ENABLE:
        names = "，含人名角色化" if config.PII_REDACT_NAMES else ""
        check(OK, "PII 本地脱敏",
              f"已开启（手机/证件/银行卡/邮箱/IP/车牌/护照{names}，映射仅存内存不落盘）")
    else:
        check(WARN, "PII 本地脱敏",
              "已关闭（MEMORA_PII_REDACT=0），敏感信息将以明文送入模型与本地索引")

    # 5) 模型根目录可写、磁盘空间
    try:
        config.MODELS_ROOT.mkdir(parents=True, exist_ok=True)
        free_gb = shutil.disk_usage(config.MODELS_ROOT).free / 1024**3
        check(OK if free_gb >= 6 else WARN, "模型盘剩余空间",
              f"{free_gb:.1f}GB（目录 {config.MODELS_ROOT}）",
              "" if free_gb >= 6 else "建议预留 6GB 以上（双模型 Q4 GGUF）")
    except OSError as e:
        check(FAIL, "模型根目录", f"不可写：{e}", "检查 MEMORA_MODELS_ROOT 路径权限")

    # 6) 数据目录
    try:
        config.ensure_dirs()
        check(OK, "本地数据目录", str(config.DATA_DIR))
    except OSError as e:
        check(FAIL, "本地数据目录", f"创建失败：{e}")

    # 7) 语音会议链路（可选；不影响文字复盘）
    ffmpeg = config.find_ffmpeg()
    check(OK if ffmpeg else WARN, "语音 ffmpeg（音频解码）",
          str(ffmpeg) if ffmpeg else "未安装（非 WAV 音频无法解码）",
          "" if ffmpeg else "下载 ffmpeg 静态构建解压到 tools/ffmpeg/bin，"
                            "或设置 MEMORA_FFMPEG_PATH")
    try:
        importlib.import_module("pywhispercpp")
        pwc = True
    except ImportError:
        pwc = False
    check(OK if pwc else WARN, "语音 pywhispercpp（转写引擎）",
          "已安装（自带 libwhisper）" if pwc else "未安装",
          "" if pwc else "pip install pywhispercpp")
    try:
        importlib.import_module("speakeronnx")
        spk = True
    except ImportError:
        spk = False
    check(OK if spk else WARN, "语音 speakeronnx（说话人识别）",
          "已安装（CAM++ 神经声纹）" if spk else "未安装（将降级 MFCC）",
          "" if spk else "pip install speakeronnx onnxruntime")
    asr = config.find_whisper_model(config.WHISPER_DEFAULT_MODEL)
    check(OK if asr else WARN,
          f"语音 ASR 模型 {config.WHISPER_DEFAULT_MODEL}",
          str(asr) if asr else "未下载",
          "" if asr else "语音页点下载（hf-mirror）或 python -m memora.model_fetch --asr，"
                         "设置 MEMORA_ASR_MODEL 可切换 small/base/turbo 档位")

    # 8) 推理参数合理性
    note = f"n_ctx={config.LLAMACPP_N_CTX}, n_gpu={config.LLAMACPP_N_GPU_LAYERS}, KV={config.LLAMACPP_KV_QUANT}"
    check(OK, "推理参数", note)
    if config.LLAMACPP_N_CTX > 131072 and config.LLAMACPP_KV_QUANT == "f16":
        check(WARN, "内存风险", "超大上下文 + f16 KV，8GB 机器可能爆内存",
              "建议 MEMORA_KV_QUANT=q8_0 或调小 MEMORA_N_CTX")

    # 输出
    print()
    for level, item, status, advice in results:
        mark = {"通过": "[OK]  ", "警告": "[WARN]", "缺失": "[FAIL]"}[level]
        print(f"{mark} {item:<26} {status}")
        if advice:
            print(f"       修复建议：{advice}")
    n_fail = sum(1 for r in results if r[0] == FAIL)
    n_warn = sum(1 for r in results if r[0] == WARN)
    print("-" * 68)
    print(f"合计：{len(results)} 项，缺失 {n_fail}，警告 {n_warn}")
    if n_fail:
        print("结论：存在必须修复的缺失项，请按上述建议处理后再启动。")
        return 1
    print("结论：关键条件齐备，可以启动（python -m server.main；前端 cd web && npm run dev）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
