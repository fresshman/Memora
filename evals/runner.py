# -*- coding: utf-8 -*-
"""M2 评测编排：定义实验矩阵，逐格子进程执行，断点续跑，跑完生成 HTML 报告。

用法：
    python evals/runner.py --suite smoke       # 4 格快速验证（数分钟）
    python evals/runner.py --suite main        # 50 格主榜（4B，自动上下文）
    python evals/runner.py --suite ablation    # 18 格消融（full/compressed/1.7B）
    python evals/runner.py --suite all         # 主榜 + 消融
    python evals/runner.py --suite main --force   # 忽略已有结果重跑
结果落 evals/results/<run-tag>/，可随时中断，重跑自动跳过已完成格。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent

M4B = "XHToken/Spark-X2.5-4B"
M17 = "XHToken/Spark-X2.5-1.7B-GGUF"
ABLATION_LONG_IDS = [f"long_{i:03d}" for i in range(1, 7)]   # 6 个代表性超长会话


def load_case_ids() -> list[str]:
    ids = []
    with open(_HERE / "cases.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                ids.append(json.loads(line)["id"])
    return ids


def build_matrix(suite: str) -> tuple[str, list[dict]]:
    ids = load_case_ids()
    short_ids = [i for i in ids if i.startswith("short_")]
    long_ids = [i for i in ids if i.startswith("long_")]
    cells: list[dict] = []

    if suite in ("smoke",):
        return "smoke", [
            {"case": "short_001", "model": M4B, "mode": "auto"},
            {"case": "short_002", "model": M4B, "mode": "auto"},
            {"case": "long_001", "model": M4B, "mode": "auto"},
            {"case": "long_002", "model": M4B, "mode": "auto"},
        ]

    if suite in ("main", "all"):
        cells += [{"case": cid, "model": M4B, "mode": "auto"} for cid in ids]
    if suite in ("ablation", "all"):
        for cid in ABLATION_LONG_IDS:
            cells.append({"case": cid, "model": M4B, "mode": "full"})
            cells.append({"case": cid, "model": M4B, "mode": "compressed"})
            cells.append({"case": cid, "model": M17, "mode": "rag"})
    return "baseline", cells


def cell_path(run_tag: str, cell: dict) -> Path:
    from worker import model_tag
    mtag = model_tag(cell["model"])
    return _HERE / "results" / run_tag / f"{cell['case']}__{mtag}__{cell['mode']}.json"


def run(suite: str, force: bool, tag: str = "") -> None:
    default_tag, cells = build_matrix(suite)
    run_tag = tag or default_tag
    out_dir = _HERE / "results" / run_tag
    out_dir.mkdir(parents=True, exist_ok=True)

    todo = [c for c in cells if force or not cell_path(run_tag, c).exists()]
    skipped = len(cells) - len(todo)
    print(f"套件={suite} 标签={run_tag} 共 {len(cells)} 格，"
          f"已完成跳过 {skipped}，待跑 {len(todo)}")
    if not todo:
        print("全部已有结果，直接生成报告。")
        _report(run_tag)
        return

    t0 = time.time()
    done = fail = 0
    for i, cell in enumerate(todo, 1):
        print(f"\n[{i}/{len(todo)}] {cell['case']} {cell['model'].split('/')[-1]} {cell['mode']}")
        cmd = [sys.executable, str(_HERE / "worker.py"),
               "--case", cell["case"], "--model", cell["model"],
               "--mode", cell["mode"], "--run-tag", run_tag]
        try:
            proc = subprocess.run(cmd, cwd=str(_ROOT), timeout=1800)
            if proc.returncode == 0:
                done += 1
            else:
                fail += 1
        except subprocess.TimeoutExpired:
            fail += 1
            print("  超时（>1800s），记为失败并继续")
        elapsed = time.time() - t0
        print(f"  进度 {i}/{len(todo)}，成功 {done} 失败 {fail}，累计 {elapsed/60:.1f} 分钟")

    print(f"\n完成：成功 {done}，失败 {fail}，跳过 {skipped}，总耗时 {(time.time()-t0)/60:.1f} 分钟")
    _report(run_tag)


def _report(run_tag: str) -> None:
    try:
        from report import build_report
        path = build_report(run_tag)
        print(f"评测报告：{path}")
    except Exception as e:  # noqa: BLE001
        print(f"报告生成失败：{e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="smoke",
                    choices=["smoke", "main", "ablation", "all"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--tag", default="",
                    help="结果标签（子目录名），默认 baseline；A/B 实验可用如 prompt_v2")
    args = ap.parse_args()
    run(args.suite, args.force, args.tag)
