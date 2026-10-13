/* 16kHz mono 录音采集：AudioContext 已以 16kHz 构造，每个渲染块把样本复制后
   经 MessagePort 发给主线程（不直接 transfer 输入 buffer，避免破坏系统缓冲）。 */
class RecorderProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0]) {
      const ch = input[0];
      const copy = new Float32Array(ch.length);
      copy.set(ch);
      this.port.postMessage(copy, [copy.buffer]);
    }
    return true;
  }
}
registerProcessor("recorder-processor", RecorderProcessor);
