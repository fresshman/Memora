"""本地离线语音转写（Whisper.cpp base INT8）。

全部在本机完成，零云端请求。需要：
  1) 已编译的 whisper.cpp（build/bin/whisper-cli.exe，Windows）
  2) 模型文件 ggml-base.bin（约 140MB，INT8）
两者缺失时给出明确的本地准备指引，不 silently 失败。
"""
from __future__ import annotations

import subprocess
import urllib.request
from pathlib import Path

from .. import config
from ..log import get_logger

log = get_logger(__name__)

MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
MODEL_BIN = config.WHISPER_MODEL_DIR / "ggml-base.bin"


class WhisperNotReadyError(RuntimeError):
    pass


def ensure_model() -> Path:
    """确保 ggml-base.bin 存在：有就用 → 没有从 ModelScope 下载 → 失败报错。"""
    from ..model_fetch import ensure_whisper_model
    try:
        return ensure_whisper_model()
    except RuntimeError as e:
        raise WhisperNotReadyError(str(e)) from e


def transcribe(audio_path: str, *, language: str = "zh") -> str:
    """转写音频文件，返回纯文本。非 wav 格式需要系统已安装 ffmpeg 并在 PATH。"""
    log.info("开始语音转写：%s（语言=%s）", audio_path, language)
    if not config.WHISPER_BIN.exists():
        raise WhisperNotReadyError(
            "未找到 whisper.cpp 可执行文件。\n"
            f"期望路径：{config.WHISPER_BIN}\n"
            "请先按 README 编译 whisper.cpp（cmake 生成 build/bin/whisper-cli.exe）。"
        )
    model = ensure_model()

    cmd = [
        str(config.WHISPER_BIN),
        "-m", str(model),
        "-f", audio_path,
        "-l", language,
        "-nt",   # 不输出时间戳文本行（只要文字）
        "-np",   # 不输出进度
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise WhisperNotReadyError(
            f"whisper.cpp 执行失败（code={proc.returncode}）：\n{proc.stderr[-800:]}"
        )
    # whisper.cpp 默认把文字打印到 stdout
    return proc.stdout.strip()
