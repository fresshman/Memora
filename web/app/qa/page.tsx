"use client";

import { useState } from "react";
import { post, postForm, postSSE, restoreRedaction } from "@/lib/api";
import { EmptyState } from "@/components/EmptyState";
import { Button, Badge, PageHeader, StepTitle } from "@/components/ui";
import {
  IconUpload,
  IconClipboard,
  IconShield,
  IconSend,
  IconAlert,
  IconCheck,
  IconEye,
} from "@/components/icons";

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
  const [toast, setToast] = useState("");
  const [paste, setPaste] = useState("");
  const [contextMode, setContextMode] = useState("");
  const [pii, setPii] = useState<Record<string, number> | null>(null);
  const [restoredAnswer, setRestoredAnswer] = useState("");

  const MODE_LABEL: Record<string, string> = {
    full: "全量上下文",
    rag: "RAG 检索增强",
    compressed: "规则时间线压缩",
  };

  function showToast(m: string) {
    setToast(m);
    setTimeout(() => setToast(""), 3000);
  }

  function applyParse(res: ParseResult) {
    setSessionId(res.session_id);
    setMeta(`${res.source} · ${res.msg_count} 条 · ${res.char_count} 字`);
    setAnswer("");
    setRestoredAnswer("");
    setPii(res.redacted ? res.pii_stats ?? {} : null);
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      applyParse(await postForm<ParseResult>("/api/conversations/parse", form));
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
      applyParse(
        await post<ParseResult>("/api/conversations/paste", { text: paste }),
      );
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
      else showToast("该会话没有可还原的脱敏信息");
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  return (
    <div className="flex-1 overflow-auto">
      <div className="mx-auto w-full max-w-4xl px-8 py-8">
        <PageHeader
          title="对话问答"
          subtitle="基于已导入对话，端侧模型即时回答追问，长对话自动走 RAG 检索增强。"
        />

        {/* 步骤 1：导入 */}
        <section className="card p-5">
          <StepTitle n={1} title="导入对话" />
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/60 px-4 py-8 text-center transition hover:border-brand-400 hover:bg-brand-50/50">
              <input type="file" accept=".txt,.csv,.html,.htm"
                onChange={onFile} className="sr-only" />
              <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-soft">
                <IconUpload className="h-5 w-5" />
              </span>
              <span className="mt-2.5 text-sm font-medium text-slate-700">选择文件</span>
              <span className="mt-1 text-xs text-slate-400">本地解析</span>
            </label>
            <div className="flex flex-col">
              <textarea value={paste} onChange={(e) => setPaste(e.target.value)}
                rows={5}
                className="w-full flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50/50 p-3 text-sm leading-relaxed text-slate-700 placeholder:text-slate-400 focus:border-brand-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                placeholder="或粘贴对话文本…"
              />
              <Button variant="secondary" icon={<IconClipboard className="h-4 w-4" />}
                onClick={onPaste} disabled={busy} className="mt-3 self-end">
                使用粘贴内容
              </Button>
            </div>
          </div>

          {meta && (
            <div className="mt-3">
              <Badge tone="brand">已导入 · {meta}</Badge>
            </div>
          )}
          {pii && Object.keys(pii).length > 0 && (
            <div className="mt-3 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3.5">
              <IconShield className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
              <div className="text-xs leading-relaxed text-emerald-800">
                <b>已在本地脱敏：{Object.entries(pii).map(([k, v]) => `${k} ${v}`).join("、")}。</b>
                敏感信息在送入模型前已替换为占位符，映射仅存本机内存、不落盘。
              </div>
            </div>
          )}
        </section>

        {/* 步骤 2：提问 */}
        {sessionId && (
          <section className="card mt-6 p-5 animate-slide-up">
            <StepTitle n={2} title="提问" />
            <div className="flex gap-2.5">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !busy && onAsk()}
                placeholder="例如：正式上线时间定在什么时候？"
                className="h-11 flex-1 rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 text-sm text-slate-700 placeholder:text-slate-400 focus:border-brand-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
              <Button onClick={onAsk} loading={busy} icon={<IconSend className="h-4 w-4" />}>
                {busy ? "查询中" : "提问"}
              </Button>
            </div>
          </section>
        )}

        {/* 回答 */}
        {answer && (
          <section className="card mt-6 p-5 animate-slide-up">
            <div className="mb-3 flex flex-wrap items-center gap-2.5">
              <h2 className="text-sm font-semibold text-slate-800">回答</h2>
              {contextMode && (
                <Badge tone={busy ? "blue" : "brand"}>
                  {MODE_LABEL[contextMode] || contextMode}
                  {busy ? " · 生成中…" : ""}
                </Badge>
              )}
            </div>
            {restoredAnswer ? (
              <div>
                <div className="mb-2 flex items-center gap-3 text-xs text-amber-700">
                  <span>已在本机还原真实信息（仅当前显示，不会上传或保存）</span>
                  <button className="underline" onClick={() => setRestoredAnswer("")}>
                    返回脱敏视图
                  </button>
                </div>
                <pre className="whitespace-pre-wrap rounded-xl border border-amber-200 bg-amber-50/40 p-4 text-sm leading-relaxed text-slate-800">
                  {restoredAnswer}
                </pre>
              </div>
            ) : (
              <div>
                <pre className="whitespace-pre-wrap rounded-xl bg-slate-50/70 p-4 text-sm leading-relaxed text-slate-700">
                  {answer}
                  {busy && <span className="animate-pulse-soft text-brand-500"> ▍</span>}
                </pre>
                {!busy && pii && Object.keys(pii).length > 0 && (
                  <Button variant="outline" size="sm"
                    icon={<IconEye className="h-4 w-4" />}
                    onClick={onRestoreAnswer} className="mt-3">
                    还原真实信息
                  </Button>
                )}
              </div>
            )}
          </section>
        )}

        {error && (
          <div className="mt-6 flex items-start gap-3 rounded-card border border-red-200 bg-red-50 p-3.5 text-sm leading-relaxed text-red-700">
            <IconAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <span className="whitespace-pre-wrap">{error}</span>
          </div>
        )}

        {!sessionId && !error && (
          <div className="mt-6">
            <EmptyState title="还没有对话" text="请先导入对话内容再提问" />
          </div>
        )}
      </div>

      {toast && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm text-white shadow-pop animate-slide-up">
          <IconCheck className="h-4 w-4 text-brand-300" />
          {toast}
        </div>
      )}
    </div>
  );
}
