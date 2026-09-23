"use client";

import { useEffect, useState } from "react";
import { getJSON, del, post } from "@/lib/api";
import { Button, Badge, PageHeader } from "@/components/ui";
import {
  IconHistory,
  IconFile,
  IconTrash,
  IconAlert,
  IconCheck,
  IconEye,
} from "@/components/icons";

interface RecordItem {
  id: string;
  name: string;
  kind: string;
  created: string;
}

export default function HistoryPage() {
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  function showToast(m: string) {
    setToast(m);
    setTimeout(() => setToast(""), 3000);
  }

  async function refresh() {
    try {
      setRecords(await getJSON<RecordItem[]>("/api/records"));
    } catch {
      setRecords([]);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onView(id: string) {
    try {
      const r = await getJSON<{ id: string; content: string }>(
        `/api/records/${id}`
      );
      setSelected(id);
      setContent(r.content);
      setError("");
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  async function onDelete(id: string) {
    try {
      await del(`/api/records/${id}`);
      await refresh();
      if (selected === id) {
        setSelected(null);
        setContent("");
      }
      showToast("已删除");
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  async function onWipe() {
    if (!confirm("确认清空全部本地数据？此操作不可恢复。")) return;
    try {
      await del("/api/records");
      await refresh();
      setSelected(null);
      setContent("");
      showToast("已清空全部数据");
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  async function onExport(fmt: string) {
    if (!content) return;
    try {
      const res = await post<{ message: string }>("/api/export", {
        content,
        name: "历史纪要",
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
          title="历史记录"
          subtitle="本地加密保存的纪要，可回看、导出或删除；密钥与数据均在本机。"
          actions={
            records.length > 0 ? (
              <Button variant="outline" size="sm"
                className="!border-red-200 !text-red-600 hover:!bg-red-50"
                icon={<IconTrash className="h-4 w-4" />}
                onClick={onWipe}>
                一键清空
              </Button>
            ) : undefined
          }
        />

        <section className="card overflow-hidden">
          {records.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
                <IconHistory className="h-6 w-6" />
              </span>
              <div className="mt-3 text-sm font-medium text-slate-600">暂无保存的记录</div>
              <div className="mt-1 text-xs text-slate-400">复盘后点「加密保存」会出现在这里</div>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {records.map((r) => {
                const active = selected === r.id;
                return (
                  <div
                    key={r.id}
                    className={`flex items-center gap-3 px-4 py-3 transition ${
                      active ? "bg-brand-50/60" : "hover:bg-slate-50"
                    }`}
                  >
                    <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                      active ? "bg-brand-100 text-brand-600" : "bg-slate-100 text-slate-400"}`}>
                      <IconFile className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800">
                      {r.name}
                    </span>
                    {r.kind && <Badge tone="slate">{r.kind}</Badge>}
                    <span className="hidden w-28 shrink-0 text-right text-xs text-slate-400 sm:block">
                      {r.created}
                    </span>
                    <Button variant="ghost" size="sm"
                      icon={<IconEye className="h-4 w-4" />}
                      onClick={() => onView(r.id)}>
                      回看
                    </Button>
                    <Button variant="ghost" size="sm"
                      className="!text-red-500 hover:!bg-red-50"
                      icon={<IconTrash className="h-4 w-4" />}
                      onClick={() => onDelete(r.id)}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {content && (
          <section className="card mt-6 p-5 animate-slide-up">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">记录内容</h2>
            <pre className="max-h-[440px] overflow-auto whitespace-pre-wrap rounded-xl bg-slate-50/70 p-4 text-sm leading-relaxed text-slate-700">
              {content}
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
