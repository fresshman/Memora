# -*- coding: utf-8 -*-
"""重采行动页深度思考档位帧（当前干净看板）。"""
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
b.navigate(B + '/action/', wait=5)
b.wait_for(
    "(function(){return Array.from(document.querySelectorAll('button')).some(function(x){"
    "return x.textContent.trim()==='快速模式';});})()", timeout=40)
# 切到深度思考
b.eval(
    "(function(){var t=Array.from(document.querySelectorAll('button')).find(function(x){"
    "return x.textContent.trim()==='快速模式';});t.click();return 'clicked';})()")
time.sleep(1.2)
label = b.eval(
    "(function(){var t=Array.from(document.querySelectorAll('button')).find(function(x){"
    "return x.textContent.indexOf('深度思考')>=0;});return t?t.textContent.trim():'';})()")
print("button label:", label)
b.shot(os.path.join(FR, 'board_deep.png'), full=False)
# 切回快速
b.eval(
    "(function(){var t=Array.from(document.querySelectorAll('button')).find(function(x){"
    "return x.textContent.indexOf('深度思考')>=0;});if(t)t.click();return 'back';})()")
b.close()
print("DONE")
