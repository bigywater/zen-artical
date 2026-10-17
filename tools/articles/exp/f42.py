import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f42'); R = {}
import http.client, threading
from flask import Flask, Response, request, stream_with_context
APP = '''
import time, os
from flask import Flask, Response, request, stream_with_context, current_app
app = Flask(__name__)
LOG = os.environ.get("LOGFILE", "/dev/null")
@app.get("/slow")
def slow():
    def gen():
        for i in range(5):
            yield f"chunk{i}\\n"; time.sleep(0.2)
    return Response(gen(), mimetype="text/plain")
@app.get("/all")
def all_():
    parts = []
    for i in range(5):
        parts.append(f"chunk{i}\\n"); time.sleep(0.2)
    return Response("".join(parts), mimetype="text/plain")
@app.get("/ctx-bad")
def ctx_bad():
    def gen():
        yield "start;"
        yield f"path={request.path}"
    return Response(gen(), mimetype="text/plain")
@app.get("/ctx-good")
def ctx_good():
    def gen():
        yield "start;"
        yield f"path={request.path}"
    return Response(stream_with_context(gen()), mimetype="text/plain")
@app.get("/big/<int:mb>")
def big(mb):
    def gen():
        chunk = b"x" * (1024 * 1024)
        for _ in range(mb): yield chunk
    return Response(gen(), mimetype="application/octet-stream")
@app.get("/big-mem/<int:mb>")
def big_mem(mb): return Response(b"x" * (mb * 1024 * 1024), mimetype="application/octet-stream")
@app.get("/watch")
def watch():
    def gen():
        try:
            for i in range(100):
                yield f"tick{i}\\n"; time.sleep(0.1)
        except GeneratorExit:
            open(LOG, "a").write("generator closed by server (client disconnected)\\n"); raise
        finally:
            open(LOG, "a").write("finally 执行了\\n")
    return Response(gen(), mimetype="text/plain")
'''
d = mkapp('f42', {'app.py': APP}); log = d / 'watch.log'
def rss_of_tree(pid):
    kids = subprocess.run(['pgrep', '-P', str(pid)], capture_output=True, text=True).stdout.split(); tot = 0
    for p in [str(pid)] + kids:
        o = subprocess.run(['ps', '-o', 'rss=', '-p', p], capture_output=True, text=True).stdout.strip(); tot = max(tot, int(o) if o else 0)
    return tot / 1024
print('== 一:真实 HTTP(gunicorn)下的流式响应:响应头、每个 chunk 到达的时间,对比先拼好再返回')
src(APP.split('@app.get("/ctx-bad")')[0].split('@app.get("/slow")')[1].split('@app.get("/all")')[0], '视图(摘自 app.py)')
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '--workers', '1', 'app:app'], LOGFILE=str(log)) as s:
    c = http.client.HTTPConnection('127.0.0.1', s.port); t0 = time.perf_counter(); c.request('GET', '/all'); r = c.getresponse(); first = time.perf_counter() - t0; body = r.read(); total = time.perf_counter() - t0
    print(f'  /all(先在内存里拼好再返回):收到响应头用了 {first:.2f} 秒,全部收完 {total:.2f} 秒;响应头:', {k: v for k, v in r.getheaders() if k.lower() in ('content-length', 'transfer-encoding')}); R['all'] = [round(first, 2), round(total, 2), {k: v for k, v in r.getheaders() if k.lower() in ('content-length', 'transfer-encoding')}]
    c = http.client.HTTPConnection('127.0.0.1', s.port); c.request('GET', '/slow'); r = c.getresponse(); print('  响应头:', {k: v for k, v in r.getheaders() if k.lower() in ('content-type', 'transfer-encoding', 'content-length', 'connection')}); R['hdr'] = {k: v for k, v in r.getheaders() if k.lower() in ('content-type', 'transfer-encoding', 'content-length', 'connection')}
    t0 = time.perf_counter(); arrivals = []
    while True:
        line = r.fp.readline()
        if not line: break
        arrivals.append((round(time.perf_counter() - t0, 2), line.strip())) if line.strip().startswith(b'chunk') else None
    c.close()
    print('  /slow 每个 chunk 到达的时间(秒)与内容:', [(a, b.decode()) for a, b in arrivals]); R['slow'] = [(a, b.decode()) for a, b in arrivals]
    print()
    print('== 二:用 curl --raw 看线路上的 chunked 分块格式')
    r = subprocess.run(['curl', '-s', '--raw', '-i', f'http://127.0.0.1:{s.port}/slow'], capture_output=True); txt = r.stdout.decode('latin-1').replace('\r\n', '\\r\\n\n'); print('  ' + txt.replace('\n', '\n  ').rstrip()[:420]); R['raw'] = txt[:420]
    print()
    print('== 三:stream_with_context:生成器里访问 request——不包装时请求上下文在响应开始流出前就被弹出了')
    for p in ('/ctx-bad', '/ctx-good'):
        r = subprocess.run(['curl', '-s', '-i', f'http://127.0.0.1:{s.port}{p}'], capture_output=True); body = r.stdout.decode('utf-8', 'replace').split('\r\n\r\n', 1)[-1]; first = r.stdout.decode('utf-8', 'replace').split('\r\n')[0]
        R.setdefault('ctx', {})[p] = [first, body[:80]]; print(f'  GET {p:<10} → {first} | 正文 {body[:80]!r}')
    time.sleep(0.3); L_ = [l for l in s.logtext().split('\n') if 'RuntimeError' in l or 'Error' in l][:2]; print('  服务器日志里的错误行:', L_); R['ctx_log'] = L_
    print()
    print('== 四:内存:下载 300 MB——流式生成每块 1 MB vs 先在内存里造出 300 MB 再返回,gunicorn worker 的峰值常驻内存(ps rss,每 20 ms 采样)')
    R['mem'] = {}
    base = rss_of_tree(s.p.pid)
    for label, path in (('流式(生成器,每块 1 MB)', '/big/300'), ('一次性 bytes(300 MB)', '/big-mem/300')):
        stop = [False]; peak = [0.0]
        def poll():
            while not stop[0]: peak[0] = max(peak[0], rss_of_tree(s.p.pid)); time.sleep(0.02)
        th = threading.Thread(target=poll); th.start(); t0 = time.perf_counter(); r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{size_download} 字节 %{time_total}s', f'http://127.0.0.1:{s.port}{path}'], capture_output=True, text=True); stop[0] = True; th.join()
        R['mem'][label] = [round(peak[0]), r.stdout.strip()]; print(f'  {label:<24} 峰值 RSS ≈ {peak[0]:.0f} MiB(基线 {base:.0f} MiB)| curl:{r.stdout.strip()}')
    R['base'] = round(base)
    print()
    print('== 五:客户端中途断开:服务器端的生成器会收到 GeneratorExit,finally 会执行(用来释放资源)')
    log.unlink(missing_ok=True)
    r = subprocess.run(['curl', '-s', '--max-time', '0.5', '-o', '/dev/null', f'http://127.0.0.1:{s.port}/watch'], capture_output=True, text=True); time.sleep(1.5)
    print('  curl --max-time 0.5(退出码', r.returncode, ')之后服务器记录的内容:', log.read_text().strip().split('\n') if log.exists() else '(没有)'); R['disc'] = log.read_text().strip().split('\n') if log.exists() else []
save('f42', R)
