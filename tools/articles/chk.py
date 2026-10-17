"""用法: python3 chk.py k8s-a.html k8s-b.html ...  —— 无头 Chrome 逐个打开页面,点完每个演示的所有步骤,汇报空面板 / JS 报错 / 横向溢出。需要先在 ktmp/site 起 python3 -m http.server 9801。"""
import sys, subprocess, json, re
chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
r = subprocess.run([chrome, '--headless=new', '--disable-gpu', '--virtual-time-budget=60000', '--dump-dom', f'http://localhost:9801/check.html?f={",".join(sys.argv[1:])}'], capture_output=True, text=True, timeout=180)
m = re.search(r'RESULT(.*?)END', r.stdout, re.S)
res = json.loads(m.group(1).replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')) if m else None
if not res: print('没有结果', r.stdout[-300:])
else:
    for x in res: print(x['f'], 'steps', x.get('steps'), 'empties', x.get('empties'), 'overflow', x.get('overflow'), 'errs', x.get('errs'), x.get('err', ''))
