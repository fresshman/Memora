"use client";

import { useState } from "react";
import { post, postForm } from "@/lib/api";
import { EmptyState } from "@/components/EmptyState";
import { Button, Badge, PageHeader, StepTitle } from "@/components/ui";
import {
  IconLayers,
  IconFile,
  IconAlert,
  IconCheck,
} from "@/components/icons";

export default function BatchPage() {
  const [overview, setOverview] = useState("");
  const [stats, setStats] = useState({ total: 0, success: 0, fail: 0 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  function showToast(m: string) {
    setToast(m);
    setTimeout(() => setToast(""), 3000);
  }

  async function onFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      for (const f of Array.from(files)) form.append("files", f);
      const res = await postForm<{
        overview: string;
        total: number;
        success: number;
        fail: number;
      }>("/api/review/batch", form);
      setOverview(res.overview);
      setStats({ total: res.total, success: res.success, fail: res.fail });
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  async function onExport(fmt: string) {
    if (!overview) return;
    try {
      const res = await post<{ message: string }>("/api/export", {
        content: overview,
        name: "批量复盘总览",
        fmt,
      });
      showToast(res.message);
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  return (
    <div className="flex-1 overflow-auto">
      <div className="mx-auto w-full max-w-4xl px-8 py-8">
        <PageHeader
          title="批量复盘"
          subtitle="一次导入多个聊天记录，端侧模型批量处理并汇总总览，全程本地完成。"
        />

        <section className="card p-5">
          <StepTitle n={1} title="选择聊天记录文件" />
          <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/60 px-4 py-12 text-center transition hover:border-brand-400 hover:bg-brand-50/50">
            <input type="file" multiple accept=".txt,.csv,.html,.htm"
              onChange={onFiles} className="sr-only" />
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-soft">
              <IconLayers className="h-6 w-6" />
            </span>
            <span className="mt-3 text-sm font-medium text-slate-700">
              点击选择一个或多个文件
            </span>
            <span className="mt-1 text-xs text-slate-400">
              支持 .txt / .csv / .html
            </span>
          </label>
          {busy && (
            <div className="mt-4">
              <p className="mb-2 text-xs text-slate-500">批量复盘中，请稍候…</p>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                <div className="h-full w-1/3 rounded-full bg-brand-500"
                  style={{ animation: "indeterminate 1.2s ease-in-out infinite" }} />
              </div>
            </div>
          )}
        </section>

        {overview && (
          <section className="card mt-6 p-5 animate-slide-up">
            <StepTitle n={2} title="汇总总览" />
            <div className="mb-3 flex flex-wrap gap-2">
              <Badge tone="slate">共 {stats.total} 份</Badge>
              <Badge tone="green">成功 {stats.success}</Badge>
              {stats.fail > 0 && <Badge tone="red">失败 {stats.fail}</Badge>}
            </div>
            <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-xl bg-slate-50/70 p-4 font-mono text-xs leading-relaxed text-slate-600">
              {overview}
            </pre>
            <div className="mt-4 flex gap-2.5">
              <Button variant="outline" size="sm" icon={<IconFile className="h-4 w-4" />}
                onClick={() => onExport("md")}>
                导出 MD
              </Button>
              <Button variant="outline" size="sm" icon={<IconFile className="h-4 w-4" />}
                onClick={() => onExport("pdf")}>
                导出 PDF
              </Button>
            </div>
          </section>
        )}

        {error && (
          <div className="mt-6 flex items-start gap-3 rounded-card border border-red-200 bg-red-50 p-3.5 text-sm leading-relaxed text-red-700">
            <IconAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <span className="whitespace-pre-wrap">{error}</span>
          </div>
        )}

        {!overview && !error && (
          <div className="mt-6">
            <EmptyState title="还没有文件" text="请先选择一个或多个聊天记录文件"
              icon={<IconLayers className="h-6 w-6" />} />
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
