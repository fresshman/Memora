# -*- coding: utf-8 -*-
"""批量复盘真实采集：选择 微信/钉钉/飞书 三个文件 → 等待汇总总览 → 截图。"""
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
b.navigate(B + '/batch/', wait=4)
b.wait_for(
    "(function(){return document.querySelector('input[type=file][multiple]')!==null;})()",
    timeout=30)
files = [
    os.path.join(ROOT, 'samples', 'wechat', '01_basic_group.txt'),
    os.path.join(ROOT, 'samples', 'dingtalk', '01_standard.csv'),
    os.path.join(ROOT, 'samples', 'feishu', '01_ts_block.html'),
]
b.set_files('input[type=file][multiple]', files)
print("files submitted, batch processing...")

# 等待汇总总览，期间采集过程帧
READY = ("(function(){return Array.from(document.querySelectorAll('h2,h3')).some(function(e){"
         "return e.textContent.trim()==='汇总总览';});})()")
for i in range(1, 25):
    time.sleep(10)
    if b.eval(READY) is True:
        break
    b.shot(os.path.join(FR, 'batch_proc_%02d.png' % i), full=True)
b.wait_for(READY, timeout=30)
time.sleep(1)
b.shot(os.path.join(FR, 'batch_final_full.png'), full=True)
overview = b.eval(
    "(function(){var h=Array.from(document.querySelectorAll('h2,h3')).find(function(e){"
    "return e.textContent.trim()==='汇总总览';});var sec=h.closest('section');"
    "return sec.innerText;})()")
print("=== OVERVIEW ===")
print(overview)
b.close()
print("DONE")
