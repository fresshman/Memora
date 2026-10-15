# -*- coding: utf-8 -*-
"""采集（真实鼠标点击 chip + 真实键盘）：清空→转写→UI重命名注册→声纹库。"""
import sys, time, subprocess, os, json, requests
ROOT = r'F:\python-exercise\Industrial_LLM\langchain-learn\Memora'
FR = os.path.join(ROOT, 'data', '_frames')
B = 'http://127.0.0.1:8010'
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

for c in requests.get(B + '/api/voice/contacts').json()['contacts']:
    requests.delete(B + '/api/voice/contact/' + c['id'])
print("contacts cleared")

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

def sec_btn(text):
    return b.eval(
        "(function(){var sec=%s;if(!sec)return 'NOSEC';"
        "var t=Array.from(sec.querySelectorAll('button')).find(function(x){"
        "return x.textContent.trim()===%s});"
        "if(!t)return 'NOBTN';t.scrollIntoView({block:'center'});t.click();return 'OK';})()"
        % (SEC, json.dumps(text)))

print("enter proof:", sec_btn('校对记录'))
time.sleep(1.5)

def chip_el(label):
    return (
        "(function(){var sec=%s;var t=Array.from(sec.querySelectorAll('button'))"
        ".find(function(x){return x.textContent.trim().indexOf(%s)>=0;});"
        "if(t)t.scrollIntoView({block:'center'});return t;})()"
        % (SEC, json.dumps(label)))

def rename_one(label, newname):
    r = b.rect_of(chip_el(label))
    print("chip rect", label, r)
    b.mouse_click(r['x'], r['y'])
    b.wait_for(
        "(function(){var i=%s;return i&&i.offsetParent!==null;})()" % RIN,
        timeout=10)
    iv = b.eval("(function(){var i=%s;return i?i.value:'NO';})()" % RIN)
    # 输入框已 autofocus；Ctrl+A 全选后输入新名
    b.press("a", vk=65, modifiers=2)
    time.sleep(0.2)
    b.insert_text(newname)
    time.sleep(0.4)
    nv = b.eval("(function(){var i=%s;return i?i.value:'NO';})()" % RIN)
    print("input before=%s after=%s" % (iv, nv))
    b.press("Enter", vk=13)
    time.sleep(3.5)
    print("renamed ->", newname, "contacts:",
          len(requests.get(B+'/api/voice/contacts').json()['contacts']))

rename_one('说话人1', '王老师')
rename_one('说话人2', '李老师')

print("finish proof:", sec_btn('完成校对'))
time.sleep(1.5)
b.shot(os.path.join(FR, 'voice_renamed_full.png'), full=True)

print("open contacts:", b.click_text('联系人声纹库'))
time.sleep(3)
b.shot(os.path.join(FR, 'voice_contacts_registered.png'))
print("dialog:", b.eval(
    "(function(){var d=document.querySelector('[role=dialog]');"
    "return d?d.innerText:'NODIALOG';})()"))
b.close()
print("DONE")
