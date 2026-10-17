import sys, os, re, struct, threading, statistics, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w74'); reset()
PUB = '104.20.23.154'
def raw(req, host=PUB, port=80, tmo=6, readall=True):
    t0 = time.time(); s = socket.create_connection((host, port), timeout=tmo); s.settimeout(tmo)
    s.sendall(req); buf = b''; closed = False
    try:
        while True:
            d = s.recv(65536)
            if not d: closed = True; break
            buf += d
            if not readall and b'\r\n\r\n' in buf: break
            if readall and len(buf) > 200000: break
    except socket.timeout: pass
    except ConnectionResetError: closed = True
    s.close(); return buf, closed, (time.time() - t0) * 1000
def head_body(buf):
    i = buf.find(b'\r\n\r\n')
    if i < 0:
        j = buf.find(b'\n\n'); return (buf[:j], buf[j + 2:]) if j >= 0 else (buf, b'')
    return buf[:i], buf[i + 4:]
def show_head(h, maxn=24):
    lines = h.split(b'\r\n') if b'\r\n' in h else h.split(b'\n')
    for i, l in enumerate(lines[:maxn]): print(f'    {i:>2}  {l.decode("latin1")[:110]}')
    if len(lines) > maxn: print(f'    …共 {len(lines)} 行')
    return lines
def hdrs(lines):
    d = {}
    for l in lines[1:]:
        if b':' in l:
            k, v = l.split(b':', 1); d.setdefault(k.strip().decode('latin1').lower(), []).append(v.strip().decode('latin1'))
    return d

print('== 一:一个最小的 HTTP/1.1 请求与响应的每一部分:请求行、头部、空行(CRLF CRLF)、消息体。向 example.com:80 发这个 56 字节的请求')
req = b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'
print(f'  发出的请求({len(req)} 字节):' + repr(req))
print(f'  = 请求行 "GET / HTTP/1.1"(方法 + 空格 + 目标 + 空格 + 版本)+ CRLF;头部 "Host: example.com" CRLF "Connection: close" CRLF;空行 CRLF 表示头部结束')
buf, closed, t = raw(req); h, b = head_body(buf)
print(f'  收到 {len(buf)} 字节,用时 {t:.0f} ms,服务器{"随后关闭了连接" if closed else "没有关闭连接"};头部 {len(h)} 字节 + CRLFCRLF 4 字节 + 消息体 {len(b)} 字节')
lines = show_head(h)
d = hdrs(lines)
print(f'  状态行:{lines[0].decode()} → 版本 {lines[0].split()[0].decode()},状态码 {lines[0].split()[1].decode()},原因短语 "{b" ".join(lines[0].split()[2:]).decode()}"')
print(f'  头部共 {len(lines) - 1} 个;Content-Length = {d.get("content-length")},实际收到的消息体 {len(b)} 字节;Content-Type = {d.get("content-type")};Transfer-Encoding = {d.get("transfer-encoding")}')
print(f'  消息体开头:{b[:60]!r}')

print('== 二:头部名字不区分大小写,顺序无关,值前后的空白被忽略;但格式错了会怎样?各发一次,看状态码')
cases = [('正常', b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'),
         ('头部名字全大写 / 乱大小写', b'GET / HTTP/1.1\r\nHOST: example.com\r\ncOnNeCtIoN: close\r\n\r\n'),
         ('冒号后无空格、值后有多余空格', b'GET / HTTP/1.1\r\nHost:example.com   \r\nConnection:close\r\n\r\n'),
         ('缺少 Host 头(HTTP/1.1 必须有)', b'GET / HTTP/1.1\r\nConnection: close\r\n\r\n'),
         ('行尾只用 LF(没有 CR)', b'GET / HTTP/1.1\nHost: example.com\nConnection: close\n\n'),
         ('未知方法 FOO', b'FOO / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'),
         ('版本号写成 HTTP/9.9', b'GET / HTTP/9.9\r\nHost: example.com\r\nConnection: close\r\n\r\n'),
         ('请求目标是绝对 URI', b'GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'),
         ('同一个头出现两次(Host 写两遍)', b'GET / HTTP/1.1\r\nHost: example.com\r\nHost: example.org\r\nConnection: close\r\n\r\n')]
for nm, rq in cases:
    buf, closed, t = raw(rq, tmo=5)
    first = buf.split(b'\r\n', 1)[0].decode('latin1')[:70] if buf else '(没有响应)'
    print(f'  {nm:<34}→ {first}')

print('== 三:HTTP/1.0 与 HTTP/1.1 的默认连接行为:不写 Connection 头,服务器会不会在发完响应后关连接?(读 5 秒)')
for ver, rq in (('HTTP/1.0', b'GET / HTTP/1.0\r\nHost: example.com\r\n\r\n'), ('HTTP/1.1', b'GET / HTTP/1.1\r\nHost: example.com\r\n\r\n')):
    buf, closed, t = raw(rq, tmo=5); h, b = head_body(buf); d = hdrs(h.split(b'\r\n'))
    print(f'  请求 {ver}:响应状态行 {h.split(b"\r\n")[0].decode()[:40]};响应里的 Connection = {d.get("connection")};{"服务器在 %.0f ms 时关闭了连接" % t if closed else "5 秒内服务器没有关闭连接(保持着,等下一个请求)"}')

print('== 四:头部的大小限制:单个头部值越来越大,服务器在多大时拒绝?(最多发到 400 KB)')
for n in (1000, 16000, 64000, 100000, 130000, 200000, 400000):
    rq = b'GET / HTTP/1.1\r\nHost: example.com\r\nX-Pad: ' + b'a' * n + b'\r\nConnection: close\r\n\r\n'
    buf, closed, t = raw(rq, tmo=5)
    print(f'  X-Pad 长度 {n:>5}:{buf.split(b"\r\n", 1)[0].decode("latin1")[:60] if buf else "(没有响应 / 连接被重置)"}')
