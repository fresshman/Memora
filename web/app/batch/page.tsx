"use client";

import { useState } from "react";
import { post, postForm } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";

export default function BatchPage() {
  const [overview, setOverview] = useState("");
  const [stats, setStats] = useState("");
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
      setStats(`共 ${res.total} 份 · 成功 ${res.success} · 失败 ${res.fail}`);
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
    <div className="flex-1 flex flex-col">
      <header className="h-14 border-b border-zinc-200 bg-white px-6 flex items-center justify-between">
        <h1 className="text-sm font-semibold">批量复盘</h1>
        <StatusBadge />
      </header>
      <div className="flex-1 overflow-auto p-6 max-w-4xl mx-auto w-full">
        <section className="mb-6">
          <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
            选择多个聊天记录文件
          </h2>
          <input
            type="file"
            multiple
            accept=".txt,.csv,.html,.htm"
            onChange={onFiles}
            className="text-sm text-zinc-500 file:mr-3 file:px-3 file:py-1.5 file:rounded-md file:border-0 file:bg-zinc-900 file:text-white file:text-sm hover:file:bg-zinc-700"
          />
          {busy && <p className="mt-3 text-sm text-zinc-500">批量复盘中…</p>}
        </section>
        {overview && (
          <section className="mb-6">
            <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
              汇总总览
              <span className="normal-case tracking-normal text-zinc-400 ml-2">
                · {stats}
              </span>
            </h2>
            <pre className="border border-zinc-200 rounded-lg bg-white p-4 text-xs text-zinc-700 whitespace-pre-wrap leading-relaxed">
              {overview}
            </pre>
            <div className="mt-3 flex gap-3">
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
        {!overview && !error && (
          <EmptyState text="请先选择一个或多个聊天记录文件" />
        )}
      </div>
    </div>
  );
}
