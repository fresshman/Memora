# -*- coding: utf-8 -*-
"""行动项状态流转 + 思考档位切换采集。"""
import sys, time, subprocess, os, requests
ROOT = r'F:\python-exercise\Industrial_LLM\langchain-learn\Memora'
FR = os.path.join(ROOT, 'data', '_frames')
B = 'http://127.0.0.1:8010'
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
subprocess.run('taskkill /F /IM chrome-headless-shell.exe',
               shell=True, capture_output=True)
time.sleep(1.5)
from _cdp_browser import Browser
b = Browser(width=1600, height=1200,
            user_data_dir=os.path.join(ROOT, 'data', '_cdp_profile'))
b.navigate(B + '/action/', wait=5)
b.wait_for(
    "(function(){return document.querySelectorAll('select[aria-label=更新状态]').length>0;})()",
    timeout=40)
time.sleep(1)
first_id = b.eval(
    "(function(){return document.querySelectorAll('select[aria-label=更新状态]').length;})()")
print("card selects:", first_id)

def set_first_status(val):
    js = """(function(v){
  var sel=document.querySelectorAll('select[aria-label=更新状态]')[0];
  var setter=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;
  setter.call(sel,v);
  sel.dispatchEvent(new Event('change',{bubbles:true}));
  return v;})('%s')""" % val
    print("set status:", b.eval(js))
    time.sleep(2.0)

# 初始截图
b.shot(os.path.join(FR, 'action_01_open.png'), full=True)
# 第一条 → 进行中
set_first_status('in_progress')
b.shot(os.path.join(FR, 'action_02_progress.png'), full=True)
# 第一条 → 已完成（此时第一个 select 是下一条待跟进；已完成的在 done 列）
# 找到当前在进行中的卡片 select，改 done
b.eval(
    "(function(){"
    "var sels=Array.from(document.querySelectorAll('select[aria-label=更新状态]'));"
    "var sel=sels.find(function(s){return s.value==='in_progress';});"
    "var setter=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;"
    "setter.call(sel,'done');sel.dispatchEvent(new Event('change',{bubbles:true}));"
    "return 'done';})()")
time.sleep(2.0)
b.shot(os.path.join(FR, 'action_03_done.png'), full=True)

# 思考档位切换（找含"快速模式"的按钮）
b.eval(
    "(function(){var t=Array.from(document.querySelectorAll('button')).find(function(x){"
    "return x.textContent.trim()==='快速模式';});if(t)t.click();return 'thinking';})()")
time.sleep(1.5)
b.shot(os.path.join(FR, 'action_04_deep.png'), full=True)

# 打印统计
stats = b.eval(
    "(function(){return Array.from(document.querySelectorAll('.grid .text-xl')).map(function(x){"
    "return x.textContent.trim();}).join(' / ');})()")
print("stats:", stats)
b.close()
print("DONE")
