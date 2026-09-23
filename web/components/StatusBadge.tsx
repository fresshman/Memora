"use client";

import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { cn, StatusDot } from "./ui";

type Tone = "green" | "red" | "slate";

export function StatusBadge() {
  const [status, setStatus] = useState("检测中…");
  const [tone, setTone] = useState<Tone>("slate");

  useEffect(() => {
    getJSON<{ status: string }>("/health")
      .then((r) => {
        setStatus(r.status);
        const s = r.status || "";
        if (/就绪|ok|ready|online/i.test(s)) setTone("green");
        else if (/未连接|失败|error|off/i.test(s)) setTone("red");
        else setTone("slate");
      })
      .catch(() => {
        setStatus("后端未连接");
        setTone("red");
      });
  }, []);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600",
      )}
    >
      <StatusDot tone={tone} pulse={tone === "green"} />
      <span className="max-w-[220px] truncate">{status}</span>
    </span>
  );
}
