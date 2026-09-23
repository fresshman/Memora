"""LangChain 复盘智能体（MemoraAgent）。

职责：用 LangChain 把「提示词模板 → 推理后端 → 结构化输出」编排成可复用流水线。
- 一键全局复盘：一次性把完整对话（1M 上下文）喂给模型，输出四段式结构化报告。
- 对话问答：基于全量对话回答自然语言问题。
- 语音纪要：对 Whisper 转写文本生成结构化纪要（结构同复盘）。

后端通过 `get_runnable()` 注入，llama.cpp / SGLang 对上层透明。
"""
from __future__ import annotations

import re

from langchain_core.prompts import PromptTemplate

from ..backend import MemoraLLM, build_backend
from .. import config
from ..parsers import Conversation
from ..retrieval import (
    build_embedder, build_retriever, compress_conversation,
)
from ..retrieval.embedder import EmbedderUnavailable
from ..prompts.templates import (
    REVIEW_PROMPT,
    QA_PROMPT,
    TRANSCRIPT_REVIEW_PROMPT,
)
from ..report.sections import meeting_decisions_rehomed
from ..log import get_logger

log = get_logger(__name__)

_SECTION_RE = re.compile(r"^##\s*(.+)$", re.MULTILINE)


class MemoraAgent:
    def __init__(self, backend: MemoraLLM) -> None:
        self.backend = backend
        self.model_id = getattr(backend, "model_id", None)
        # 复盘/纪要给足生成长度，问答链使用更短的 MAX_TOKENS_QA
        self._review_chain = (
            PromptTemplate.from_template(REVIEW_PROMPT)
            | backend.get_runnable(max_tokens=config.MAX_TOKENS_REVIEW)
        )
        self._qa_chain = (
            PromptTemplate.from_template(QA_PROMPT)
            | backend.get_runnable(max_tokens=config.MAX_TOKENS_QA)
        )
        self._review_tpl = PromptTemplate.from_template(REVIEW_PROMPT)
        self._qa_tpl = PromptTemplate.from_template(QA_PROMPT)
        self._transcript_chain = (
            PromptTemplate.from_template(TRANSCRIPT_REVIEW_PROMPT)
            | backend.get_runnable(max_tokens=config.MAX_TOKENS_REVIEW)
        )
        # RAG embedding 后端（懒加载；短对话不启动，省内存）
        self._embedder = None
        # 评测/调试用：强制上下文策略，None=按长度自动；可选 full/rag/compressed
        self.force_context_mode: str | None = None
        self.last_context_mode: str | None = None

    @classmethod
    def from_config(cls, backend: str | None = None,
                    model_id: str | None = None) -> "MemoraAgent":
        return cls(build_backend(backend, model_id))

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

    def review(self, conv: Conversation) -> str:
        """一键全局复盘，返回 Markdown 结构化报告。"""
        text, mode = self._context(conv, None)
        self.last_context_mode = mode
        log.info("执行全局复盘：模式=%s 对话字数=%d 上下文长度=%d",
                 mode, conv.char_count, len(text))
        return self._review_chain.invoke({"conversation": text}).strip()

    def answer(self, conv: Conversation, question: str) -> str:
        """基于全部对话回答用户问题。"""
        text, mode = self._context(conv, question)
        self.last_context_mode = mode
        log.info("执行对话问答：模式=%s 问题=%s", mode, question[:50])
        return self._qa_chain.invoke(
            {"conversation": text, "question": question}
        ).strip()

    def review_stream(self, conv: Conversation):
        """流式全局复盘：先给 meta（上下文模式），再逐段 delta，最后 done（含分段）。"""
        text, mode = self._context(conv, None)
        self.last_context_mode = mode
        log.info("流式全局复盘：模式=%s 对话字数=%d 上下文长度=%d",
                 mode, conv.char_count, len(text))
        prompt = self._review_tpl.format(conversation=text)
        yield {"type": "meta", "context_mode": mode, "char_count": len(text)}
        parts: list[str] = []
        for d in self.backend.stream_complete(
                prompt, max_tokens=config.MAX_TOKENS_REVIEW):
            parts.append(d)
            yield {"type": "delta", "text": d}
        report = "".join(parts).strip()
        yield {"type": "done", "report": report,
               "sections": self.split_report(report)}

    def answer_stream(self, conv: Conversation, question: str):
        """流式问答：meta -> delta* -> done(answer)。"""
        text, mode = self._context(conv, question)
        self.last_context_mode = mode
        log.info("流式对话问答：模式=%s 问题=%s", mode, question[:50])
        prompt = self._qa_tpl.format(conversation=text, question=question)
        yield {"type": "meta", "context_mode": mode, "char_count": len(text)}
        parts: list[str] = []
        for d in self.backend.stream_complete(
                prompt, max_tokens=config.MAX_TOKENS_QA):
            parts.append(d)
            yield {"type": "delta", "text": d}
        yield {"type": "done", "answer": "".join(parts).strip()}

    def close(self) -> None:
        """释放 RAG embedding 子进程（推理后端由依赖管理层统一关闭）。"""
        if self._embedder is not None:
            try:
                self._embedder.close()
            except Exception:  # noqa: BLE001
                pass
            self._embedder = None

    def review_transcript(self, transcript: str) -> str:
        """对语音转写文本生成结构化纪要。"""
        log.info("执行语音纪要生成：转写文本长度=%d", len(transcript))
        return self._transcript_chain.invoke(
            {"conversation": transcript.strip()}
        ).strip()

    def review_transcript_stream(self, transcript: str):
        """流式语音纪要：meta -> delta* -> done(含分段)。"""
        log.info("流式语音纪要：转写文本长度=%d", len(transcript))
        tpl = PromptTemplate.from_template(TRANSCRIPT_REVIEW_PROMPT)
        prompt = tpl.format(conversation=transcript.strip())
        yield {"type": "meta"}
        parts: list[str] = []
        for d in self.backend.stream_complete(
                prompt, max_tokens=config.MAX_TOKENS_REVIEW):
            parts.append(d)
            yield {"type": "delta", "text": d}
        report = "".join(parts).strip()
        yield {"type": "done", "report": report,
               "sections": self.split_report(report)}

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
