"use client";

import { useEffect, useRef, useState } from "react";
import { post, getJSON, del, postForm, postSSE, downloadZip } from "@/lib/api";
import { LiveRecorder, pcmToBase64 } from "@/lib/recorder";
import { Button, PageHeader, StepTitle } from "@/components/ui";
import { ReportCard } from "@/components/ReportCard";
import {
  IconMic, IconAlert, IconCheck, IconSparkles, IconDownload, IconUsers,
  IconClock, IconFileDown, IconPencil, IconUndo, IconCheckCircle,
  IconX, IconTrash, IconBrain, IconPackage, IconRefresh,
} from "@/components/icons";

interface VSeg {
  start: number;
  end: number;
  text: string;
  speaker?: string | null;
}
interface VMeta {
  audio_name: string;
  duration_seconds: number;
  num_speakers: number;
  speech_seconds: number;
  language: string;
}
interface SpeakerInfo {
  name: string;
  embedding: number[];
  identified: boolean;
  contact_id?: string;
  score?: number;
}
interface ContactSummary {
  id: string;
  name: string;
  samples: number;
  meetings: number;
  created_at: string;
  last_met: string;
}
interface Meeting {
  meta: VMeta;
  segments: VSeg[];
  text: string;
  speakers?: SpeakerInfo[];
}
interface VStatus {
  ffmpeg: boolean;
  asr_engine: boolean;
  asr_model: boolean;
  speaker: boolean;
  asr_model_name: string;
  message: string;
}

const SPEAKER_CHIP = [
  "bg-brand-50 text-brand-700 border-brand-200",
  "bg-sky-50 text-sky-700 border-sky-200",
  "bg-amber-50 text-amber-700 border-amber-200",
  "bg-emerald-50 text-emerald-700 border-emerald-200",
  "bg-red-50 text-red-700 border-red-200",
  "bg-slate-100 text-slate-600 border-slate-200",
];
const SPEAKER_TEXT = [
  "text-brand-700", "text-sky-700", "text-amber-700",
  "text-emerald-700", "text-red-700", "text-slate-500",
];

function speakerIdx(s?: string | null): number {
  const m = /(\d+)\s*$/.exec(s || "说话人1");
  return (((m ? parseInt(m[1], 10) : 1) - 1) % SPEAKER_CHIP.length +
    SPEAKER_CHIP.length) % SPEAKER_CHIP.length;
}
function hms(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return [h, m, s].map((x) => String(x).padStart(2, "0")).join(":");
}

// 从 meta + segments 重新拼标注记录文本（与 memora/whisper/meeting.py 的 build_meeting 对齐）
function buildText(m: Meeting): string {
  const meta = m.meta;
  const lines = [
    "# 会议记录",
    "",
    `音频文件：${meta.audio_name}`,
    `总时长：${hms(meta.duration_seconds)}　识别说话人：${meta.num_speakers} 位`
      + `　有效语音：${hms(meta.speech_seconds)}　语言：${meta.language}`,
    "=".repeat(48),
    "",
  ];
  for (const s of m.segments) {
    lines.push(`[${hms(s.start)}] ${s.speaker || "说话人1"}：${s.text}`);
    lines.push("");
  }
  return lines.join("\n").trimEnd();
}

// 说话人颜色：重命名后按 colorMap 保持稳定，未登记则回退按末尾数字
function colorOf(label: string | null | undefined,
                  map: Record<string, number>): number {
  const key = label || "说话人1";
  return map[key] !== undefined ? map[key] : speakerIdx(label);
}

const ACCEPT =
  ".mp3,.wav,.m4a,.aac,.flac,.ogg,.oga,.wma,.opus,.amr,.aiff,.mp4,.webm";
const BASE = process.env.NEXT_PUBLIC_API_BASE || "";
const EXPORT_FMTS = ["md", "txt", "srt", "pdf"];

export default function VoicePage() {
  const [status, setStatus] = useState<VStatus | null>(null);
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [language, setLanguage] = useState("zh");
  const [numSpeakers, setNumSpeakers] = useState(0);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [minutes, setMinutes] = useState("");
  const [minSections, setMinSections] = useState<Record<string, string>>({});
  const [minBusy, setMinBusy] = useState(false);
  const [proofMode, setProofMode] = useState(false);
  const [colorMap, setColorMap] = useState<Record<string, number>>({});
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [contactsOpen, setContactsOpen] = useState(false);
  const [contacts, setContacts] = useState<ContactSummary[]>([]);
  const [contactsBusy, setContactsBusy] = useState(false);
  const [thinking, setThinking] = useState("");
  const [tracking, setTracking] = useState(false);
  const [packaging, setPackaging] = useState(false);
  const originalRef = useRef<Meeting | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // —— 实时录音 ——
  const [inputMode, setInputMode] = useState<"upload" | "live">("upload");
  const [recording, setRecording] = useState(false);
  const [recSeconds, setRecSeconds] = useState(0);
  const [liveSegs, setLiveSegs] = useState<VSeg[]>([]);
  const [level, setLevel] = useState(0);
  const [finalizing, setFinalizing] = useState(false);
  const recorderRef = useRef<LiveRecorder | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const liveListRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(BASE + "/api/voice/status")
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => {});
  }, []);

  useEffect(() => {
    getJSON<{ mode: string }>("/api/actions/thinking")
      .then((d) => setThinking(d.mode))
      .catch(() => {});
  }, []);

  // 实时转写列表自动滚动到底
  useEffect(() => {
    liveListRef.current?.scrollTo({
      top: liveListRef.current.scrollHeight,
    });
  }, [liveSegs]);

  // 卸载时释放麦克风 / 计时器 / WS
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      try {
        recorderRef.current?.stop();
      } catch {
        /* noop */
      }
      wsRef.current?.close();
    };
  }, []);

  function showToast(m: string) {
    setToast(m);
    setTimeout(() => setToast(""), 3000);
  }

  async function handleFile(file: File) {
    setBusy(true);
    setError("");
    setMeeting(null);
    setMinutes("");
    setMinSections({});
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("language", language);
      form.append("num_speakers", String(numSpeakers));
      const data = await postForm<Meeting>("/api/voice/transcribe", form);
      originalRef.current = structuredClone(data);
      setMeeting(data);
      setProofMode(false);
      setColorMap({});
      setRenaming(null);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) void handleFile(f);
    e.target.value = "";
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void handleFile(f);
  }

  function wsUrl(): string {
    if (BASE && /^https?:\/\//.test(BASE)) {
      const proto = BASE.startsWith("https") ? "wss:" : "ws:";
      const host = BASE.slice(BASE.indexOf("://") + 3);
      return proto + "//" + host + "/api/voice/stream";
    }
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return proto + "//" + window.location.host + "/api/voice/stream";
  }

  function cleanupRecording() {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setRecording(false);
    try {
      recorderRef.current?.stop();
    } catch {
      /* noop */
    }
    const ws = wsRef.current;
    if (ws) {
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      if (ws.readyState === WebSocket.OPEN ||
          ws.readyState === WebSocket.CONNECTING)
        ws.close();
    }
    recorderRef.current = null;
    wsRef.current = null;
    setLevel(0);
  }

  function finishLive(m: Meeting & { type: string }) {
    const rec: Meeting = { meta: m.meta, segments: m.segments, text: m.text };
    originalRef.current = structuredClone(rec);
    setMeeting(rec);
    setProofMode(false);
    setColorMap({});
    setRenaming(null);
    cleanupRecording();
    setFinalizing(false);
  }

  async function startRecording() {
    setError("");
    setMeeting(null);
    setMinutes("");
    setMinSections({});
    setLiveSegs([]);
    setRecSeconds(0);
    setFinalizing(false);
    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl());
    } catch (e) {
      setError(String((e as Error).message));
      return;
    }
    wsRef.current = ws;
    const recorder = new LiveRecorder();
    recorderRef.current = recorder;

    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === "ready") {
        recorder
          .start(
            (chunk) => {
              if (ws.readyState === WebSocket.OPEN)
                ws.send(JSON.stringify({
                  type: "chunk",
                  data: pcmToBase64(chunk),
                }));
            },
            (lv) => setLevel(lv),
          )
          .then(() => {
            setRecording(true);
            timerRef.current = setInterval(
              () => setRecSeconds((s) => s + 1),
              1000,
            );
          })
          .catch((e) => {
            setError("无法访问麦克风：" + String((e as Error).message));
            cleanupRecording();
          });
      } else if (m.type === "delta") {
        setLiveSegs((prev) => prev.concat(m.segments as VSeg[]));
      } else if (m.type === "final") {
        finishLive(m as Meeting & { type: string });
      } else if (m.type === "error") {
        setError("实时转写失败：" + String(m.message));
        cleanupRecording();
      }
    };
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "start", language }));
    };
    ws.onclose = () => {
      setRecording(false);
    };
    ws.onerror = () => {
      setError("WebSocket 连接失败，请确认后端已启动。");
      cleanupRecording();
    };
  }

  function stopRecording() {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setRecording(false);
    setFinalizing(true);
    const ws = wsRef.current;
    let rest = new Float32Array(0);
    try {
      rest = recorderRef.current?.stop() ?? rest;
    } catch {
      /* noop */
    }
    if (ws && ws.readyState === WebSocket.OPEN) {
      if (rest.length)
        ws.send(JSON.stringify({
          type: "chunk",
          data: pcmToBase64(rest),
        }));
      ws.send(JSON.stringify({ type: "stop" }));
    } else {
      setFinalizing(false);
      setError("连接已中断，未能整理记录。");
    }
  }

  async function exportMeeting(fmt: string) {
    if (!meeting) return;
    try {
      const res = await fetch(BASE + "/api/voice/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          record: meeting,
          fmt,
          name: `会议记录_${meeting.meta.audio_name}`,
        }),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error((e as { detail?: string }).detail || "导出失败");
      }
      const blob = await res.blob();
      const cd = res.headers.get("content-disposition") || "";
      const m = /filename="?([^"]+)"?/.exec(cd);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = m ? m[1] : `会议记录.${fmt}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast(`已导出 ${fmt.toUpperCase()}`);
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  async function makeMinutes() {
    if (!meeting) return;
    setMinBusy(true);
    setError("");
    setMinutes("");
    setMinSections({});
    let acc = "";
    try {
      await postSSE(
        "/api/voice/minutes/stream",
        { record_text: meeting.text },
        (ev) => {
          if (ev.type === "delta") {
            acc += String(ev.text || "");
            setMinutes(acc);
          } else if (ev.type === "done") {
            setMinutes(String(ev.report || acc));
            if (ev.sections)
              setMinSections(ev.sections as Record<string, string>);
          } else if (ev.type === "error") {
            throw new Error(String(ev.message || "纪要生成失败"));
          }
        },
      );
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setMinBusy(false);
    }
  }

  async function toggleThinking() {
    const next = thinking === "deep" ? "fast" : "deep";
    try {
      await post("/api/actions/thinking", { mode: next });
      setThinking(next);
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  async function onTrack() {
    if (!meeting) return;
    setTracking(true);
    setError("");
    try {
      const res = await post<{
        checked: number;
        updates: Array<{ changed: boolean }>;
      }>("/api/actions/track", {
        meeting_text: meeting.text,
        source_kind: "voice",
        source_meeting: meeting.meta.audio_name,
      });
      const changed = res.updates.filter((u) => u.changed).length;
      showToast(`已核对 ${res.checked} 项，更新 ${changed} 项`);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setTracking(false);
    }
  }

  async function onPackage() {
    if (!meeting) return;
    setPackaging(true);
    try {
      const ts = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      const base = meeting.meta.audio_name;
      await downloadZip("/api/export/package", {
        title: base,
        report: minutes,
        record_text: meeting.text,
        include_raw: false,
      }, `${base}_复盘包_${ts}.zip`);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setPackaging(false);
    }
  }

  // 提交新的 segments，并重拼 text（md 导出 / 纪要都依赖 text）
  function commitSegments(newSegs: VSeg[]) {
    setMeeting((prev) => {
      if (!prev) return prev;
      const next: Meeting = { ...prev, segments: newSegs };
      next.text = buildText(next);
      return next;
    });
  }

  function updateSegText(i: number, value: string) {
    if (!meeting) return;
    const segs = meeting.segments.slice();
    segs[i] = { ...segs[i], text: value };
    commitSegments(segs);
  }

  function startRename(label: string) {
    setRenaming(label);
    setRenameValue(label);
  }

  function cancelRename() {
    setRenaming(null);
  }

  function confirmRename() {
    const oldLabel = renaming;
    const newLabel = renameValue.trim();
    setRenaming(null);
    if (!oldLabel || !newLabel || newLabel === oldLabel) return;
    const used = new Set((meeting?.segments || []).map((s) => s.speaker));
    if (used.has(newLabel)) {
      showToast("该名字已被其他说话人使用");
      return;
    }
    const idx = colorOf(oldLabel, colorMap);
    setColorMap((prev) => {
      const m = { ...prev, [newLabel]: idx };
      delete m[oldLabel];
      return m;
    });
    if (meeting) {
      const segs = meeting.segments.map((s) =>
        s.speaker === oldLabel ? { ...s, speaker: newLabel } : s);
      commitSegments(segs);
    }
    // 重命名即注册：声纹写入联系人库，下次会议自动认出同一人
    const info = (meeting?.speakers || []).find((s) => s.name === oldLabel);
    if (info) {
      if (info.identified && info.contact_id) {
        post("/api/voice/contact/rename",
             { id: info.contact_id, name: newLabel }).catch(() => undefined);
      } else if (info.embedding?.length) {
        post("/api/voice/contact/register",
             { name: newLabel, embedding: info.embedding }).catch(() => undefined);
      }
    }
    showToast(`已重命名为「${newLabel}」`);
  }

  function resetEdits() {
    if (!originalRef.current) return;
    setMeeting(structuredClone(originalRef.current));
    setColorMap({});
    setRenaming(null);
    showToast("已撤销全部校对修改");
  }

  function loadContacts() {
    setContactsBusy(true);
    getJSON<{ contacts: ContactSummary[] }>("/api/voice/contacts")
      .then((d) => setContacts(d.contacts))
      .catch(() => setContacts([]))
      .finally(() => setContactsBusy(false));
  }
  function openContacts() {
    setContactsOpen(true);
    loadContacts();
  }
  function removeContact(id: string) {
    setContactsBusy(true);
    del("/api/voice/contact/" + id)
      .then(() => getJSON<{ contacts: ContactSummary[] }>("/api/voice/contacts"))
      .then((d) => setContacts(d.contacts))
      .catch(() => undefined)
      .finally(() => setContactsBusy(false));
  }
  function renameContact(id: string) {
    const cur = contacts.find((c) => c.id === id);
    const name = window.prompt("修改联系人姓名", cur?.name || "");
    if (!name || !name.trim()) return;
    setContactsBusy(true);
    post("/api/voice/contact/rename", { id, name: name.trim() })
      .then(() => getJSON<{ contacts: ContactSummary[] }>("/api/voice/contacts"))
      .then((d) => setContacts(d.contacts))
      .catch(() => undefined)
      .finally(() => setContactsBusy(false));
  }
  const componentsReady = status
    ? status.ffmpeg && status.asr_engine && status.asr_model
    : true;

  return (
    <div className="flex-1 overflow-auto">
      <div className="mx-auto w-full max-w-4xl px-8 py-8">
        <PageHeader
          title="语音会议复盘"
          subtitle="上传会议录音，本地完成转写、说话人分离与会议记录整理，可一键导出或提炼结构化纪要；全程离线、数据不出设备。"
        />
        <div className="mb-4 flex justify-end gap-2">
          <Button
            variant={thinking === "deep" ? "dark" : "ghost"} size="sm"
            icon={<IconBrain className="h-4 w-4" />}
            onClick={toggleThinking}
          >
            {thinking === "deep" ? "深度思考" : "快速模式"}
          </Button>
          <Button variant="ghost" size="sm"
            icon={<IconUsers className="h-4 w-4" />}
            onClick={openContacts}>
            联系人声纹库
          </Button>
        </div>

        {status && !componentsReady && (
          <div className="mb-6 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-800">
            <IconAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="whitespace-pre-wrap">
              语音链路尚未就绪：{status.message}
              {"\n"}请在「模型管理」页按指引下载，或参考 README 准备 ffmpeg /
              pywhispercpp / ASR 模型 / speakeronnx。
            </div>
          </div>
        )}

        {/* 导入 / 实时录音 */}
        <section className="card p-5">
          <div className="mb-5 flex items-center justify-between gap-3">
            <StepTitle n={1} title={inputMode === "upload" ? "上传会议录音" : "实时录音"} />
            <div className="inline-flex rounded-xl border border-slate-200 bg-slate-50 p-1">
              <button
                type="button"
                onClick={() => { if (!recording && !finalizing) setInputMode("upload"); }}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  inputMode === "upload"
                    ? "bg-white text-brand-700 shadow-soft"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                上传录音文件
              </button>
              <button
                type="button"
                onClick={() => { if (!recording && !finalizing) setInputMode("live"); }}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  inputMode === "live"
                    ? "bg-white text-brand-700 shadow-soft"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                实时录音
              </button>
            </div>
          </div>

          {inputMode === "upload" ? (
            <>
              <label
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-11 text-center transition ${
                  dragging
                    ? "border-brand-500 bg-brand-50/60"
                    : "border-slate-300 bg-slate-50/60 hover:border-brand-400 hover:bg-brand-50/40"
                }`}
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept={ACCEPT}
                  onChange={onPick}
                  className="sr-only"
                />
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-soft">
                  <IconMic className="h-6 w-6" />
                </span>
                <span className="mt-3 text-sm font-medium text-slate-700">
                  点击选择，或将音频拖拽到此处
                </span>
                <span className="mt-1 text-xs text-slate-400">
                  MP3 / WAV / M4A / AAC / FLAC / OGG / WMA / OPUS
                </span>
              </label>

              <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3">
                <label className="flex items-center gap-2 text-xs text-slate-500">
                  语言
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
                  >
                    <option value="zh">中文</option>
                    <option value="en">英文</option>
                    <option value="auto">自动检测</option>
                  </select>
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-500">
                  <IconUsers className="h-4 w-4 text-slate-400" />
                  参会人数
                  <input
                    type="number"
                    min={0}
                    max={8}
                    value={numSpeakers}
                    onChange={(e) =>
                      setNumSpeakers(Math.max(0, Number(e.target.value)))
                    }
                    className="w-16 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
                  />
                  <span className="text-[11px] text-slate-400">0 = 自动识别</span>
                </label>
                <span className="flex items-center gap-1.5 text-[11px] text-slate-400">
                  自动统计有效语音（能量 VAD），无需手动设置
                </span>
              </div>

              {busy && (
                <div className="mt-5">
                  <p className="mb-2 text-xs text-slate-500">
                    正在本地处理：解码 → 降噪 / 响度归一 → 语音转写 →
                    说话人分离，CPU 转写需要一些时间，请耐心等待…
                  </p>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full w-1/3 rounded-full bg-brand-500"
                      style={{
                        animation: "indeterminate 1.2s ease-in-out infinite",
                      }}
                    />
                  </div>
                </div>
              )}
            </>
          ) : (
            <>
              {!recording && !finalizing && liveSegs.length === 0 && (
                <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/60 px-4 py-10 text-center">
                  <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-soft">
                    <IconMic className="h-7 w-7" />
                  </span>
                  <p className="mt-3 text-sm font-medium text-slate-700">
                    点击下方按钮，开始实时录音
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    边说边出字，全程本地离线、数据不出设备
                  </p>
                  <div className="mt-4">
                    <Button
                      icon={<IconMic className="h-4 w-4" />}
                      onClick={() => void startRecording()}
                    >
                      开始录音
                    </Button>
                  </div>
                </div>
              )}

              {(recording || finalizing) && (
                <div>
                  <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3">
                    <span className="flex items-center gap-2">
                      <span
                        className={`h-2.5 w-2.5 rounded-full ${
                          recording ? "animate-pulse bg-red-500" : "bg-slate-300"
                        }`}
                      />
                      <span className="font-mono text-sm font-medium text-slate-700">
                        {hms(recSeconds)}
                      </span>
                    </span>
                    <span className="flex h-4 min-w-[6rem] flex-1 items-center gap-px overflow-hidden">
                      {Array.from({ length: 24 }).map((_, i) => (
                        <span
                          key={i}
                          className={`h-full w-1 rounded-sm ${
                            i < Math.min(24, Math.round(level * 200))
                              ? "bg-brand-400"
                              : "bg-slate-200"
                          }`}
                        />
                      ))}
                    </span>
                    {recording ? (
                      <Button
                        variant="primary"
                        size="sm"
                        icon={<IconCheck className="h-4 w-4" />}
                        onClick={stopRecording}
                      >
                        结束并整理
                      </Button>
                    ) : (
                      <span className="text-xs text-slate-500">
                        正在整理完整记录…
                      </span>
                    )}
                  </div>

                  <div
                    ref={liveListRef}
                    className="mt-3 max-h-80 overflow-auto rounded-xl bg-slate-50/60 px-4 py-2"
                  >
                    {liveSegs.length === 0 ? (
                      <p className="py-6 text-center text-xs text-slate-400">
                        正在聆听，请开始说话…
                      </p>
                    ) : (
                      liveSegs.map((seg, i) => {
                        const ci = speakerIdx(seg.speaker);
                        return (
                          <div key={i} className="flex gap-3 py-1.5">
                            <span
                              className={`mt-0.5 w-16 shrink-0 font-mono text-[11px] ${SPEAKER_TEXT[ci]}`}
                            >
                              {hms(seg.start)}
                            </span>
                            <span
                              className={`mt-0.5 shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${SPEAKER_CHIP[ci]}`}
                            >
                              {seg.speaker || "说话人1"}
                            </span>
                            <span className="text-sm leading-relaxed text-slate-700">
                              {seg.text}
                            </span>
                          </div>
                        );
                      })
                    )}
                  </div>

                  {finalizing && (
                    <div className="mt-3">
                      <p className="mb-2 text-xs text-slate-500">
                        录音结束，正在本地完成整体重转写与说话人精修，CPU
                        处理需要一些时间…
                      </p>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                        <div
                          className="h-full w-1/3 rounded-full bg-brand-500"
                          style={{
                            animation: "indeterminate 1.2s ease-in-out infinite",
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {!recording && !finalizing && (
                <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3">
                  <label className="flex items-center gap-2 text-xs text-slate-500">
                    语言
                    <select
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
                    >
                      <option value="zh">中文</option>
                      <option value="en">英文</option>
                      <option value="auto">自动检测</option>
                    </select>
                  </label>
                  <span className="flex items-center gap-1.5 text-[11px] text-slate-400">
                    <IconUsers className="h-4 w-4 text-slate-400" />
                    说话人实时识别，结束后自动精修，无需手动设置人数
                  </span>
                </div>
              )}
            </>
          )}
        </section>

        {/* 会议记录 */}
        {meeting && (
          <section className="card mt-6 p-5 animate-slide-up">
            <StepTitle n={2} title="会议记录" />
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
                <IconClock className="h-3.5 w-3.5 text-slate-400" />
                总时长 {hms(meeting.meta.duration_seconds)}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
                <IconUsers className="h-3.5 w-3.5 text-slate-400" />
                说话人 {meeting.meta.num_speakers} 位
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
                <IconMic className="h-3.5 w-3.5 text-slate-400" />
                有效语音 {hms(meeting.meta.speech_seconds)}
              </span>
            </div>

            <div className="mb-3 flex items-center justify-between gap-2">
              <span className="text-[11px] text-slate-400">
                {proofMode
                  ? "校对模式：点击说话人标签可重命名，直接修改每段文字"
                  : "可校对：重命名说话人、修正转写文字，再重新提炼纪要"}
              </span>
              <div className="flex shrink-0 gap-2">
                {proofMode && (
                  <Button variant="ghost" size="sm"
                    icon={<IconUndo className="h-4 w-4" />}
                    onClick={resetEdits}>
                    撤销修改
                  </Button>
                )}
                <Button variant={proofMode ? "primary" : "outline"} size="sm"
                  icon={<IconPencil className="h-4 w-4" />}
                  onClick={() => { setProofMode((v) => !v); setRenaming(null); }}>
                  {proofMode ? "完成校对" : "校对记录"}
                </Button>
              </div>
            </div>

            <div className={`max-h-[26rem] overflow-auto rounded-xl px-4 py-2 ${proofMode ? "bg-brand-50/40 ring-1 ring-brand-100" : "bg-slate-50/60"}`}>
              {meeting.segments.map((seg, i) => {
                const idx = colorOf(seg.speaker, colorMap);
                const label = seg.speaker || "说话人1";
                const isRenaming = proofMode && renaming === label;
                const isIdentified = !!meeting.speakers?.find(
                  (s) => s.name === label)?.identified;
                return (
                  <div key={i} className="flex gap-3 py-2">
                    <span className={`mt-0.5 w-16 shrink-0 font-mono text-[11px] ${SPEAKER_TEXT[idx]}`}>
                      {hms(seg.start)}
                    </span>
                    {isRenaming ? (
                      <input
                        autoFocus
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") confirmRename();
                          else if (e.key === "Escape") cancelRename();
                        }}
                        onBlur={confirmRename}
                        className="mt-0.5 h-6 w-24 shrink-0 rounded-full border border-brand-300 bg-white px-2 text-[11px] font-medium text-slate-700 outline-none"
                      />
                    ) : proofMode ? (
                      <button type="button"
                        onClick={() => startRename(label)}
                        title="点击重命名该说话人"
                        className={`mt-0.5 inline-flex items-center gap-1 shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium transition hover:ring-2 hover:ring-brand-200 ${SPEAKER_CHIP[idx]}`}>
                        {label}
                        {isIdentified && <IconCheckCircle className="h-3 w-3" />}
                      </button>
                    ) : (
                      <span className={`mt-0.5 inline-flex items-center gap-1 shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${SPEAKER_CHIP[idx]}`}>
                        {label}
                        {isIdentified && <IconCheckCircle className="h-3 w-3" />}
                      </span>
                    )}
                    {proofMode ? (
                      <textarea
                        value={seg.text}
                        onChange={(e) => updateSegText(i, e.target.value)}
                        rows={Math.max(1, Math.ceil(seg.text.length / 36))}
                        className="min-h-[2rem] flex-1 resize-y rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm leading-relaxed text-slate-700 outline-none focus:border-brand-300 focus:ring-2 focus:ring-brand-100"
                      />
                    ) : (
                      <span className="text-sm leading-relaxed text-slate-700">
                        {seg.text}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="mt-4 flex flex-wrap gap-2.5">
              {EXPORT_FMTS.map((f) => (
                <Button
                  key={f}
                  variant="outline"
                  size="sm"
                  icon={<IconFileDown className="h-4 w-4" />}
                  onClick={() => void exportMeeting(f)}
                >
                  导出 {f.toUpperCase()}
                </Button>
              ))}
            </div>
          </section>
        )}

        {/* 会议纪要 */}
        {meeting && (
          <section className="card mt-6 p-5 animate-slide-up">
            <StepTitle n={3} title="会议纪要" meta="由 Spark-X2.5 基于标注记录提炼" />
            {minutes ? (
              Object.keys(minSections).length ? (
                <ReportCard sections={minSections} report={minutes} />
              ) : (
                <pre className="whitespace-pre-wrap rounded-xl bg-slate-50/70 p-4 font-sans text-sm leading-relaxed text-slate-700">
                  {minutes}
                </pre>
              )
            ) : (
              <p className="text-xs text-slate-400">
                点击下方按钮，基于上面的标注记录提炼结论 / 待办 / 关键信息 / 风险。
              </p>
            )}
            <div className="mt-4 flex flex-wrap items-center gap-2.5">
              <Button
                icon={<IconSparkles className="h-4 w-4" />}
                loading={minBusy}
                onClick={() => void makeMinutes()}
              >
                {minutes ? "重新提炼会议纪要" : "一键提炼会议纪要"}
              </Button>
              <Button
                variant="secondary"
                icon={<IconRefresh className="h-4 w-4" />}
                loading={tracking}
                onClick={() => void onTrack()}
              >
                进展回顾
              </Button>
              <Button
                variant="outline"
                icon={<IconPackage className="h-4 w-4" />}
                loading={packaging}
                onClick={() => void onPackage()}
              >
                导出复盘包
              </Button>
            </div>
          </section>
        )}

        {error && (
          <div className="mt-6 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-3.5 text-sm leading-relaxed text-red-700">
            <IconAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <span className="whitespace-pre-wrap">{error}</span>
          </div>
        )}
      </div>

      {contactsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
          onClick={() => setContactsOpen(false)}>
          <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-800">联系人声纹库</h3>
              <button type="button" onClick={() => setContactsOpen(false)}
                className="rounded-full p-1 text-slate-400 hover:bg-slate-100">
                <IconX className="h-4 w-4" />
              </button>
            </div>
            <p className="mb-3 text-xs leading-relaxed text-slate-400">
              重命名说话人时自动注册声纹；下一场会议凭声纹自动认出同一人。纯本地存储，数据不出设备。
            </p>
            {contactsBusy ? (
              <div className="py-8 text-center text-sm text-slate-400">加载中…</div>
            ) : contacts.length === 0 ? (
              <div className="py-8 text-center text-sm text-slate-400">
                还没有联系人。在会议记录中重命名「说话人N」即可注册。
              </div>
            ) : (
              <ul className="max-h-80 divide-y divide-slate-100 overflow-auto">
                {contacts.map((c) => (
                  <li key={c.id} className="flex items-center justify-between gap-2 py-2.5">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-slate-700">{c.name}</div>
                      <div className="text-[11px] text-slate-400">
                        相遇 {c.meetings} 次 · {c.samples} 个声纹 · 最近 {c.last_met.slice(0, 10)}
                      </div>
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <button type="button" title="重命名"
                        onClick={() => renameContact(c.id)}
                        className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
                        <IconPencil className="h-4 w-4" />
                      </button>
                      <button type="button" title="删除"
                        onClick={() => removeContact(c.id)}
                        className="rounded-lg p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-500">
                        <IconTrash className="h-4 w-4" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm text-white shadow-pop animate-slide-up">
          <IconCheck className="h-4 w-4 text-brand-300" />
          {toast}
        </div>
      )}
    </div>
  );
}
