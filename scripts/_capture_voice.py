# -*- coding: utf-8 -*-
"""采集：真实上传多人会议片段，转写 + 说话人分离，采集处理帧与标注会议记录。"""
import sys, time, subprocess, os, json
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

# 上传演示音频（语音页第一个 file input）
b.set_files('input[type=file]', [os.path.join(FR, 'demo_meeting.wav')])
print("audio uploaded, transcribing...")

# 边转写边截图（每 8 秒），等待“会议记录”出现
t0 = time.time()
fi = 0
done = False
while time.time() - t0 < 300:
    time.sleep(8)
    fi += 1
    b.shot(os.path.join(FR, 'voice_proc_%02d.png' % fi))
    has = b.eval(
        "Array.from(document.querySelectorAll('h2'))"
        ".some(function(e){return e.textContent.trim()==='会议记录'})")
    busy = b.eval(
        "document.body.innerText.indexOf('正在本地处理')>=0")
    print("t=%ds h2_records=%s processing=%s" %
          (int(time.time()-t0), has, busy))
    if has and not busy:
        done = True
        break

time.sleep(1.5)
b.shot(os.path.join(FR, 'voice_record_view.png'))
b.shot(os.path.join(FR, 'voice_record_full.png'), full=True)

# 提取 meta + 分段
data = b.eval(
    "(function(){var txt=document.body.innerText;"
    "var rows=[];"
    "var lines=document.querySelectorAll('[class*=font-mono]');"
    "var segs=[];"
    "document.querySelectorAll('div').forEach(function(){});"
    "return JSON.stringify({raw:txt.slice(0,3000)});})()")
# 更结构化：从 React 数据不易拿，改为解析记录区文本
record_text = b.eval(
    "(function(){var h=Array.from(document.querySelectorAll('h2'))"
    ".find(function(e){return e.textContent.trim()==='会议记录'});"
    "if(!h) return '';var sec=h.closest('section');"
    "return sec?sec.innerText:'';})()")
with open(os.path.join(FR, 'voice_record_text.txt'), 'w', encoding='utf-8') as f:
    f.write(record_text)
print("=== record text (first 2500) ===")
print(record_text[:2500])

b.close()
print("DONE done_flag=", done)
