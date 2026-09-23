"""一次性：Edge headless 走完语音全流程，产出 07（会议记录）与 09（会议纪要）两张横版截图。"""
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


def start_edge():
    profile = tempfile.mkdtemp(prefix="edge_voice_")
    proc = subprocess.Popen([
        EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", f"--remote-debugging-port={PORT}",
        "--remote-allow-origins=*", f"--user-data-dir={profile}",
        "about:blank",
    ])
    wait_port()
    targets = json.load(urllib.request.urlopen(
        f"http://127.0.0.1:{PORT}/json/list"))
    page = next(t for t in targets if t.get("type") == "page")
    return proc, CDP(page["webSocketDebuggerUrl"])


def shot(c, out):
    s = c.call("Page.captureScreenshot", format="png")
    Path(out).write_bytes(base64.b64decode(s["data"]))
    print("saved", out)


def wait_includes(c, text, timeout):
    t0 = time.time()
    expr = "document.body.innerText.includes(%s)" % json.dumps(text)
    while time.time() - t0 < timeout:
        if c.eval(expr):
            return True
        time.sleep(4)
    return False


_MIN_TEXT = (
    "(()=>{const h=[...document.querySelectorAll('h2')]"
    ".find(x=>x.textContent.includes('会议纪要'));"
    "const s=h?h.closest('section'):null;return s?s.innerText:'';})()")


def wait_minutes_stable(c, timeout, stable_n=3):
    """纪要区文本连续 stable_n 次（每次5s）长度不变即视为生成完成。"""
    t0 = time.time()
    last, stable = -1, 0
    while time.time() - t0 < timeout:
        v = c.eval(_MIN_TEXT) or ""
        if len(v) == last and len(v) > 30:
            stable += 1
            if stable >= stable_n:
                return True
        else:
            stable = 0
        last = len(v)
        time.sleep(5)
    return False


def scroll_h2(c, text):
    c.eval(
        "(()=>{const h=[...document.querySelectorAll('h2')]"
        ".find(x=>x.textContent.includes(%s));"
        "h&&h.scrollIntoView({block:'start'});})()" % json.dumps(text))


def main():
    proc, c = start_edge()
    try:
        c.call("Page.enable")
        c.call("Emulation.setDeviceMetricsOverride", width=1440,
               height=900, deviceScaleFactor=1, mobile=False)
        c.call("Page.navigate", url="http://127.0.0.1:8000/voice/")
        time.sleep(4)

        doc = c.call("DOM.getDocument")
        node = c.call("DOM.querySelector", nodeId=doc["root"]["nodeId"],
                      selector="input[type=file]")["nodeId"]
        c.call("DOM.setFileInputFiles", nodeId=node,
               files=[str((ROOT / "data/voice_test/clip_8ch_30_210.wav").resolve())])
        print("waiting transcribe...")
        wait_includes(c, "说话人 7 位", 280)
        time.sleep(2)
        scroll_h2(c, "会议记录")
        time.sleep(1)
        shot(c, str(ROOT / "docs/images/07_voice.png"))

        c.eval("(()=>{const b=[...document.querySelectorAll('button')]"
               ".find(x=>x.textContent.includes('提炼'));b.click();})()")
        print("waiting minutes (first LLM load)...")
        ok = wait_minutes_stable(c, 300)
        print("minutes done:", ok)
        time.sleep(1)
        scroll_h2(c, "会议纪要")
        time.sleep(1)
        shot(c, str(ROOT / "docs/images/09_voice_minutes.png"))
    finally:
        c.close()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()