"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getJSON, post, postForm, postSSE, restoreRedaction } from "@/lib/api";
import { ReportCard } from "@/components/ReportCard";
import { EmptyState } from "@/components/EmptyState";
import { Button, Badge, PageHeader, StepTitle, cn } from "@/components/ui";
import {
  IconUpload,
  IconClipboard,
  IconShield,
  IconSparkles,
  IconAlert,
  IconArrowRight,
  IconCheck,
  IconEye,
  IconLock,
  IconFile,
} from "@/components/icons";

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

  function applyParse(res: ParseResult) {
    setSessionId(res.session_id);
    setPreview(res.preview);
    setMeta(`${res.source} · ${res.msg_count} 条 · ${res.char_count} 字`);
    setReport("");
    setSections({});
    setRestoredReport("");
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
            const done = ev as unknown as ReviewResult;
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

  const inputCls =
    "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

  return (
    <div className="flex-1 overflow-auto">
      <div className="mx-auto w-full max-w-4xl px-8 py-8">
        <PageHeader
          title="导入与复盘"
          subtitle="粘贴或上传聊天记录，端侧模型在本地完成结构化复盘，数据全程不出本机。"
        />

        {modelReady === false && (
          <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-card border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-start gap-3 text-sm leading-relaxed text-amber-900">
              <IconAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
              <div>
                <b>尚未就绪本地端侧模型。</b>推荐使用{" "}
                <b>Spark-X2.5-4B</b>（主力）或 <b>Spark-X2.5-1.7B</b>
                （轻量），在模型管理页一键下载，全程通过 ModelScope、下载即用。
              </div>
            </div>
            <Link
              href="/models"
              className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-slate-900 px-4 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              前往模型管理 <IconArrowRight className="h-4 w-4" />
            </Link>
          </div>
        )}

        {/* 步骤 1：导入 */}
        <section className="card p-5">
          <StepTitle n={1} title="导入对话" />
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/60 px-4 py-9 text-center transition hover:border-brand-400 hover:bg-brand-50/50">
              <input
                type="file"
                accept=".txt,.csv,.html,.htm"
                onChange={onFile}
                className="sr-only"
              />
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-soft">
                <IconUpload className="h-5 w-5" />
              </span>
              <span className="mt-3 text-sm font-medium text-slate-700">
                点击选择聊天记录文件
              </span>
              <span className="mt-1 text-xs text-slate-400">
                支持 .txt / .csv / .html，本地解析
              </span>
            </label>

            <div className="flex flex-col">
              <textarea
                value={paste}
                onChange={(e) => setPaste(e.target.value)}
                rows={6}
                className="w-full flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50/50 p-3 text-sm leading-relaxed text-slate-700 placeholder:text-slate-400 focus:border-brand-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                placeholder="或把对话内容粘贴到这里…"
              />
              <Button
                variant="secondary"
                icon={<IconClipboard className="h-4 w-4" />}
                onClick={onPaste}
                disabled={busy}
                className="mt-3 self-end"
              >
                使用粘贴内容
              </Button>
            </div>
          </div>
        </section>

        {/* 步骤 2：预览 */}
        {preview && (
          <section className="card mt-6 p-5 animate-slide-up">
            <StepTitle n={2} title="对话预览" meta={meta} />
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-50/70 p-4 font-mono text-xs leading-relaxed text-slate-600">
              {preview}
            </pre>
            {pii && Object.keys(pii).length > 0 && (
              <div className="mt-3 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3.5">
                <IconShield className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                <div className="text-xs leading-relaxed text-emerald-800">
                  <b>
                    已在本地脱敏：
                    {Object.entries(pii)
                      .map(([k, v]) => `${k} ${v}`)
                      .join("、")}
                    。
                  </b>
                  敏感信息在送入模型与本地向量索引前已替换为占位符，发言人角色化为成员
                  A/B；映射仅存本机，报告生成后可一键还原。
                </div>
              </div>
            )}
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Button
                size="lg"
                icon={<IconSparkles className="h-4 w-4" />}
                onClick={onReview}
                loading={busy}
              >
                {busy ? "正在复盘，请稍候…" : "一键全局复盘"}
              </Button>
              {busy && (
                <span className="text-xs text-slate-400">
                  首次推理需加载模型，可能需要约 1 分钟
                </span>
              )}
            </div>
          </section>
        )}

        {/* 步骤 3：报告 */}
        {report && (
          <section className="mt-6 animate-slide-up">
            <div className="mb-4 flex flex-wrap items-center gap-2.5">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
                3
              </span>
              <h2 className="text-sm font-semibold text-slate-800">
                结构化复盘报告
              </h2>
              {contextMode && (
                <Badge tone={busy ? "blue" : "brand"}>
                  {MODE_LABEL[contextMode] || contextMode}
                  {busy ? " · 生成中…" : ""}
                </Badge>
              )}
            </div>

            {restoredReport ? (
              <div>
                <div className="mb-2 flex items-center gap-3 text-xs text-amber-700">
                  <span>已在本机还原真实信息（仅当前显示，不会上传或写入加密库）</span>
                  <button
                    className="underline"
                    onClick={() => setRestoredReport("")}
                  >
                    返回脱敏视图
                  </button>
                </div>
                <pre className="whitespace-pre-wrap rounded-card border border-amber-200 bg-amber-50/40 p-5 text-sm leading-relaxed text-slate-800">
                  {restoredReport}
                </pre>
              </div>
            ) : Object.keys(sections).length > 0 ? (
              <ReportCard sections={sections} report={report} />
            ) : (
              <pre className="min-h-[140px] whitespace-pre-wrap rounded-card border border-slate-200 bg-white p-5 text-sm leading-relaxed text-slate-800">
                {report}
                {busy && (
                  <span className="animate-pulse-soft text-brand-500"> ▍</span>
                )}
              </pre>
            )}

            {Object.keys(sections).length > 0 && (
              <div className="card mt-4 flex flex-wrap items-center gap-2.5 p-4">
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="纪要名称"
                  className={cn(inputCls, "h-9.5 flex-1 min-w-[160px]")}
                />
                <Button
                  variant="outline"
                  size="sm"
                  icon={<IconEye className="h-4 w-4" />}
                  onClick={onRestore}
                >
                  还原
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<IconLock className="h-4 w-4" />}
                  onClick={onSave}
                >
                  加密保存
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  icon={<IconFile className="h-4 w-4" />}
                  onClick={() => onExport("md")}
                >
                  导出 MD
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  icon={<IconFile className="h-4 w-4" />}
                  onClick={() => onExport("pdf")}
                >
                  导出 PDF
                </Button>
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

        {!preview && !report && !error && <div className="mt-6"><EmptyState /></div>}
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
