# -*- coding: utf-8 -*-
"""真实 QA 采集：上传微信样本 → 提问 → 流式回答 → 截图（含过程帧）。"""
import sys, time, subprocess, os, requests
ROOT = r'F:\python-exercise\Industrial_LLM\langchain-learn\Memora'
FR = os.path.join(ROOT, 'data', '_frames')
B = 'http://127.0.0.1:8010'
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
subprocess.run('taskkill /F /IM chrome-headless-shell.exe',
               shell=True, capture_output=True)
time.sleep(1.5)
from _cdp_browser import Browser
b = Browser(width=1600, height=1000,
            user_data_dir=os.path.join(ROOT, 'data', '_cdp_profile'))
b.navigate(B + '/qa/', wait=4)
b.set_files('input[type=file]',
            [os.path.join(ROOT, 'samples', 'wechat', '01_basic_group.txt')])
b.wait_for(
    "(function(){return Array.from(document.querySelectorAll('h2')).some(function(e){"
    "return e.textContent.trim()==='提问';});})()", timeout=60)
print("parsed, question section shown")

# 定位可见提问 input
ASKIN = ("(function(){return Array.from(document.querySelectorAll('input'))"
         ".find(function(i){return i.type!=='file'&&i.offsetParent!==null;});})()")
b.eval("(function(){var i=%s;i.focus();})()" % ASKIN)
time.sleep(0.2)
b.insert_text('交付时间定在什么时候？')
time.sleep(0.4)
qv = b.eval("(function(){var i=%s;return i.value;})()" % ASKIN)
print("question:", qv)

# 点提问
b.eval(
    "(function(){var t=Array.from(document.querySelectorAll('button')).find(function(x){"
    "return x.textContent.trim()==='提问';});t.click();})()")
# 采集流式过程（等待回答区出现，每隔几秒截帧）
b.wait_for(
    "(function(){return Array.from(document.querySelectorAll('h2')).some(function(e){"
    "return e.textContent.trim()==='回答';});})()", timeout=60)
for i in range(1, 7):
    time.sleep(5)
    busy = b.eval(
        "(function(){return Array.from(document.querySelectorAll('button')).some(function(x){"
        "return x.textContent.trim()==='查询中';});})()")
    b.shot(os.path.join(FR, 'qa_stream_%02d.png' % i), full=True)
    if busy is False:
        break
time.sleep(1)
b.shot(os.path.join(FR, 'qa_answer_full.png'), full=True)
ans = b.eval(
    "(function(){var h=Array.from(document.querySelectorAll('h2')).find(function(e){"
    "return e.textContent.trim()==='回答';});var sec=h.closest('section');"
    "return sec.innerText;})()")
print("=== ANSWER SECTION ===")
print(ans)
b.close()
print("DONE")
