import sys, os, time, json, re, signal, http.client, subprocess, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d68'); R = {}
GUN = str(HERE.parent / 'djlab' / 'bin' / 'gunicorn')
urls = '''
import os
from django.urls import path
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
@csrf_exempt
def up(request):
    f = request.FILES['f']
    info = {'cls': type(f).__name__, 'size': f.size}
    if hasattr(f, 'temporary_file_path'): p = f.temporary_file_path(); info['tmp_exists'] = os.path.exists(p); info['tmp_dir'] = os.path.dirname(p)
    return JsonResponse(info)
urlpatterns = [path('up/', up)]
'''
PORT = 9440
def start(extra_settings='', workers=1):
    d = proj('d68', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, settings_extra=extra_settings)
    p = subprocess.Popen([GUN, 'proj.wsgi:application', '-b', f'127.0.0.1:{PORT}', '-w', str(workers), '--timeout', '120', '--log-level', 'error'], cwd=d, env=env(d), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try: http.client.HTTPConnection('127.0.0.1', PORT, timeout=1).request('GET', '/up/'); break
        except Exception: time.sleep(0.1)
    time.sleep(0.5); return p
def stop(p):
    p.send_signal(signal.SIGTERM)
    try: p.wait(10)
    except Exception: p.kill()
    time.sleep(0.5)
def children(pid): return [int(x) for x in subprocess.run(['pgrep', '-P', str(pid)], capture_output=True, text=True).stdout.split()]
def rss(pid): return int(subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True).stdout.strip() or 0) / 1024
def upload(size_mb):
    boundary = 'XBOUNDARYX'; head = f'--{boundary}\r\nContent-Disposition: form-data; name="f"; filename="a.bin"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode(); tail = f'\r\n--{boundary}--\r\n'.encode()
    n = size_mb * 1048576; total = len(head) + n + len(tail)
    c = http.client.HTTPConnection('127.0.0.1', PORT, timeout=120); c.putrequest('POST', '/up/'); c.putheader('Content-Type', f'multipart/form-data; boundary={boundary}'); c.putheader('Content-Length', str(total)); c.endheaders()
    c.send(head); chunk = b'x' * 1048576
    for _ in range(size_mb): c.send(chunk)
    c.send(tail); r = c.getresponse(); return json.loads(r.read())
def peak_during(fn, pid):
    peak = [0]; stop_ = threading.Event()
    def s():
        while not stop_.is_set():
            for cp in children(pid) or [pid]: peak[0] = max(peak[0], rss(cp))
            time.sleep(0.02)
    t = threading.Thread(target=s); t.start(); r = fn(); stop_.set(); t.join(); return r, peak[0]
print('== 一:默认 FILE_UPLOAD_MAX_MEMORY_SIZE(2.5 MiB):小文件在内存,大文件落盘到临时文件')
p = start(); R['types'] = {}
for mb in (1, 2, 3, 50):
    r = upload(mb); R['types'][mb] = r; print(f'  上传 {mb:>2} MiB → {r["cls"]:<24} size={r["size"]}' + (f'  临时文件存在={r["tmp_exists"]}' if 'tmp_exists' in r else ''))
print('  (临时文件的目录:', R['types'][50].get('tmp_dir'), ';视图返回时它还在,响应发出后被清理)')
print()
print('== 二:上传 200 MiB 时 gunicorn worker 的内存:默认(落盘)')
time.sleep(0.5); base = max(rss(x) for x in children(p.pid))
r, pk = peak_during(lambda: upload(200), p.pid); R['big_default'] = dict(cls=r['cls'], peak=pk, base=base); print(f'  worker 起始 RSS ≈ {base:.0f} MiB;上传 200 MiB({r["cls"]})期间峰值 RSS ≈ {pk:.0f} MiB')
stop(p)
print()
print('== 三:把 FILE_UPLOAD_MAX_MEMORY_SIZE 调到 1 GiB:200 MiB 全部留在内存里')
p = start("\nFILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 1024\nDATA_UPLOAD_MAX_MEMORY_SIZE = None\n"); time.sleep(0.5); base = max(rss(x) for x in children(p.pid))
r, pk = peak_during(lambda: upload(200), p.pid); R['big_mem'] = dict(cls=r['cls'], peak=pk, base=base); print(f'  worker 起始 RSS ≈ {base:.0f} MiB;上传 200 MiB({r["cls"]})期间峰值 RSS ≈ {pk:.0f} MiB')
stop(p)
print()
print('== 四:FILE_UPLOAD_TEMP_DIR 指定临时目录')
tmpd = str(HERE / 'djtmp' / 'd68_uploads'); os.makedirs(tmpd, exist_ok=True)
p = start(f"\nFILE_UPLOAD_TEMP_DIR = {tmpd!r}\n"); r = upload(5); R['tempdir'] = dict(cls=r['cls'], tmp_dir=r.get('tmp_dir'), want=tmpd); print('  上传 5 MiB → 临时文件目录:', r.get('tmp_dir'), ' 是否等于指定目录:', r.get('tmp_dir') == tmpd)
stop(p); save('d68', R)
