# -*- coding: utf-8 -*-
"""Memora 真机离线端到端终验（M3/M4/M5）。

前置：本机模型已就位（4B GGUF + bge-m3 GGUF），且没有其它评测/模型进程占用 CPU。
运行（项目根，用装好依赖的解释器）：
    set MEMORA_ENFORCE_OFFLINE=1
    python scripts\\e2e_offline_check.py

脚本会：启动单端口 uvicorn -> 校验静态托管 -> 粘贴含 PII 的短对话验脱敏 ->
SSE 流式复盘（短，full 模式）-> 还原映射 -> SSE 流式问答 ->
粘贴超长会话验 RAG 模式 -> 采样外联连接 -> 关闭服务，逐项打印 PASS/FAIL。
全程只连 127.0.0.1；ENFORCE_OFFLINE=1 时模型/向量依赖均走本地。
"""
from __future__ import annotations

import http.client
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST, PORT = "127.0.0.1", 8000
BASE = f"http://{HOST}:{PORT}"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))


def conn() -> http.client.HTTPConnection:
    return http.client.HTTPConnection(HOST, PORT, timeout=900)


def get(path: str) -> tuple[int, str]:
    c = conn()
    c.request("GET", path)
    r = c.getresponse()
    body = r.read().decode("utf-8", "replace")
    c.close()
    return r.status, body


def post_json(path: str, obj: dict) -> tuple[int, dict]:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    c = conn()
    c.request("POST", path, body=data, headers={"Content-Type": "application/json"})
    r = c.getresponse()
    body = r.read().decode("utf-8", "replace")
    c.close()
    try:
        return r.status, json.loads(body)
    except Exception:
        return r.status, {"_raw": body}


def post_sse(path: str, obj: dict) -> list[dict]:
    """读取完整 SSE 事件序列（meta -> delta* -> done/error）。"""
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    c = conn()
    c.request("POST", path, body=data, headers={"Content-Type": "application/json",
                                                "Accept": "text/event-stream"})
    r = c.getresponse()
    assert r.status == 200, f"SSE HTTP {r.status}: {r.read(2000)!r}"
    buf = ""
    events: list[dict] = []
    while True:
        chunk = r.read(4096)
        if not chunk:
            break
        buf += chunk.decode("utf-8", "replace")
        while "\n\n" in buf:
            raw, buf = buf.split("\n\n", 1)
            line = next((l for l in raw.split("\n") if l.startswith("data:")), None)
            if not line:
                continue
            try:
                ev = json.loads(line[5:].strip())
                events.append(ev)
            except Exception:
                pass
            if events and events[-1].get("type") in ("done", "error"):
                # 排空后结束
                rest = r.read()
                if rest:
                    buf += rest.decode("utf-8", "replace")
                c.close()
                return events
    c.close()
    return events


def wait_health(proc: subprocess.Popen, timeout: int = 120) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        try:
            st, _ = get("/health")
            if st == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def external_connections() -> set[str]:
    """采样非本地的 ESTABLISHED 外联（Foreign Address）。"""
    out = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                         text=True, encoding="gbk", errors="replace").stdout
    ext = set()
    for ln in out.splitlines():
        m = re.search(r"\s(ESTABLISHED|SYN_SENT)\s*$", ln.strip())
        if not m:
            continue
        parts = ln.split()
        if len(parts) < 4:
            continue
        faddr = parts[2]
        ip = faddr.rsplit(":", 1)[0]
        if ip in ("127.0.0.1", "0.0.0.0", "::", "::1", "*") or ip.startswith("192.168."):
            continue
        ext.add(faddr)
    return ext


def main() -> int:
    env = dict(os.environ)
    env["MEMORA_ENFORCE_OFFLINE"] = "1"
    env["MEMORA_PII_REDACT"] = "1"
    env["MEMORA_PII_REDACT_NAMES"] = "1"

    print("== 启动单端口服务 ==")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--host", HOST, "--port", str(PORT)],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_health(proc):
            check("服务健康 /health", False, "服务未能启动")
            return report()
        check("服务健康 /health", True)

        # 1) 静态托管（单端口）
        st, html = get("/")
        check("首页静态托管 GET /", st == 200 and ("<html" in html.lower() or "<div" in html.lower()),
              f"status={st} len={len(html)}")
        st, html_qa = get("/qa/")
        check("问答页静态托管 GET /qa/", st == 200 and len(html_qa) > 200, f"status={st}")
        st, _ = get("/api/__not_exist__")
        check("未知 API 路径非 200", st in (404, 405), f"status={st}")

        # 2) 粘贴含 PII 的短对话 -> 脱敏
        short_text = (
            "张伟：大家好，我的手机号 13812345678，邮箱 zhangwei@example.com，"
            "付款银行卡号 4111111111111111。\n"
            "张伟：合同金额已经拍板定为12万元。\n"
            "李娜：那正式上线时间就定在10月15日，我来负责准备全链路压测报告。\n"
            "张伟：风险是第三方支付限流额度还没确认，可能导致上线延期。\n"
        )
        st, pr = post_json("/api/conversations/paste", {"text": short_text})
        check("粘贴解析 200", st == 200, f"status={st}")
        sid = pr.get("session_id", "")
        check("返回 session_id", bool(sid))
        check("PII 开关已触发 redacted=True", pr.get("redacted") is True,
              f"pii_stats={pr.get('pii_stats')}")
        preview = pr.get("preview", "")
        check("预览无明文手机号", "13812345678" not in preview)
        check("预览无明文邮箱", "zhangwei@example.com" not in preview)
        check("预览无真人姓名(角色化)", ("张伟" not in preview and "李娜" not in preview))

        # 3) SSE 流式复盘（短 -> full）
        ext_before = external_connections()
        evs = post_sse("/api/review/stream", {"session_id": sid})
        types = [e.get("type") for e in evs]
        check("复盘 SSE 以 meta 起始", types[:1] == ["meta"], str(types[:3]))
        metas = [e for e in evs if e.get("type") == "meta"]
        deltas = [e for e in evs if e.get("type") == "delta"]
        dones = [e for e in evs if e.get("type") == "done"]
        errs = [e for e in evs if e.get("type") == "error"]
        check("复盘逐块 delta>=3", len(deltas) >= 3, f"delta 数={len(deltas)}")
        check("复盘以 done 结束且无 error", bool(dones) and not errs,
              errs[0].get("message", "") if errs else "")
        mode = metas[0].get("context_mode") if metas else None
        check("短对话 context_mode=full", mode == "full", f"mode={mode}")
        report_text = dones[0].get("report", "") if dones else ""
        check("done 含报告与 sections", bool(report_text) and bool(dones[0].get("sections")),
              f"report_len={len(report_text)}")
        check("报告无明文 PII", ("13812345678" not in report_text
                                  and "zhangwei@example.com" not in report_text
                                  and "4111111111111111" not in report_text))

        # 4) 还原映射
        st, rr = post_json("/api/redact/restore",
                           {"session_id": sid, "text": "联系方式【手机1】"})
        check("还原端点 200", st == 200 and rr.get("restored") is True, str(rr)[:120])
        check("占位还原为真实手机号", rr.get("text", "").find("13812345678") >= 0,
              rr.get("text", "")[:60])

        # 5) SSE 流式问答
        qevs = post_sse("/api/qa/stream", {"session_id": sid, "question": "正式上线时间定在哪天？"})
        qdeltas = [e for e in qevs if e.get("type") == "delta"]
        qdone = [e for e in qevs if e.get("type") == "done"]
        qerr = [e for e in qevs if e.get("type") == "error"]
        check("问答 SSE 有 delta 且 done", len(qdeltas) >= 1 and bool(qdone) and not qerr,
              qerr[0].get("message", "") if qerr else f"delta={len(qdeltas)}")
        answer = qdone[0].get("answer", "") if qdone else ""
        check("问答命中上线时间(10月15日)", "10月15日" in answer, answer[:80])

        # 6) 超长会话 -> RAG
        lines = ["主持人：我们开始本次超长项目例会，逐条过进展。"]
        anchor = "王强：特别强调，已经拍板决定本次正式上线日期定为11月8日，任何人不得更改。"
        lines.append(anchor)
        filler = ("赵雷：本周我这边主要是在做模块联调、接口对接、日志整理、"
                  "文档补充、环境配置、数据核对等常规工作，整体进展平稳，各项按计划推进。")
        i = 0
        while sum(len(x) for x in lines) < 21000:
            lines.append(f"赵雷：第{i}条进展，{filler} 编号{i:04d}。")
            i += 1
        lines.append("孙莉：补充一个待办，我负责在上线前完成全链路压测报告并归档。")
        long_text = "\n".join(lines)
        st, lp = post_json("/api/conversations/paste", {"text": long_text})
        lsid = lp.get("session_id", "")
        check("超长会话解析 200 且字数>2万", st == 200 and lp.get("char_count", 0) > 20000,
              f"chars={lp.get('char_count')}")
        print("    （超长复盘真实推理中，约需 1-5 分钟……）")
        levs = post_sse("/api/review/stream", {"session_id": lsid})
        lmeta = [e for e in levs if e.get("type") == "meta"]
        ldone = [e for e in levs if e.get("type") == "done"]
        lerr = [e for e in levs if e.get("type") == "error"]
        lmode = lmeta[0].get("context_mode") if lmeta else None
        check("超长会话 context_mode=rag", lmode == "rag" and bool(ldone) and not lerr,
              lerr[0].get("message", "") if lerr else f"mode={lmode}")
        lreport = ldone[0].get("report", "") if ldone else ""
        check("超长报告命中尾部/头部锚点(11月8日)", "11月8日" in lreport,
              "未召回锚点" if "11月8日" not in lreport else "")

        # 7) 外联核查
        time.sleep(2)
        ext_after = external_connections()
        new_ext = ext_after - ext_before
        check("推理期间无新增外网连接", len(new_ext) == 0,
              ", ".join(sorted(new_ext)) if new_ext else "仅 127.0.0.1/内网")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()

    return report()


def report() -> int:
    n_pass = sum(1 for _, ok, _ in results if ok)
    n_fail = sum(1 for _, ok, _ in results if not ok)
    print("\n" + "=" * 56)
    print(f"端到端终验结果：{n_pass} PASS / {n_fail} FAIL，共 {len(results)} 项")
    print("=" * 56)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
