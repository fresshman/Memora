# -*- coding: utf-8 -*-
"""历史记录真实采集：首页复盘 → 加密保存 → 历史页回看 → 截图。"""
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
# 点一键全局复盘
b.eval(
    "(function(){var t=Array.from(document.querySelectorAll('button')).find(function(x){"
    "return x.textContent.trim()==='一键全局复盘';});t.click();return 'review';})()")
print("reviewing...")
# 等待复盘完成：按钮文本回到"一键全局复盘"且报告 pre 非空
DONE = ("(function(){var btns=Array.from(document.querySelectorAll('button'));"
        "var rb=btns.find(function(x){return x.textContent.indexOf('全局复盘')>=0"
        "||x.textContent.indexOf('正在复盘')>=0;});"
        "var busy=rb&&rb.textContent.indexOf('正在复盘')>=0;"
        "var pres=Array.from(document.querySelectorAll('pre'));"
        "var has=pres.some(function(p){return p.textContent.length>50;});"
        "return has&&!busy;})()")
for i in range(1, 20):
    time.sleep(8)
    if b.eval(DONE) is True:
        print("review done at iter", i)
        break
b.wait_for(DONE, timeout=30)
time.sleep(1)

# 点加密保存
b.eval(
    "(function(){var t=Array.from(document.querySelectorAll('button')).find(function(x){"
    "return x.textContent.trim()==='加密保存';});t.click();return 'save';})()")
time.sleep(3)
b.shot(os.path.join(FR, 'home_saved.png'), full=True)
print("saved to records")

# 到历史页
b.navigate(B + '/history/', wait=4)
b.wait_for(
    "(function(){return document.querySelectorAll('button').length>0&&"
    "Array.from(document.querySelectorAll('button')).some(function(x){"
    "return x.textContent.trim()==='回看';});})()", timeout=30)
time.sleep(0.5)
# 点回看
b.eval(
    "(function(){var t=Array.from(document.querySelectorAll('button')).find(function(x){"
    "return x.textContent.trim()==='回看';});t.click();return 'view';})()")
b.wait_for(
    "(function(){return Array.from(document.querySelectorAll('h2')).some(function(e){"
    "return e.textContent.trim()==='记录内容';});})()", timeout=30)
time.sleep(1)
b.shot(os.path.join(FR, 'history_view_full.png'), full=True)
hist = b.eval(
    "(function(){return Array.from(document.querySelectorAll('.card')).map(function(c){"
    "return c.innerText.slice(0,120);}).join('\n---\n');})()")
print("=== HISTORY ===")
print(hist[:600])
b.close()
print("DONE")
