"""报告导出：Markdown（纯 Python，零依赖）+ PDF（reportlab，工业简洁风）。

风格遵循工业简洁报告规范：
  - 低饱和度配色（墨黑 / 次灰 / 细线灰）
  - 无装饰元素
  - 细分隔线、简单表格边框
  - 矢量输出（PDF 本身为矢量）

PDF 依赖 reportlab，未安装时 export_pdf 抛出清晰指引；Markdown 始终可用。
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from . import config
from .log import get_logger

log = get_logger(__name__)

EXPORT_DIR = config.DATA_DIR / "exports"


def _ensure_dir(out_dir: Path | None = None) -> Path:
    d = out_dir or EXPORT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stamp(name: str) -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe = "".join(c for c in name if c.isalnum() or c in "-_") or "report"
    return f"{safe}_{ts}"


def _strip_md(text: str) -> str:
    """去掉简单 Markdown 标记，供 PDF 段落渲染。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def export_markdown(report: str, name: str = "复盘报告",
                    out_dir: Path | None = None) -> Path:
    """导出 Markdown 文件，返回路径。零依赖。"""
    d = _ensure_dir(out_dir)
    path = d / f"{_stamp(name)}.md"
    header = (
        f"# {name}\n\n"
        f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}　·　Memora 离线复盘\n\n"
        f"---\n\n"
    )
    path.write_text(header + report, encoding="utf-8")
    log.info("已导出 Markdown：%s", path)
    return path


def export_pdf(report: str, name: str = "复盘报告",
               out_dir: Path | None = None) -> Path:
    """导出 PDF（工业简洁风），返回路径。依赖 reportlab。"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        )
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    except ImportError as e:
        raise RuntimeError(
            "PDF 导出需要 reportlab，请安装：pip install reportlab"
        ) from e

    # 注册中文 CID 字体（无需外部字体文件）
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        font = "STSong-Light"
    except Exception:
        font = "Helvetica"

    d = _ensure_dir(out_dir)
    path = d / f"{_stamp(name)}.pdf"

    # 工业简洁风：低饱和度配色
    ink = HexColor("#1a1a1a")
    muted = HexColor("#666666")
    line = HexColor("#cccccc")

    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=name, author="Memora",
    )
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Heading1"], fontName=font,
                        fontSize=16, textColor=ink, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontName=font,
                        fontSize=12, textColor=ink, spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("body", parent=base["BodyText"], fontName=font,
                          fontSize=10, textColor=ink, leading=15)
    meta = ParagraphStyle("meta", parent=body, fontSize=8, textColor=muted)

    story = [
        Paragraph(name, h1),
        Paragraph(f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}　·　Memora 离线复盘", meta),
        HRFlowable(width="100%", thickness=0.5, color=line, spaceBefore=4, spaceAfter=8),
    ]

    for raw in report.splitlines():
        s = raw.strip()
        if not s:
            story.append(Spacer(1, 4))
            continue
        if s.startswith("## "):
            story.append(Paragraph(s[3:].strip(), h2))
        elif s.startswith("# "):
            story.append(Paragraph(s[2:].strip(), h1))
        elif s.startswith("- "):
            story.append(Paragraph("· " + _strip_md(s[2:]), body))
        else:
            story.append(Paragraph(_strip_md(s), body))

    doc.build(story)
    log.info("已导出 PDF：%s", path)
    return path


def export(report: str, name: str = "复盘报告", fmt: str = "md",
           out_dir: Path | None = None) -> Path:
    """统一导出入口：fmt 为 'md' 或 'pdf'。"""
    if fmt.lower() == "pdf":
        return export_pdf(report, name, out_dir)
    return export_markdown(report, name, out_dir)


# ---------------------------------------------------------------------------
# 会议记录导出：Markdown / TXT / SRT / PDF
# ---------------------------------------------------------------------------
def _write_text_file(content: str, ext: str, name: str,
                     out_dir: Path | None) -> Path:
    d = _ensure_dir(out_dir)
    path = d / f"{_stamp(name)}{ext}"
    path.write_text(content, encoding="utf-8")
    log.info("已导出 %s：%s", ext.lstrip(".").upper(), path)
    return path


def _meeting_plain_text(record) -> str:
    from .whisper.meeting import fmt_ts
    m = record.meta
    lines = [
        "会议记录", "",
        f"音频文件：{m.audio_name}",
        f"总时长：{fmt_ts(m.duration_seconds)}　识别说话人：{m.num_speakers} 位"
        f"　有效语音：{fmt_ts(m.speech_seconds)}　语言：{m.language}",
        "=" * 48, "",
    ]
    for seg in record.segments:
        lines.append(f"[{fmt_ts(seg.start)}] {seg.speaker or '说话人1'}：{seg.text}")
        lines.append("")
    return "\n".join(lines).rstrip()


def export_meeting_pdf(record, name: str = "会议记录",
                       out_dir: Path | None = None) -> Path:
    """会议记录 PDF：时间戳 + 说话人（品牌色加粗）+ 文本。"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import SimpleDocTemplate, Paragraph, HRFlowable
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from xml.sax.saxutils import escape as _esc
    except ImportError as e:
        raise RuntimeError("PDF 导出需要 reportlab，请安装：pip install reportlab") from e

    from .whisper.meeting import fmt_ts
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        font = "STSong-Light"
    except Exception:
        font = "Helvetica"

    d = _ensure_dir(out_dir)
    path = d / f"{_stamp(name)}.pdf"
    ink, muted, line, brand = (HexColor("#1a1a1a"), HexColor("#666666"),
                               HexColor("#cccccc"), HexColor("#0f766e"))
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=name, author="Memora",
    )
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Heading1"], fontName=font,
                        fontSize=16, textColor=ink, spaceAfter=6)
    body = ParagraphStyle("body", parent=base["BodyText"], fontName=font,
                          fontSize=10, textColor=ink, leading=16, spaceAfter=4)
    meta_style = ParagraphStyle("meta", parent=body, fontSize=8, textColor=muted)

    m = record.meta
    story = [
        Paragraph("会议记录", h1),
        Paragraph(
            f"音频：{_esc(m.audio_name)}　总时长：{fmt_ts(m.duration_seconds)}"
            f"　说话人：{m.num_speakers} 位　有效语音：{fmt_ts(m.speech_seconds)}",
            meta_style),
        HRFlowable(width="100%", thickness=0.5, color=line,
                   spaceBefore=4, spaceAfter=8),
    ]
    for seg in record.segments:
        story.append(Paragraph(
            f'<font color="#0f766e">[{fmt_ts(seg.start)}]</font> '
            f'<b><font color="#0f766e">{_esc(seg.speaker or "说话人1")}：</font></b>'
            f'{_esc(seg.text)}', body))
    doc.build(story)
    log.info("已导出会议记录 PDF：%s", path)
    return path


def export_meeting(record, fmt: str = "md", name: str | None = None,
                   out_dir: Path | None = None) -> Path:
    """会议记录统一导出：fmt ∈ md / txt / srt / pdf。"""
    from .whisper.meeting import to_srt
    name = name or f"会议记录_{record.meta.audio_name}"
    f = fmt.lower()
    if f == "md":
        return _write_text_file(record.text, ".md", name, out_dir)
    if f == "txt":
        return _write_text_file(_meeting_plain_text(record), ".txt", name, out_dir)
    if f == "srt":
        return _write_text_file(to_srt(record.segments), ".srt", name, out_dir)
    if f == "pdf":
        return export_meeting_pdf(record, name, out_dir)
    raise ValueError(f"不支持的会议记录导出格式：{fmt}")


# ---------------------------------------------------------------------------
# 项目复盘包：一键聚合 报告 + 行动项 + 会议记录 + 问答 + 原始对话，导出 zip
# （纯标准库 zipfile，零额外依赖；zip 内为 UTF-8 Markdown，可直接交付/归档）
# ---------------------------------------------------------------------------
def _render_qa(qa: list[dict]) -> str:
    lines = ["## 问答记录", ""]
    for i, item in enumerate(qa, 1):
        lines.append(f"**Q{i}：{item.get('q', '')}**")
        lines.append("")
        lines.append(str(item.get("a", "")))
        lines.append("")
    return "\n".join(lines).strip()


def _package_index(title: str, ts: str, file_names: list[str],
                   action_summary: dict) -> str:
    lines = [
        f"# {title} · 项目复盘包", "",
        f"> 生成时间：{ts}　·　Memora 本地离线生成，数据不出设备", "",
        "## 目录", "",
    ]
    for name in file_names:
        lines.append(f"- [{name}](./{name})")
    c = action_summary.get("counts", {})
    lines += [
        "", "## 行动项概览", "",
        f"- 行动项总数：{action_summary.get('total', 0)}",
        f"- 待跟进：{c.get('open', 0)}　进行中：{c.get('in_progress', 0)}",
        f"- 已完成：{c.get('done', 0)}　已取消：{c.get('cancelled', 0)}",
        f"- 逾期：{action_summary.get('overdue', 0)}", "",
    ]
    return "\n".join(lines)


def export_package(title: str = "项目复盘包", report: str = "",
                   qa: list[dict] | None = None, record_text: str = "",
                   raw_text: str = "", *, include_raw: bool = True,
                   out_dir: Path | None = None) -> Path:
    """一键导出完整项目复盘包（zip），返回路径。

    - report：结构化复盘报告 / 会议纪要；
    - qa：问答记录 [{q, a}]；
    - record_text：语音会议记录（说话人 + 时间戳）；
    - raw_text：原始对话文本；
    - 行动项清单始终从本地行动项库取最新状态（无需调用方传入）。
    """
    import zipfile

    from .action_items import get_store, render_action_items

    d = _ensure_dir(out_dir)
    zip_path = d / f"{_stamp(title + '_复盘包')}.zip"
    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    store = get_store()
    actions_md = render_action_items(store.items, title="行动项清单")

    files: list[tuple[str, str]] = [
        ("01_复盘报告.md", report.strip() or "（本次未生成复盘报告）"),
        ("02_行动项清单.md", actions_md),
    ]
    if record_text.strip():
        files.append(("03_会议记录.md", record_text.strip()))
    if qa:
        files.append(("04_问答记录.md", _render_qa(qa)))
    if include_raw and raw_text.strip():
        files.append(("05_原始对话.md", raw_text.strip()))

    index = _package_index(title, ts, [n for n, _ in files], store.summary())

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.md", index)
        for name, content in files:
            z.writestr(name, content)
    log.info("已导出项目复盘包：%s（含 %d 个文件）", zip_path, len(files) + 1)
    return zip_path
