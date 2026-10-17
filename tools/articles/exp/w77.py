import sys, os, re, struct, threading, statistics, errno, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import urllib3
tee('w77'); reset()
PUB = '104.20.23.154'
def raw(req, tmo=6):
    s = socket.create_connection((PUB, 80), timeout=tmo); s.settimeout(tmo); s.sendall(req); buf = b''
    try:
        while True:
            d = s.recv(65536)
            if not d: break
            buf += d
    except socket.timeout: pass
    s.close(); return buf
def parse(buf):
    if not buf: return None, {}, b''
    h, _, b = buf.partition(b'\r\n\r\n'); lines = h.split(b'\r\n'); d = {}
    for l in lines[1:]:
        if b':' in l: k, v = l.split(b':', 1); d[k.strip().decode().lower()] = v.strip().decode()
    return lines[0].decode(), d, b

print('== 一:example.com 对各种方法的态度:同一个路径 / 依次用 GET、HEAD、POST、PUT、DELETE、OPTIONS、PATCH、TRACE,看状态行和 Allow 头')
for m in ('GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH', 'TRACE'):
    body = b'x=1' if m in ('POST', 'PUT', 'PATCH') else b''
    req = f'{m} / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\nContent-Length: {len(body)}\r\n\r\n'.encode() + body
    st, d, b = parse(raw(req))
    print(f'  {m:<8}→ {st or "(无响应)"}'.ljust(52) + f'Allow: {d.get("allow")}  body {len(b)} 字节')

print('== 二:HEAD 与 GET:HEAD 应该返回和 GET 相同的头部,但没有消息体。比较两者的头部')
g = parse(raw(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n')); h = parse(raw(b'HEAD / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'))
skip = {'date', 'age', 'cf-ray', 'last-modified'}
same = sorted(k for k in g[1] if k in h[1] and g[1][k] == h[1][k] and k not in skip); diff = sorted(k for k in set(g[1]) | set(h[1]) if g[1].get(k) != h[1].get(k) and k not in skip)
print(f'  GET:{g[0]},头部 {len(g[1])} 个,消息体 {len(g[2])} 字节;HEAD:{h[0]},头部 {len(h[1])} 个,消息体 {len(h[2])} 字节')
print(f'  值相同的头部:{same};不同或只在一边的头部(除 Date / Age / CF-RAY / Last-Modified):{diff or "无"}')
print(f'  GET 有 Transfer-Encoding = {g[1].get("transfer-encoding")},HEAD 的 Content-Length = {h[1].get("content-length")}')

print('== 三:幂等性与重试:本机服务器模拟“服务器处理了请求,但响应丢了”。服务器收到请求先执行业务(把效果记在账上),然后在前 N 次连接上直接复位(不返回响应),第 N+1 次才正常返回。客户端用 urllib3 的重试机制')
ledger = {'post': 0, 'put': 0, 'get': 0, 'conns': 0}; fail_n = [2]
def srv(port, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(16); ls.settimeout(0.3)
    def h(c):
        ledger['conns'] += 1; buf = b''
        try:
            c.settimeout(5)
            while b'\r\n\r\n' not in buf: buf += c.recv(65536)
            head, _, rest = buf.partition(b'\r\n\r\n'); m = head.split()[0].decode()
            n = int(re.search(rb'content-length: *(\d+)', head, re.I).group(1)) if re.search(rb'content-length', head, re.I) else 0
            while len(rest) < n: rest += c.recv(65536)
            ledger[m.lower()] += 1
            if fail_n[0] > 0:
                fail_n[0] -= 1; c.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)); c.close(); return
            body = b'ok'; c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok'); c.close()
        except Exception: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
port = lab_port(); stop = [False]; srv(port, stop)
print(f'  urllib3 的默认重试方法集合(只有这些方法会在连接出错后自动重试):{sorted(urllib3.util.Retry.DEFAULT_ALLOWED_METHODS)}')
pm = urllib3.PoolManager(retries=urllib3.util.Retry(total=4, backoff_factor=0, connect=4, read=4, other=4))
for m in ('GET', 'PUT', 'POST'):
    for k in ledger: ledger[k] = 0
    fail_n[0] = 2
    try:
        r = pm.request(m, f'http://127.0.0.1:{port}/x', body=b'a=1' if m != 'GET' else None); out = f'最终成功,状态 {r.status}'
    except Exception as e: out = f'最终失败:{type(e).__name__}'
    print(f'  {m:<5}:前 2 次连接在服务器处理后被复位 → 客户端 {out};服务器共收到 {ledger["get"] + ledger["put"] + ledger["post"]} 次该请求,连接数 {ledger["conns"]}')
pm2 = urllib3.PoolManager(retries=urllib3.util.Retry(total=4, backoff_factor=0, allowed_methods=None))
for k in ledger: ledger[k] = 0
fail_n[0] = 2
try: r = pm2.request('POST', f'http://127.0.0.1:{port}/x', body=b'a=1'); out = f'最终成功,状态 {r.status}'
except Exception as e: out = f'最终失败:{type(e).__name__}'
print(f'  POST,强制允许 POST 重试(allowed_methods=None):客户端 {out};服务器的账上 POST 被执行了 {ledger["post"]} 次——前 2 次的响应丢了,但业务已经执行了,重试就重复执行了(这里是 "扣款" 的重复)')
stop[0] = True

print('== 四:方法名区分大小写;请求目标可以是 *:几种边缘情况')
for nm, req in (('小写 get', b'get / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'), ('OPTIONS *', b'OPTIONS * HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'), ('GET 带请求体(Content-Length: 5)', b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\nContent-Length: 5\r\n\r\nhello'), ('DELETE /', b'DELETE / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n')):
    st, d, b = parse(raw(req)); print(f'  {nm:<26}→ {st or "(无响应)"}  Allow: {d.get("allow")}')
