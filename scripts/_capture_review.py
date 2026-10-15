# -*- coding: utf-8 -*-
"""采集：真实触发一键全局复盘（SSE 流式），采集生成过程帧 + 最终四段式报告 + 还原。"""
import sys, time, subprocess, os, json
ROOT = r'F:\python-exercise\Industrial_LLM\langchain-learn\Memora'
FR = os.path.join(ROOT, 'data', '_frames')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
subprocess.run('taskkill /F /IM chrome-headless-shell.exe',
               shell=True, capture_output=True)
time.sleep(1.5)
from _cdp_browser import Browser

b = Browser(width=1600, height=1000,
            user_data_dir=os.path.join(ROOT, 'data', '_cdp_profile'))
b.navigate('http://127.0.0.1:8010/', wait=2.5)

# 上传微信群样本
b.set_files('input[type=file]',
            [os.path.join(ROOT, 'samples', 'wechat', '01_basic_group.txt')])
b.wait_for(
    "Array.from(document.querySelectorAll('h2'))"
    ".some(function(e){return e.textContent.indexOf('对话预览')>=0})",
    timeout=60)
time.sleep(1)
print("parsed, clicking review")

# 点击“一键全局复盘”
clicked = b.eval(
    "(function(){var x=Array.from(document.querySelectorAll('button'))"
    ".find(function(e){return e.textContent.indexOf('全局复盘')>=0});"
    "if(!x) return 'NO';"
    "x.scrollIntoView({block:'center'});x.click();return 'OK';})()")
print("click:", clicked)

# 轮询采集流式过程，每 6 秒一帧，直到按钮恢复（busy=false）
t0 = time.time()
frame_i = 0
last_len = -1
stable = 0
while time.time() - t0 < 240:
    time.sleep(6)
    busy = b.eval(
        "Array.from(document.querySelectorAll('button'))"
        ".some(function(e){return e.textContent.indexOf('正在复盘')>=0})")
    rlen = b.eval(
        "(function(){var p=document.querySelector('section pre, section + section pre');"
        "var ps=document.querySelectorAll('pre');var m=0;"
        "ps.forEach(function(p){m=Math.max(m,p.innerText.length)});return m;})()")
    frame_i += 1
    b.shot(os.path.join(FR, 'stream_%02d.png' % frame_i))
    print("t=%ds busy=%s maxprelen=%s" % (int(time.time()-t0), busy, rlen))
    if not busy and frame_i >= 2:
        if rlen == last_len:
            stable += 1
        else:
            stable = 0
        if stable >= 1:
            break
    last_len = rlen

time.sleep(2)
b.shot(os.path.join(FR, 'review_final_view.png'))
b.shot(os.path.join(FR, 'review_final_full.png'), full=True)

# 提取四段式 sections（ReportCard: h3 标题 + pre 内容）
data = b.eval(
    "(function(){var out=[];"
    "document.querySelectorAll('h3').forEach(function(h){"
    "var card=h.closest('div');var pre=h.parentElement.parentElement.querySelector('pre');"
    "if(pre) out.push({section:h.innerText,text:pre.innerText});});"
    "var ctx=document.querySelector('span.badge, [class*=rounded-full]');"
    "var badges=Array.from(document.querySelectorAll('span'))"
    ".map(function(s){return s.innerText}).filter(function(t){return t.indexOf('上下文')>=0});"
    "return JSON.stringify({sections:out,context_badge:badges});})()")
try:
    parsed = json.loads(data)
except Exception:
    parsed = {"raw": data}
with open(os.path.join(FR, 'review_data.json'), 'w', encoding='utf-8') as f:
    json.dump(parsed, f, ensure_ascii=False, indent=2)
print("=== sections ===")
for s in parsed.get('sections', []):
    print("##", s['section'])
    print(s['text'][:600])
print("context badge:", parsed.get('context_badge'))

# 点击“还原”
r = b.eval(
    "(function(){var x=Array.from(document.querySelectorAll('button'))"
    ".find(function(e){return e.textContent.trim()==='还原'});"
    "if(!x) return 'NO';x.click();return 'OK';})()")
print("restore click:", r)
time.sleep(4)
b.shot(os.path.join(FR, 'review_restored.png'))
restored = b.eval(
    "(function(){var p=document.querySelector('[class*=amber-50]');"
    "return p?p.innerText.slice(0,1200):'';})()")
print("=== restored text (first 1000) ===")
print(restored[:1000])
with open(os.path.join(FR, 'restored_text.txt'), 'w', encoding='utf-8') as f:
    f.write(restored)

b.close()
print("DONE")
