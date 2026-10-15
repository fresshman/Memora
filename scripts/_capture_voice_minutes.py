# -*- coding: utf-8 -*-
"""采集：语音纪要提炼（真实推理）+ 校对记录 + 联系人声纹库。"""
import sys, time, subprocess, os
ROOT = r'F:\python-exercise\Industrial_LLM\langchain-learn\Memora'
FR = os.path.join(ROOT, 'data', '_frames')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
subprocess.run('taskkill /F /IM chrome-headless-shell.exe',
               shell=True, capture_output=True)
time.sleep(1.5)
from _cdp_browser import Browser

b = Browser(width=1600, height=1000,
            user_data_dir=os.path.join(ROOT, 'data', '_cdp_profile'))
b.navigate('http://127.0.0.1:8010/voice/', wait=4)
b.set_files('input[type=file]', [os.path.join(FR, 'demo_meeting.wav')])
b.wait_for(
    "Array.from(document.querySelectorAll('h2'))"
    ".some(function(e){return e.textContent.trim()==='会议记录'})",
    timeout=120)
time.sleep(1)
print("record ready")

# 一键提炼会议纪要（流式，约 60s）
b.click_text('一键提炼会议纪要')
print("minutes requested, waiting...")
t0 = time.time()
fi = 0
while time.time() - t0 < 180:
    time.sleep(8)
    fi += 1
    b.shot(os.path.join(FR, 'minutes_proc_%02d.png' % fi))
    streaming = b.eval(
        "document.body.innerText.indexOf('正在提炼')>=0")
    has = b.eval(
        "(function(){var h=Array.from(document.querySelectorAll('h2'))"
        ".find(function(e){return e.textContent.indexOf('会议纪要')>=0});"
        "if(!h)return false;var sec=h.closest('section');"
        "return sec?sec.innerText.length>120:false;})()")
    print("t=%ds streaming=%s has_minutes=%s" %
          (int(time.time()-t0), streaming, has))
    if has and not streaming:
        break
time.sleep(1.5)
b.shot(os.path.join(FR, 'voice_minutes_full.png'), full=True)
minutes_text = b.eval(
    "(function(){var h=Array.from(document.querySelectorAll('h2'))"
    ".find(function(e){return e.textContent.indexOf('会议纪要')>=0});"
    "if(!h)return '';var sec=h.closest('section');return sec?sec.innerText:'';})()")
with open(os.path.join(FR, 'voice_minutes_text.txt'), 'w', encoding='utf-8') as f:
    f.write(minutes_text)
print("=== minutes text ===")
print(minutes_text[:2500])

# 校对记录：点击展开
b.click_text('校对记录')
time.sleep(2)
b.shot(os.path.join(FR, 'voice_proof.png'), full=True)
print("proof opened")

# 联系人声纹库弹窗
b.click_text('联系人声纹库')
time.sleep(2.5)
b.shot(os.path.join(FR, 'voice_contacts.png'))
print("contacts opened")

b.close()
print("DONE")
