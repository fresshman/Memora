"""Memora 中文日志系统。

集中配置 logging，输出中文日志到控制台与本地文件（data/logs/memora.log）。
各模块用 get_logger(__name__) 获取 logger，文案统一简体中文。

设计：log 依赖 config（取数据目录），config 不依赖 log，无循环。
"""
from __future__ import annotations

import logging

from . import config

LOG_DIR = config.DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "memora.log"

_initialized = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """初始化全局日志配置，返回 memora 根 logger。重复调用幂等。"""
    global _initialized
    root = logging.getLogger("memora")
    if _initialized:
        return root

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root.setLevel(level)
    root.propagate = False

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s：%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    _initialized = True
    root.info("Memora 离线对话复盘工具 日志系统已初始化（日志文件：%s）", LOG_FILE)
    return root


def get_logger(name: str) -> logging.Logger:
    """获取子 logger，自动挂到 memora 命名空间下。"""
    if not _initialized:
        setup_logging()
    if name.startswith("memora"):
        return logging.getLogger(name)
    return logging.getLogger(f"memora.{name}")
