# -*- coding: utf-8 -*-
"""密集采集复盘流式增长帧（报告section滚动对齐，每1.0s一帧，视口截图）。"""
import sys, time, subprocess, os
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
b.navigate(B + '/', wait=4)
b.set_files('input[type=file]',
            [os.path.join(ROOT, 'samples', 'wechat', '01_basic_group.txt')])
b.wait_for(
    "(function(){return Array.from(document.querySelectorAll('button')).some(function(x){"
    "return x.textContent.trim()==='一键全局复盘';});})()", timeout=60)
time.sleep(0.5)
b.eval(
    "(function(){var t=Array.from(document.querySelectorAll('button')).find(function(x){"
    "return x.textContent.trim()==='一键全局复盘';});t.click();return 'review';})()")
print("reviewing...")

APPEAR = ("(function(){return document.body.textContent.indexOf('结构化复盘报告')>=0;})()")
for _ in range(60):
    if b.eval(APPEAR) is True:
        break
    time.sleep(1)
print("report appeared")

# 滚动报告section到视口顶部，并返回其内容长度
SEC = ("(function(){var secs=Array.from(document.querySelectorAll('section'));"
       "var rep=secs.find(function(s){return s.textContent.indexOf('结构化复盘报告')>=0;});"
       "if(!rep)return 0;rep.scrollIntoView({block:'start'});return rep.textContent.length;})()")
BUSY = ("(function(){return Array.from(document.querySelectorAll('button')).some(function(x){"
        "return x.textContent.indexOf('正在复盘')>=0;});})()")
last_len, stable = 0, 0
for i in range(1, 45):
    rlen = b.eval(SEC) or 0
    b.shot(os.path.join(FR, 'grow_%02d.png' % i), full=False)
    busy = b.eval(BUSY)
    stable = stable + 1 if rlen == last_len else 0
    last_len = rlen
    if not busy and stable >= 3 and rlen > 400:
        print("done frame", i, "len", rlen)
        break
    time.sleep(1.0)
# 最终全页
b.shot(os.path.join(FR, 'grow_final_full.png'), full=True)
b.close()
print("DONE")
