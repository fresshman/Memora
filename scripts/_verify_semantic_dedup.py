"""真机验证：SemanticMerger 在真实 Spark-X2.5 上是否稳定输出 JSON 并正确判同。

仅加载推理后端，不启 FastAPI；验证完释放模型。
用法：
  $env:PYTHONPATH='项目根'
  python scripts/_verify_semantic_dedup.py
"""
from __future__ import annotations

import sys

from memora.backend import build_backend
from memora.backend.base import build_chat_prompt, strip_thinking
from memora.action_items import (
    SemanticMerger,
    _DEDUP_SYSTEM,
    _DEDUP_USER_TMPL,
    titles_match_by_text,
)

# (待办1, 待办2, 期望 same)
CASES = [
    ("完成测试环境部署", "把测试环境部署好", True),    # 同任务不同说法
    ("完成测试环境部署", "完成生产环境部署", False),   # 危险反例
    ("部署完成后在群内告知", "部署完成后在群里通知", True),
    ("编写需求文档", "评审需求文档", False),
    ("将昨晚整理的需求文档发至工作群", "把需求文档发到工作群", True),
]


def main() -> int:
    backend = build_backend("llamacpp")
    print("模型已加载：", backend.name, flush=True)
    merger = SemanticMerger(backend)
    ok = 0
    try:
        for a, b, expect in CASES:
            band = titles_match_by_text(a, b)
            # 先看真实 raw（确认是否纯 JSON）
            prompt = build_chat_prompt(
                _DEDUP_USER_TMPL.format(a=a, b=b),
                system=_DEDUP_SYSTEM, enable_thinking=False,
            )
            raw = strip_thinking(
                backend.complete(prompt, max_tokens=64, temperature=0.0,
                                 enable_thinking=False)
            )
            got = merger.same_task(a, b)
            passed = got == expect
            ok += int(passed)
            print(
                f"\n[{ 'PASS' if passed else 'FAIL' }] band={band} expect={expect} got={got}",
                f"\n  {a}  ||  {b}",
                f"\n  raw={raw!r}",
                flush=True,
            )
    finally:
        backend.close()
        print(f"\n{ok}/{len(CASES)} 符合预期，模型已释放", flush=True)
    return 0 if ok == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
