# -*- coding: utf-8 -*-
"""M2 评测报告：把 results/<run-tag> 下的格子结果聚合成单文件 HTML（离线可开）。"""
from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(_HERE))
from metrics import aggregate  # noqa: E402


def group_label(cell: dict) -> str:
    mtag = cell.get("model_tag", "?")
    mode = cell.get("mode", "?")
    is_long = cell.get("is_long")
    if mode == "auto":
        return f"{mtag.upper()} · 自动 · " + ("超长(RAG)" if is_long else "短/中(全量)")
    name = {"full": "全量基线", "rag": "RAG检索",
            "compressed": "规则压缩"}.get(mode, mode)
    return f"{mtag.upper()} · {name} · 超长"


_GROUP_ORDER = [
    "4B · 自动 · 短/中(全量)",
    "4B · 自动 · 超长(RAG)",
    "4B · 全量基线 · 超长",
    "4B · 规则压缩 · 超长",
    "1.7B · RAG检索 · 超长",
]


def load_cells(run_tag: str) -> list[dict]:
    d = _HERE / "results" / run_tag
    cells = []
    for p in sorted(d.glob("*.json")):
        try:
            cells.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return cells


def _pct(v):
    return "—" if v is None else f"{v * 100:.1f}%"


def _bar(v):
    if v is None:
        return '<div class="bar"><span class="fill na" style="width:0%"></span><b>—</b></div>'
    w = max(2, round(v * 100))
    cls = "good" if v >= 0.8 else ("mid" if v >= 0.5 else "bad")
    return (f'<div class="bar"><span class="fill {cls}" style="width:{w}%"></span>'
            f'<b>{v*100:.0f}%</b></div>')


def _hall_bar(v):
    if v is None:
        return _bar(None)
    # 幻觉率越低越好，反向着色
    w = max(2, round(v * 100))
    cls = "good" if v <= 0.2 else ("mid" if v <= 0.5 else "bad")
    return (f'<div class="bar"><span class="fill {cls}" style="width:{w}%"></span>'
            f'<b>{v*100:.0f}%</b></div>')


def build_report(run_tag: str) -> Path:
    cells = load_cells(run_tag)
    groups: dict[str, list[dict]] = {}
    for c in cells:
        if c.get("card"):
            groups.setdefault(group_label(c), []).append(c)

    ordered_labels = [g for g in _GROUP_ORDER if g in groups] + \
                     [g for g in groups if g not in _GROUP_ORDER]

    # ---- 总览行 ----
    rows = []
    chart_rows = []
    for label in ordered_labels:
        gc = groups[label]
        agg = aggregate([c["card"] for c in gc])
        avg_review = round(sum(c.get("review_s") or 0 for c in gc) / len(gc), 1)
        avg_total = round(sum(c.get("total_s") or 0 for c in gc) / len(gc), 1)
        rows.append(
            "<tr>"
            f"<td class='gl'>{html.escape(label)}</td>"
            f"<td>{agg['n_cases']}</td>"
            f"<td>{_pct(agg['todos']['precision'])}</td>"
            f"<td>{_pct(agg['todos']['recall'])}</td>"
            f"<td>{_pct(agg['todos']['f1'])}</td>"
            f"<td>{_pct(agg['risk_completeness'])}</td>"
            f"<td>{_pct(agg['extraction_recall'])}</td>"
            f"<td>{_pct(agg['decisions']['f1'])}</td>"
            f"<td>{_pct(agg['owner_accuracy'])}</td>"
            f"<td>{_pct(agg['deadline_recall'])}</td>"
            f"<td>{_pct(agg['qa_evidence_recall'])}</td>"
            f"<td>{_pct(agg['hallucination_rate'])}</td>"
            f"<td>{avg_review}s / {avg_total}s</td>"
            "</tr>")
        chart_rows.append(
            f"<div class='crow'><div class='clabel'>{html.escape(label)}</div>"
            f"<div class='cmetrics'>"
            f"<span>风险完整度 {_bar(agg['risk_completeness'])}</span>"
            f"<span>信息提取(全文) {_bar(agg['extraction_recall'])}</span>"
            f"<span>QA证据命中 {_bar(agg['qa_evidence_recall'])}</span>"
            f"<span>待办F1 {_bar(agg['todos']['f1'])}</span>"
            f"<span>决定F1 {_bar(agg['decisions']['f1'])}</span>"
            f"<span>幻觉率 {_hall_bar(agg['hallucination_rate'])}</span>"
            "</div></div>")

    # ---- 逐格明细 ----
    detail = []
    for label in ordered_labels:
        for c in groups[label]:
            card = c["card"]
            qa_html = "".join(
                f"<li><b>问</b>：{html.escape(a['q'])}<br>"
                f"<b>答</b>：{html.escape(a['answer'][:300])}</li>"
                for a in c.get("answers", []))
            badge = ""
            if c.get("context_mode_review"):
                badge = f"实际上下文：{c['context_mode_review']}｜字数：{c.get('char_count')}"
            detail.append(
                f"<details><summary>{html.escape(c['case_id'])} · {html.escape(label)}"
                f" <span class='mini'>todoR {_pct(card['todos']['recall'])}｜"
                f"风险R {_pct(card['risks']['recall'])}｜决定R {_pct(card['decisions']['recall'])}"
                f"｜全文提取 todo {_pct(card['todos'].get('extraction_recall'))}/风险 {_pct(card['risks'].get('extraction_recall'))}/决定 {_pct(card['decisions'].get('extraction_recall'))}"
                f"｜QA {_pct(card['qa']['evidence_recall'])}｜幻觉 {_pct(card['qa']['hallucination_rate'])}"
                f"</span></summary>"
                f"<div class='dmeta'>{html.escape(badge or '')}｜复盘 {c.get('review_s')}s</div>"
                f"<div class='dgrid'><div><h4>复盘报告</h4><pre>{html.escape(c.get('report') or '')}</pre></div>"
                f"<div><h4>探针问答</h4><ul class='qa'>{qa_html}</ul></div></div></details>")

    failed = [c for c in cells if c.get("error")]
    fail_html = ""
    if failed:
        fail_html = "<h2>失败格子</h2><ul>" + "".join(
            f"<li>{html.escape(c['case_id'])} {c.get('model_tag')} {c.get('mode')}："
            f"{html.escape(c['error'])}</li>" for c in failed) + "</ul>"

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    n_cases = len(cells)
    page = f"""<html style="margin:0;padding:0;">
<title>Memora 离线评测报告 · {html.escape(run_tag)}</title>
<div style="width:100%;box-sizing:border-box;padding:28px;font-family:'Microsoft YaHei',Segoe UI,Arial,sans-serif;color:#1f2933;max-width:1180px;margin:0 auto;">
<h1 style="margin:0 0 4px;font-size:24px;">Memora 端侧对话复盘 · 离线评测报告</h1>
<div style="color:#667;font-size:14px;margin-bottom:18px;">
实验标签 <b>{html.escape(run_tag)}</b>｜生成时间 {now}｜有效格子 {len(cells)-len(failed)}/{n_cases}
｜模型 Spark-X2.5（本地 llama-server，全 CPU）｜评测集 50 例（含 20 例超长，关键事实锚定头/中/尾）</div>

<h2>一、指标总览</h2>
<div style="font-size:13px;color:#556;margin-bottom:10px;">
精确率=复盘条目有据可查比例；召回=golden 事实被覆盖到对应段落比例；信息提取(全文)=事实在报告任意位置被提到的比例；风险完整度=风险的全文提取召回；
字段级=责任人/截止时间覆盖；QA证据命中=可答探针答对；幻觉率=无答案问题未正确拒答比例。</div>
<table style="border-collapse:collapse;width:100%;font-size:13px;">
<thead><tr style="background:#102a43;color:#fff;">
<th>配置档</th><th>n</th><th>待办P</th><th>待办R</th><th>待办F1</th>
<th>风险完整度</th><th>信息提取<br>(全文)</th><th>决定F1</th><th>责任人</th><th>截止</th>
<th>QA证据</th><th>幻觉率</th><th>耗时(复盘/格)</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>

<h2>二、关键指标对比</h2>
<div style="font-size:13px;color:#556;margin-bottom:8px;">超长会话下，全量基线会截断最旧记录；RAG 与规则压缩用于保住被噪声淹没的头/尾关键信息。</div>
{''.join(chart_rows)}

{fail_html}
<h2>三、逐格明细</h2>
{''.join(detail) if detail else '<p>暂无有效结果。</p>'}

<div style="margin-top:24px;color:#889;font-size:12px;">
口径：中文短语归一化子串匹配（去标点/空白、小写）；跨段复述不计误报；
超长=正文&gt;RAG触发阈值（约2.0万字）；全部计算与推理在本机离线完成。</div>
<style>
td,th{{border:1px solid #d9e2ec;padding:6px 8px;text-align:center;}}
td.gl{{text-align:left;font-weight:600;background:#f0f4f8;white-space:nowrap;}}
tbody tr:nth-child(even){{background:#fafcfe;}}
.bar{{position:relative;background:#e4e9f0;border-radius:4px;height:18px;width:150px;display:inline-block;vertical-align:middle;}}
.bar .fill{{position:absolute;left:0;top:0;bottom:0;border-radius:4px;}}
.bar b{{position:absolute;right:6px;top:0;line-height:18px;font-size:11px;color:#102a43;}}
.fill.good{{background:#2f9e44;}} .fill.mid{{background:#f08c00;}} .fill.bad{{background:#e03131;}} .fill.na{{background:#ccc;}}
.crow{{display:flex;align-items:center;border-bottom:1px solid #eef2f6;padding:8px 0;}}
.clabel{{width:210px;font-size:13px;font-weight:600;flex-shrink:0;}}
.cmetrics{{display:flex;flex-wrap:wrap;gap:14px;flex:1;}}
.cmetrics span{{font-size:12px;color:#445;display:flex;align-items:center;gap:6px;}}
details{{border:1px solid #d9e2ec;border-radius:6px;margin:8px 0;padding:8px 12px;background:#fcfdff;}}
summary{{cursor:pointer;font-weight:600;font-size:14px;}}
.mini{{font-weight:400;color:#52606d;font-size:12px;}}
.dmeta{{font-size:12px;color:#667;margin:6px 0;}}
.dgrid{{display:grid;grid-template-columns:1.2fr 1fr;gap:16px;}}
pre{{white-space:pre-wrap;word-break:break-word;font-size:12px;background:#f4f7fa;padding:10px;border-radius:6px;max-height:420px;overflow:auto;}}
.qa{{font-size:12px;padding-left:18px;}} .qa li{{margin-bottom:10px;}}
h4{{margin:6px 0;font-size:13px;color:#334;}}
@media(max-width:820px){{.dgrid{{grid-template-columns:1fr;}}.clabel{{width:auto;}}}}
</style>
</div></html>"""

    out = _HERE / "results" / run_tag / "report.html"
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    print(build_report(tag))
