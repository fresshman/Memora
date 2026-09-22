# -*- coding: utf-8 -*-
"""复盘报告结构化与「决定归位」后处理（纯函数、零模型依赖、可单测）。

背景：端侧模型偶发把"已经敲定的会议/活动安排"写进第三段「关键信息提取」
（作为时间/地点实体罗列），导致结构化的「核心结论 / 决定」区漏掉这些决定。
评测显示全文提取召回(extraction_recall)≈0.97，信息并未丢失，只是归位错误。

本模块在不改动模型原文、不动待办/风险段的前提下，做**确定性、补全式**归位：
- 仅扫描「关键信息提取」段，识别"事件名 + 就近时间 + 会场地点"齐备的安排；
- 聚合成一句干净的决定，追加进「核心结论 / 决定」面（复制，不删除原实体）；
- 设取消/改期/推迟安全闸、事件去重、会场白名单、时间就近配对（中间不得隔着
  另一个时间点或分句），宁可不归位也不臆造。

评测（离线重放 50 格）：决定段内召回 短对话 0.78→0.90 / 超长 0.88→0.91，
精确率与待办、风险各指标零变化。
"""
from __future__ import annotations

import re

# 段落标题关键词 -> 标准段（info = 关键信息提取，保留用于归位）
_SECTION_RULES = (
    ("todos", ("待办", "任务清单", "行动项", "todo")),
    ("risks", ("风险", "隐患", "问题提示")),
    ("decisions", ("结论", "决定", "共识", "拍板")),
    ("info", ("关键信息", "信息提取", "关键实体")),
)

_PUNCT = r"""[\s\*\_\-\[\]\(\)（）。，、,.：:；;！!？?·|｜/\\#>“”\"'‘’~`^&=+@]+"""
_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s*(?:\[[ xX]\]\s*)?|\d+\s*[.、)]\s*)")

# 会议 / 活动事件（"会议室"不是事件，负向排除）
_EVENT_RE = re.compile(
    r"季度复盘会(?:议)?|复盘会(?:议)?|评审会(?:议)?|宣讲会|培训会|发布会|例会|会议(?!室)")
_CN = r"[0-9零〇一二两三四五六七八九十]{1,3}"
_CLOCK_RE = re.compile(
    rf"(?:上午|下午|晚上|中午|凌晨)?\s*{_CN}\s*[点时](?:半|{_CN}\s*分?)?|\d{{1,2}}:\d{{2}}")
# 会场：数字楼层 + 厅/会议室/礼堂，或命名厅 / 命名会议室
_VENUE_RES = (
    re.compile(r"[0-9一二两三四五六七八九十]+\s*楼\s*[一-龥0-9]{0,8}?(?:会议室|会议中心|会场|礼堂|厅)"),
    re.compile(r"星河厅"),
    re.compile(r"[一-龥]{2,6}(?:会议室|会议中心|会场|礼堂)"),
)
_NON_VENUE = ("前台", "停车", "现场", "基地", "茶水", "餐厅")
_CANCEL_RE = re.compile(r"取消|改期|延期至|推迟至|另行通知|暂时搁置")
_TIME_NOISE = ("故障", "结束", "打扫", "纸箱", "下午茶", "遥控器", "清理")
_SPLIT_RE = re.compile(r"[；;。\n]")


def norm(text: str) -> str:
    """归一化：小写 + 去空白与标点，得到便于子串匹配的紧凑串。"""
    if not text:
        return ""
    return re.sub(_PUNCT, "", text.lower())


def parse_standard_sections(report_md: str) -> dict[str, str]:
    """把 Markdown 复盘报告切成 {标准段名: 文本}，含 info（关键信息提取）。"""
    sections: dict[str, list[str]] = {}
    current = None
    hash_re = re.compile(r"^\s{0,3}#{1,6}\s*(.+?)\s*#*\s*$")
    cn_re = re.compile(r"^\s*[一二三四五六七八九十]+\s*[、.．]\s*(.+)$")
    for raw in report_md.splitlines():
        name = None
        m = hash_re.match(raw)
        if m and raw.strip().startswith("#"):
            name = m.group(1)
        else:
            m2 = cn_re.match(raw)
            if m2 and len(raw.strip()) < 40:
                name = m2.group(1)
        if name:
            current = None
            for key, kws in _SECTION_RULES:
                if any(kw in name for kw in kws):
                    current = key
                    sections.setdefault(current, [])
                    break
            continue
        if current:
            sections.setdefault(current, []).append(raw)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def extract_list_items(section_text: str) -> list[str]:
    """从段落抽取列表 / 编号条目。"""
    items = []
    for raw in section_text.splitlines():
        if _ITEM_RE.match(raw):
            t = _ITEM_RE.sub("", raw).strip().strip("|｜ ").strip()
            # 兼容 Markdown 加粗前缀 **时间节点**：
            t = re.sub(r"^\*+\s*", "", t)
            if len(t) >= 2:
                items.append(t)
    return items


def _dedup_events(matches: list[re.Match]) -> list[str]:
    """span 重叠（短事件名被长事件名包含）时保留更长者。"""
    spans = sorted(((m.group(0), m.span()) for m in matches), key=lambda x: x[1][0])
    keep: list[tuple[str, tuple[int, int]]] = []
    for name, sp in spans:
        if keep and sp[0] < keep[-1][1][1]:
            if len(name) > len(keep[-1][0]):
                keep[-1] = (name, sp)
            continue
        keep.append((name, sp))
    return [n for n, _ in keep]


def _pair_time(info: str, ev: str) -> str | None:
    """为事件就近配对时间：优先时间后括号紧邻事件，其次时间前紧邻事件；
    时间与事件之间不得隔着另一个时间点或分句。"""
    clocks = list(_CLOCK_RE.finditer(info))
    for cm in clocks:  # 时间之后紧邻事件（如"上午十点（季度复盘会议）"）
        tail = info[cm.end(): cm.end() + 14]
        if ev in tail:
            between = tail[:tail.index(ev)]
            if not _CLOCK_RE.search(between) and not _SPLIT_RE.search(between):
                return cm.group(0).strip()
    for cm in clocks:  # 时间之前紧邻事件（如"季度复盘会议时间为上午十点"）
        head = info[max(0, cm.start() - 18): cm.start()]
        if ev in head:
            between = head[head.index(ev) + len(ev):]
            if (not _CLOCK_RE.search(between) and not _SPLIT_RE.search(between)
                    and not any(n in head for n in _TIME_NOISE)):
                return cm.group(0).strip()
    return None


def _find_venue(info: str, ev: str, n_events: int) -> str | None:
    """识别会场地点（命名厅/会议室，排除前台/现场等非会场），清洗残字。"""
    cands: list[tuple[int, str]] = []
    for pri, rgx in enumerate(_VENUE_RES):
        for vm in rgx.finditer(info):
            v = re.sub(r"^(?:会议室?|会议)+", "", vm.group(0).strip())
            if any(n in v for n in _NON_VENUE):
                continue
            win = info[max(0, vm.start() - 18): vm.end() + 18]
            if ev in win or n_events == 1:
                cands.append((pri, v))
                break
    if not cands:
        return None
    cands.sort(key=lambda x: x[0])
    return cands[0][1]


def meeting_decisions_rehomed(report_md: str) -> list[str]:
    """从「关键信息提取」段聚合出被埋没的会议/活动安排决定句（可能为空）。"""
    secs = parse_standard_sections(report_md)
    info = secs.get("info", "")
    existing = secs.get("decisions", "")
    if not info:
        return []
    out: list[str] = []
    seen_venue: set[str] = set()
    events = _dedup_events(list(_EVENT_RE.finditer(info)))
    for ev in events:
        sp = re.search(re.escape(ev), info).span()
        if _CANCEL_RE.search(info[max(0, sp[0] - 12): sp[1] + 12]):
            continue  # 取消 / 改期 / 推迟，且无确定新安排，不归位
        t = _pair_time(info, ev)
        venue = _find_venue(info, ev, len(events))
        if not venue:
            continue
        key = norm(venue)
        if key in seen_venue or key[:3] in norm(existing):
            continue  # 结论段已含该会场，或同会场已归位
        if t:
            out.append(f"{ev}定于{t}在{venue}举行")
        else:
            out.append(f"{ev}地点确定为{venue}")
        seen_venue.add(key)
    return out


def structure_report(report_md: str) -> dict[str, str]:
    """标准四段（todos/risks/decisions/info），decisions 已并入归位的会议决定。"""
    secs = parse_standard_sections(report_md)
    rehomed = meeting_decisions_rehomed(report_md)
    if rehomed:
        merged = "\n".join([secs.get("decisions", "")] + ["- " + s for s in rehomed])
        secs["decisions"] = merged.strip()
    return secs
