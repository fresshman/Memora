# -*- coding: utf-8 -*-
"""干净跨会议看板：初始 → 一条进行中 → 一条已完成 → 筛选/档位，全程采集。"""
import sys, time, subprocess, os
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

def set_card(title, val):
    js = """(function(title,v){
  var sels=Array.from(document.querySelectorAll('select[aria-label=更新状态]'));
  var sel=sels.find(function(s){
    var n=s;
    for(var k=0;k<6;k++){n=n.parentElement;
      if(n&&n.className&&n.className.indexOf('shadow-sm')>=0&&n.textContent.indexOf(title)>=0)return true;}
    return false;});
  var setter=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;
  setter.call(sel,v);sel.dispatchEvent(new Event('change',{bubbles:true}));
  return v;})('%s','%s')""" % (title, val)
    print("set:", b.eval(js))
    time.sleep(2.2)

# 初始（7条全待跟进，跨3来源）
b.shot(os.path.join(FR, 'board_final_01.png'), full=True)
# 部署 → 进行中
set_card('完成测试环境部署', 'in_progress')
b.shot(os.path.join(FR, 'board_final_02.png'), full=True)
# 部署完成后告知 → 已完成
set_card('部署完成后在群内告知', 'done')
b.shot(os.path.join(FR, 'board_final_03.png'), full=True)
stats = b.eval(
    "(function(){return Array.from(document.querySelectorAll('.grid .text-xl')).map(function(x){"
    "return x.textContent.trim();}).join(' / ');})()")
print("stats:", stats)
# 按责任人筛选（成员C）
b.eval(
    "(function(){var s=Array.from(document.querySelectorAll('select')).find(function(x){"
    "return Array.from(x.options).some(function(o){return o.textContent==='成员C';});});"
    "var setter=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;"
    "setter.call(s,'成员C');s.dispatchEvent(new Event('change',{bubbles:true}));return 'filter';})()")
time.sleep(2.0)
b.shot(os.path.join(FR, 'board_final_04_filter.png'), full=True)
b.close()
print("DONE")
