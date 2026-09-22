"use client";

import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";

export function StatusBadge() {
  const [status, setStatus] = useState("检测中…");
  useEffect(() => {
    getJSON<{ backend: string; status: string }>("/health")
      .then((r) => setStatus(r.status))
      .catch(() => setStatus("后端未连接"));
  }, []);
  return (
    <span className="text-xs text-zinc-400 truncate max-w-md">{status}</span>
  );
}
