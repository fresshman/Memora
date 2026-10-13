"""跨会议行动项库单测（不加载模型）。"""
from __future__ import annotations

from memora import action_items as A

SAMPLE_REPORT = """## 一、核心结论
- 确定采用方案 A。

## 二、待办
- [ ] 完成接口文档 ｜ 责任人：张三 ｜ 时间节点：2026-10-01
- [ ] 联系供应商报价 ｜ 责任人：李四 ｜ 时间节点：未明确
- [ ] 周五前同步测试结果 ｜ 责任人：未明确 ｜ 时间节点：下周五

## 三、关键信息
- 预算上限为 10 万元。
"""


# ---------------------------------------------------------------------------
# 待办解析
# ---------------------------------------------------------------------------
def test_parse_todo_standard():
    p = A.parse_todo_item("完成接口文档 ｜ 责任人：张三 ｜ 时间节点：2026-10-01")
    assert p["title"] == "完成接口文档"
    assert p["owner"] == "张三"
    assert p["due"] == "2026-10-01"


def test_parse_todo_no_separator():
    # 模型偶发不写分隔符
    p = A.parse_todo_item("联系供应商 责任人：李四 时间节点：10月15日")
    assert p["title"] == "联系供应商"
    assert p["owner"] == "李四"
    assert "10月15日" in p["due"]


def test_parse_todo_unknown_blank():
    p = A.parse_todo_item("任务X ｜ 责任人：未明确 ｜ 时间节点：待定")
    assert p["owner"] == "" and p["due"] == ""
    assert p["title"] == "任务X"


def test_parse_todo_checkbox_prefix():
    p = A.parse_todo_item("- [ ] 修复登录异常 ｜ 责任人：王五")
    assert p["title"] == "修复登录异常" and p["owner"] == "王五"


def test_extract_candidates():
    cands = A.extract_action_candidates(SAMPLE_REPORT)
    assert len(cands) == 3
    assert cands[0]["title"] == "完成接口文档"
    assert cands[2]["owner"] == ""          # 责任人未明确
    # 「下周五」作为原始时间文本保留（有参考价值），但无法解析为确定日期、不参与逾期
    assert cands[2]["due"] == "下周五"
    assert A.parse_due_date(cands[2]["due"]) is None


def test_norm_title():
    assert A.norm_title("完成接口文档！") == A.norm_title("完成接口文档")
    assert A.norm_title("Fix Bug-1") == "fixbug1"


# ---------------------------------------------------------------------------
# 存储 / 归并 / 状态
# ---------------------------------------------------------------------------
def test_add_new(tmp_path):
    st = A.ActionItemStore(str(tmp_path / "a.json"))
    it, is_new = st.add("准备评审材料", "张三", "2026-11-01")
    assert is_new and it.id.startswith("a_") and it.status == "open"


def test_add_merge_completes_fields(tmp_path):
    st = A.ActionItemStore(str(tmp_path / "a.json"))
    st.add("准备评审材料")
    it, is_new = st.add("准备评审材料", "张三", "2026-11-01")
    assert is_new is False
    assert it.owner == "张三" and it.due == "2026-11-01"
    assert len(st.items) == 1


def test_ingest_dedup(tmp_path):
    st = A.ActionItemStore(str(tmp_path / "a.json"))
    cands = [
        {"title": "任务A", "owner": "张三", "due": ""},
        {"title": "任务A", "owner": "张三", "due": "2026-12-01"},
        {"title": "任务B", "owner": "", "due": ""},
    ]
    stats = st.ingest(cands, source_meeting="群1")
    assert stats["created"] == 2 and stats["merged"] == 1
    assert len(st.items) == 2


def test_set_status_records_history(tmp_path):
    st = A.ActionItemStore(str(tmp_path / "a.json"))
    it, _ = st.add("任务A")
    st.set_status(it.id, "in_progress", "已开工", source="手动")
    st.set_status(it.id, "done", "已交付", source="手动")
    cur = st.find_by_id(it.id)
    assert cur.status == "done" and len(cur.history) == 2
    assert cur.history[0]["from"] == "open"
    assert cur.history[0]["to"] == "in_progress"


def test_persistence(tmp_path):
    p = str(tmp_path / "a.json")
    st = A.ActionItemStore(p)
    st.add("任务A", "张三")
    st2 = A.ActionItemStore(p)
    assert len(st2.items) == 1 and st2.items[0].title == "任务A"


def test_list_filter_and_owners(tmp_path):
    st = A.ActionItemStore(str(tmp_path / "a.json"))
    st.ingest([
        {"title": "任务A", "owner": "张三"},
        {"title": "任务B", "owner": "李四"},
    ], source_meeting="群1")
    assert len(st.list(owner="张三")) == 1
    assert st.owners() == ["张三", "李四"]
    assert len(st.active_items()) == 2


# ---------------------------------------------------------------------------
# 日期 / 逾期
# ---------------------------------------------------------------------------
def test_parse_due_date():
    assert A.parse_due_date("2026-10-01") is not None
    assert A.parse_due_date("2026年10月1日") is not None
    assert A.parse_due_date("10月1日") is not None
    assert A.parse_due_date("下周五") is None


def test_is_overdue(tmp_path):
    st = A.ActionItemStore(str(tmp_path / "a.json"))
    old, _ = st.add("旧任务", due="2026-10-01")
    future, _ = st.add("未来任务", due="2027-01-01")
    nodate, _ = st.add("无日期任务")
    assert A.is_overdue(old)
    assert not A.is_overdue(future)
    assert not A.is_overdue(nodate)
    # 已完成的旧任务不算逾期
    st.set_status(old.id, "done")
    assert not A.is_overdue(old)


def test_summary_counts_overdue(tmp_path):
    st = A.ActionItemStore(str(tmp_path / "a.json"))
    a, _ = st.add("旧任务", due="2026-10-01")
    st.add("新任务", due="2027-01-01")
    st.set_status(a.id, "done")
    s = st.summary()
    assert s["total"] == 2
    assert s["counts"]["done"] == 1 and s["counts"]["open"] == 1
    assert s["overdue"] == 0


# ---------------------------------------------------------------------------
# 进展回顾输出解析
# ---------------------------------------------------------------------------
def test_parse_track_output(tmp_path):
    st = A.ActionItemStore(str(tmp_path / "a.json"))
    it1, _ = st.add("任务一")
    it2, _ = st.add("任务二")
    it3, _ = st.add("任务三")
    raw = (
        "1｜已完成｜已经交付验收\n"
        "2｜推进中｜本周继续开发\n"
        "3｜未提及｜\n"
    )
    parsed = A.parse_track_output(raw, [it1, it2, it3])
    assert len(parsed) == 3
    assert parsed[0][1] == "done"
    assert parsed[1][1] == "in_progress"
    assert parsed[2][1] == ""        # 未提及 -> 保持原状
    assert "验收" in parsed[0][2]


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------
def test_render_action_items(tmp_path):
    st = A.ActionItemStore(str(tmp_path / "a.json"))
    it, _ = st.add("任务A", "张三", "2026-10-01")
    st.set_status(it.id, "done")
    md = A.render_action_items(st.items)
    assert "行动项清单" in md and "任务A" in md and "已完成" in md
