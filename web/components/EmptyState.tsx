import type { ReactNode } from "react";
import { IconReview } from "./icons";

export function EmptyState({
  text = "请先导入对话内容",
  title = "还没有内容",
  icon,
}: {
  text?: string;
  title?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-card border border-dashed border-slate-300 bg-white/50 px-6 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-500">
        {icon ?? <IconReview className="h-6 w-6" />}
      </div>
      <div className="mt-3 text-sm font-medium text-slate-700">{title}</div>
      <div className="mt-1 text-xs text-slate-400">{text}</div>
    </div>
  );
}
