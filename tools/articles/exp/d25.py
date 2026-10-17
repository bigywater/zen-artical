import sys, os, time, json, signal, urllib.request, glob; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d25'); R = {}
LOG = "import os, time\ndef mark(s):\n    with open(os.environ['EV_LOG'], 'a') as f: f.write(f'{time.time():.3f} {os.getpid()} {s}\\n')\n"
files = {
    'proj/mark.py': LOG,
    'lab/views.py': "from django.http import HttpResponse\nfrom django.shortcuts import render\nfrom proj.mark import mark\nmark('lab/views.py 被导入')\nVERSION = 'v1'\ndef hello(request): return HttpResponse('view ' + VERSION)\ndef page(request): return render(request, 'page.html', {})\n",
    'proj/urls.py': "from django.urls import path\nfrom lab import views\nurlpatterns = [path('hello/', views.hello), path('page/', views.page)]\n",
    'templates/page.html': 'template v1',
    'lab/other.py': "X = 1\n",
    'notes.txt': 'not python',
}
d = proj('d25', files=files, apps=['django.contrib.contenttypes', 'lab'])
PORT = 9330; LG = str(DJ / 'd25' / 'ev.log'); open(LG, 'w').close()
p = subprocess.Popen([PY, 'manage.py', 'runserver', f'127.0.0.1:{PORT}'], cwd=d, env=env(d, EV_LOG=LG), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
import threading
outl = []
threading.Thread(target=lambda: [outl.append(l.rstrip()) for l in p.stdout], daemon=True).start()
def get(path):
    try: return urllib.request.urlopen(f'http://127.0.0.1:{PORT}{path}', timeout=2).read().decode()
    except Exception as e: return None
def wait_up(timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if get('/hello/'): return True
        time.sleep(0.05)
    return False
assert wait_up(); time.sleep(3)
print('== 一:runserver 的启动输出(默认使用哪种 reloader)')
for l in outl[:12]: print('  ', l)
R['banner'] = outl[:12]
def pids(): return sorted(set(l.split()[1] for l in open(LG).read().splitlines() if 'views.py' in l))
print()
print('== 二:改一个被导入的 .py 文件:多久后新代码生效?进程有没有换?(每种情形重复 3 次)')
vp = d / 'lab' / 'views.py'
def edit_and_time(pathfile, mutate, probe, expect, label, reps=3):
    res = []
    for i in range(reps):
        before = set(pids()); t0 = time.time(); mutate(i)
        seen = None
        while time.time() - t0 < 15:
            r = get(probe)
            if r and expect(i) in r: seen = time.time() - t0; break
            time.sleep(0.02)
        time.sleep(1.5); res.append((seen, len(set(pids()) - before)))
    print(f'  {label:<34} 生效用时(s):{[round(x[0], 2) if x[0] else None for x in res]};期间新增的进程数:{[x[1] for x in res]}')
    return res
R['py'] = edit_and_time(vp, lambda i: vp.write_text(vp.read_text().replace(f"VERSION = 'v{i+1}'", f"VERSION = 'v{i+2}'")), '/hello/', lambda i: f'view v{i+2}', '改视图模块 lab/views.py')
print()
print('== 三:改模板文件、改没被导入的 .py、改非 .py 文件:会不会重启')
tp = d / 'templates' / 'page.html'
get('/page/'); time.sleep(0.5)
def tpl_case():
    res = []
    for i in range(3):
        get('/page/'); b4 = set(pids()); t0 = time.time(); tp.write_text(f'template v{i+2}'); seen = None; stale = 0
        while time.time() - t0 < 10:
            r = get('/page/')
            if r and f'template v{i+2}' in r: seen = time.time() - t0; break
            stale += 1; time.sleep(0.02)
        time.sleep(1.5); res.append((seen, stale, len(set(pids()) - b4)))
    return res
R['tpl'] = tpl_case()
print('  改模板 templates/page.html(每次先请求一次让它进缓存)生效用时(s):', [round(x[0], 2) if x[0] is not None else None for x in R['tpl']], ' 期间读到旧内容的次数:', [x[1] for x in R['tpl']], ' 新增进程:', [x[2] for x in R['tpl']])
op = d / 'lab' / 'other.py'
b4 = set(pids()); op.write_text('X = 2\n'); time.sleep(3); R['unimported'] = len(set(pids()) - b4); print(f'  改「没有被任何模块导入」的 lab/other.py 后 3 s 内新增进程 {R["unimported"]} 个')
nt = d / 'notes.txt'; b4 = set(pids()); nt.write_text('changed'); time.sleep(3); R['txt'] = len(set(pids()) - b4); print(f'  改 notes.txt 后 3 s 内新增进程 {R["txt"]} 个')
print()
print('== 四:runserver 输出里关于重载的行')
time.sleep(0.5)
for l in [l for l in outl if 'changed' in l or 'Watching' in l or 'Reloading' in l or 'reload' in l.lower()][:8]: print('  ', l)
R['reload_lines'] = [l for l in outl if 'changed' in l or 'Watching' in l][:6]
p.send_signal(signal.SIGINT)
try: p.wait(10)
except Exception: p.kill()
subprocess.run(['pkill', '-f', f'runserver 127.0.0.1:{PORT}'], capture_output=True)
save('d25', R)
