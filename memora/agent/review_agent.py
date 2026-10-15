"""LangChain 复盘智能体（MemoraAgent）。

职责：用 LangChain 把「提示词模板 → 推理后端 → 结构化输出」编排成可复用流水线。
- 一键全局复盘：一次性把完整对话（1M 上下文）喂给模型，输出四段式结构化报告，
  并把报告里的「待办」沉淀进跨会议行动项库；
- 对话问答：基于全量对话回答自然语言问题；
- 语音纪要：对 Whisper 转写文本生成结构化纪要（结构同复盘），同样入库；
- 跨会议行动项进展回顾（track_progress）：判断本次会议是否推进/完成历史行动项。

后端通过 `get_runnable()` 注入，llama.cpp / SGLang 对上层透明；思考档位
（快速 / 深度思考）在运行时切换，无需重建后端。
"""
from __future__ import annotations

import re

from langchain_core.prompts import PromptTemplate

from ..backend import MemoraLLM, build_backend, strip_thinking
from .. import config
from .. import action_items as action_mod
from ..parsers import Conversation
from ..retrieval import (
    build_embedder, build_retriever, compress_conversation,
)
from ..retrieval.embedder import EmbedderUnavailable
from ..prompts.templates import (
    REVIEW_PROMPT,
    QA_PROMPT,
    TRANSCRIPT_REVIEW_PROMPT,
    ACTION_TRACK_PROMPT,
)
from ..report.sections import meeting_decisions_rehomed
from ..log import get_logger

log = get_logger(__name__)

_SECTION_RE = re.compile(r"^##\s*(.+)$", re.MULTILINE)


class MemoraAgent:
    def __init__(self, backend: MemoraLLM) -> None:
        self.backend = backend
        self.model_id = getattr(backend, "model_id", None)
        # 提示词模板（生成长度、思考档位在调用时按当前状态动态决定）
        self._review_tpl = PromptTemplate.from_template(REVIEW_PROMPT)
        self._qa_tpl = PromptTemplate.from_template(QA_PROMPT)
        self._transcript_tpl = PromptTemplate.from_template(TRANSCRIPT_REVIEW_PROMPT)
        # RAG embedding 后端（懒加载；短对话不启动，省内存）
        self._embedder = None
        # 评测/调试用：强制上下文策略，None=按长度自动；可选 full/rag/compressed
        self.force_context_mode: str | None = None
        self.last_context_mode: str | None = None
        # 最近一次行动项入库统计（供 UI 提示）
        self.last_action_ingest: dict = {"created": 0, "merged": 0}
        # 给行动项库注入语义判断器（模糊区间用端侧 LLM 判定，失败保守不合并）
        try:
            action_mod.attach_semantic_merger(backend)
        except Exception as e:  # noqa: BLE001
            log.warning("语义去重未接入（不影响主流程）：%s", e)

    @classmethod
    def from_config(cls, backend: str | None = None,
                    model_id: str | None = None) -> "MemoraAgent":
        return cls(build_backend(backend, model_id))

    # ------------------------------------------------------------------
    # 思考档位
    # ------------------------------------------------------------------
    def set_thinking_mode(self, mode: str) -> str:
        """切换思考档位：'fast' 快速 / 'deep' 深度思考。"""
        if mode not in ("fast", "deep"):
            raise ValueError(f"未知思考档位：{mode}")
        self.backend.set_thinking_enabled(mode == "deep")
        log.info("思考档位切换为：%s", mode)
        return mode

    def get_thinking_mode(self) -> str:
        return "deep" if self.backend.thinking_enabled else "fast"

    def _max_tokens(self, kind: str) -> int:
        """按当前思考档位给出生成长度：深度思考给足思考预算。"""
        deep = self.backend.thinking_enabled
        if kind == "review":
            return config.MAX_TOKENS_DEEP_REVIEW if deep else config.MAX_TOKENS_REVIEW
        return config.MAX_TOKENS_DEEP_QA if deep else config.MAX_TOKENS_QA

    # ------------------------------------------------------------------
    def _context(self, conv: Conversation, question: str | None = None):
        """根据对话长度选择上下文策略，返回 (文本, 模式)。

        - full：放得下窗口时全量直喂（零损耗，默认）；
        - rag：超长对话走本地 embedding + faiss 混合检索；
        - compressed：embedding 不可用时的规则时间线压缩（仍覆盖各话题段）。
        force_context_mode 可强制某一策略（评测消融用）。
        """
        forced = self.force_context_mode
        if forced == "full":
            return conv.to_prompt_text(), "full"
        if forced == "compressed":
            ctx = compress_conversation(conv, config.RAG_CONTEXT_CHARS)
            return ctx.context_text, "compressed"
        if forced == "rag":
            return self._rag_context(conv, question)
        if not config.RAG_ENABLE or conv.char_count <= config.RAG_TRIGGER_CHARS:
            return conv.to_prompt_text(), "full"
        return self._rag_context(conv, question)

    def _rag_context(self, conv: Conversation, question: str | None = None):
        budget = config.RAG_CONTEXT_CHARS
        try:
            if self._embedder is None:
                self._embedder = build_embedder()
            if self._embedder is None:
                raise EmbedderUnavailable("embedding 模型未就绪")
            retr = build_retriever(conv, self._embedder)
            if question:
                ctx = retr.retrieve_qa(self._embedder, question, budget)
            else:
                ctx = retr.retrieve_review(self._embedder, budget)
            log.info("RAG 上下文：模式=%s 块=%d 话题=%d",
                     ctx.mode, ctx.n_chunks, ctx.n_topics)
            return ctx.context_text, ctx.mode
        except Exception as e:  # noqa: BLE001
            log.warning("RAG 不可用，降级为规则压缩：%s", e)
            ctx = compress_conversation(conv, budget)
            return ctx.context_text, ctx.mode

    # ------------------------------------------------------------------
    # 行动项入库
    # ------------------------------------------------------------------
    def _ingest_report(self, report: str, source_meeting: str,
                       source_kind: str, source_session: str = "") -> dict:
        """从报告/纪要的待办段解析并入库（确定性、无额外推理）。失败不影响主流程。"""
        try:
            cands = action_mod.extract_action_candidates(report)
            if not cands:
                return {"created": 0, "merged": 0}
            stats = action_mod.get_store().ingest(
                cands, source_meeting=source_meeting or "未命名会议",
                source_kind=source_kind, source_session=source_session,
            )
            self.last_action_ingest = stats
            return stats
        except Exception as e:  # noqa: BLE001
            log.warning("行动项入库失败（不影响复盘）：%s", e)
            return {"created": 0, "merged": 0}

    # ------------------------------------------------------------------
    def review(self, conv: Conversation) -> str:
        """一键全局复盘，返回 Markdown 结构化报告（待办同步入行动项库）。"""
        text, mode = self._context(conv, None)
        self.last_context_mode = mode
        log.info("执行全局复盘：模式=%s 对话字数=%d 上下文长度=%d",
                 mode, conv.char_count, len(text))
        prompt = self._review_tpl.format(conversation=text)
        report = self.backend.complete(
            prompt, max_tokens=self._max_tokens("review")
        ).strip()
        self._ingest_report(report, conv.title, "chat")
        return report

    def answer(self, conv: Conversation, question: str) -> str:
        """基于全部对话回答用户问题。"""
        text, mode = self._context(conv, question)
        self.last_context_mode = mode
        log.info("执行对话问答：模式=%s 问题=%s", mode, question[:50])
        prompt = self._qa_tpl.format(conversation=text, question=question)
        return self.backend.complete(
            prompt, max_tokens=self._max_tokens("qa")
        ).strip()

    def review_stream(self, conv: Conversation):
        """流式全局复盘：先 meta（上下文模式），逐段 delta，最后 done（含分段+行动项）。"""
        text, mode = self._context(conv, None)
        self.last_context_mode = mode
        log.info("流式全局复盘：模式=%s 对话字数=%d 上下文长度=%d",
                 mode, conv.char_count, len(text))
        prompt = self._review_tpl.format(conversation=text)
        yield {"type": "meta", "context_mode": mode, "char_count": len(text),
               "thinking": self.get_thinking_mode()}
        parts: list[str] = []
        for d in self.backend.stream_complete(
                prompt, max_tokens=self._max_tokens("review")):
            parts.append(d)
            yield {"type": "delta", "text": d}
        report = strip_thinking("".join(parts)).strip()
        actions = self._ingest_report(report, conv.title, "chat")
        yield {"type": "done", "report": report,
               "sections": self.split_report(report), "actions": actions}

    def answer_stream(self, conv: Conversation, question: str):
        """流式问答：meta -> delta* -> done(answer)。"""
        text, mode = self._context(conv, question)
        self.last_context_mode = mode
        log.info("流式对话问答：模式=%s 问题=%s", mode, question[:50])
        prompt = self._qa_tpl.format(conversation=text, question=question)
        yield {"type": "meta", "context_mode": mode, "char_count": len(text),
               "thinking": self.get_thinking_mode()}
        parts: list[str] = []
        for d in self.backend.stream_complete(
                prompt, max_tokens=self._max_tokens("qa")):
            parts.append(d)
            yield {"type": "delta", "text": d}
        yield {"type": "done", "answer": strip_thinking("".join(parts)).strip()}

    def close(self) -> None:
        """释放 RAG embedding 子进程（推理后端由依赖管理层统一关闭）。"""
        if self._embedder is not None:
            try:
                self._embedder.close()
            except Exception:  # noqa: BLE001
                pass
            self._embedder = None

    def review_transcript(self, transcript: str) -> str:
        """对语音转写文本生成结构化纪要（待办同步入行动项库）。"""
        log.info("执行语音纪要生成：转写文本长度=%d", len(transcript))
        prompt = self._transcript_tpl.format(conversation=transcript.strip())
        report = self.backend.complete(
            prompt, max_tokens=self._max_tokens("review")
        ).strip()
        self._ingest_report(report, "语音会议", "voice")
        return report

    def review_transcript_stream(self, transcript: str):
        """流式语音纪要：meta -> delta* -> done(含分段+行动项)。"""
        log.info("流式语音纪要：转写文本长度=%d", len(transcript))
        prompt = self._transcript_tpl.format(conversation=transcript.strip())
        yield {"type": "meta", "thinking": self.get_thinking_mode()}
        parts: list[str] = []
        for d in self.backend.stream_complete(
                prompt, max_tokens=self._max_tokens("review")):
            parts.append(d)
            yield {"type": "delta", "text": d}
        report = strip_thinking("".join(parts)).strip()
        actions = self._ingest_report(report, "语音会议", "voice")
        yield {"type": "done", "report": report,
               "sections": self.split_report(report), "actions": actions}

    # ------------------------------------------------------------------
    # 跨会议行动项进展回顾
    # ------------------------------------------------------------------
    def track_progress(self, meeting_text: str, *, source_meeting: str = "",
                       source_kind: str = "chat") -> dict:
        """判断本次会议是否推进/完成历史未完成行动项，并更新状态。

        无未完成项时直接返回；进展判断使用快速模式（省算力），与当前思考档位无关。
        """
        store = action_mod.get_store()
        active = store.active_items()[:config.ACTION_TRACK_MAX]
        if not active:
            return {"checked": 0, "updates": []}
        pending_lines = [
            f"{i}. [{it.id}] {it.title}（责任人：{it.owner or '未明确'}）"
            for i, it in enumerate(active, 1)
        ]
        prompt = ACTION_TRACK_PROMPT.format(
            pending="\n".join(pending_lines), meeting=meeting_text
        )
        log.info("执行跨会议进展回顾：待核对 %d 项（来源：%s）",
                 len(active), source_meeting)
        raw = self.backend.complete(
            prompt, max_tokens=self._max_tokens("qa"), enable_thinking=False
        )
        parsed = action_mod.parse_track_output(raw, active)

        updates: list[dict] = []
        for it, new_status, note in parsed:
            if not new_status or new_status == it.status:
                updates.append({"id": it.id, "title": it.title,
                                "status": it.status, "suggested": new_status,
                                "note": note, "changed": False})
                continue
            if config.ACTION_AUTO_UPDATE:
                store.set_status(it.id, new_status, note, source=source_meeting)
                updates.append({"id": it.id, "title": it.title,
                                "status": new_status, "note": note,
                                "changed": True})
            else:
                # 仅建议：不改状态，交由用户在看板确认
                updates.append({"id": it.id, "title": it.title,
                                "status": it.status, "suggested": new_status,
                                "note": note, "changed": False})
        changed_n = sum(1 for u in updates if u["changed"])
        log.info("进展回顾完成：更新 %d 项", changed_n)
        return {"checked": len(active), "updates": updates,
                "raw": raw}

    # ------------------------------------------------------------------
    @staticmethod
    def split_report(report: str) -> dict[str, str]:
        """把复盘报告按二级标题切片，便于 UI 分块展示。

        返回 {标题文本: 内容文本}；若无标题则整体放入「报告」。
        """
        matches = list(_SECTION_RE.finditer(report))
        if not matches:
            return {"报告": report.strip()}
        out: dict[str, str] = {}
        for i, m in enumerate(matches):
            title = m.group(1).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(report)
            out[title] = report[start:end].strip()
        rehomed = meeting_decisions_rehomed(report)
        if rehomed:
            block = (
                "\n\n**※ 已定安排（系统从关键信息归位）**\n"
                + "\n".join("- " + x for x in rehomed)
            )
            tgt = next((t for t in out
                        if any(k in t for k in ("结论", "决定", "共识", "拍板"))), None)
            if tgt is not None:
                out[tgt] = out[tgt] + block
            else:
                out["核心结论（归位）"] = block.strip()
        return out
