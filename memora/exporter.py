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
