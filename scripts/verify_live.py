"""端到端真机验证：实时录音流式转写（麦克风边说边出字，结束整理为完整记录）。

Edge headless + 模拟麦克风（fake device，喂入 clear_zh.wav）+ CDP。
校验链路：
  切「实时录音」-> 开始 -> 等 WebSocket ready / 录音中
  -> 等待实时增量段（liveSegs 出现说话人 + 文本）
  -> 结束并整理 -> 等最终「会议记录」section（整体重转写）
  -> 断言含真实内容，截图保存

用法（后端已在 8000）：
  python scripts/verify_live.py
"""
from __future__ import annotations

import base64
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from cdp_shot import CDP, EDGE, PORT, wait_port

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "data/voice_test/clear_zh.wav"
SHOT = ROOT / "docs/images/10_voice_live.png"


def start_edge():
    profile = tempfile.mkdtemp(prefix="edge_live_")
    proc = subprocess.Popen([
        EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", f"--remote-debugging-port={PORT}",
        "--remote-allow-origins=*", f"--user-data-dir={profile}",
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        "--use-file-for-fake-audio-capture=" + str(AUDIO).replace("\\", "/"),
        "about:blank",
    ])
    wait_port()
    targets = json.load(urllib.request.urlopen(
        f"http://127.0.0.1:{PORT}/json/list"))
    page = next(t for t in targets if t.get("type") == "page")
    page_cdp = CDP(page["webSocketDebuggerUrl"])
    return proc, page_cdp


def click_button(c, fragment: str) -> bool:
    ok = c.eval(
        "(()=>{const b=[...document.querySelectorAll('button')]"
        ".find(x=>x.textContent.includes(%s));"
        "if(!b)return false;b.click();return true;})()" % json.dumps(fragment))
    return bool(ok)


def wait_includes(c, text: str, timeout: int) -> bool:
    t0 = time.time()
    expr = "document.body.innerText.includes(%s)" % json.dumps(text)
    while time.time() - t0 < timeout:
        if c.eval(expr):
            return True
        time.sleep(2)
    return False


_RECORD_TEXT = (
    "(()=>{const h=[...document.querySelectorAll('*')]"
    ".find(x=>x.textContent.trim()==='会议记录');"
    "const s=h?h.closest('section'):null;return s?s.innerText:'';})()")


def main():
    proc, c = start_edge()
    try:
        c.call("Page.enable")
        c.call("Emulation.setDeviceMetricsOverride", width=1440,
               height=1100, deviceScaleFactor=1, mobile=False)
        c.call("Page.navigate", url="http://127.0.0.1:8000/voice/")
        time.sleep(4)

        # 1) 切到「实时录音」
        assert click_button(c, "实时录音"), "未找到实时录音 tab"
        time.sleep(0.8)
        assert click_button(c, "开始录音"), "未找到开始录音按钮"
        print("waiting WS ready + recorder...")
        assert wait_includes(c, "结束并整理", 20), "录音未启动"
        print("recording started (mic = clear_zh.wav)")

        # 2) 固定等待 7s，让 8s 音频恰好完整播放一遍（避免 fake device 循环）
        print("waiting 7s for one full pass of audio...")
        time.sleep(7)
        live_text = c.eval(
            "(()=>{const d=document.querySelector('[class*=\"max-h-80\"]');"
            "return d?d.innerText:'';})()") or ""
        print("live preview:\n", live_text[:400])
        assert "说话人" in live_text and "正在聆听" not in live_text, \
            "实时增量段未出现"
        print("real-time deltas OK (early segments covered)")

        # 3) 结束并整理，等最终整体重转写（final 会覆盖完整末段）
        assert click_button(c, "结束并整理"), "未找到结束按钮"
        print("finalizing: 整体重转写 + 说话人精修...")
        assert wait_includes(c, "导出 MD", 150), "最终记录未在限定时间内完成"
        time.sleep(1)
        record = c.eval(_RECORD_TEXT) or ""
        print("final record:\n", record[:400])
        assert "李四" in record and "测试" in record, \
            "最终记录缺少完整末段转写"
        assert record.count("项目进度") == 1, \
            "最终记录出现重复（fake device 循环未避免）"
        print("final Meeting OK (complete, no repetition)")
        print("final Meeting OK")

        # 4) 截图
        data = c.call("Page.captureScreenshot", format="png")
        SHOT.parent.mkdir(parents=True, exist_ok=True)
        SHOT.write_bytes(base64.b64decode(data["data"]))
        print("screenshot saved:", SHOT.name)

        print("\n===== ALL LIVE-RECORDING CHECKS PASSED =====")
    finally:
        c.close()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
