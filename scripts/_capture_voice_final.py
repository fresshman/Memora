# -*- coding: utf-8 -*-
"""最终采集：重命名注册（含输入帧）+ 声纹库 + 第二次转写跨会议自动识别。"""
import sys, time, subprocess, os, json, requests
ROOT = r'F:\python-exercise\Industrial_LLM\langchain-learn\Memora'
FR = os.path.join(ROOT, 'data', '_frames')
B = 'http://127.0.0.1:8010'
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
for c in requests.get(B + '/api/voice/contacts').json()['contacts']:
    requests.delete(B + '/api/voice/contact/' + c['id'])
subprocess.run('taskkill /F /IM chrome-headless-shell.exe',
               shell=True, capture_output=True)
time.sleep(1.5)
from _cdp_browser import Browser
b = Browser(width=1600, height=1000,
            user_data_dir=os.path.join(ROOT, 'data', '_cdp_profile'))
b.navigate(B + '/voice/', wait=4)
b.set_files('input[type=file]', [os.path.join(FR, 'demo_meeting.wav')])
b.wait_for(
    "Array.from(document.querySelectorAll('h2'))"
    ".some(function(e){return e.textContent.trim()==='会议记录'})",
    timeout=120)
SEC = ("(function(){var h=Array.from(document.querySelectorAll('h2'))"
       ".find(function(e){return e.textContent.trim()==='会议记录'});"
       "return h?h.closest('section'):null;})()")
RIN = ("(function(){var sec=%s;if(!sec)return null;"
       "return Array.from(sec.querySelectorAll('input')).find(function(i){"
       "return i.type!=='file';})||null;})()") % SEC
b.eval(
    "(function(){var sec=%s;var t=Array.from(sec.querySelectorAll('button'))"
    ".find(function(x){return x.textContent.trim()==='校对记录';});t.click();})()" % SEC)
time.sleep(1.5)
print("proof on")
# 注入 focusout 拦截
b.eval("""(function(){window.__blockBlur=function(e){
  if(e.target&&e.target.className.indexOf('w-24')>=0)e.stopImmediatePropagation();};
  document.addEventListener('focusout',window.__blockBlur,true);return 1;})()""")

def rename_one(label, newname, tag):
    js = """(function(){var sec=%s;
  var chip=Array.from(sec.querySelectorAll('button')).find(function(x){
    return x.textContent.trim().indexOf(%s)>=0;});
  chip.scrollIntoView({block:'center'});chip.click();
  return new Promise(function(r){setTimeout(function(){
    var input=Array.from(sec.querySelectorAll('input')).find(function(i){
      return i.type!=='file';});
    if(input){input.focus();r('OK');}else r('NO');},150);});})()""" % (
        SEC, json.dumps(label))
    print("start", label, b.eval(js, await_promise=True))
    time.sleep(0.4)
    b.shot(os.path.join(FR, 'rename_input_%s.png' % tag))  # 输入框原值
    b.press("a", vk=65, modifiers=2)
    time.sleep(0.2)
    b.insert_text(newname)
    time.sleep(0.4)
    nv = b.eval("(function(){var i=%s;return i?i.value:'NO';})()" % RIN)
    print("inserted:", nv)
    b.shot(os.path.join(FR, 'rename_typed_%s.png' % tag))  # 输入框新值
    b.press("Enter", vk=13)
    time.sleep(3.0)

rename_one('说话人1', '王老师', 'w1')
rename_one('说话人2', '李老师', 'w2')

# 移除拦截 + 完成校对
b.eval("document.removeEventListener('focusout',window.__blockBlur,true);")
b.eval(
    "(function(){var sec=%s;var t=Array.from(sec.querySelectorAll('button'))"
    ".find(function(x){return x.textContent.trim()==='完成校对';});t.click();})()" % SEC)
time.sleep(1.5)
b.shot(os.path.join(FR, 'voice_renamed_full.png'), full=True)
print("renamed full saved")

# 打开联系人声纹库
b.click_text('联系人声纹库')
time.sleep(3)
b.shot(os.path.join(FR, 'voice_contacts_registered.png'))
print("dialog:", b.eval(
    "(function(){var d=document.querySelector('[role=dialog]');"
    "return d?d.innerText:'NODIALOG';})()"))
b.close()
print("DONE")
