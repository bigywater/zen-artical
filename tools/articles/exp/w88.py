import sys, os, re, struct, threading, statistics, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w88'); reset()
seen_req = []
def chunk(b): return b'%x\r\n' % len(b) + b + b'\r\n'
def srv(port, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(32); ls.settimeout(0.3)
    def h(c):
        try:
            c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1); c.settimeout(10); buf = b''
            while b'\r\n\r\n' not in buf: buf += c.recv(65536)
            head = buf.split(b'\r\n\r\n')[0]; path = head.split()[1].decode(); lei = re.search(rb'(?i)last-event-id: *(\S+)', head); seen_req.append((path, lei.group(1).decode() if lei else None, time.time()))
            if path.startswith('/events'):
                c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\nTransfer-Encoding: chunked\r\n\r\n')
                start = int(lei.group(1)) + 1 if lei else 1
                if path == '/events':
                    c.sendall(chunk(b'retry: 500\n\n'))
                    for i in range(start, start + 3):
                        time.sleep(0.2); c.sendall(chunk(b'id: %d\nevent: tick\ndata: message %d\n\n' % (i, i)))
                    time.sleep(0.1)  # 然后服务器主动断开(不发结尾块),模拟连接掉线
                elif path == '/events/format':
                    c.sendall(chunk(': 这是注释,用于保活\n\n'.encode())); time.sleep(0.1)
                    c.sendall(chunk('data: 第一行\ndata: 第二行\n\n'.encode())); time.sleep(0.1)
                    c.sendall(chunk(b'event: update\nid: 7\ndata: {"x":1}\n\n')); time.sleep(0.1)
                    c.sendall(chunk(b'data:no-space\n\n')); time.sleep(0.1)
                    c.sendall(chunk(b'unknown: field\ndata: after-unknown\n\n')); time.sleep(0.1)
                    c.sendall(chunk('data: 没有结尾空行的事件'.encode())); time.sleep(0.3)
                elif path == '/events/many':
                    n = 1000
                    for i in range(n): c.sendall(chunk(b'data: 0123456789abcdefghij\n\n'))
                    c.sendall(b'0\r\n\r\n')
            elif path.startswith('/poll'):
                body = b'0123456789abcdefghij'; c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: %d\r\n\r\n' % len(body) + body)
                # 保持连接等下一个请求
                while True:
                    buf = b''
                    while b'\r\n\r\n' not in buf:
                        d = c.recv(65536)
                        if not d: return
                        buf += d
                    c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: %d\r\n\r\n' % len(body) + body)
        except Exception: pass
        finally: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
port = lab_port(); stop = [False]; srv(port, stop)
def read_chunks(s, buf=b'', tmo=3):
    """返回 (头部, 事件流文本, 是否正常结束)"""
    s.settimeout(tmo)
    while b'\r\n\r\n' not in buf: buf += s.recv(65536)
    head, rest = buf.split(b'\r\n\r\n', 1); text = b''; t0 = time.time(); arr = []; ended = False
    try:
        while True:
            while b'\r\n' not in rest:
                d = s.recv(65536)
                if not d: return head, text, ended, arr
                rest += d
            ln, rest = rest.split(b'\r\n', 1); n = int(ln, 16)
            if n == 0: ended = True; return head, text, ended, arr
            while len(rest) < n + 2:
                d = s.recv(65536)
                if not d: return head, text, ended, arr
                rest += d
            text += rest[:n]; arr.append((time.time(), rest[:n])); rest = rest[n + 2:]
    except socket.timeout: pass
    return head, text, ended, arr

print('== 一:SSE 的响应:一个普通的 HTTP 响应,Content-Type: text/event-stream,不设 Content-Length(分块传输),连接保持打开,服务器不断追加文本。看头部和每个事件到达的时刻')
s = socket.create_connection(('127.0.0.1', port)); s.sendall(b'GET /events HTTP/1.1\r\nHost: x\r\nAccept: text/event-stream\r\n\r\n'); t0 = time.time()
head, text, ended, arr = read_chunks(s)
print('  响应头:' + ' | '.join(head.decode().split('\r\n')))
print(f'  事件流文本({len(text)} 字节):{text!r}')
print('  每个数据块到达的时刻(从发出请求起,ms):' + ', '.join(f'{(t - t0) * 1000:.0f}' for t, _ in arr))
print(f'  连接在发完 3 个事件后被服务器掐断(没有结尾的 0 长度块):正常结束 = {ended}')
s.close()

print('== 二:事件流的文本格式:字段名 + 冒号 + 值,空行表示一个事件结束。注释行以冒号开头;多个 data 行用换行连接;没有结尾空行的事件不会被派发。用我写的解析器按规范解析服务器发的这一串')
s = socket.create_connection(('127.0.0.1', port)); s.sendall(b'GET /events/format HTTP/1.1\r\nHost: x\r\n\r\n'); head, text, ended, arr = read_chunks(s, tmo=2); s.close()
print('  服务器发出的原始文本:'); [print('    ' + repr(l)) for l in text.decode().split('\n')]
def parse_sse(t):
    evs = []; ev = {'data': [], 'event': None, 'id': None}; last_id = None
    for line in t.split('\n')[:-1] if t.endswith('\n') else t.split('\n')[:-1]:
        if line == '':
            if ev['data'] or ev['event']: evs.append((ev['event'] or 'message', '\n'.join(ev['data']), ev['id']))
            ev = {'data': [], 'event': None, 'id': None}; continue
        if line.startswith(':'): continue
        f, _, v = line.partition(':'); v = v[1:] if v.startswith(' ') else v
        if f == 'data': ev['data'].append(v)
        elif f == 'event': ev['event'] = v
        elif f == 'id': ev['id'] = v
    return evs
for e in parse_sse(text.decode()): print(f'  派发的事件:类型 {e[0]!r},数据 {e[1]!r},id {e[2]!r}')
print('  注释行(: 开头)被忽略;两个 data 行变成一个事件、值用换行连接;"data:no-space" 冒号后没有空格也行;未知字段 unknown 被忽略;最后一个事件没有结尾空行,不会被派发(解析器只在遇到空行时派发)')

print('== 三:断线重连与 Last-Event-ID:服务器每次发 3 个事件(id 递增)就断开,并在开头告诉客户端 retry: 500(毫秒)。客户端断线后等 retry 时间重连,并带上 Last-Event-ID 请求头,服务器从下一个 id 继续')
seen_req.clear(); last = None; log = []; t_start = time.time(); drops = []
for rnd in range(3):
    s = socket.create_connection(('127.0.0.1', port)); req = b'GET /events HTTP/1.1\r\nHost: x\r\n' + (b'Last-Event-ID: ' + last.encode() + b'\r\n' if last else b'') + b'\r\n'; s.sendall(req)
    head, text, ended, arr = read_chunks(s, tmo=3); s.close(); drops.append(time.time())
    evs = parse_sse(text.decode()); log.append([e[2] for e in evs]); last = evs[-1][2]
    if rnd < 2: time.sleep(0.5)
print(f'  三轮收到的事件 id:{log}(没有重复、没有缺失:每次从 Last-Event-ID 的下一个继续)')
print(f'  服务器记录到的三次请求带的 Last-Event-ID:{[r[1] for r in seen_req]}')
gaps = [(seen_req[i + 1][2] - drops[i]) * 1000 for i in range(2)] if len(seen_req) >= 3 else []
print(f'  断线(我们读到连接被掐断)到下一次请求到达服务器的间隔:{[round(g) for g in gaps]} ms(客户端按服务器给的 retry: 500 睡了 500 ms,再加上建立连接的时间)')

print('== 四:开销对比:推送 1000 条各 20 字节的消息,服务器→客户端方向总共多少字节:SSE(一个响应里 1000 个事件)、WebSocket(1000 个文本帧)、长轮询 / 反复请求(1000 次请求 + 响应,每次带完整的 HTTP 头)')
s = socket.create_connection(('127.0.0.1', port)); s.sendall(b'GET /events/many HTTP/1.1\r\nHost: x\r\n\r\n'); buf = b''; s.settimeout(5)
while True:
    d = s.recv(1 << 20)
    if not d: break
    buf += d
    if buf.endswith(b'0\r\n\r\n'): break
s.close(); sse_bytes = len(buf); hdr_len = len(buf.split(b'\r\n\r\n')[0]) + 4
print(f'  SSE:服务器发出 {sse_bytes} 字节(响应头 {hdr_len} 字节,之后每条 {(sse_bytes - hdr_len - 5) / 1000:.1f} 字节:"data: " 6 + 20 字节载荷 + "\\n\\n" 2 = 28 字节事件文本,再加分块框架 "1c\\r\\n" 和 "\\r\\n" 共 6 字节 = 34 字节)')
ws_bytes = 1000 * (2 + 20)
print(f'  WebSocket:每条帧头 2 字节 + 20 字节载荷 = 22 字节(服务器→客户端不掩码,<126 字节的载荷),1000 条 {ws_bytes} 字节(不含一次性的升级握手)')
s = socket.create_connection(('127.0.0.1', port)); s.settimeout(5); tot = 0; req = b'GET /poll HTTP/1.1\r\nHost: x\r\nAccept: text/plain\r\n\r\n'
for i in range(1000):
    s.sendall(req); buf = b''
    while b'\r\n\r\n' not in buf: buf += s.recv(65536)
    head, rest = buf.split(b'\r\n\r\n', 1)
    while len(rest) < 20: rest += s.recv(65536)
    tot += len(head) + 4 + len(rest)
s.close()
print(f'  反复请求(同一条 keep-alive 连接上 1000 次 GET):服务器→客户端 {tot} 字节(每次响应头约 {(tot - 20000) / 1000:.0f} 字节 + 20 字节载荷);另外客户端→服务器每次还要发 {len(req)} 字节的请求')
print(f'  按单条消息:SSE {(sse_bytes - hdr_len - 5) / 1000:.0f} 字节、WebSocket 22 字节、反复请求 {tot / 1000:.0f} 字节;反复请求还多一个往返的延迟')
stop[0] = True
