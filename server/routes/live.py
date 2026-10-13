"""实时录音流式转写（WebSocket，本地离线、纯 CPU）。

协议（均为 JSON，音频块为 base64 编码的 16kHz / mono Int16 PCM）：
  客户端 -> {type:"start", language:"zh"}
  客户端 -> {type:"chunk", data:"<base64 int16>"}*     浏览器边录边发
  服务端 -> {type:"delta", segments:[{start,end,text,speaker}]*}  实时增量出字
  客户端 -> {type:"stop"}
  服务端 -> {type:"final", meta, segments, text}       停止后整体重转写 + 精修
  服务端 -> {type:"error", message}

设计要点（兼顾低时延与最终质量）：
  - 实时：每攒够约 3s 窗口即用「常驻 whisper 模型」转写，CAM++ 声纹与已出现
    说话人实时比对归并，快速回推（容忍窗口切词带来的小瑕疵）。
  - 最终：停止后对整场录音一次性重转写 + 整体 AHC 说话人分离（复用上传链路），
    得到连贯、不丢词、可校对/导出/提炼的完整记录。
"""
from __future__ import annotations

import base64
import time as _time

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from memora.whisper import audio, diarize
from memora.whisper.transcribe import Segment, transcribe_window
from memora.whisper.meeting import build_meeting

router = APIRouter()

SR = 16000
WINDOW_S = 3.0          # 攒够该时长即转写一个实时窗口
SIM_THR = diarize._SIM_THR


class LiveSession:
    """一次实时录音的会话状态。仅在单个 WebSocket 内使用。"""

    def __init__(self, language: str):
        self.language = "" if language in ("", "auto") else language
        self.all_pcm: list[np.ndarray] = []   # 整场录音（用于最终重转写）
        self.pending: list[np.ndarray] = []   # 尚未实时转写的音频
        self.processed_s = 0.0                # 已实时转写的秒数（全局偏移）
        # 实时说话人声纹：label -> (embedding 累加, 计数)
        self.centroids: dict[str, tuple[np.ndarray, int]] = {}

    def _pending_len_s(self) -> float:
        return sum(len(x) for x in self.pending) / SR

    def feed(self, pcm: np.ndarray) -> bool:
        """追加音频；返回是否达到窗口转写阈值。"""
        if pcm.size:
            self.all_pcm.append(pcm)
            self.pending.append(pcm)
        return self._pending_len_s() >= WINDOW_S

    def _assign(self, emb: np.ndarray) -> str:
        """把一段声纹实时归并到已出现说话人，否则新建。"""
        best_label, best_sim = None, -1.0
        for label, (s, n) in self.centroids.items():
            c = s / n
            c = c / (np.linalg.norm(c) + 1e-9)
            sim = float(np.dot(emb, c))
            if sim > best_sim:
                best_sim, best_label = sim, label
        if best_label is not None and best_sim >= SIM_THR:
            s, n = self.centroids[best_label]
            self.centroids[best_label] = (s + emb, n + 1)
            return best_label
        label = f"说话人{len(self.centroids) + 1}"
        self.centroids[label] = (emb.copy(), 1)
        return label

    def process_window(self) -> list[Segment]:
        win = np.concatenate(self.pending)
        self.pending = []
        offset = self.processed_s
        self.processed_s += len(win) / SR
        rel = transcribe_window(win, self.language, 0.0)
        if not rel:
            return []
        try:
            embedder = diarize._get_embedder()
        except Exception:  # noqa: BLE001
            embedder = None
        out: list[Segment] = []
        for seg in rel:
            label = ""
            if embedder is not None:
                a, b = int(seg.start * SR), int(seg.end * SR)
                clip = win[a:b]
                if len(clip) < int(0.3 * SR):
                    clip = win[max(0, a - int(0.2 * SR)):
                               min(len(win), b + int(0.2 * SR))]
                try:
                    label = self._assign(embedder.embed(clip))
                except Exception:  # noqa: BLE001
                    label = ""
            if not label:
                label = "说话人1"
            out.append(Segment(round(seg.start + offset, 3),
                               round(seg.end + offset, 3),
                               seg.text, label))
        return out

    def finalize(self) -> dict:
        """整场重转写 + 整体说话人精修，返回完整记录 dict。"""
        full = np.concatenate(self.all_pcm) if self.all_pcm \
            else np.zeros(0, dtype=np.float32)
        if full.size < int(0.2 * SR):
            raise RuntimeError("录音过短或未采集到声音")
        segs = transcribe_window(full, self.language, 0.0)
        if not segs:
            segs = [Segment(0.0, len(full) / SR, "（未识别到有效语音）",
                            "说话人1")]
        try:
            segs, _ = diarize.diarize(full, segs, num_speakers=0, sr=SR)
        except Exception:  # noqa: BLE001
            for s in segs:
                if not s.speaker:
                    s.speaker = "说话人1"
        speech_s = audio.speech_duration(full)
        name = _time.strftime("实时录音_%Y%m%d_%H%M%S")
        rec = build_meeting(name, len(full) / SR, speech_s,
                            self.language or "zh", segs)
        return rec.to_dict()


@router.websocket("/voice/stream")
async def voice_live_stream(ws: WebSocket):
    await ws.accept()
    sess: LiveSession | None = None
    try:
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")

            if mtype == "start":
                sess = LiveSession(str(msg.get("language", "zh")))
                await ws.send_json({"type": "ready"})

            elif mtype == "chunk":
                if sess is None:
                    continue
                raw = base64.b64decode(msg.get("data", ""))
                pcm = (np.frombuffer(raw, dtype=np.int16)
                       .astype(np.float32) / 32768.0)
                if sess.feed(pcm):
                    segs = await run_in_threadpool(sess.process_window)
                    if segs:
                        await ws.send_json({
                            "type": "delta",
                            "segments": [s.to_dict() for s in segs],
                        })

            elif mtype == "stop":
                if sess is None:
                    await ws.close()
                    return
                # 处理最后不足一个窗口的残余（实时补一段）
                if sess.pending:
                    segs = await run_in_threadpool(sess.process_window)
                    if segs:
                        await ws.send_json({
                            "type": "delta",
                            "segments": [s.to_dict() for s in segs],
                        })
                record = await run_in_threadpool(sess.finalize)
                await ws.send_json({"type": "final", **record})
                await ws.close()
                return

    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001
        try:
            await ws.send_json({"type": "error", "message": str(e)})
            await ws.close()
        except Exception:  # noqa: BLE001
            pass
