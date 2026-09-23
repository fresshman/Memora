"""通过独立 Chromium（Edge headless）+ CDP 完成"上传音频→等待转写→横版截图"。

为何不用内置浏览器：其外层 webview 强制窄视口，Emulation 无法覆盖。
用法：
  python scripts/cdp_shot.py --url http://127.0.0.1:8000/voice/ \
      --audio data/voice_test/clip_8ch_30_210.wav \
      --ready-text "说话人 7 位" --scroll-h2 "会议记录" \
      --out docs/images/07_voice.png
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9223


class CDP:
    def __init__(self, wsurl):
        self.ws = websocket.create_connection(wsurl, timeout=30)
        self._id = 0

    def call(self, method, **params):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method,
                                 "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def eval(self, expr):
        r = self.call("Runtime.evaluate", expression=expr,
                      returnByValue=True)
        return r.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def wait_port():
    for _ in range(30):
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/json/version", timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Edge debugging port not ready")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--audio", default="")
    ap.add_argument("--ready-text", default="")
    ap.add_argument("--scroll-h2", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--max-wait", type=int, default=260)
    a = ap.parse_args()

    profile = tempfile.mkdtemp(prefix="edge_shot_")
    proc = subprocess.Popen([
        EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", f"--remote-debugging-port={PORT}",
        f"--user-data-dir={profile}", "--remote-allow-origins=*", "about:blank",
    ])
    try:
        wait_port()
        targets = json.load(urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/json/list"))
        page = next(t for t in targets if t.get("type") == "page")
        c = CDP(page["webSocketDebuggerUrl"])
        c.call("Page.enable")
        c.call("Emulation.setDeviceMetricsOverride", width=a.width,
               height=a.height, deviceScaleFactor=1, mobile=False)
        c.call("Page.navigate", url=a.url)
        time.sleep(4)

        if a.audio:
            doc = c.call("DOM.getDocument")
            node = c.call("DOM.querySelector",
                          nodeId=doc["root"]["nodeId"],
                          selector="input[type=file]")["nodeId"]
            c.call("DOM.setFileInputFiles", nodeId=node,
                   files=[str(Path(a.audio).resolve())])
            print("uploaded, waiting for processing...")
            if a.ready_text:
                t0 = time.time()
                while time.time() - t0 < a.max_wait:
                    if c.eval(
                        "document.body.innerText.includes(%s)"
                        % json.dumps(a.ready_text)
                    ):
                        break
                    time.sleep(5)
                time.sleep(2)

        if a.scroll_h2:
            c.eval(
                "(()=>{const h=[...document.querySelectorAll('h2')]"
                ".find(x=>x.textContent.includes(%s));"
                "h&&h.scrollIntoView({block:'start'});})()"
                % json.dumps(a.scroll_h2)
            )
            time.sleep(1)

        shot = c.call("Page.captureScreenshot", format="png")
        import base64
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(base64.b64decode(shot["data"]))
        print("saved", out, out.stat().st_size)
        c.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()