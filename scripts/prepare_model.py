"""一次性模型准备（命令行版，与 Web「模型管理」页同一套逻辑）。

默认策略（推荐）：直接从 ModelScope 下载官方已量化的 Q4_K_M GGUF，
单文件、免 torch、免编译 llama.cpp，下载完成即可推理：

    python scripts/prepare_model.py
    python scripts/prepare_model.py --model XHToken/Spark-X2.5-1.7B

等价官方命令：
    from modelscope import snapshot_download
    snapshot_download('XHToken/Spark-X2.5-4B-GGUF', allow_file_pattern=['*Q4_K_M*'])

兜底策略（仅当你需要从 safetensors 自行转换时）：
    python scripts/prepare_model.py --from-safetensors
    需本机有含 Spark2_5 支持的 llama.cpp（2026-09-07 之后合入），
    可用 --llamacpp 指定，或放到项目同级 ../llama.cpp。

联网下载阶段需设置 MEMORA_ENFORCE_OFFLINE=0。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许直接以 `python scripts/prepare_model.py` 运行：把项目根加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memora import config
from memora.model_fetch import (
    check_model_local,
    fetch_official_gguf,
    ensure_gguf,
    get_model_meta,
    MODEL_IDS,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="准备 Memora 端侧模型（默认下载官方 Q4_K_M GGUF）")
    ap.add_argument("--model", default=config.DEFAULT_MODEL_ID,
                    choices=MODEL_IDS, help="模型 ID，默认 4B")
    ap.add_argument("--from-safetensors", action="store_true",
                    help="走 safetensors 下载 + 本地 llama.cpp 转换的兜底链路")
    ap.add_argument("--llamacpp", default=None, help="llama.cpp 仓库路径（仅转换链路需要）")
    ap.add_argument("--quant", default="Q4_K_M", help="量化档位，默认 Q4_K_M（仅转换链路）")
    args = ap.parse_args()

    meta = get_model_meta(args.model)
    local = check_model_local(args.model)
    if local["status"] == "ready":
        print(f"模型已就绪：{local['gguf']}")
        return

    try:
        if args.from_safetensors:
            print(f"[兜底链路] 下载 safetensors 并本地转换 {args.model} …")
            gguf = ensure_gguf(
                model_id=args.model,
                quant=args.quant,
                llamacpp_path=args.llamacpp,
            )
        else:
            if config.ENFORCE_OFFLINE:
                sys.exit(
                    "当前为强制离线模式（MEMORA_ENFORCE_OFFLINE=1），无法下载。\n"
                    "请在联网安装阶段设置 MEMORA_ENFORCE_OFFLINE=0 后重试，或在联网机器执行：\n"
                    "  from modelscope import snapshot_download\n"
                    f"  snapshot_download('{meta['gguf_repo']}', allow_file_pattern=['*Q4_K_M*'])"
                )
            print(f"[默认链路] 从 ModelScope 下载官方 GGUF：{meta['gguf_repo']}（{meta['gguf_filename']}）")
            gguf = fetch_official_gguf(args.model)
    except RuntimeError as e:
        sys.exit(str(e))

    print(f"完成。{args.model} 的 GGUF 已就绪：{gguf}")
    print("可在「模型管理」页选择该模型，或调用 POST /api/models/select。")


if __name__ == "__main__":
    main()
