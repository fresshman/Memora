// 空字符串 = 同源相对路径（静态导出后由 FastAPI 单端口托管，换端口也无需改配置）；
// 开发模式（npm run dev，端口 3000）由 web/.env.local 指向 http://127.0.0.1:8000。
const BASE = process.env.NEXT_PUBLIC_API_BASE || "";

export async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export type SSEEvent = { type: string; [key: string]: unknown };

/**
 * 以 SSE（text/event-stream）方式发起 POST，逐事件回调 onEvent。
 * 事件约定：meta（上下文模式等元信息）→ delta（增量文本）* →
 * done（最终结果）/ error（错误消息）。
 */
export async function postSSE(
  path: string,
  body: unknown,
  onEvent: (ev: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}));
    throw new Error(
      (err as { detail?: string }).detail || res.statusText || "流式请求失败",
    );
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const line = raw.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      try {
        onEvent(JSON.parse(payload) as SSEEvent);
      } catch {
        // 忽略半包/非 JSON 行
      }
    }
  }
}

export async function restoreRedaction(
  sessionId: string,
  text: string,
): Promise<{ text: string; restored: boolean }> {
  return post("/api/redact/restore", { session_id: sessionId, text });
}
