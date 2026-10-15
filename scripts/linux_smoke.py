"""Linux/macOS 跨平台最小冒烟（零第三方依赖，仅验证标准库即可运行的平台分支）。

在 WSL / 麒麟 / 统信 / macOS 上：
    cd <Memora 根>
    python3 scripts/linux_smoke.py
验证：平台识别、可执行后缀、路径解析、ffmpeg/llama-server 发现、数据目录可建。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memora import config  # noqa: E402

checks: list[tuple[str, bool, str]] = []


def expect(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, ok, detail))


def main() -> int:
    print("=" * 60)
    print(f"跨平台冒烟：{sys.platform}")
    print("=" * 60)

    # 1) 后缀在非 Windows 必须为空
    expect("可执行后缀", config._EXE_SUFFIX == ("" if sys.platform != "win32" else ".exe"),
           repr(config._EXE_SUFFIX))

    # 2) PROJECT_ROOT 解析正确、存在
    expect("PROJECT_ROOT", config.PROJECT_ROOT.is_dir(), str(config.PROJECT_ROOT))

    # 3) MODELS_ROOT 不写死盘符（应是相对项目或环境变量）
    expect("MODELS_ROOT", config.MODELS_ROOT.is_absolute(), str(config.MODELS_ROOT))

    # 4) ffmpeg 发现：Linux 装了系统包应能找到；找不到也不报错（降级 soundfile）
    ff = config.find_ffmpeg()
    expect("ffmpeg 发现", True, str(ff) if ff else "未找到（将用 soundfile 兜底）")

    # 5) 数据目录可在 Linux 创建（权限）
    try:
        config.ensure_dirs()
        expect("数据目录可建", config.DATA_DIR.is_dir(), str(config.DATA_DIR))
    except OSError as e:  # noqa: BLE001
        expect("数据目录可建", False, str(e))

    # 6) llama-server 发现（非 Windows 应查找无后缀名）
    try:
        from memora.backend.llamacpp_backend import find_llama_server
        ls = find_llama_server()
        expect("llama-server 发现", True, str(ls) if ls else "未找到（见平台二进制指引）")
    except Exception as e:  # noqa: BLE001
        expect("llama-server 发现", False, str(e))

    print()
    n_ok = 0
    for name, ok, detail in checks:
        n_ok += int(ok)
        print(f"[{'OK' if ok else 'FAIL'}] {name:<18} {detail}")
    print("-" * 60)
    print(f"{n_ok}/{len(checks)} 通过")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
