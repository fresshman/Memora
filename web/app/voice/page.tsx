"use client";

import { useState } from "react";
import { post, postForm } from "@/lib/api";
import { EmptyState } from "@/components/EmptyState";
import { Button, Badge, PageHeader, StepTitle } from "@/components/ui";
import { ReportCard } from "@/components/ReportCard";
import {
  IconMic,
  IconFile,
  IconAlert,
  IconCheck,
} from "@/components/icons";

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
    <div className="flex-1 overflow-auto">
      <div className="mx-auto w-full max-w-4xl px-8 py-8">
        <PageHeader
          title="语音复盘"
          subtitle="上传会议录音，本地转写并生成结构化纪要；语音链路需配置 whisper.cpp。"
        />

        <section className="card p-5">
          <StepTitle n={1} title="上传会议录音" />
          <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/60 px-4 py-12 text-center transition hover:border-brand-400 hover:bg-brand-50/50">
            <input type="file" accept="audio/*,.wav,.mp3,.m4a"
              onChange={onFile} className="sr-only" />
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-soft">
              <IconMic className="h-6 w-6" />
            </span>
            <span className="mt-3 text-sm font-medium text-slate-700">点击选择音频文件</span>
            <span className="mt-1 text-xs text-slate-400">.wav / .mp3 / .m4a，wav 最佳</span>
          </label>
          {busy && (
            <div className="mt-4">
              <p className="mb-2 text-xs text-slate-500">转写并生成纪要中，请稍候…</p>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                <div className="h-full w-1/3 rounded-full bg-brand-500"
                  style={{ animation: "indeterminate 1.2s ease-in-out infinite" }} />
              </div>
            </div>
          )}
        </section>

        {transcript && (
          <section className="card mt-6 p-5 animate-slide-up">
            <StepTitle n={2} title="转写文本" />
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-50/70 p-4 font-mono text-xs leading-relaxed text-slate-600">
              {transcript}
            </pre>
          </section>
        )}

        {report && (
          <section className="mt-6 animate-slide-up">
            <div className="mb-4 flex items-center gap-2.5">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
                3
              </span>
              <h2 className="text-sm font-semibold text-slate-800">语音纪要</h2>
            </div>
            <ReportCard sections={sections} report={report} />
            <div className="card mt-4 flex gap-2.5 p-4">
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

        {!transcript && !error && (
          <div className="mt-6">
            <EmptyState title="还没有音频" text="请上传音频文件（wav 最佳）"
              icon={<IconMic className="h-6 w-6" />} />
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
