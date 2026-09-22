"use client";

import { useState } from "react";
import { post, postForm, postSSE, restoreRedaction } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";

interface ParseResult {
  session_id: string;
  source: string;
  msg_count: number;
  char_count: number;
  preview: string;
  redacted?: boolean;
  pii_stats?: Record<string, number> | null;
}

export default function QAPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [meta, setMeta] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [paste, setPaste] = useState("");
  const [contextMode, setContextMode] = useState("");
  const [pii, setPii] = useState<Record<string, number> | null>(null);
  const [restoredAnswer, setRestoredAnswer] = useState("");

  const MODE_LABEL: Record<string, string> = {
    full: "全量上下文",
    rag: "RAG 检索增强",
    compressed: "规则时间线压缩",
  };

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await postForm<ParseResult>("/api/conversations/parse", form);
      setSessionId(res.session_id);
      setMeta(`${res.source} · ${res.msg_count} 条 · ${res.char_count} 字`);
      setAnswer("");
      setRestoredAnswer("");
      setPii(res.redacted ? res.pii_stats ?? {} : null);
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  async function onPaste() {
    if (!paste.trim()) return;
    setBusy(true);
    setError("");
    try {
      const res = await post<ParseResult>("/api/conversations/paste", {
        text: paste,
      });
      setSessionId(res.session_id);
      setMeta(`${res.source} · ${res.msg_count} 条 · ${res.char_count} 字`);
      setAnswer("");
      setRestoredAnswer("");
      setPii(res.redacted ? res.pii_stats ?? {} : null);
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  async function onAsk() {
    if (!sessionId || !question.trim()) return;
    setBusy(true);
    setError("");
    setAnswer("");
    setRestoredAnswer("");
    setContextMode("");
    let acc = "";
    try {
      await postSSE(
        "/api/qa/stream",
        { session_id: sessionId, question },
        (ev) => {
          if (ev.type === "meta") {
            setContextMode(String(ev.context_mode || ""));
          } else if (ev.type === "delta") {
            acc += String(ev.text || "");
            setAnswer(acc);
          } else if (ev.type === "done") {
            const done = ev as unknown as { answer?: string };
            setAnswer(done.answer || acc);
          } else if (ev.type === "error") {
            throw new Error(String(ev.message || "问答失败"));
          }
        },
      );
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  async function onRestoreAnswer() {
    if (!sessionId || !answer) return;
    try {
      const res = await restoreRedaction(sessionId, answer);
      if (res.restored) setRestoredAnswer(res.text);
      else setError("该会话没有可还原的脱敏信息");
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  return (
    <div className="flex-1 flex flex-col">
      <header className="h-14 border-b border-zinc-200 bg-white px-6 flex items-center justify-between">
        <h1 className="text-sm font-semibold">对话问答</h1>
        <StatusBadge />
      </header>
      <div className="flex-1 overflow-auto p-6 max-w-4xl mx-auto w-full">
        <section className="mb-6">
          <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
            1. 导入对话
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="border border-zinc-200 rounded-lg bg-white p-4">
              <input
                type="file"
                accept=".txt,.csv,.html,.htm"
                onChange={onFile}
                className="text-sm text-zinc-500 file:mr-3 file:px-3 file:py-1.5 file:rounded-md file:border-0 file:bg-zinc-900 file:text-white file:text-sm hover:file:bg-zinc-700"
              />
            </div>
            <div className="border border-zinc-200 rounded-lg bg-white p-4">
              <textarea
                value={paste}
                onChange={(e) => setPaste(e.target.value)}
                rows={2}
                className="w-full text-sm border border-zinc-200 rounded-md p-2 resize-none"
                placeholder="或粘贴对话文本…"
              />
              <button
                onClick={onPaste}
                disabled={busy}
                className="mt-2 text-sm px-3 py-1.5 rounded-md bg-zinc-100 text-zinc-700 hover:bg-zinc-200 disabled:opacity-50"
              >
                使用粘贴内容
              </button>
            </div>
          </div>
          {meta && (
            <p className="mt-2 text-xs text-zinc-400">已导入：{meta}</p>
          )}
{pii && Object.keys(pii).length > 0 && (
            <div className="mt-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800 leading-relaxed">
              已在本地脱敏：{Object.entries(pii).map(([k, v]) => `${k} ${v}`).join("、")}
              。敏感信息在送入模型与本地向量索引前已替换为占位符，发言人角色化为成员 A/B；映射仅存本机内存、不落盘。
            </div>
          )}
        </section>

        {sessionId && (
          <section className="mb-6">
            <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
              2. 提问
            </h2>
            <div className="flex gap-3">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && onAsk()}
                placeholder="例如：张三承诺什么时候交付？"
                className="flex-1 text-sm border border-zinc-200 rounded-md px-3 py-2"
              />
              <button
                onClick={onAsk}
                disabled={busy}
                className="text-sm px-4 py-2 rounded-md bg-zinc-900 text-white hover:bg-zinc-700 disabled:opacity-50"
              >
                {busy ? "查询中…" : "提问"}
              </button>
            </div>
          </section>
        )}

        {answer && (
          <section className="mb-6">
            <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
              回答
              {contextMode && (
                <span className="text-zinc-400 normal-case tracking-normal ml-2">
                  · {MODE_LABEL[contextMode] || contextMode}
                  {busy ? " · 生成中…" : ""}
                </span>
              )}
            </h2>
            {restoredAnswer ? (
              <div>
                <div className="mb-2 flex items-center gap-3 text-xs text-amber-700">
                  <span>已在本机还原真实信息（仅当前显示，不会上传或保存）</span>
                  <button onClick={() => setRestoredAnswer("")} className="underline">
                    返回脱敏视图
                  </button>
                </div>
                <pre className="border border-amber-200 rounded-lg bg-amber-50/40 p-4 text-sm text-zinc-800 whitespace-pre-wrap leading-relaxed">
                  {restoredAnswer}
                </pre>
              </div>
            ) : (
              <div>
                <pre className="border border-zinc-200 rounded-lg bg-white p-4 text-sm text-zinc-700 whitespace-pre-wrap leading-relaxed">
                  {answer}
                  {busy && <span className="animate-pulse"> ▍</span>}
                </pre>
                {!busy && answer && pii && Object.keys(pii).length > 0 && (
                  <button
                    onClick={onRestoreAnswer}
                    className="mt-2 text-sm px-3 py-1.5 rounded-md border border-zinc-200 text-zinc-700 hover:bg-zinc-50"
                  >
                    还原真实信息
                  </button>
                )}
              </div>
            )}
          </section>
        )}

        {error && (
          <div className="border border-red-200 bg-red-50 text-red-700 text-sm rounded-md p-3">
            {error}
          </div>
        )}
        {!sessionId && !error && <EmptyState text="请先导入对话内容再提问" />}
      </div>
    </div>
  );
}
