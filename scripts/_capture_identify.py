# -*- coding: utf-8 -*-
"""跨会议识别：声纹库已有王老师/李老师，再次转写同一人语音 → 自动认出真名。"""
import sys, time, subprocess, os, requests
ROOT = r'F:\python-exercise\Industrial_LLM\langchain-learn\Memora'
FR = os.path.join(ROOT, 'data', '_frames')
B = 'http://127.0.0.1:8010'
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
print("contacts before:",
      [c['name'] for c in requests.get(B+'/api/voice/contacts').json()['contacts']])
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
time.sleep(1)
b.shot(os.path.join(FR, 'voice_identified_full.png'), full=True)

# speakers identified 状态
sp = b.eval(
    "(function(){var h=Array.from(document.querySelectorAll('h2')).find(function(e){"
    "return e.textContent.trim()==='会议记录';});var sec=h.closest('section');"
    "return Array.from(sec.querySelectorAll('span')).map(function(x){return x.textContent.trim();})"
    ".filter(function(x){return x.indexOf('老师')>=0||x.indexOf('说话人')>=0;});})()")
print("record chips:", sp)
# 直接看后端转写 speakers
b.close()
print("DONE")
