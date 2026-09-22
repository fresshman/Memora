# -*- coding: utf-8 -*-
"""M2 评测单格执行器（在独立子进程中运行，模型/服务进程随退出释放）。

用法：
    python evals/worker.py --case long_001 --model XHToken/Spark-X2.5-4B \
        --mode auto --run-tag baseline
产物：evals/results/<run-tag>/<case>__<modeltag>__<mode>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))
os.environ.setdefault("MEMORA_TEMP", "0")  # eval: greedy, reproducible


def model_tag(model_repo: str) -> str:
    tail = model_repo.rstrip("/").split("/")[-1].lower()
    if "1.7" in tail:
        return "1.7b"
    if "4b" in tail:
        return "4b"
    return tail.replace("spark-x2.5-", "")


def load_case(case_id: str) -> dict:
    with open(_HERE / "cases.jsonl", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if c["id"] == case_id:
                return c
    raise KeyError(f"未找到评测用例：{case_id}")


def to_conversation(case: dict):
    from memora.parsers.base import Conversation, Message
    msgs = [Message(speaker=m["speaker"], time=m["time"], text=m["text"])
            for m in case["messages"]]
    return Conversation(source="eval", title=case["title"], messages=msgs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--mode", default="auto",
                    choices=["auto", "full", "rag", "compressed"])
    ap.add_argument("--run-tag", default="baseline")
    args = ap.parse_args()

    # 必须在导入 config 前指定模型
    os.environ["MEMORA_MODEL_ID"] = args.model
    # 评测默认离线（模型应已就位）
    os.environ.setdefault("MEMORA_ENFORCE_OFFLINE", "1")

    out_dir = _HERE / "results" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    mtag = model_tag(args.model)
    out_path = out_dir / f"{args.case}__{mtag}__{args.mode}.json"

    result = {
        "case_id": args.case, "model": args.model, "model_tag": mtag,
        "mode": args.mode, "is_long": None, "char_count": None,
        "context_mode_review": None, "context_mode_qa": None,
        "review_s": None, "qa_s": None, "error": None,
        "report": None, "answers": [], "card": None,
    }
    t_start = time.time()
    try:
        case = load_case(args.case)
        result["is_long"] = case["is_long"]
        result["char_count"] = case["char_count"]
        conv = to_conversation(case)

        from memora.agent import MemoraAgent
        agent = MemoraAgent.from_config()
        if args.mode != "auto":
            agent.force_context_mode = args.mode

        t0 = time.time()
        report = agent.review(conv)
        result["review_s"] = round(time.time() - t0, 1)
        result["context_mode_review"] = agent.last_context_mode
        result["report"] = report

        # 两个探针：一个可答（超长 case 锚定开头）+ 一个无答案（测幻觉）
        probes = [case.get("probe_qa"), case.get("probe_unanswerable")]
        probes = [p for p in probes if p]
        answers = []
        for pq in probes:
            t0 = time.time()
            ans = agent.answer(conv, pq["q"])
            answers.append({"q": pq["q"], "answerable": pq.get("answerable", True),
                            "answer": ans, "s": round(time.time() - t0, 1)})
        result["answers"] = answers
        result["context_mode_qa"] = agent.last_context_mode
        result["qa_s"] = round(sum(a["s"] for a in answers), 1)

        # 评分（仅对实际追问的两个问题评 QA）
        from metrics import score_case
        gold = dict(case["gold"])
        gold["qa"] = [{k: p.get(k) for k in ("q", "answerable", "all", "any", "hedge")}
                      for p in probes]
        result["card"] = score_case(report, [a["answer"] for a in answers], gold)
        try:
            agent.close()
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()[-2000:]

    result["total_s"] = round(time.time() - t_start, 1)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    if result["error"]:
        print(f"[FAIL] {args.case} {mtag} {args.mode}: {result['error']}")
        return 1
    card = result["card"]
    print(f"[OK] {args.case} {mtag} {args.mode} "
          f"({result['context_mode_review']}) "
          f"todoR={card['todos']['recall']} riskR={card['risks']['recall']} "
          f"decR={card['decisions']['recall']} "
          f"QA={card['qa']['evidence_recall']} hall={card['qa']['hallucination_rate']} "
          f"{result['total_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
