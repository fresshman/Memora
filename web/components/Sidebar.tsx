"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "导入与复盘" },
  { href: "/batch", label: "批量复盘" },
  { href: "/qa", label: "对话问答" },
  { href: "/voice", label: "语音复盘" },
  { href: "/history", label: "历史记录" },
  { href: "/models", label: "模型管理" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-zinc-200 bg-white flex flex-col">
      <div className="h-14 flex items-center px-5 border-b border-zinc-200">
        <span className="text-base font-semibold tracking-tight text-zinc-900">
          Memora
        </span>
        <span className="ml-2 text-[10px] text-zinc-400 tracking-wider">
          v0.2
        </span>
      </div>
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {NAV.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-zinc-100 text-zinc-900 font-medium"
                  : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="p-3 border-t border-zinc-200 text-xs text-zinc-400 leading-relaxed">
        离线运行 · 零上传
        <br />
        基于 Spark-X2.5-4B
      </div>
    </aside>
  );
}
