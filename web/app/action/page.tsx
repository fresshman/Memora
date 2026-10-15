"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader, Button, Badge, cn } from "@/components/ui";
import {
  IconBrain, IconPackage, IconRefresh, IconCheck, IconClock, IconTrash,
} from "@/components/icons";
import { getJSON, post, del, downloadZip } from "@/lib/api";

type HistoryEntry = {
  time: string; from: string; to: string; note?: string; source?: string;
};
type ActionItem = {
  id: string;
  title: string;
  owner: string;
  contact_id: string;
  due: string;
  status: string;
  status_label: string;
  overdue: boolean;
  source_meeting: string;
  source_kind: string;
  created_at: string;
  updated_at: string;
  history: HistoryEntry[];
};
type ListResponse = {
  items: ActionItem[];
  summary: { total: number; counts: Record<string, number>; overdue: number };
  owners: string[];
};

const COLUMNS = [
  { code: "open", label: "待跟进", tone: "amber" as const, dot: "bg-amber-500" },
  { code: "in_progress", label: "进行中", tone: "blue" as const, dot: "bg-sky-500" },
  { code: "done", label: "已完成", tone: "green" as const, dot: "bg-emerald-500" },
  { code: "cancelled", label: "已取消", tone: "slate" as const, dot: "bg-slate-300" },
];

const STATUS_OPTIONS = [
  ["open", "待跟进"], ["in_progress", "进行中"],
  ["done", "已完成"], ["cancelled", "已取消"],
];

function StatCard({ label, value, tone }:
  { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div className="text-[11px] text-slate-400">{label}</div>
      <div className={cn("mt-1 text-xl font-semibold tracking-tight", tone)}>
        {value}
      </div>
    </div>
  );
}

function ActionCard({ item, busy, onStatus, onDelete }: {
  item: ActionItem;
  busy: boolean;
  onStatus: (id: string, status: string) => void;
  onDelete: (id: string) => void;
}) {
  const finalCol = item.status === "done" || item.status === "cancelled";
  return (
    <div className={cn(
      "rounded-xl border bg-white p-3 shadow-sm transition-all",
      item.overdue ? "border-red-300 ring-1 ring-red-100" : "border-slate-200",
    )}>
      <div className="flex items-start gap-2">
        <div className={cn(
          "min-w-0 flex-1 text-[13px] leading-relaxed",
          finalCol ? "text-slate-400 line-through decoration-slate-300" : "text-slate-800",
        )}>
          {item.title}
        </div>
        {item.overdue && <Badge tone="red">逾期</Badge>}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {item.owner ? (
          <Badge tone={item.contact_id ? "brand" : "slate"}>{item.owner}</Badge>
        ) : (
          <Badge tone="slate">责任人未明确</Badge>
        )}
        {item.due ? (
          <Badge tone={item.overdue ? "red" : "slate"}>
            <IconClock className="h-3 w-3" />{item.due}
          </Badge>
        ) : null}
      </div>

      {item.source_meeting ? (
        <div className="mt-1.5 truncate text-[10px] text-slate-400">
          来源：{item.source_meeting}
        </div>
      ) : null}

      <div className="mt-2.5 flex items-center justify-between gap-2">
        <select
          value={item.status}
          disabled={busy}
          onChange={(e) => onStatus(item.id, e.target.value)}
          className="h-7 rounded-lg border border-slate-200 bg-white px-1.5 text-[11px] text-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
          aria-label="更新状态"
        >
          {STATUS_OPTIONS.map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        {item.status !== "done" && (
          <button
            onClick={() => onStatus(item.id, "done")}
            disabled={busy}
            className="inline-flex h-7 items-center gap-1 rounded-lg bg-emerald-50 px-2 text-[11px] font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
          >
            <IconCheck className="h-3.5 w-3.5" />完成
          </button>
        )}
        <button
          onClick={() => onDelete(item.id)}
          disabled={busy}
          title="删除"
          className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-500 disabled:opacity-50"
        >
          <IconTrash className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

export default function ActionBoardPage() {
  const [data, setData] = useState<ListResponse | null>(null);
  const [ownerFilter, setOwnerFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [thinking, setThinking] = useState("fast");
  const [exporting, setExporting] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const qs = ownerFilter ? `?owner=${encodeURIComponent(ownerFilter)}` : "";
      const d = await getJSON<ListResponse>(`/api/actions${qs}`);
      setData(d);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [ownerFilter]);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    getJSON<{ mode: string }>("/api/actions/thinking")
      .then((d) => setThinking(d.mode))
      .catch(() => {});
  }, []);

  const onStatus = useCallback(async (id: string, status: string) => {
    setBusyId(id);
    try {
      await post("/api/actions/status", { id, status });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "更新失败");
    } finally {
      setBusyId("");
    }
  }, [refresh]);

  const onDelete = useCallback(async (id: string) => {
    if (!window.confirm("确定删除这条行动项吗？")) return;
    setBusyId(id);
    try {
      await del<{ deleted: string }>(`/api/actions/${id}`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
    } finally {
      setBusyId("");
    }
  }, [refresh]);

  const toggleThinking = useCallback(async () => {
    const next = thinking === "fast" ? "deep" : "fast";
    try {
      await post("/api/actions/thinking", { mode: next });
      setThinking(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "切换失败");
    }
  }, [thinking]);

  const onExport = useCallback(async () => {
    setExporting(true);
    try {
      const ts = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      await downloadZip("/api/export/package", { title: "行动项追踪" },
        `行动项追踪_${ts}.zip`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "导出失败");
    } finally {
      setExporting(false);
    }
  }, []);

  const counts = data?.summary.counts ?? {};

  return (
    <div className="mx-auto w-full max-w-7xl px-8 py-8">
      <PageHeader
        title="行动项追踪"
        subtitle="跨会议沉淀待办，跟进责任人、时间节点与完成状态，全部本地存储"
        actions={
          <>
            <Button
              variant={thinking === "deep" ? "dark" : "outline"}
              size="sm"
              icon={<IconBrain className="h-4 w-4" />}
              onClick={toggleThinking}
            >
              {thinking === "deep" ? "深度思考中" : "快速模式"}
            </Button>
            <Button
              variant="outline" size="sm"
              icon={<IconPackage className="h-4 w-4" />}
              loading={exporting}
              onClick={onExport}
            >
              导出复盘包
            </Button>
            <Button
              variant="secondary" size="sm"
              icon={<IconRefresh className="h-4 w-4" />}
              loading={loading}
              onClick={refresh}
            >
              刷新
            </Button>
          </>
        }
      />

      {/* 统计卡 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <StatCard label="行动项总数" value={data?.summary.total ?? 0} tone="text-slate-900" />
        <StatCard label="待跟进" value={counts.open ?? 0} tone="text-amber-600" />
        <StatCard label="进行中" value={counts.in_progress ?? 0} tone="text-sky-600" />
        <StatCard label="已完成" value={counts.done ?? 0} tone="text-emerald-600" />
        <StatCard label="逾期" value={data?.summary.overdue ?? 0} tone="text-red-600" />
      </div>

      {/* 筛选 */}
      <div className="mt-5 flex items-center gap-2">
        <span className="text-xs text-slate-400">按责任人筛选：</span>
        <select
          value={ownerFilter}
          onChange={(e) => setOwnerFilter(e.target.value)}
          className="h-8 rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
        >
          <option value="">全部责任人</option>
          {data?.owners.map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </div>

      {error && (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* 看板列 */}
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {COLUMNS.map((col) => {
          const items = (data?.items ?? []).filter((i) => i.status === col.code);
          return (
            <div key={col.code} className="flex flex-col gap-2.5 rounded-2xl bg-slate-50/70 p-3">
              <div className="flex items-center gap-2 px-1">
                <span className={cn("h-2 w-2 rounded-full", col.dot)} />
                <span className="text-sm font-medium text-slate-700">{col.label}</span>
                <span className="text-xs text-slate-400">{items.length}</span>
              </div>
              {items.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-200 py-6 text-center text-[11px] text-slate-300">
                  暂无
                </div>
              ) : (
                items.map((it) => (
                  <ActionCard
                    key={it.id} item={it}
                    busy={busyId === it.id} onStatus={onStatus}
                    onDelete={onDelete}
                  />
                ))
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
