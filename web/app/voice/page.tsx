"use client";

import { useEffect, useRef, useState } from "react";
import { postForm, postSSE } from "@/lib/api";
import { Button, PageHeader, StepTitle } from "@/components/ui";
import { ReportCard } from "@/components/ReportCard";
import {
  IconMic, IconAlert, IconCheck, IconSparkles, IconDownload, IconUsers,
  IconClock, IconFileDown,
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
interface Meeting {
  meta: VMeta;
  segments: VSeg[];
  text: string;
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
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(BASE + "/api/voice/status")
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => {});
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
      setMeeting(await postForm<Meeting>("/api/voice/transcribe", form));
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

        {/* 上传与选项 */}
        <section className="card p-5">
          <StepTitle n={1} title="上传会议录音" />
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

            <div className="max-h-[26rem] overflow-auto rounded-xl bg-slate-50/60 px-4 py-2">
              {meeting.segments.map((seg, i) => {
                const idx = speakerIdx(seg.speaker);
                return (
                  <div key={i} className="flex gap-3 py-2">
                    <span
                      className={`mt-0.5 w-16 shrink-0 font-mono text-[11px] ${SPEAKER_TEXT[idx]}`}
                    >
                      {hms(seg.start)}
                    </span>
                    <span
                      className={`mt-0.5 shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${SPEAKER_CHIP[idx]}`}
                    >
                      {seg.speaker || "说话人1"}
                    </span>
                    <span className="text-sm leading-relaxed text-slate-700">
                      {seg.text}
                    </span>
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
            <div className="mt-4">
              <Button
                icon={<IconSparkles className="h-4 w-4" />}
                loading={minBusy}
                onClick={() => void makeMinutes()}
              >
                {minutes ? "重新提炼会议纪要" : "一键提炼会议纪要"}
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

      {toast && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm text-white shadow-pop animate-slide-up">
          <IconCheck className="h-4 w-4 text-brand-300" />
          {toast}
        </div>
      )}
    </div>
  );
}
