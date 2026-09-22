"use client";

import { useEffect, useState } from "react";
import { getJSON, del, post } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

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
    <div className="flex-1 flex flex-col">
      <header className="h-14 border-b border-zinc-200 bg-white px-6 flex items-center justify-between">
        <h1 className="text-sm font-semibold">历史记录</h1>
        <StatusBadge />
      </header>
      <div className="flex-1 overflow-auto p-6 max-w-4xl mx-auto w-full">
        <section className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
              已保存记录
            </h2>
            <button
              onClick={onWipe}
              className="text-xs px-2.5 py-1 rounded-md border border-red-200 text-red-600 hover:bg-red-50"
            >
              一键清空
            </button>
          </div>
          {records.length === 0 ? (
            <div className="border border-dashed border-zinc-200 rounded-lg py-12 text-center text-sm text-zinc-400">
              暂无保存的记录
            </div>
          ) : (
            <div className="border border-zinc-200 rounded-lg bg-white divide-y divide-zinc-100">
              {records.map((r) => (
                <div
                  key={r.id}
                  className={`flex items-center px-4 py-2.5 text-sm ${
                    selected === r.id ? "bg-zinc-50" : ""
                  }`}
                >
                  <span className="flex-1 text-zinc-900">{r.name}</span>
                  <span className="text-xs text-zinc-400 w-32">{r.created}</span>
                  <button
                    onClick={() => onView(r.id)}
                    className="text-xs px-2 py-1 text-zinc-600 hover:text-zinc-900"
                  >
                    回看
                  </button>
                  <button
                    onClick={() => onDelete(r.id)}
                    className="text-xs px-2 py-1 text-red-500 hover:text-red-700 ml-2"
                  >
                    删除
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        {content && (
          <section className="mb-6">
            <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
              记录内容
            </h2>
            <pre className="border border-zinc-200 rounded-lg bg-white p-4 text-sm text-zinc-700 whitespace-pre-wrap leading-relaxed">
              {content}
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
      </div>
    </div>
  );
}
