// 端侧实时录音采集：getUserMedia + AudioWorklet，输出 16kHz mono PCM（本地离线）。
const BASE = process.env.NEXT_PUBLIC_API_BASE || "";

/** Float32 16k PCM → Int16 → base64（供 WebSocket 发送，体积减半）。 */
export function pcmToBase64(f: Float32Array): string {
  const i16 = new Int16Array(f.length);
  for (let i = 0; i < f.length; i++) {
    const s = Math.max(-1, Math.min(1, f[i]));
    i16[i] = s < 0 ? s * 32768 : s * 32767;
  }
  const bytes = new Uint8Array(i16.buffer);
  let bin = "";
  const step = 0x8000;
  for (let i = 0; i < bytes.length; i += step) {
    bin += String.fromCharCode(...bytes.subarray(i, i + step));
  }
  return btoa(bin);
}

export class LiveRecorder {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;
  private acc: number[] = [];
  private readonly CHUNK = 16000; // 每 1s 回调一块
  private onLevel?: (level: number) => void;

  async start(
    onChunk: (chunk: Float32Array) => void,
    onLevel?: (level: number) => void,
  ) {
    this.onLevel = onLevel;
    this.acc = [];
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    const Ctor =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext;
    this.ctx = new Ctor({ sampleRate: 16000 });
    await this.ctx.audioWorklet.addModule(
      BASE + "/worklets/recorder-worklet.js",
    );
    const source = this.ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.ctx, "recorder-processor");
    this.node.port.onmessage = (e: MessageEvent) => {
      const f = e.data as Float32Array;
      if (this.onLevel) {
        let sum = 0;
        for (let i = 0; i < f.length; i++) sum += f[i] * f[i];
        this.onLevel(Math.sqrt(sum / f.length));
      }
      for (let i = 0; i < f.length; i++) this.acc.push(f[i]);
      while (this.acc.length >= this.CHUNK) {
        const c = new Float32Array(this.CHUNK);
        for (let i = 0; i < this.CHUNK; i++) c[i] = this.acc[i];
        this.acc.splice(0, this.CHUNK);
        onChunk(c);
      }
    };
    source.connect(this.node); // 不连 destination，避免回放自己
  }

  /** 停止并返回不足 1s 的残余（可能为空）。 */
  stop(): Float32Array<ArrayBuffer> {
    const rest = new Float32Array(this.acc.length);
    for (let i = 0; i < this.acc.length; i++) rest[i] = this.acc[i];
    this.acc = [];
    try {
      this.node?.disconnect();
    } catch {
      /* noop */
    }
    try {
      void this.ctx?.close();
    } catch {
      /* noop */
    }
    this.stream?.getTracks().forEach((t) => t.stop());
    this.node = null;
    this.ctx = null;
    this.stream = null;
    return rest;
  }
}
