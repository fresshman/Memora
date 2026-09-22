"""混合检索：多路语义召回 + 高置信时间线骨架 + 无向量降级。

复盘是「全局理解」任务，纯向量召回会漏掉措辞平实但关键的信息，纯规则骨架又会
被“再看看 / 等领导拍板 / 有空再弄”这类没有实质承诺的寒暄噪声稀释。因此：

- 语义路（主力）：用 8 个面向（待办/风险/决定/上线/预算/会议/供应商/变更）的
  query 分别召回、合并去重，覆盖措辞多样的真实事实；
- 骨架路（高置信）：只保留①每个话题段首末块（时间线锚点）②命中“强信号”的块——
  强信号要求出现具体的风险词/决定词/承诺词，且承诺需带明确时间，同时排除含
  “再看看/回头/晚点/等…再/有空”等未决语气的块，避免把寒暄当结论；
- 组装优先级：强信号块 ＞ 语义高相关块 ＞ 话题首末锚点，统一受字符预算约束，
  最终按时间顺序排列；
- 降级：embedding 不可用时仅用高置信骨架做结构化压缩，仍覆盖各话题段。

索引按「会话指纹 + 分块参数 + 模型」持久化到 data/index，重复复盘零重算。
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .. import config
from ..log import get_logger
from .chunker import Chunk, chunk_conversation
from .index import VectorStore
from .embedder import LlamaServerEmbedder, EmbedderUnavailable

log = get_logger(__name__)

# ---- 高置信信号词表（宁紧勿滥，避免寒暄/未决讨论被当成结论）----
RISK_TERMS = (
    "风险", "阻塞", "延期", "推迟", "延迟", "卡点", "卡住", "故障", "报错",
    "限流", "隐患", "缺货", "断供", "到期", "损坏", "受阻", "请假", "事故",
    "泄露", "中断", "变更", "回滚", "崩溃", "超时", "丢数据",
)
DECISION_TERMS = (
    "定了", "拍板", "决定", "确定", "最终", "就选", "选定", "选为", "定为",
    "定在", "就定", "确定为", "定给", "改在", "改为", "改用", "改到", "推迟到",
    "放弃", "敲定", "订好", "定好", "选了", "共识",
)
COMMIT_VERBS = (
    "负责", "我来", "我写", "我出", "我去", "我跑", "我做", "我补", "我整理",
    "跟进", "值守", "编写", "编制", "整理", "设计", "核对", "部署", "承担",
    "牵头", "盖章", "截止",
)
# 未决 / 寒暄语气：出现这些即便含信号词也不算高置信（“等领导拍板”不是决定）
UNCERTAIN_RE = re.compile(
    r"(再看看|不急|回头|晚点|后面再|往后放|暂时|有空|再评估|再细化|再讨论|"
    r"再对一下|再验证|信息还?不全|待定|看看情况|先准备材料|领导拍板|"
    r"先按当前节奏|优先级不高|再了解)")
TIME_RE = re.compile(
    r"(周[一二三四五六日天]|月底|月初|凌晨|上午|下午|晚上|中午|早上|下班前|"
    r"点前|号前|日前|明天|今天|后天|\d{1,2}\s*月\s*\d{1,2}|\d{1,2}\s*[:：]\d{2})")

# 复盘多路语义召回 query（贴近真实业务措辞，提升 bge 召回率）
REVIEW_FACETS = (
    "待办任务、行动项、谁负责什么事、负责人和截止时间 deadline",
    "风险、隐患、阻塞、延期、故障、缺货、证书到期、人员请假等问题",
    "最终做出的决定、定了拍板的结论、选定或放弃的技术方案",
    "上线发布窗口时间、凌晨值守和回滚预案安排",
    "预算、金额、报价、单价、成本是多少钱",
    "会议、会议室、时间地点安排",
    "供应商选择、采购、合同盖章、物料交付",
    "客户需求变更、工作量增加、对排期的影响",
)

_PREAMBLE = (
    "（以下为超长对话按话题时间线与相关度检索整理的片段，按时间顺序排列，"
    "已优先保留明确的结论、待办、责任人、截止时间与风险；寒暄及未决讨论可能被省略）\n"
)


@dataclass
class RagContext:
    mode: str
    context_text: str
    cited_chunks: list[Chunk] = field(default_factory=list)
    n_chunks: int = 0
    n_topics: int = 0


# 分块行前缀「[时间] 发言人：」，判定前剥掉，避免消息时间戳污染时间正则
_PREFIX_RE = re.compile(r"^\s*\[[^\]]*\]\s*[^：:]{0,24}[：:]\s*")


def _msg_is_signal(body: str) -> bool:
    """单条消息正文是否为高置信信号（具体风险/决定/承诺，且语气已确定）。"""
    if UNCERTAIN_RE.search(body):
        return False
    if any(k in body for k in RISK_TERMS):
        return True
    if any(k in body for k in DECISION_TERMS):
        return True
    if "负责" in body or "截止" in body:
        return True
    if any(v in body for v in COMMIT_VERBS) and TIME_RE.search(body):
        return True
    return False


# 复盘分面：与报告三段对应，每组配多条语义检索 query
REVIEW_FACET_GROUPS = [
    ("todo", "一、与【待办任务 / 责任人 / 截止时间】相关的记录",
     ["待办任务 行动项 谁负责 具体要做的事 截止时间 承诺完成",
      "需要跟进落实的工作 责任人 时间节点 我来 我负责"]),
    ("risk", "二、与【风险 / 阻塞 / 延期 / 故障】相关的记录",
     ["项目风险 阻塞 延期 推迟 故障 报错 缺货 限流 合同或证书到期 关键人员请假",
      "需求变更 工作量增加 排期受影响 潜在问题 履约风险"]),
    ("decision", "三、与【决定 / 结论 / 方案 / 供应商 / 时间窗口 / 预算】相关的记录",
     ["最终决定 拍板结论 选定或放弃的技术方案 供应商 单价 合同",
      "确定的上线发布时间窗口 预算金额 会议时间地点 改期"]),
]


def _signal_facets(text: str) -> set[str]:
    """返回块内消息命中的分面集合（消息级，剥离时间戳/发言人前缀）。"""
    facets: set[str] = set()
    lines = text.splitlines()
    bodies = [_PREFIX_RE.sub("", ln, count=1) for ln in lines] if len(lines) > 1 else [text]
    for body in bodies:
        if not body or UNCERTAIN_RE.search(body):
            continue
        if any(k in body for k in RISK_TERMS):
            facets.add("risk")
        if any(k in body for k in DECISION_TERMS):
            facets.add("decision")
        if ("负责" in body or "截止" in body or
                (any(v in body for v in COMMIT_VERBS) and TIME_RE.search(body))):
            facets.add("todo")
    return facets


def _has_strong_signal(text: str) -> bool:
    """块级信号：块内任一条消息（剥离时间戳/发言人前缀后）命中即算。

    关键：信号在「消息级」判定——一个分块打包了多条消息，一条未决寒暄
    不应连坐、否决同块里的真实事实；消息时间戳也不能让时间正则恒真。
    """
    lines = text.splitlines()
    if len(lines) <= 1:
        return _msg_is_signal(text)
    for line in lines:
        body = _PREFIX_RE.sub("", line, count=1)
        if body and _msg_is_signal(body):
            return True
    return False


def conversation_fingerprint(conv, max_chars: int, overlap: int,
                             gap: int, model_tag: str) -> str:
    h = hashlib.sha256()
    for m in conv.user_messages:
        h.update((m.time or "").encode("utf-8")); h.update(b"\x00")
        h.update(m.speaker.encode("utf-8")); h.update(b"\x00")
        h.update(m.text.encode("utf-8")); h.update(b"\n")
    h.update(f"|{max_chars}|{overlap}|{gap}|{model_tag}".encode("utf-8"))
    return h.hexdigest()[:16]


def _topic_anchors(chunks: list[Chunk]) -> list[Chunk]:
    """每个话题段的首末块（时间线锚点）。"""
    out: dict[str, Chunk] = {}
    by_topic: dict[int, list[Chunk]] = {}
    for c in chunks:
        by_topic.setdefault(c.topic_id, []).append(c)
    for group in by_topic.values():
        out[group[0].chunk_id] = group[0]
        if len(group) > 1:
            out[group[-1].chunk_id] = group[-1]
    return list(out.values())


def _skeleton_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """高置信骨架：强信号块 + 话题首末锚点（保持时间顺序去重）。"""
    picked: dict[str, Chunk] = {}
    for c in _topic_anchors(chunks):
        picked[c.chunk_id] = c
    for c in chunks:
        if _has_strong_signal(c.text):
            picked[c.chunk_id] = c
    return [c for c in chunks if c.chunk_id in picked]


def _fit_budget(preferred: list[Chunk], budget: int) -> list[Chunk]:
    """跨话题均匀采样，把优选块塞进字符预算（降级路径用）。"""
    ordered = sorted(preferred, key=lambda c: (c.topic_id, c.start_idx))
    total = lambda cs: sum(len(c.text) + 1 for c in cs)
    if total(ordered) <= budget:
        return ordered
    step = 2
    while step <= len(ordered):
        sampled = ordered[::step]
        if total(sampled) <= budget:
            return sampled
        step += 1
    out, used, per = [], 0, max(200, budget // max(1, len(ordered)))
    for c in ordered:
        t = c.text[:per]
        if used + len(t) > budget:
            break
        out.append(Chunk(**{**c.to_dict(), "text": t})); used += len(t) + 1
    return out


def _render(chunks: list[Chunk]) -> str:
    return "\n".join(c.text for c in chunks)


def compress_conversation(conv, char_budget: int | None = None) -> RagContext:
    """无向量降级：高置信骨架结构化压缩，覆盖所有话题段。"""
    budget = char_budget or config.RAG_CONTEXT_CHARS
    chunks = chunk_conversation(
        conv, config.RAG_CHUNK_CHARS, config.RAG_CHUNK_OVERLAP,
        config.RAG_TOPIC_GAP_MIN)
    skeleton = _skeleton_chunks(chunks)
    picked = _fit_budget(skeleton, budget - len(_PREAMBLE))
    text = _PREAMBLE + _render(picked)
    return RagContext(mode="compressed", context_text=text, cited_chunks=picked,
                      n_chunks=len(picked),
                      n_topics=len({c.topic_id for c in chunks}))


class Retriever:
    def __init__(self, conv, store: VectorStore, chunks: list[Chunk], cache_dir=None):
        self.conv = conv
        self.store = store
        self.chunks = chunks
        self.cache_dir = cache_dir
        self.n_topics = len({c.topic_id for c in chunks})

    def retrieve_review(self, embedder, char_budget: int | None = None,
                        top_k: int | None = None) -> RagContext:
        """分面分组投喂：每个抽取面单独检索并加主题标签，引导小模型逐面提取。

        强信号块允许跨面重复（保证召回），语义块全局去重（控制长度），
        最后补对话头/尾时间线锚点。
        """
        top_k = top_k or config.RAG_TOP_K
        budget = (char_budget or config.RAG_CONTEXT_CHARS) - len(_PREAMBLE)
        per_facet = int(budget * 0.28)
        anchor_budget = budget - per_facet * len(REVIEW_FACET_GROUPS)

        # 全局硬红线：强信号块设计上「宁全勿漏、可跨面重复」，真实对话强信号块很少，
        # 软预算（per_facet）即可把上下文收敛到 RAG_CONTEXT_CHARS；但若对话信号词异常
        # 密集（如危机复盘逐条都提延期/阻塞），强信号块会绕过 per_facet 无限膨胀，直接
        # 撑爆模型上下文（llama-server 400 exceed_context_size）。因此再设一条不可越过
        # 的总长度红线（锚定模型安全输入 MAX_INPUT_CHARS），强信号块也受其约束；并预留
        # 少量预算给对话头/尾时间线锚点。正常对话远低于此红线，行为不变。
        hard = config.MAX_INPUT_CHARS - len(_PREAMBLE) - 1024
        anchor_reserve = min(1500, int(hard * 0.1))
        signal_cap = hard - anchor_reserve
        global_spent = 0  # 跨面重复渲染按实际出现次数累计成本

        sig = {c.chunk_id: _signal_facets(c.text) for c in self.chunks}
        strong_ids = {cid for cid, fs in sig.items() if fs}
        anchor_ids = {c.chunk_id for c in _topic_anchors(self.chunks)}

        groups: list[tuple[str, list[Chunk]]] = []
        used_semantic: set[str] = set()
        all_chosen: set[str] = set()
        for fkey, heading, queries in REVIEW_FACET_GROUPS:
            qvecs = embedder.embed(queries)
            hits = self.store.search_many(list(qvecs), k_per_query=config.RAG_FACET_TOPK)
            fstrong = sorted(
                (c for c in self.chunks if fkey in sig.get(c.chunk_id, ())),
                key=lambda x: (x.topic_id, x.start_idx))
            chosen: dict[str, Chunk] = {}
            spent = 0

            def take(c: Chunk, allow_dup: bool) -> bool:
                nonlocal spent, global_spent
                if c.chunk_id in chosen:
                    return True
                if not allow_dup and c.chunk_id in used_semantic:
                    return False
                cost = len(c.text) + 1
                # 非强信号块受单面软预算约束（聚焦）；
                if c.chunk_id not in strong_ids and spent + cost > per_facet:
                    return False
                # 所有块（含跨面重复的强信号块）都受全局硬红线约束（绝不撑爆上下文）
                if global_spent + cost > signal_cap:
                    return False
                chosen[c.chunk_id] = c
                spent += cost
                global_spent += cost
                return True

            for c in fstrong:                      # 强信号：跨面可重复，必保
                take(c, allow_dup=True)
            for c, _score in hits:                 # 语义补充：全局去重
                if len(chosen) >= top_k:
                    break
                take(c, allow_dup=False)
            ordered = sorted(chosen.values(), key=lambda c: (c.topic_id, c.start_idx))
            groups.append((heading, ordered))
            for c in ordered:
                used_semantic.add(c.chunk_id)
                all_chosen.add(c.chunk_id)

        # 时间线锚点：头/尾交替优先（有限预算下两端都尽量保留），渲染前再按时间序排回
        anchor_pool = sorted((x for x in self.chunks if x.chunk_id in anchor_ids),
                             key=lambda x: (x.topic_id, x.start_idx))
        zigzag, seen_z = [], set()
        i, j = 0, len(anchor_pool) - 1
        while i <= j:
            for c in (anchor_pool[i], anchor_pool[j] if j != i else None):
                if c is not None and c.chunk_id not in seen_z:
                    seen_z.add(c.chunk_id)
                    zigzag.append(c)
            i += 1
            j -= 1
        anchor_chosen: list[Chunk] = []
        aspent = 0
        for c in zigzag:
            if c.chunk_id in all_chosen:
                continue
            cost = len(c.text) + 1
            if aspent + cost > anchor_budget:
                break
            if global_spent + cost > hard:  # 全局硬红线：锚点也不可越过
                break
            anchor_chosen.append(c)
            aspent += cost
            global_spent += cost
        anchor_chosen.sort(key=lambda x: (x.topic_id, x.start_idx))

        parts = [_PREAMBLE]
        for heading, ordered in groups:
            if ordered:
                parts.append(f"【{heading}】\n" + _render(ordered))
        if anchor_chosen:
            parts.append("【四、对话开头与结尾（时间线锚点）】\n" + _render(anchor_chosen))
        text = "\n".join(parts)
        cited = [c for _, gs in groups for c in gs] + anchor_chosen
        return RagContext(mode="rag", context_text=text, cited_chunks=cited,
                          n_chunks=len(all_chosen) + len(anchor_chosen),
                          n_topics=self.n_topics)

    def retrieve_qa(self, embedder, question: str, char_budget: int | None = None,
                    top_k: int | None = None) -> RagContext:
        top_k = top_k or config.RAG_TOP_K
        budget = char_budget or config.RAG_CONTEXT_CHARS
        qv = embedder.embed([question])[0]
        hits = self.store.search(qv, k=max(top_k, config.RAG_FACET_TOPK * 2))
        return self._compose(hits, budget, top_k, mode="rag")

    def _compose(self, hits, char_budget, top_k, mode) -> RagContext:
        """按 强信号 ＞ 语义高相关 ＞ 话题锚点 的优先级在预算内选块，再按时间排序。"""
        budget = char_budget - len(_PREAMBLE)
        strong = [c for c in self.chunks if _has_strong_signal(c.text)]
        anchor_ids = {c.chunk_id for c in _topic_anchors(self.chunks)}

        picked: dict[str, Chunk] = {}
        used = 0

        def feed(c: Chunk) -> bool:
            nonlocal used
            if c.chunk_id in picked:
                return True
            if used + len(c.text) + 1 > budget:
                return False
            picked[c.chunk_id] = c
            used += len(c.text) + 1
            return True

        # 1) 强信号块（时间序，必保，少而精）
        for c in sorted(strong, key=lambda x: (x.topic_id, x.start_idx)):
            feed(c)
        # 2) 语义高相关块（按检索分数）
        for c, _score in hits:
            if len(picked) >= top_k and c.chunk_id not in anchor_ids:
                break
            feed(c)
        # 3) 仍有预算则补话题首末锚点
        for c in [x for x in self.chunks if x.chunk_id in anchor_ids]:
            feed(c)

        ordered = sorted(picked.values(), key=lambda c: (c.topic_id, c.start_idx))
        text = _PREAMBLE + _render(ordered)
        return RagContext(mode=mode, context_text=text, cited_chunks=ordered,
                          n_chunks=len(ordered), n_topics=self.n_topics)


def build_embedder():
    """构造 embedding 后端；模型缺失返回 None（上层降级）。"""
    if not config.RAG_ENABLE:
        return None
    gguf = config.discover_embedding_gguf()
    if gguf is None:
        log.warning("未找到本地 embedding 模型（%s），超长对话将使用规则压缩",
                    config.EMBED_REPO)
        return None
    return LlamaServerEmbedder(gguf, model_name="bge-m3", n_ctx=config.EMBED_CTX)


def build_retriever(conv, embedder, use_cache: bool = True) -> Retriever:
    chunks = chunk_conversation(
        conv, config.RAG_CHUNK_CHARS, config.RAG_CHUNK_OVERLAP,
        config.RAG_TOPIC_GAP_MIN)
    if not chunks:
        raise ValueError("对话为空，无法建立索引")
    model_tag = str(getattr(embedder, "gguf", embedder.__class__.__name__))
    fp = conversation_fingerprint(
        conv, config.RAG_CHUNK_CHARS, config.RAG_CHUNK_OVERLAP,
        config.RAG_TOPIC_GAP_MIN, model_tag)
    cache_dir = config.RAG_INDEX_DIR / fp
    store = None
    if use_cache and (cache_dir / "vec.index").exists():
        try:
            store = VectorStore.load(cache_dir)
            log.info("命中会话向量缓存：%s", fp)
        except Exception:  # noqa: BLE001
            store = None
    if store is None:
        if embedder is None:
            raise EmbedderUnavailable("无 embedding 后端且无缓存")
        log.info("为会话建立向量索引：%d 块，%d 个话题", len(chunks),
                 len({c.topic_id for c in chunks}))
        store = VectorStore.build(chunks, embedder)
        try:
            store.save(cache_dir)
        except Exception as e:  # noqa: BLE001
            log.warning("向量索引缓存写入失败（不影响当次）：%s", e)
    return Retriever(conv, store, chunks, cache_dir)
