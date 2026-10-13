"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { cn, StatusDot } from "./ui";
import {
  LogoM,
  IconReview,
  IconLayers,
  IconQA,
  IconMic,
  IconTodo,
  IconHistory,
  IconCpu,
} from "./icons";

const NAV = [
  { href: "/", label: "导入与复盘", Icon: IconReview },
  { href: "/batch", label: "批量复盘", Icon: IconLayers },
  { href: "/qa", label: "对话问答", Icon: IconQA },
  { href: "/voice", label: "语音复盘", Icon: IconMic },
  { href: "/action", label: "行动项", Icon: IconTodo },
  { href: "/history", label: "历史记录", Icon: IconHistory },
  { href: "/models", label: "模型管理", Icon: IconCpu },
];

export function Sidebar() {
  const pathname = usePathname();
  const [model, setModel] = useState("端侧模型");

  useEffect(() => {
    getJSON<{ selected_model?: string }>("/api/models/config")
      .then((c) => c.selected_model && setModel(c.selected_model))
      .catch(() => {});
  }, []);

  return (
    <aside className="z-10 flex w-60 shrink-0 flex-col border-r border-slate-200/80 bg-white">
      {/* 品牌 */}
      <div className="flex h-16 items-center gap-2.5 px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-glow">
          <LogoM className="h-5 w-5" />
        </div>
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight text-slate-900">
            Memora
          </div>
          <div className="text-[10px] text-slate-400">端侧对话复盘</div>
        </div>
      </div>

      {/* 导航 */}
      <nav className="flex-1 space-y-1 px-3 py-2">
        {NAV.map(({ href, label, Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "group relative flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-all",
                active
                  ? "bg-brand-50 font-medium text-brand-700"
                  : "text-slate-500 hover:bg-slate-100 hover:text-slate-800",
              )}
            >
              {active && (
                <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-brand-500" />
              )}
              <Icon
                className={cn(
                  "h-[18px] w-[18px] shrink-0 transition-colors",
                  active
                    ? "text-brand-600"
                    : "text-slate-400 group-hover:text-slate-600",
                )}
              />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* 离线状态卡 */}
      <div className="p-3">
        <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-700">
            <StatusDot tone="green" pulse />
            <span>完全离线 · 零上传</span>
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-400">
            <IconCpu className="h-3.5 w-3.5" />
            <span className="truncate">{model}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
