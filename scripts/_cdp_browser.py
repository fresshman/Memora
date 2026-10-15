# -*- coding: utf-8 -*-
"""轻量 CDP 驱动：基于 hyperframes 缓存的 chrome-headless-shell，全尺寸真实操作并截图。"""
import json, subprocess, time, os, base64
import requests, websocket

CHROME = r"C:\Users\SHJ\.cache\hyperframes\chrome\chrome-headless-shell\win64-152.0.7977.30\chrome-headless-shell-win64\chrome-headless-shell.exe"


class Browser:
    def __init__(self, port=9222, width=1600, height=1000, user_data_dir=None):
        self.port = port
        args = [CHROME, f"--remote-debugging-port={port}",
                "--remote-allow-origins=*",
                f"--window-size={width},{height}",
                "--hide-scrollbars", "--force-device-scale-factor=1",
                "--no-first-run", "--no-default-browser-check",
                "--disable-gpu",
                "--proxy-server=direct://", "--proxy-bypass-list=*"]
        if user_data_dir:
            args.append(f"--user-data-dir={user_data_dir}")
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        tabs = None
        for _ in range(80):
            try:
                tabs = requests.get(f"http://127.0.0.1:{port}/json", timeout=2).json()
                break
            except Exception:
                time.sleep(0.5)
        if tabs is None:
            raise RuntimeError("devtools not ready")
        pages = [t for t in tabs if t["type"] == "page"]
        if not pages:
            r = requests.put(
                f"http://127.0.0.1:{port}/json/new?about:blank", timeout=5)
            pages = [r.json()]
        page = pages[0]
        self.ws = websocket.create_connection(page["webSocketDebuggerUrl"],
                                              max_size=None, timeout=60)
        self.mid = 0
        self.events = []
        for d in ("Page.enable", "Runtime.enable", "DOM.enable",
                  "Network.enable"):
            self.send(d)
        # 禁用磁盘缓存：确保每次加载最新构建，避免缓存旧 chunk 导致 API 指向旧端口
        self.send("Network.setCacheDisabled", {"cacheDisabled": True})

    def send(self, method, params=None):
        self.mid += 1
        mid = self.mid
        self.ws.send(json.dumps({"id": mid, "method": method,
                                 "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            self.events.append(msg)

    def navigate(self, url, wait=1.5):
        self.send("Page.navigate", {"url": url})
        time.sleep(wait)

    def eval(self, expr, await_promise=False):
        r = self.send("Runtime.evaluate",
                      {"expression": expr, "returnByValue": True,
                       "awaitPromise": await_promise, "userGesture": True})
        if "exceptionDetails" in r:
            raise RuntimeError("JS exception: "
                               + json.dumps(r["exceptionDetails"])[:600])
        return r.get("result", {}).get("value")

    def wait_for(self, js_expr, timeout=120, interval=0.5):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.eval(js_expr):
                return True
            time.sleep(interval)
        raise RuntimeError("wait_for timeout: " + js_expr)

    def shot(self, path, full=False, width=None, height=None):
        params = {"format": "png", "captureBeyondViewport": full}
        if full:
            d = json.loads(self.eval(
                "JSON.stringify({w:document.documentElement.scrollWidth,"
                "h:document.documentElement.scrollHeight})"))
            params["clip"] = {"x": 0, "y": 0, "width": d["w"],
                              "height": d["h"], "scale": 1}
        elif width and height:
            params["clip"] = {"x": 0, "y": 0, "width": width,
                              "height": height, "scale": 1}
        r = self.send("Page.captureScreenshot", params)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(base64.b64decode(r["data"]))
        return path

    def click(self, selector, wait=0.6):
        r = self.eval(
            "(function(){var el=document.querySelector(%s);"
            "if(!el) return 'NOEL';"
            "el.scrollIntoView({block:'center'});el.click();return 'OK';})()"
            % json.dumps(selector))
        time.sleep(wait)
        return r

    def click_text(self, text, wait=0.6):
        r = self.eval(
            "(function(){var els=document.querySelectorAll('button,a,div,span');"
            "for(var i=0;i<els.length;i++){var e=els[i];"
            "if(e.textContent && e.textContent.trim()==%s){"
            "e.scrollIntoView({block:'center'});e.click();return 'OK';}}"
            "return 'NOEL';})()" % json.dumps(text))
        time.sleep(wait)
        return r

    def focus(self, selector):
        root = self.send("DOM.getDocument", {"depth": -1})
        node = self.send("DOM.querySelector",
                         {"nodeId": root["root"]["nodeId"], "selector": selector})
        self.send("DOM.focus", {"nodeId": node["nodeId"]})

    def insert_text(self, text):
        self.send("Input.insertText", {"text": text})

    def press(self, key, vk=0, modifiers=0):
        self.send("Input.dispatchKeyEvent",
                  {"type": "rawKeyDown", "key": key,
                   "windowsVirtualKeyCode": vk, "modifiers": modifiers})
        self.send("Input.dispatchKeyEvent",
                  {"type": "keyUp", "key": key,
                   "windowsVirtualKeyCode": vk, "modifiers": modifiers})

    def rect_of(self, js_get_el):
        r = self.eval(
            "(function(){var el=%s;if(!el)return null;var r=el.getBoundingClientRect();"
            "return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2});})()"
            % js_get_el)
        return json.loads(r) if r else None

    def mouse_click(self, x, y):
        self.send("Input.dispatchMouseEvent",
                  {"type": "mouseMoved", "x": x, "y": y})
        self.send("Input.dispatchMouseEvent",
                  {"type": "mousePressed", "x": x, "y": y,
                   "button": "left", "clickCount": 1})
        self.send("Input.dispatchMouseEvent",
                  {"type": "mouseReleased", "x": x, "y": y,
                   "button": "left", "clickCount": 1})

    def set_files(self, selector, files):
        root = self.send("DOM.getDocument", {"depth": -1})
        node = self.send("DOM.querySelector",
                         {"nodeId": root["root"]["nodeId"], "selector": selector})
        self.send("DOM.setFileInputFiles",
                  {"nodeId": node["nodeId"], "files": files})

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
        except Exception:
            pass
