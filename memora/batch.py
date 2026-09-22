"""批量复盘：对多个聊天记录文件依次解析 + 复盘，汇总输出。

独立于 UI，可被 app.py 或测试直接调用。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .parsers import parse_file
from .pii import redact_if_configured
from .agent import MemoraAgent
from .log import get_logger

log = get_logger(__name__)


@dataclass
class BatchResult:
    file: str
    success: bool
    report: str = ""
    error: str = ""
    source: str = ""
    msg_count: int = 0


def batch_review(files: list[str], agent: MemoraAgent) -> list[BatchResult]:
    """对多个文件依次解析并复盘，返回逐条结果（不抛异常，失败记入 error）。"""
    results: list[BatchResult] = []
    for f in files:
        log.info("批量复盘处理：%s", f)
        try:
            conv = parse_file(f)
            conv, _red = redact_if_configured(conv)
            report = agent.review(conv)
            results.append(BatchResult(
                file=f, success=True, report=report,
                source=conv.source, msg_count=len(conv),
            ))
            log.info("批量复盘成功：%s（来源=%s，消息数=%d）", f, conv.source, len(conv))
        except Exception as e:  # noqa: BLE001
            results.append(BatchResult(file=f, success=False, error=str(e)))
            log.warning("批量复盘失败：%s：%s", f, e)
    return results


def summarize(results: list[BatchResult]) -> str:
    """把批量结果汇总成一份 Markdown 总览。"""
    ok = [r for r in results if r.success]
    fail = [r for r in results if not r.success]
    lines = [
        "# 批量复盘总览",
        "",
        f"> 共 {len(results)} 份，成功 {len(ok)} 份，失败 {len(fail)} 份",
        "",
    ]
    for i, r in enumerate(ok, 1):
        lines += [
            "---",
            "",
            f"# 第 {i} 份：{Path(r.file).name}（来源 {r.source}，{r.msg_count} 条消息）",
            "",
            r.report,
        ]
    if fail:
        lines += ["", "---", "", "## 失败文件", ""]
        for r in fail:
            lines.append(f"- {r.file}：{r.error}")
    return "\n".join(lines)
