"""端到端真机验证：说话人重命名 + 转写人工校对 + 校对后导出 / 重新提炼。

独立 Edge headless 横版 + CDP（内置浏览器强制窄视口且 JS 注入受限，故不用）。
校验链路：
  上传 -> 等转写 -> 进校对模式
    -> 把「说话人2」重命名为「副院长」（点击 chip -> 重命名输入 -> 回车）
    -> 修正第一条转写文本（加「【校对】」标记）
  -> 完成校对
  -> 导出 MD：断言文件内同时含「副院长」与「【校对】」
  -> 重新提炼纪要：断言纪要区含「副院长」（重命名贯穿到 LLM 输入）

用法（后端已在 8000）：
  python scripts/verify_proof.py
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from cdp_shot import CDP, EDGE, PORT, wait_port

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "data/voice_test/clip_8ch_30_210.wav"


def start_edge():
    profile = tempfile.mkdtemp(prefix="edge_proof_")
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
    ver = json.load(urllib.request.urlopen(
        f"http://127.0.0.1:{PORT}/json/version"))
    page_cdp = CDP(page["webSocketDebuggerUrl"])
    browser_cdp = CDP(ver["webSocketDebuggerUrl"])
    return proc, page_cdp, browser_cdp


def click_button(c, fragment: str) -> bool:
    ok = c.eval(
        "(()=>{const b=[...document.querySelectorAll('button')]"
        ".find(x=>x.textContent.includes(%s));"
        "if(!b)return false;b.click();return true;})()" % json.dumps(fragment))
    return bool(ok)


def wait_includes(c, text: str, timeout: int, absent: str = "") -> bool:
    t0 = time.time()
    expr = "document.body.innerText.includes(%s)" % json.dumps(text)
    while time.time() - t0 < timeout:
        if c.eval(expr) and (
                not absent or not c.eval(
                    "document.body.innerText.includes(%s)"
                    % json.dumps(absent))):
            return True
        time.sleep(4)
    return False


_MIN_TEXT = (
    "(()=>{const h=[...document.querySelectorAll('h2')]"
    ".find(x=>x.textContent.includes('会议纪要'));"
    "const s=h?h.closest('section'):null;return s?s.innerText:'';})()")


def wait_minutes_stable(c, timeout, stable_n=3):
    t0 = time.time()
    last, stable = -1, 0
    while time.time() - t0 < timeout:
        v = c.eval(_MIN_TEXT) or ""
        if len(v) == last and len(v) > 30:
            stable += 1
            if stable >= stable_n:
                return v
        else:
            stable = 0
        last = len(v)
        time.sleep(5)
    return ""


def main():
    dl_dir = Path(tempfile.mkdtemp(prefix="memora_dl_"))
    proc, c, bc = start_edge()
    try:
        c.call("Page.enable")
        c.call("Emulation.setDeviceMetricsOverride", width=1440,
               height=1000, deviceScaleFactor=1, mobile=False)
        c.call("Page.navigate", url="http://127.0.0.1:8000/voice/")
        time.sleep(4)

        # 1) 上传 + 等转写
        doc = c.call("DOM.getDocument")
        node = c.call("DOM.querySelector", nodeId=doc["root"]["nodeId"],
                      selector="input[type=file]")["nodeId"]
        c.call("DOM.setFileInputFiles", nodeId=node,
               files=[str(AUDIO.resolve())])
        print("uploaded, waiting transcribe...")
        assert wait_includes(c, "校对记录", 280, absent="正在本地处理"), \
            "转写未在限定时间内完成"
        time.sleep(1)

        # 2) 进入校对模式
        assert click_button(c, "校对记录"), "未找到校对记录按钮"
        assert wait_includes(c, "完成校对", 10), "未进入校对模式"
        n_seg = c.eval("document.querySelectorAll('section textarea').length")
        print("proof mode on, editable segments =", n_seg)
        assert n_seg and n_seg > 5, "可编辑文本框数量异常"

        # 3) 重命名：点击「说话人2」chip -> 出现重命名输入
        clicked = c.eval(
            "(()=>{const b=[...document.querySelectorAll('section button')]"
            ".find(x=>x.textContent.trim()==='说话人2');"
            "if(!b)return false;b.click();return true;})()")
        assert clicked, "未找到说话人2标签"
        time.sleep(0.6)
        # 设置新名字（React 受控需用原生 setter + input 事件）
        setv = c.eval(
            "(()=>{const inp=document.querySelector(\"input[class*='w-24']\");"
            "if(!inp)return 'noinput';"
            "const s=Object.getOwnPropertyDescriptor"
            "(window.HTMLInputElement.prototype,'value').set;"
            "s.call(inp,'副院长');"
            "inp.dispatchEvent(new Event('input',{bubbles:true}));"
            "return 'set';})()")
        assert setv == "set", "重命名输入未就绪"
        time.sleep(0.6)  # 等 React flush renameValue
        # 回车确认
        c.eval(
            "(()=>{const inp=document.querySelector(\"input[class*='w-24']\");"
            "inp&&inp.dispatchEvent(new KeyboardEvent('keydown',"
            "{key:'Enter',bubbles:true}));})()")
        time.sleep(0.8)
        body = c.eval("document.body.innerText")
        assert "副院长" in body, "重命名未生效"
        assert "说话人2" not in body, "旧说话人标签仍残留"
        print("rename OK: 说话人2 -> 副院长")

        # 4) 修正第一条转写文本
        edited = c.eval(
            "(()=>{const ta=document.querySelector('section textarea');"
            "if(!ta)return 'nota';"
            "const s=Object.getOwnPropertyDescriptor"
            "(window.HTMLTextAreaElement.prototype,'value').set;"
            "s.call(ta,'【校对】明年我是指导老师。');"
            "ta.dispatchEvent(new Event('input',{bubbles:true}));"
            "return ta.value;})()")
        assert edited == "【校对】明年我是指导老师。", "文本校对未生效"
        time.sleep(0.6)
        print("text proof OK:", edited)

        # 5) 完成校对
        assert click_button(c, "完成校对"), "未找到完成校对按钮"
        time.sleep(0.6)

        # 6) 导出 MD（配置 headless 下载目录 -> 点 MD -> 等文件）
        bc.call("Browser.setDownloadBehavior", behavior="allow",
                downloadPath=str(dl_dir), eventsEnabled=True)
        assert click_button(c, "MD"), "未找到 MD 导出按钮"
        md_path = None
        t0 = time.time()
        while time.time() - t0 < 40:
            files = list(dl_dir.glob("*.md"))
            if files:
                md_path = files[0]
                break
            time.sleep(1)
        assert md_path, "MD 导出文件未出现"
        md = md_path.read_text(encoding="utf-8")
        assert "副院长" in md, "导出 MD 未包含重命名后的说话人"
        assert "【校对】" in md, "导出 MD 未包含校对后的文本"
        print("export MD OK:", md_path.name, f"({len(md)} chars)")

        # 7) 重新提炼纪要：拦截请求体，确定性证明发送的是校对后文本
        c.eval(
            "(()=>{if(window.__patched)return 'already';"
            "window.__minBody='';const of=window.fetch;"
            "window.fetch=function(u,o){"
            "try{if(String(u).includes('minutes/stream')&&o&&o.body)"
            "{window.__minBody=o.body;}}catch(e){}"
            "return of.apply(this,arguments);};"
            "window.__patched=true;return 'patched';})()")
        time.sleep(0.3)
        assert click_button(c, "提炼"), "未找到提炼按钮"
        minutes = wait_minutes_stable(c, 300)
        assert minutes, "纪要生成未完成"
        body_sent = c.eval("window.__minBody") or ""
        sent = json.loads(body_sent) if body_sent else {}
        record_text = sent.get("record_text", "")
        assert "副院长" in record_text, "纪要请求未携带重命名后的文本"
        assert "【校对】" in record_text, "纪要请求未携带校对后的文本"
        print("minutes request carries proofed record_text = True")
        assert "说话人2" not in minutes, "纪要仍引用已被重命名的旧标签"
        print("minutes regenerated OK; no stale 说话人2")
        print("minutes preview:\n", minutes[:400])

        print("\n===== ALL PROOF-CHAIN CHECKS PASSED =====")
    finally:
        c.close()
        bc.close()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
