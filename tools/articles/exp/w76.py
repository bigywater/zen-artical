import sys, os, re, struct, threading, statistics, errno, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w76'); reset()
PUB = '104.20.23.154'
def scripted(pieces, close=True, nconn=1, keep=0):
    """起一个一次性服务器:读完请求头,按 pieces=[(延迟秒, 字节)] 逐段发送;close=True 发完关闭,否则保持 keep 秒"""
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); p = lab_port(); ls.bind(('127.0.0.1', p)); ls.listen(4); ls.settimeout(8)
    def run():
        for _ in range(nconn):
            try: c, _ = ls.accept()
            except Exception: break
            c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1); buf = b''
            try:
                while b'\r\n\r\n' not in buf: buf += c.recv(65536)
                for d, b in pieces:
                    if d: time.sleep(d)
                    c.sendall(b)
                if not close: time.sleep(keep)
            except Exception: pass
            finally: c.close()
        ls.close()
    threading.Thread(target=run, daemon=True).start(); return p
def chunked(parts, trailer=b''):
    return b''.join(b'%x\r\n' % len(x) + x + b'\r\n' for x in parts) + b'0\r\n' + trailer + b'\r\n'

print('== 一:解码 example.com 的分块响应:把 w74 里看到的 "241\\r\\n<!doctype …" 逐块拆开,数框架开销')
s = socket.create_connection((PUB, 80), timeout=6); s.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'); buf = b''
while True:
    d = s.recv(65536)
    if not d: break
    buf += d
s.close(); head, body = buf.split(b'\r\n\r\n', 1)
print(f'  响应头里:Transfer-Encoding = {re.search(rb"transfer-encoding: *(.*)", head, re.I).group(1).decode()};Content-Length = {re.search(rb"content-length", head, re.I)}')
i = 0; chunks = []; overhead = 0
while True:
    j = body.index(b'\r\n', i); size = int(body[i:j].split(b';')[0], 16); overhead += (j + 2 - i)
    if size == 0: end = body[j + 2:]; overhead += 2 if end == b'\r\n' else len(end); break
    chunks.append(body[j + 2:j + 2 + size]); overhead += 2; i = j + 2 + size + 2
payload = b''.join(chunks)
print(f'  消息体共 {len(body)} 字节:{len(chunks)} 个数据块,块大小 {[len(c) for c in chunks]};实际内容 {len(payload)} 字节,框架开销 {overhead} 字节(块长度行 + 每块后的 CRLF + 结尾的 "0\\r\\n\\r\\n")')
print(f'  内容开头 {payload[:40]!r}…结尾 {payload[-20:]!r};最后一个块之后 {body[-7:]!r} 是结束标记(长度 0 的块 + 空的 trailer + 空行)')

print('== 二:分块的开销与块大小的关系:把同样 100000 字节的内容分别用 Content-Length、每块 100 字节 / 1 KiB / 16 KiB 的 chunked 发送,算框架开销(计算 + 本机服务器实测)')
data = b'x' * 100000
for nm, cs in (('Content-Length', None), ('chunked,每块 100 字节', 100), ('chunked,每块 1 KiB', 1024), ('chunked,每块 16 KiB', 16384)):
    if cs is None: body = data; hdr = b'Content-Length: 100000\r\n'
    else: body = chunked([data[i:i + cs] for i in range(0, len(data), cs)]); hdr = b'Transfer-Encoding: chunked\r\n'
    p = scripted([(0, b'HTTP/1.1 200 OK\r\n' + hdr + b'Connection: close\r\n\r\n' + body)])
    c = socket.create_connection(('127.0.0.1', p)); c.sendall(b'GET / HTTP/1.1\r\nHost: x\r\n\r\n'); got = b''
    while True:
        d = c.recv(65536)
        if not d: break
        got += d
    c.close(); b2 = got.split(b'\r\n\r\n', 1)[1]
    print(f'  {nm:<22}:消息体 {len(b2)} 字节,框架开销 {len(b2) - 100000} 字节({(len(b2) - 100000) / 100000:.2%})')

print('== 三:chunked 的真正用处:边生成边发。服务器每 200 ms 生成一块(共 5 块),不知道总长度。客户端每块什么时候到?Content-Length 的做法则必须全部生成完才能发')
pieces = [(0, b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n')] + [(0.2, b'%x\r\n' % 20 + (b'part%d-' % i).ljust(20, b'.') + b'\r\n') for i in range(5)] + [(0, b'0\r\n\r\n')]
p = scripted(pieces); c = socket.create_connection(('127.0.0.1', p)); t0 = time.time(); c.sendall(b'GET / HTTP/1.1\r\nHost: x\r\n\r\n'); arr = []; buf = b''
while True:
    d = c.recv(65536)
    if not d: break
    arr.append((time.time() - t0) * 1000, ) if False else arr.append(((time.time() - t0) * 1000, len(d)))
c.close()
print('  chunked:客户端收到的数据(到达时刻 ms, 字节):' + ', '.join(f'({t:.0f}, {n})' for t, n in arr))
pieces = [(1.0, b'HTTP/1.1 200 OK\r\nContent-Length: 100\r\nConnection: close\r\n\r\n' + b'.' * 100)]
p = scripted(pieces); c = socket.create_connection(('127.0.0.1', p)); t0 = time.time(); c.sendall(b'GET / HTTP/1.1\r\nHost: x\r\n\r\n'); first = None; tot = 0
while True:
    d = c.recv(65536)
    if not d: break
    if first is None: first = (time.time() - t0) * 1000
    tot += len(d)
c.close()
print(f'  Content-Length(服务器要先生成完整内容,算出长度再发):第一个字节在 {first:.0f} ms 才到,共 {tot} 字节,全部在同一时刻到达')

print('== 四:既没有 Content-Length 也没有 chunked 的响应:消息体以“连接关闭”为终点(HTTP/1.0 的做法)。服务器发完 100 字节后保持连接 2 秒再关,客户端什么时候能认定响应结束?')
pieces = [(0, b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n' + b'.' * 100)]
p = scripted(pieces, close=False, keep=2); c = socket.create_connection(('127.0.0.1', p)); t0 = time.time(); c.sendall(b'GET / HTTP/1.1\r\nHost: x\r\n\r\n'); got = b''; t_first = None
while True:
    d = c.recv(65536)
    if not d: break
    if t_first is None: t_first = (time.time() - t0) * 1000
    got += d
c.close()
print(f'  100 字节在 {t_first:.0f} ms 就到齐了,但客户端无从知道这是全部——一直等到服务器在 {(time.time() - t0) * 1000:.0f} ms 关闭连接才能确定。这样的响应不可能复用连接')

print('== 五:长度写错会怎样,以及截断能不能被发现。用 Python 自带的 http.client 当客户端')
def hc(pieces, **kw):
    p = scripted(pieces, **kw); c = http.client.HTTPConnection('127.0.0.1', p, timeout=3)
    try:
        c.request('GET', '/'); r = c.getresponse(); b = r.read(); return f'正常读到 {len(b)} 字节(状态 {r.status})'
    except http.client.IncompleteRead as e: return f'IncompleteRead:已读 {len(e.partial)} 字节,还缺 {e.expected}'
    except Exception as e: return f'{type(e).__name__}: {str(e)[:50]}'
    finally: c.close()
H = b'HTTP/1.1 200 OK\r\nConnection: close\r\n'
print(f'  Content-Length: 1000,实际只发 600 字节就关闭连接 → {hc([(0, H + b"Content-Length: 1000\r\n\r\n" + b"x" * 600)])}')
print(f'  chunked,发了一个块之后没有发结尾的 0 块就关闭连接 → {hc([(0, H + b"Transfer-Encoding: chunked\r\n\r\n" + b"100\r\n" + b"x" * 256 + b"\r\n")])}')
print(f'  没有长度,发 600 字节就关闭连接(close 定界) → {hc([(0, H + b"X: y\r\n\r\n" + b"x" * 600)])}(读起来一切正常,但客户端无法判断是否被截断)')
print(f'  Content-Length: 500,实际发了 1000 字节 → {hc([(0, H + b"Content-Length: 500\r\n\r\n" + b"x" * 1000)])}(多出的 500 字节被客户端忽略 / 留在连接里)')
p = scripted([(0, b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n' + b'hello' + b'WORLD-EXTRA' + b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabc')], close=False, keep=1)
c = socket.create_connection(('127.0.0.1', p)); c.sendall(b'GET /a HTTP/1.1\r\nHost: x\r\n\r\nGET /b HTTP/1.1\r\nHost: x\r\n\r\n'); time.sleep(0.5); got = c.recv(65536); c.close()
h1, rest = got.split(b'\r\n\r\n', 1); n = 5; body1, leftover = rest[:n], rest[n:]
print(f'  响应错位演示:服务器对第 1 个请求声明 Content-Length: 5 却多发了 6 个字节 "WORLD-EXTRA"[:6]…客户端按长度读出第 1 个响应的 {body1!r};紧接着的字节是 {leftover[:40]!r},被当作“第 2 个响应”的开头——不是合法的状态行,连接上的响应从此错位(请求走私 / 响应拆分漏洞的根源)')
