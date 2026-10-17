import sys, os, re, struct, threading, statistics, errno, http.client, urllib.request, urllib.error, urllib.parse; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import urllib3, requests
tee('w82'); reset()

print('== 一:真实的重定向:http://www.python.org/ 和 http://python.org/ 各发一次明文请求(不跟随),看状态码、Location 和其它头')
for host in ('www.python.org', 'python.org'):
    c = http.client.HTTPConnection(host, 80, timeout=8); t0 = time.time(); c.request('GET', '/', headers={'User-Agent': 'w82'}); r = c.getresponse(); b = r.read(); dt = (time.time() - t0) * 1000
    hd = {k.lower(): v for k, v in r.getheaders()}
    print(f'  http://{host}/ → {r.status} {r.reason},Location = {hd.get("location")},消息体 {len(b)} 字节,用时 {dt:.0f} ms;Cache-Control = {hd.get("cache-control")};Content-Type = {hd.get("content-type")}')
t0 = time.time(); s = requests.get('http://python.org/', headers={'User-Agent': 'w82'}, timeout=10); dt = (time.time() - t0) * 1000
print(f'  requests 跟随 http://python.org/:经过 {len(s.history)} 次重定向,最终 {s.status_code} {s.url},总用时 {dt:.0f} ms;跳转链 {[(h.status_code, h.headers.get("location")) for h in s.history]}')

print('== 二:同一个重定向,不同客户端对方法和请求体的处理。本机服务器收到 POST /start(带 5 字节请求体 "hello"),回 301 / 302 / 303 / 307 / 308 重定向到 /final;/final 记下最终收到的方法和请求体长度')
log = []
def srv(port, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(32); ls.settimeout(0.3)
    def h(c):
        try:
            c.settimeout(5); buf = b''
            while b'\r\n\r\n' not in buf: buf += c.recv(65536)
            head, _, rest = buf.partition(b'\r\n\r\n'); line = head.split(b'\r\n')[0].decode(); m, path = line.split()[0], line.split()[1]
            n = int(re.search(rb'(?i)content-length: *(\d+)', head).group(1)) if re.search(rb'(?i)content-length', head) else 0
            while len(rest) < n: rest += c.recv(65536)
            u = urllib.parse.urlparse(path); q = urllib.parse.parse_qs(u.query)
            if u.path == '/start':
                code = int(q['code'][0]); c.sendall(b'HTTP/1.1 %d X\r\nLocation: /final?from=%d\r\nContent-Length: 0\r\nConnection: close\r\n\r\n' % (code, code))
            elif u.path == '/final':
                log.append((int(q['from'][0]), m, len(rest))); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok')
            elif u.path == '/loop':
                k = int(q.get('n', ['0'])[0]); log.append(('loop', k)); c.sendall(b'HTTP/1.1 302 Found\r\nLocation: /loop?n=%d\r\nContent-Length: 0\r\nConnection: close\r\n\r\n' % (k + 1))
            elif u.path == '/rel':
                loc = q['to'][0]; c.sendall(b'HTTP/1.1 302 Found\r\nLocation: ' + loc.encode() + b'\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            else:
                log.append(('path', m, path)); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok')
        except Exception: pass
        finally: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
port = lab_port(); stop = [False]; srv(port, stop); B = f'http://127.0.0.1:{port}'
def final(): 
    r = [x for x in log if x[0] != 'loop' and x[0] != 'path']; return r[-1] if r else None
res = {}
for code in (301, 302, 303, 307, 308):
    row = {}
    for cl in ('requests', 'urllib3', 'urllib.request'):
        log.clear()
        try:
            if cl == 'requests': requests.post(f'{B}/start?code={code}', data=b'hello', timeout=5)
            elif cl == 'urllib3': urllib3.PoolManager().request('POST', f'{B}/start?code={code}', body=b'hello', retries=urllib3.util.Retry(redirect=5))
            else: urllib.request.urlopen(urllib.request.Request(f'{B}/start?code={code}', data=b'hello', method='POST'), timeout=5).read()
            f = final(); row[cl] = f'{f[1]}+{f[2]}B' if f else '没到 /final'
        except urllib.error.HTTPError as e: row[cl] = f'异常 HTTP {e.code}'
        except Exception as e: row[cl] = f'异常 {type(e).__name__}'
    res[code] = row
print('    状态码   requests                urllib3                 urllib.request     (每格:最终到达 /final 时的 方法+请求体字节数)')
for code, row in res.items(): print(f'    {code}      {row["requests"]:<22} {row["urllib3"]:<22} {row["urllib.request"]}')
print('  规范(RFC 9110)的意图:301 / 302 历史上浏览器把 POST 改成 GET;303 明确要求改成 GET;307 / 308 必须保持方法和请求体。')

print('== 三:重定向循环:/loop 不停地 302 到下一个 /loop?n=k+1。各客户端在放弃之前走了多少步')
for cl in ('requests', 'urllib3 默认', 'urllib.request'):
    log.clear()
    try:
        if cl == 'requests': requests.get(f'{B}/loop', timeout=5)
        elif cl == 'urllib3 默认': urllib3.PoolManager().request('GET', f'{B}/loop')
        else: urllib.request.urlopen(f'{B}/loop', timeout=5).read()
        out = '没有出错'
    except Exception as e: out = f'{type(e).__name__}'
    print(f'  {cl:<16}:服务器共收到 {len([x for x in log if x[0] == "loop"])} 次 /loop 请求后客户端放弃,异常 {out}')

print('== 四:Location 的写法:相对路径、父目录、协议相对、带片段。各发一个 302,看 requests 最终请求的路径')
for to in ('/abs/path', 'rel/path', '../up', '//127.0.0.1:%d/proto-rel' % port, '/with?x=1#frag'):
    log.clear()
    try:
        r = requests.get(f'{B}/rel?to={urllib.parse.quote(to, safe="")}', timeout=5); got = [x for x in log if x[0] == 'path']
        print(f'  Location: {to:<34}→ 最终请求 {got[-1][2] if got else "(没有到达)"};最终 URL {r.url.replace(str(port), "<端口>")}')
    except Exception as e: print(f'  Location: {to:<34}→ 异常 {type(e).__name__}')
stop[0] = True
