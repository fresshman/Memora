# -*- coding: utf-8 -*-
"""批量采集：钉钉/飞书解析 + 批量复盘/问答/语音/行动项/历史/模型管理页面。"""
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

def upload_shot(fname, outname):
    b.set_files('input[type=file]', [os.path.join(ROOT, 'samples', fname)])
    b.wait_for(
        "Array.from(document.querySelectorAll('h2'))"
        ".some(function(e){return e.textContent.indexOf('对话预览')>=0})",
        timeout=60)
    time.sleep(1.2)
    b.shot(os.path.join(FR, outname), full=True)
    meta = b.eval(
        "(function(){var h=Array.from(document.querySelectorAll('h2'))"
        ".find(function(e){return e.textContent.indexOf('对话预览')>=0});"
        "return h?h.parentElement.innerText.split(String.fromCharCode(10))[0]:'';})()")
    print("uploaded", fname, "->", meta)

# 首页：钉钉 csv
b.navigate('http://127.0.0.1:8010/', wait=2.5)
upload_shot(os.path.join('dingtalk', '01_standard.csv'), 'parse_dingtalk.png')
# 首页：飞书 html
b.navigate('http://127.0.0.1:8010/', wait=2.0)
upload_shot(os.path.join('feishu', '01_ts_block.html'), 'parse_feishu.png')

# 各页面导航截图
pages = [
    ('batch', 'page_batch.png', 3.0),
    ('qa', 'page_qa.png', 2.5),
    ('voice', 'page_voice.png', 4.0),
    ('action', 'page_action.png', 3.0),
    ('history', 'page_history.png', 3.0),
    ('models', 'page_models.png', 4.5),
]
for slug, out, w in pages:
    b.navigate('http://127.0.0.1:8010/%s/' % slug, wait=w)
    b.shot(os.path.join(FR, out), full=True)
    txt = b.eval("document.body.innerText.slice(0,160)")
    print("page", slug, "->", out, "|", txt.replace(chr(10), ' / ')[:120])

b.close()
print("DONE")
