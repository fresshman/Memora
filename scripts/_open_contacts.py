# -*- coding: utf-8 -*-
"""打开语音页 → 点右上角联系人声纹库 → 截图。"""
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
r = b.eval(
    "(function(){var t=Array.from(document.querySelectorAll('button')).find(function(x){"
    "return x.textContent.trim().indexOf('联系人声纹库')>=0;});"
    "if(!t)return 'NOBTN';t.click();return 'OK';})()")
print("click:", r)
time.sleep(2.5)
d = b.eval("(function(){var h=Array.from(document.querySelectorAll('h3')).find(function(x){"
           "return x.textContent.trim()==='联系人声纹库';});"
           "return h?h.closest('.fixed').innerText:'NODIALOG';})()")
print("dialog:", d)
b.shot(os.path.join(FR, 'voice_contacts_registered.png'))
b.close()
print("DONE")
