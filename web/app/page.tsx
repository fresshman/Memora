"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getJSON, post, postForm, postSSE, restoreRedaction } from "@/lib/api";
import { ReportCard } from "@/components/ReportCard";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";

interface ModelInfo {
  id: string;
  name: string;
  selected: boolean;
  local_status: "ready" | "downloaded" | "missing";
}

interface ParseResult {
  session_id: string;
  source: string;
  msg_count: number;
  char_count: number;
  preview: string;
  redacted?: boolean;
  pii_stats?: Record<string, number> | null;
}
interface ReviewResult {
  report: string;
  sections: Record<string, string>;
}

export default function ReviewPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [preview, setPreview] = useState("");
  const [meta, setMeta] = useState("");
  const [report, setReport] = useState("");
  const [sections, setSections] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [paste, setPaste] = useState("");
  const [name, setName] = useState("");
  const [modelReady, setModelReady] = useState<boolean | null>(null);
  const [contextMode, setContextMode] = useState("");
  const [pii, setPii] = useState<Record<string, number> | null>(null);
  const [restoredReport, setRestoredReport] = useState("");

  const MODE_LABEL: Record<string, string> = {
    full: "全量上下文",
    rag: "RAG 检索增强",
    compressed: "规则时间线压缩",
  };

  useEffect(() => {
    getJSON<ModelInfo[]>("/api/models")
      .then((list) => {
        const sel = list.find((m) => m.selected) || list[0];
        setModelReady(!!sel && sel.local_status === "ready");
      })
      .catch(() => setModelReady(null));
  }, []);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  }

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
      setPreview(res.preview);
      setMeta(`${res.source} · ${res.msg_count} 条 · ${res.char_count} 字`);
      setReport("");
      setSections({});
      setRestoredReport("");
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
      setPreview(res.preview);
      setMeta(`${res.source} · ${res.msg_count} 条 · ${res.char_count} 字`);
      setReport("");
      setSections({});
      setRestoredReport("");
      setPii(res.redacted ? res.pii_stats ?? {} : null);
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  async function onReview() {
    if (!sessionId) return;
    setBusy(true);
    setError("");
    setReport("");
    setSections({});
    setContextMode("");
    setRestoredReport("");
    let acc = "";
    try {
      await postSSE(
        "/api/review/stream",
        { session_id: sessionId },
        (ev) => {
          if (ev.type === "meta") {
            setContextMode(String(ev.context_mode || ""));
          } else if (ev.type === "delta") {
            acc += String(ev.text || "");
            setReport(acc);
          } else if (ev.type === "done") {
            const done = ev as unknown as {
              report: string;
              sections: Record<string, string>;
            };
            acc = done.report || acc;
            setReport(acc);
            setSections(done.sections || {});
          } else if (ev.type === "error") {
            throw new Error(String(ev.message || "复盘失败"));
          }
        },
      );
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  async function onExport(fmt: string) {
    if (!report) return;
    try {
      const res = await post<{ path: string; message: string }>("/api/export", {
        content: report,
        name: name || "复盘报告",
        fmt,
      });
      showToast(res.message);
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  async function onSave() {
    if (!report) return;
    try {
      const res = await post<{ id: string; message: string }>("/api/records", {
        name: name || "未命名纪要",
        content: report,
      });
      showToast(res.message);
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  async function onRestore() {
    if (!sessionId || !report) return;
    try {
      const res = await restoreRedaction(sessionId, report);
      if (res.restored) setRestoredReport(res.text);
      else showToast("该会话没有可还原的脱敏信息");
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  return (
    <div className="flex-1 flex flex-col">
      <header className="h-14 border-b border-zinc-200 bg-white px-6 flex items-center justify-between">
        <h1 className="text-sm font-semibold">导入与复盘</h1>
        <StatusBadge />
      </header>

      <div className="flex-1 overflow-auto p-6 max-w-4xl mx-auto w-full">
        {modelReady === false && (
          <div className="mb-5 rounded-lg border border-amber-300 bg-amber-50 p-4 flex items-start justify-between gap-4 flex-wrap">
            <div className="text-sm text-amber-900 leading-relaxed">
              <b>尚未就绪本地端侧模型。</b>推荐使用{" "}
              <b>Spark-X2.5-4B</b>（主力，约 2.5GB Q4 GGUF）或{" "}
              <b>Spark-X2.5-1.7B</b>（轻量，约 1.1GB），在模型管理页点下载即可，
              全程通过 ModelScope 自动下载、下载即用，无需安装其他工具。
            </div>
            <Link
              href="/models"
              className="shrink-0 text-sm px-4 py-2 rounded-md bg-zinc-900 text-white hover:bg-zinc-700"
            >
              前往模型管理
            </Link>
          </div>
        )}
        <section className="mb-6">
          <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
            1. 导入对话
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="border border-zinc-200 rounded-lg bg-white p-4">
              <label className="block text-sm text-zinc-600 mb-2">
                上传聊天记录文件
              </label>
              <input
                type="file"
                accept=".txt,.csv,.html,.htm"
                onChange={onFile}
                className="text-sm text-zinc-500 file:mr-3 file:px-3 file:py-1.5 file:rounded-md file:border-0 file:bg-zinc-900 file:text-white file:text-sm hover:file:bg-zinc-700"
              />
            </div>
            <div className="border border-zinc-200 rounded-lg bg-white p-4">
              <label className="block text-sm text-zinc-600 mb-2">
                或粘贴对话文本
              </label>
              <textarea
                value={paste}
                onChange={(e) => setPaste(e.target.value)}
                rows={3}
                className="w-full text-sm border border-zinc-200 rounded-md p-2 resize-none"
                placeholder="把对话内容粘贴到这里…"
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
        </section>

        {preview && (
          <section className="mb-6">
            <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
              2. 对话预览
              <span className="text-zinc-400 normal-case tracking-normal ml-2">
                · {meta}
              </span>
            </h2>
            <pre className="border border-zinc-200 rounded-lg bg-white p-4 text-xs text-zinc-600 whitespace-pre-wrap leading-relaxed">
              {preview}
            </pre>
{pii && Object.keys(pii).length > 0 && (
              <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800 leading-relaxed">
                已在本地脱敏：{Object.entries(pii).map(([k, v]) => `${k} ${v}`).join("、")}
                。敏感信息在送入模型与本地向量索引前已替换为占位符，发言人角色化为成员 A/B；映射仅存本机内存、不落盘，报告生成后可在本机一键还原。
              </div>
            )}
            <button
              onClick={onReview}
              disabled={busy}
              className="mt-3 px-4 py-2 rounded-md bg-zinc-900 text-white text-sm hover:bg-zinc-700 disabled:opacity-50"
            >
              {busy ? "复盘中…" : "一键全局复盘"}
            </button>
          </section>
        )}

        {report && (
          <section className="mb-6">
            <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
              3. 结构化复盘报告
              {contextMode && (
                <span className="text-zinc-400 normal-case tracking-normal ml-2">
                  · {MODE_LABEL[contextMode] || contextMode}
                  {busy ? " · 正在生成…" : ""}
                </span>
              )}
            </h2>
            {restoredReport ? (
              <div>
                <div className="mb-2 flex items-center gap-3 text-xs text-amber-700">
                  <span>已在本机还原真实信息（仅当前显示，不会上传或写入加密库）</span>
                  <button onClick={() => setRestoredReport("")} className="underline">
                    返回脱敏视图
                  </button>
                </div>
                <pre className="border border-amber-200 rounded-lg bg-amber-50/40 p-4 text-sm text-zinc-800 whitespace-pre-wrap leading-relaxed">
                  {restoredReport}
                </pre>
              </div>
            ) : Object.keys(sections).length > 0 ? (
              <ReportCard sections={sections} report={report} />
            ) : (
              <pre className="border border-zinc-200 rounded-lg bg-white p-4 text-sm text-zinc-800 whitespace-pre-wrap leading-relaxed min-h-[120px]">
                {report}
                {busy && <span className="animate-pulse"> ▍</span>}
              </pre>
            )}
            {Object.keys(sections).length > 0 && (
            <div className="mt-4 flex items-center gap-3">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="纪要名称"
                className="text-sm border border-zinc-200 rounded-md px-3 py-1.5 flex-1"
              />
              <button
                onClick={onRestore}
                className="text-sm px-3 py-1.5 rounded-md border border-zinc-200 text-zinc-700 hover:bg-zinc-50"
              >
                还原真实信息
              </button>
              <button
                onClick={onSave}
                className="text-sm px-3 py-1.5 rounded-md border border-zinc-200 text-zinc-700 hover:bg-zinc-50"
              >
                加密保存
              </button>
              <button
                onClick={() => onExport("md")}
                className="text-sm px-3 py-1.5 rounded-md border border-zinc-200 text-zinc-700 hover:bg-zinc-50"
              >
                导出 MD
              </button>
              <button
                onClick={() => onExport("pdf")}
                className="text-sm px-3 py-1.5 rounded-md border border-zinc-200 text-zinc-700 hover:bg-zinc-50"
              >
                导出 PDF
              </button>
            </div>
            )}
          </section>
        )}

        {error && (
          <div className="border border-red-200 bg-red-50 text-red-700 text-sm rounded-md p-3">
            {error}
          </div>
        )}
        {toast && (
          <div className="fixed bottom-6 right-6 bg-zinc-900 text-white text-sm px-4 py-2 rounded-md shadow-sm">
            {toast}
          </div>
        )}
        {!preview && !report && !error && <EmptyState />}
      </div>
    </div>
  );
}
