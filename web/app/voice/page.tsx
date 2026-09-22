"use client";

import { useState } from "react";
import { post, postForm } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { ReportCard } from "@/components/ReportCard";

export default function VoicePage() {
  const [transcript, setTranscript] = useState("");
  const [report, setReport] = useState("");
  const [sections, setSections] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  function showToast(m: string) {
    setToast(m);
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
      const res = await postForm<{ transcript: string; report: string }>(
        "/api/voice/transcribe",
        form
      );
      setTranscript(res.transcript);
      setReport(res.report);
      setSections({});
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  async function onExport(fmt: string) {
    if (!report) return;
    try {
      const res = await post<{ message: string }>("/api/export", {
        content: report,
        name: "语音纪要",
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
        <h1 className="text-sm font-semibold">语音复盘</h1>
        <StatusBadge />
      </header>
      <div className="flex-1 overflow-auto p-6 max-w-4xl mx-auto w-full">
        <section className="mb-6">
          <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
            上传会议录音
          </h2>
          <input
            type="file"
            accept="audio/*,.wav,.mp3,.m4a"
            onChange={onFile}
            className="text-sm text-zinc-500 file:mr-3 file:px-3 file:py-1.5 file:rounded-md file:border-0 file:bg-zinc-900 file:text-white file:text-sm hover:file:bg-zinc-700"
          />
          {busy && <p className="mt-3 text-sm text-zinc-500">转写并生成纪要中…</p>}
        </section>

        {transcript && (
          <section className="mb-6">
            <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
              转写文本
            </h2>
            <pre className="border border-zinc-200 rounded-lg bg-white p-4 text-xs text-zinc-600 whitespace-pre-wrap leading-relaxed">
              {transcript}
            </pre>
          </section>
        )}

        {report && (
          <section className="mb-6">
            <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
              语音纪要
            </h2>
            <ReportCard sections={sections} report={report} />
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
        {!transcript && !error && (
          <EmptyState text="请上传音频文件（wav 最佳）" />
        )}
      </div>
    </div>
  );
}
