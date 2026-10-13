"""跨会议行动项库：把单次复盘/纪要里的「待办」沉淀为可追踪的行动项。

纯本地 JSON（默认 data/action_items.json），数据不出设备，离线可用。

闭环：
  1. 复盘报告 / 语音纪要生成后，从「待办」段确定性地解析出行动项
     （内容 / 责任人 / 时间节点），复用 report.sections，无需额外推理；
  2. 归一化去重：同一项在多次会议被重复提到，只保留一条、不重复入库；
  3. 责任人可匹配联系人库（ContactStore），挂上 contact_id；
  4. 新会议可把历史未完成项作为上下文，让模型判断是否推进 / 完成
     （见 agent.track_progress），状态：待跟进 / 进行中 / 已完成 / 已取消；
  5. 「时间节点」能解析为日期且已过期、又未完成的，动态标记为逾期。

状态机：open（待跟进）-> in_progress（进行中）-> done（已完成）
        任意非终态 -> cancelled（已取消）。
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config
from .log import get_logger
from .report.sections import (
    extract_list_items,
    parse_standard_sections,
)

log = get_logger(__name__)

# 状态码 -> 中文标签
STATUSES: dict[str, str] = {
    "open": "待跟进",
    "in_progress": "进行中",
    "done": "已完成",
    "cancelled": "已取消",
}
# 非终态（仍需追踪）
ACTIVE_STATUSES = ("open", "in_progress")
# 终态
FINAL_STATUSES = ("done", "cancelled")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class ActionItem:
    id: str
    title: str
    owner: str = ""
    contact_id: str = ""
    due: str = ""
    status: str = "open"
    source_meeting: str = ""       # 首次提出的会议/对话标题
    source_kind: str = "chat"      # chat 文本对话 / voice 语音
    source_session: str = ""
    created_at: str = ""
    updated_at: str = ""
    history: list[dict] = field(default_factory=list)

    def __post_init__(self):
        ts = _now()
        if not self.created_at:
            self.created_at = ts
        if not self.updated_at:
            self.updated_at = ts

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 待办条目解析（报告 / 纪要 -> 行动项字段）
# ---------------------------------------------------------------------------
# 去掉 checkbox / 列表符号后的格式约定：
#   任务内容 ｜ 责任人：XXX ｜ 时间节点：XXX
# 字段值非贪婪匹配，遇到分隔符或下一个字段标签（责任人/时间节点…）即停止，
# 以兼容模型偶发不写分隔符或字段顺序颠倒的情况。
_NEXT_FIELD = (
    r"(?=\s*(?:责任人|时间节点|截止时间|完成时间|截止日期|截止|期限|deadline)[：:]|"
    r"[｜|]|$)"
)
_OWNER_RE = re.compile(r"责任人[：:]\s*(.*?)" + _NEXT_FIELD)
_DUE_RE = re.compile(
    r"(?:时间节点|截止时间|完成时间|截止日期|截止|期限|deadline)[：:]\s*(.*?)"
    + _NEXT_FIELD,
    re.IGNORECASE,
)
_UNKNOWN = ("未明确", "待定", "无", "暂未明确", "未指定", "TBD", "N/A")


def _clean_field(v: str) -> str:
    v = v.strip().strip("。.，,；; ")
    if v in _UNKNOWN:
        return ""
    return v


def parse_todo_item(raw: str) -> dict:
    """把单条待办文本解析为 {title, owner, due}。

    模型偶发不写分隔符或字段顺序变化，这里做容错：
    先抽取「责任人 / 时间节点」字段，再从剩余文本取任务内容。
    """
    t = raw.strip()
    owner = due = ""
    m = _OWNER_RE.search(t)
    if m:
        owner = _clean_field(m.group(1))
    m = _DUE_RE.search(t)
    if m:
        due = _clean_field(m.group(1))

    # 任务内容：取第一个分隔符之前，或剥离字段标签后的残文
    title = re.split(r"[｜|]", t, maxsplit=1)[0]
    title = re.sub(r"(?:责任人|时间节点|截止时间|完成时间|截止日期|截止|期限|deadline)[：:].*$",
                   "", title, flags=re.IGNORECASE)
    # 去掉 checkbox / 列表前缀
    title = re.sub(r"^\s*(?:[-*+]\s*)?(?:\[[ xX]\]\s*)?(?:\d+\s*[.、)]\s*)?",
                   "", title)
    title = title.strip().strip(" -[]*")
    return {"title": title, "owner": owner, "due": due}


def extract_action_candidates(report_md: str) -> list[dict]:
    """从复盘报告 / 语音纪要的「待办」段解析候选行动项。

    返回 [{title, owner, due}]，已过滤空标题与明显非任务的寒暄。
    """
    secs = parse_standard_sections(report_md)
    todo_text = secs.get("todos", "")
    if not todo_text:
        return []
    out: list[dict] = []
    for raw in extract_list_items(todo_text):
        parsed = parse_todo_item(raw)
        if len(parsed["title"]) >= 2:
            out.append(parsed)
    return out


# ---------------------------------------------------------------------------
# 归一化去重
# ---------------------------------------------------------------------------
_PUNCT_RE = re.compile(r"""[\s\*\_\-\[\]\(\)（）。，、,.：:；;！!？?·|｜/\\#>“”"'‘’~`^&=+@]+""")


def norm_title(text: str) -> str:
    if not text:
        return ""
    return _PUNCT_RE.sub("", text.lower())


# ---------------------------------------------------------------------------
# 行动项持久化
# ---------------------------------------------------------------------------
class ActionItemStore:
    def __init__(self, path: str = "") -> None:
        self.path = Path(path) if path else config.ACTION_ITEMS_FILE
        self.items: list[ActionItem] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.items = []
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = [ActionItem(**c) for c in data.get("items", [])]
        except Exception:  # noqa: BLE001
            self.items = []

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "items": [c.to_dict() for c in self.items]}
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(self.path)

    # ------------------------------------------------------------------
    def find_by_id(self, aid: str) -> ActionItem | None:
        for it in self.items:
            if it.id == aid:
                return it
        return None

    def find_active_similar(self, title: str) -> ActionItem | None:
        """归一化标题匹配「仍在追踪」的行动项（跨会议去重）。"""
        nt = norm_title(title)
        if not nt:
            return None
        for it in self.items:
            if it.status in ACTIVE_STATUSES and norm_title(it.title) == nt:
                return it
        return None

    def add(self, title: str, owner: str = "", due: str = "",
            *, source_meeting: str = "", source_kind: str = "chat",
            source_session: str = "", contact_id: str = "") -> tuple[ActionItem, bool]:
        """新增或归并行动项。

        已存在相同的未完成项 -> 归并（补全此前缺失的责任人/时间节点），返回 (item, False)；
        否则新建，返回 (item, True)。
        """
        title = title.strip()
        existing = self.find_active_similar(title)
        if existing is not None:
            changed = False
            if not existing.owner and owner:
                existing.owner = owner
                changed = True
            if not existing.due and due:
                existing.due = due
                changed = True
            if not existing.contact_id and contact_id:
                existing.contact_id = contact_id
                changed = True
            if changed:
                existing.updated_at = _now()
                self.save()
            return existing, False

        it = ActionItem(
            id="a_" + uuid.uuid4().hex[:10],
            title=title, owner=owner, due=due, contact_id=contact_id,
            source_meeting=source_meeting, source_kind=source_kind,
            source_session=source_session,
        )
        self.items.append(it)
        self.save()
        return it, True

    def set_status(self, aid: str, status: str, note: str = "",
                   *, source: str = "") -> ActionItem | None:
        """更新状态并记录历史。"""
        if status not in STATUSES:
            raise ValueError(f"未知状态：{status}")
        it = self.find_by_id(aid)
        if it is None:
            return None
        if it.status != status:
            it.history.append({
                "time": _now(), "from": it.status, "to": status,
                "note": note.strip(), "source": source,
            })
            it.status = status
            it.updated_at = _now()
            self.save()
        return it

    def ingest(self, candidates: list[dict], *, source_meeting: str,
               source_kind: str = "chat", source_session: str = "") -> dict:
        """批量入库一次复盘/纪要的候选行动项，返回统计 {created, merged}。"""
        created = merged = 0
        # 联系人库用于责任人匹配（缺失也不影响）
        contact_by_name = {}
        try:
            from .whisper.contacts import get_store as _contacts
            for c in _contacts().contacts:
                contact_by_name[c.name] = c.id
        except Exception:  # noqa: BLE001
            contact_by_name = {}

        for cand in candidates:
            cid = contact_by_name.get(cand.get("owner", ""), "")
            _, is_new = self.add(
                cand["title"], cand.get("owner", ""), cand.get("due", ""),
                source_meeting=source_meeting, source_kind=source_kind,
                source_session=source_session, contact_id=cid,
            )
            if is_new:
                created += 1
            else:
                merged += 1
        if created or merged:
            log.info("行动项入库：新增 %d / 归并 %d（来源：%s）",
                     created, merged, source_meeting)
        return {"created": created, "merged": merged}

    # ------------------------------------------------------------------
    def active_items(self) -> list[ActionItem]:
        """仍在追踪的行动项（待跟进 + 进行中）。"""
        return [it for it in self.items if it.status in ACTIVE_STATUSES]

    def list(self, status: str | None = None,
             owner: str | None = None) -> list[ActionItem]:
        out = self.items
        if status:
            out = [it for it in out if it.status == status]
        if owner:
            out = [it for it in out if it.owner == owner]
        return out

    def owners(self) -> list[str]:
        names = sorted({it.owner for it in self.items if it.owner})
        return names

    def summary(self) -> dict:
        counts = {k: 0 for k in STATUSES}
        overdue = 0
        for it in self.items:
            counts[it.status] = counts.get(it.status, 0) + 1
            if is_overdue(it):
                overdue += 1
        return {"total": len(self.items), "counts": counts, "overdue": overdue}


def get_store(path: str = "") -> ActionItemStore:
    return ActionItemStore(path)


# ---------------------------------------------------------------------------
# 逾期判断（确定性，不修改数据）
# ---------------------------------------------------------------------------
# 从「时间节点」文本提取日期，支持：2026-10-01 / 2026年10月1日 / 10月1日（当年）
_DATE_RES = (
    re.compile(r"(\d{4})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})"),
    re.compile(r"(\d{1,2})\s*[月.]\s*(\d{1,2})\s*日?"),
)


def parse_due_date(due: str) -> time.struct_time | None:
    """把时间节点文本解析为日期；无法确定具体日期（如「下周五」）返回 None。"""
    if not due:
        return None
    m = _DATE_RES[0].search(due)
    if m:
        try:
            return time.strptime(
                f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}",
                "%Y-%m-%d",
            )
        except ValueError:
            return None
    m = _DATE_RES[1].search(due)
    if m:
        year = time.localtime().tm_year
        try:
            return time.strptime(
                f"{year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}", "%Y-%m-%d"
            )
        except ValueError:
            return None
    return None


def is_overdue(item: ActionItem, *, now: float | None = None) -> bool:
    """非终态且时间节点日期早于今天 -> 逾期。无确定日期 / 已完成不算。"""
    if item.status not in ACTIVE_STATUSES:
        return False
    d = parse_due_date(item.due)
    if d is None:
        return False
    today = time.localtime(now) if now is not None else time.localtime()
    # 比较到「天」：把今天 0 点与 due 当天 0 点比较
    today_day = time.strptime(time.strftime("%Y-%m-%d", today), "%Y-%m-%d")
    return time.mktime(d) < time.mktime(today_day)


# ---------------------------------------------------------------------------
# 跨会议进展回顾输出解析（纯函数、零模型依赖、可单测）
# ---------------------------------------------------------------------------
_TRACK_LINE_RE = re.compile(
    r"^\s*(\d+)\s*[｜|]\s*([^｜|]+?)\s*(?:[｜|](.*))?$"
)
# 状态词（按优先级）：先匹配「已完成」，再「推进中」「已取消」
_STATUS_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("done", ("已完成", "已做完", "已交付", "已通过", "完成")),
    ("in_progress", ("推进中", "进行中", "跟进中", "在跟进", "有进展", "在推进")),
    ("cancelled", ("已取消", "不再需要", "取消")),
)


def parse_track_output(text: str, active_items: list[ActionItem]
                       ) -> list[tuple[ActionItem, str, str]]:
    """解析进展回顾模型输出。

    输入按编号顺序的 active_items（编号从 1 起），返回
    [(item, new_status, note)]；未提及/状态无法识别时 new_status 为 ""，
    表示保持原状态（不改动）。
    """
    idx_map = {i + 1: it for i, it in enumerate(active_items)}
    out: list[tuple[ActionItem, str, str]] = []
    for raw in text.splitlines():
        m = _TRACK_LINE_RE.match(raw)
        if not m:
            continue
        idx = int(m.group(1))
        status_text = m.group(2)
        note = (m.group(3) or "").strip()
        item = idx_map.get(idx)
        if item is None:
            continue
        new_status = ""
        for code, words in _STATUS_WORDS:
            if any(w in status_text for w in words):
                new_status = code
                break
        out.append((item, new_status, note))
    return out


# ---------------------------------------------------------------------------
# Markdown 渲染（供复盘包 / 导出）
# ---------------------------------------------------------------------------
def render_action_items(items: list[ActionItem], *, title: str = "行动项清单") -> str:
    lines = [f"## {title}", ""]
    if not items:
        lines.append("（暂无行动项）")
        return "\n".join(lines)
    groups: dict[str, list[ActionItem]] = {}
    for it in items:
        groups.setdefault(it.status, []).append(it)
    for code in ("open", "in_progress", "done", "cancelled"):
        group = groups.get(code, [])
        if not group:
            continue
        lines.append(f"### {STATUSES[code]}（{len(group)}）")
        for it in group:
            owner = f"责任人：{it.owner}" if it.owner else "责任人：未明确"
            due = f"时间节点：{it.due}" if it.due else "时间节点：未明确"
            mark = "✓" if code == "done" else ("×" if code == "cancelled" else " ")
            extra = "（已逾期）" if is_overdue(it) else ""
            lines.append(f"- [{mark}] {it.title} ｜ {owner} ｜ {due}{extra}")
            if it.source_meeting:
                lines.append(f"    来源：{it.source_meeting}")
        lines.append("")
    return "\n".join(lines).rstrip()
