"""导出功能单元测试（Markdown 零依赖部分）。"""
from __future__ import annotations

from memora.exporter import export_markdown


def test_export_markdown(tmp_path):
    report = "## 结论\n- 要点A\n"
    path = export_markdown(report, "测试报告", tmp_path)
    assert path.exists()
    assert path.suffix == ".md"
    content = path.read_text(encoding="utf-8")
    assert "测试报告" in content
    assert "结论" in content
