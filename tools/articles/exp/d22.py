import sys, os, time, json, subprocess, http.client, signal, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d22'); R = {}
GUN = str(HERE.parent / 'djlab' / 'bin' / 'gunicorn')
urls = '''
import time
from django.urls import path
from django.http import HttpResponse, StreamingHttpResponse
def slow_chunks(n, delay):
    for i in range(n):
        time.sleep(delay); yield f'chunk {i}\\n'.encode()
def buffered(request):
    return HttpResponse(b''.join(slow_chunks(5, 0.3)))
def streaming(request):
    return StreamingHttpResponse(slow_chunks(5, 0.3))
def big_buffered(request): return HttpResponse(b'x' * (200 * 1024 * 1024))
def big_streaming(request):
    def gen():
        chunk = b'x' * (1024 * 1024)
        for _ in range(200): yield chunk
    return StreamingHttpResponse(gen())
def attrs(request):
    r = StreamingHttpResponse(iter([b'a', b'b']))
    out = []
    out.append('streaming = %s' % r.streaming)
    try: r.content
    except AttributeError as e: out.append('r.content → AttributeError: %s' % e)
    out.append('Content-Length 头: %s' % r.has_header('Content-Length'))
    out.append('streaming_content 类型: %s' % type(r.streaming_content).__name__)
    return HttpResponse('\\n'.join(out))
urlpatterns = [path('buffered/', buffered), path('streaming/', streaming), path('big_buffered/', big_buffered), path('big_streaming/', big_streaming), path('attrs/', attrs)]
'''
d = proj('d22', urls=urls, apps=['django.contrib.contenttypes'], with_lab=False, middleware=['django.middleware.common.CommonMiddleware'])
PORT = 9320
def rss(pid):
    r = subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True); return int(r.stdout.strip() or 0) / 1024
def children(pid):
    r = subprocess.run(['pgrep', '-P', str(pid)], capture_output=True, text=True); return [int(x) for x in r.stdout.split()]
def start():
    p = subprocess.Popen([GUN, 'proj.wsgi:application', '-b', f'127.0.0.1:{PORT}', '-w', '1', '--timeout', '60', '--log-level', 'error'], cwd=d, env=env(d), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try: http.client.HTTPConnection('127.0.0.1', PORT, timeout=1).request('GET', '/attrs/'); break
        except Exception: time.sleep(0.1)
    time.sleep(0.5); return p
def stop(p):
    p.send_signal(signal.SIGTERM)
    try: p.wait(10)
    except Exception: p.kill()
    time.sleep(0.5)
p = start()
def fetch(path, sample_pid=None):
    c = http.client.HTTPConnection('127.0.0.1', PORT, timeout=60); t0 = time.perf_counter(); c.request('GET', path); r = c.getresponse()
    first = None; total = 0; times = []; peak = 0
    stop = [False]
    def sampler():
        nonlocal peak
        while not stop[0]:
            if sample_pid:
                for cp in children(sample_pid) or [sample_pid]: peak = max(peak, rss(cp))
            time.sleep(0.02)
    th = threading.Thread(target=sampler); th.start()
    while True:
        b = r.read1(65536)
        if not b: break
        if first is None: first = time.perf_counter() - t0
        total += len(b); times.append(time.perf_counter() - t0)
    stop[0] = True; th.join()
    return dict(first_ms=first * 1000, total_ms=(time.perf_counter() - t0) * 1000, bytes=total, headers=dict(r.getheaders()), peak_mb=peak)
print('== 一:5 段内容,每段之间服务端睡 0.3 s:客户端什么时候收到第一个字节?')
R['ttfb'] = {}
for name in ('buffered', 'streaming'):
    r = fetch(f'/{name}/'); R['ttfb'][name] = r
    print(f'  /{name}/  首字节 {r["first_ms"]:.0f} ms,收完 {r["total_ms"]:.0f} ms,共 {r["bytes"]} 字节;Content-Length: {r["headers"].get("Content-Length")}  Transfer-Encoding: {r["headers"].get("Transfer-Encoding")}')
print()
print('== 二:StreamingHttpResponse 对象的属性')
c = http.client.HTTPConnection('127.0.0.1', PORT, timeout=10); c.request('GET', '/attrs/'); o = c.getresponse().read().decode(); print('  ' + o.replace('\n', '\n  ')); R['attrs'] = o
print()
print('== 三:200 MiB 的响应:一次性 HttpResponse vs 生成器流式;每种都用全新的 gunicorn worker,每 20 ms 采样 worker 进程的 RSS')
stop(p)
R['big'] = {}
for name in ('big_buffered', 'big_streaming'):
    p = start(); w = children(p.pid); base = max(rss(x) for x in w)
    r = fetch(f'/{name}/', sample_pid=p.pid); R['big'][name] = r; r['base'] = base
    print(f'  /{name}/  worker 起始 RSS ≈ {base:.0f} MiB;收完 {r["total_ms"]:.0f} ms,首字节 {r["first_ms"]:.0f} ms,{r["bytes"] / 1048576:.0f} MiB;峰值 RSS ≈ {r["peak_mb"]:.0f} MiB;Content-Length: {r["headers"].get("Content-Length")}')
    stop(p)
save('d22', R)
