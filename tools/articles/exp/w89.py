import sys, os, re, struct, threading, statistics, errno, urllib.request, urllib.error, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import requests, urllib3
tee('w89'); reset()

print('== 一:状态码长什么样:向 httpbin.org/status/<码> 逐个请求(它专门按你要的码回应),看状态行里的原因短语、消息体大小,和有特殊含义的头部')
codes = [200, 201, 204, 301, 302, 304, 400, 401, 403, 404, 405, 409, 410, 418, 429, 500, 501, 502, 503, 504]
print('    码    原因短语                      消息体字节   特殊头部')
for code in codes:
    try:
        r = requests.get(f'https://httpbin.org/status/{code}', timeout=10, allow_redirects=False)
        sp = {k: v for k, v in r.headers.items() if k.lower() in ('location', 'www-authenticate', 'retry-after', 'allow', 'content-type') and (k.lower() != 'content-type' or len(r.content))}
        print(f'    {r.status_code}   {r.reason:<26} {len(r.content):>8}    {sp}')
    except Exception as e: print(f'    {code}   失败 {type(e).__name__}')

print('== 二:同一个 404 / 500,不同客户端库怎么表现(要不要抛异常)')
for code in (404, 500):
    u = f'https://httpbin.org/status/{code}'
    r = requests.get(u, timeout=10); a = f'requests.get:不抛异常,status_code = {r.status_code};r.ok = {r.ok};调用 raise_for_status() → '
    try: r.raise_for_status(); a += '无异常'
    except requests.HTTPError as e: a += f'抛 HTTPError("{str(e)[:50]}")'
    try: urllib.request.urlopen(u, timeout=10); b = 'urllib.request.urlopen:成功'
    except urllib.error.HTTPError as e: b = f'urllib.request.urlopen:抛 HTTPError {e.code}'
    pm = urllib3.PoolManager(); rr = pm.request('GET', u, retries=False, timeout=10); c = f'urllib3.request(retries=False):不抛异常,status = {rr.status}'
    cc = http.client.HTTPSConnection('httpbin.org', 443, timeout=10); cc.request('GET', f'/status/{code}'); d = f'http.client:不抛异常,status = {cc.getresponse().status}'
    print(f'  {code}:\n    {a}\n    {b}\n    {c}\n    {d}')

print('== 三:429 / 503 与 Retry-After:本机服务器前 N 次返回错误码,之后返回 200。urllib3 的 Retry(status_forcelist=[429, 503])会按 Retry-After 头等待,没有这个头时用指数退避。测量客户端实际等了多久')
cnt = [0]; mode = ['ra']
def srv(port, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(32); ls.settimeout(0.3)
    def h(c):
        try:
            c.settimeout(5); buf = b''
            while b'\r\n\r\n' not in buf: buf += c.recv(65536)
            cnt[0] += 1; arrive.append(time.time())
            if mode[0] == 'ra' and cnt[0] == 1: c.sendall(b'HTTP/1.1 429 Too Many Requests\r\nRetry-After: 2\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            elif mode[0] == 'backoff' and cnt[0] <= 4: c.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            else: c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok')
        except Exception: pass
        finally: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
arrive = []; port = lab_port(); stop = [False]; srv(port, stop)
cnt[0] = 0; arrive.clear(); mode[0] = 'ra'
t0 = time.time(); r = urllib3.PoolManager().request('GET', f'http://127.0.0.1:{port}/', retries=urllib3.util.Retry(total=3, status_forcelist=[429, 503], respect_retry_after_header=True, backoff_factor=0.5))
print(f'  429 + Retry-After: 2:客户端第 {cnt[0]} 次请求拿到 {r.status};两次请求到达服务器的间隔 {(arrive[1] - arrive[0]):.2f} 秒(服务器要求等 2 秒)')
cnt[0] = 0; arrive.clear(); mode[0] = 'backoff'
r = urllib3.PoolManager().request('GET', f'http://127.0.0.1:{port}/', retries=urllib3.util.Retry(total=5, status_forcelist=[503], backoff_factor=0.5))
gaps = [arrive[i + 1] - arrive[i] for i in range(len(arrive) - 1)]
print(f'  503 前 4 次失败(没有 Retry-After),backoff_factor = 0.5:客户端第 {cnt[0]} 次请求拿到 {r.status};相邻请求的间隔(秒){[round(g, 2) for g in gaps]}(指数退避:0 / 1.0 / 2.0 / 4.0 附近;urllib3 第一次重试不等)')
r = urllib3.PoolManager().request('GET', f'http://127.0.0.1:{port}/', retries=False); print(f'  不开重试时,同样的 503/200 序列只发 1 次请求:状态 {r.status}')

print('== 四:Expect: 100-continue:要发一个 5 MB 的请求体之前,先只发请求头并带 Expect: 100-continue,等服务器回 100 Continue 再发体;如果服务器因为认证失败直接回 401,客户端就省了 5 MB。对比不用 Expect 的做法')
recv = {'n': 0}
def srv2(port, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(32); ls.settimeout(0.3)
    def h(c):
        try:
            c.settimeout(5); buf = b''
            while b'\r\n\r\n' not in buf: buf += c.recv(65536)
            head, rest = buf.split(b'\r\n\r\n', 1); expect = b'100-continue' in head.lower(); got = len(rest)
            if b'authorization' not in head.lower():
                c.sendall(b'HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'); c.shutdown(socket.SHUT_WR)
                end = time.time() + 1.0
                while time.time() < end:
                    try:
                        d = c.recv(1 << 20)
                        if not d: break
                        got += len(d)
                    except socket.timeout: break
                recv['n'] = got; return
            if expect: c.sendall(b'HTTP/1.1 100 Continue\r\n\r\n')
            c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
        except Exception: pass
        finally: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
port2 = lab_port(); stop2 = [False]; srv2(port2, stop2); BODY = b'x' * 5_000_000
def post(expect):
    recv['n'] = 0; s = socket.create_connection(('127.0.0.1', port2)); s.settimeout(5); sent = 0
    s.sendall(b'POST /upload HTTP/1.1\r\nHost: x\r\nContent-Length: %d\r\n%s\r\n' % (len(BODY), b'Expect: 100-continue\r\n' if expect else b'')); sent += 0
    first = None
    if expect:
        s.settimeout(1.0)
        try: first = s.recv(1024).split(b'\r\n')[0].decode()
        except socket.timeout: first = '(1 秒内没有收到任何响应,按规范可以直接发体)'
    sent_body = 0
    if first is None or first.startswith('HTTP/1.1 100'):
        s.settimeout(5)
        try:
            while sent_body < len(BODY): n = s.send(BODY[sent_body:sent_body + 262144]); sent_body += n
        except Exception: pass
    else: pass
    try: resp = s.recv(1024).split(b'\r\n')[0].decode() if first is None else first
    except Exception: resp = '(读响应时连接被重置)'
    s.close(); time.sleep(1.2); return resp, sent_body, recv['n']
a = post(False); b = post(True)
print(f'  不带 Expect:客户端把 5 MB 都发了(客户端写出 {a[1]} 字节),服务器读了 {a[2]} 字节后拒绝;客户端收到的第一行 {a[0]!r}')
print(f'  带 Expect: 100-continue(未认证):服务器直接回 {b[0]!r},客户端没有发请求体(写出 {b[1]} 字节),服务器读到的请求体 {b[2]} 字节——省下 5 MB')
stop[0] = True; stop2[0] = True
