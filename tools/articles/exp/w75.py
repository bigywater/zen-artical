import sys, os, re, struct, threading, statistics, errno, urllib.parse; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w75'); reset()
PUB = '104.20.23.154'
def serve(port, stop, nodelay=False):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(64); ls.settimeout(0.3)
    nconn = [0]
    def handle(c):
        nconn[0] += 1; buf = b''; c.settimeout(10)
        if nodelay: c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            while True:
                while b'\r\n\r\n' not in buf:
                    d = c.recv(65536)
                    if not d: return
                    buf += d
                head, buf = buf.split(b'\r\n\r\n', 1)
                line = head.split(b'\r\n')[0].decode(); path = line.split()[1]
                q = urllib.parse.parse_qs(urllib.parse.urlparse(path).query); ms = int(q.get('ms', ['0'])[0])
                if ms: time.sleep(ms / 1000)
                body = (path.encode() + b' ') * 80
                close = b'connection: close' in head.lower()
                c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: %d\r\nContent-Type: text/plain\r\nConnection: %s\r\n\r\n' % (len(body), b'close' if close else b'keep-alive') + body)
                if close: return
        except Exception: pass
        finally: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=handle, args=(c,), daemon=True).start()
        ls.close()
    th = threading.Thread(target=acc, daemon=True); th.start(); return nconn
def read_resp(s, buf=b''):
    while b'\r\n\r\n' not in buf:
        d = s.recv(65536)
        if not d: return None, buf
        buf += d
    head, rest = buf.split(b'\r\n\r\n', 1)
    m = re.search(rb'content-length: *(\d+)', head, re.I); n = int(m.group(1)) if m else 0
    while len(rest) < n:
        d = s.recv(65536)
        if not d: break
        rest += d
    return head, rest[n:]

port = lab_port(); stop = [False]; nconn = serve(port, stop)
print('== 一:连接复用 vs 每次新建:本机服务器,lo0 上 netlab 每方向延迟 50 ms(往返 100 ms)。顺序取 10 个小资源(每个 1 KB 左右):每次新建一条连接(Connection: close)与同一条连接上依次取(keep-alive)')
def get(s, path, extra=b''):
    s.sendall(b'GET ' + path.encode() + b' HTTP/1.1\r\nHost: x\r\n' + extra + b'\r\n'); h, rest = read_resp(s); return h
with lossy(loss=0, delay=50, bw=0):
    ts = []
    for rep in range(3):
        t0 = time.time()
        for i in range(10):
            s = socket.create_connection(('127.0.0.1', port)); get(s, f'/r{i}', b'Connection: close\r\n'); s.close()
        ts.append((time.time() - t0) * 1000)
    new_t = statistics.median(ts)
    ts = []; c0 = nconn[0]
    for rep in range(3):
        t0 = time.time(); s = socket.create_connection(('127.0.0.1', port))
        for i in range(10): get(s, f'/r{i}')
        ts.append((time.time() - t0) * 1000); s.close()
    keep_t = statistics.median(ts)
print(f'  每次新建连接:10 个资源总共 {new_t:.0f} ms(≈ 10 × (握手 1 个 RTT + 请求响应 1 个 RTT) = 10 × 200 ms)')
print(f'  同一条连接上依次取:总共 {keep_t:.0f} ms(≈ 握手 1 RTT + 10 × 1 RTT = 11 × 100 ms)')
print(f'  省下 {new_t - keep_t:.0f} ms,约 {(new_t - keep_t) / 100:.1f} 个 RTT;每个资源平均 {new_t / 10:.0f} ms 对 {keep_t / 10:.0f} ms')

print('== 二:流水线(pipelining):不等响应就连续发出多个请求。同样 10 个资源,同一条连接,一次性全发出去再读 10 个响应')
with lossy(loss=0, delay=50, bw=0):
    ts = []
    for rep in range(3):
        t0 = time.time(); s = socket.create_connection(('127.0.0.1', port)); t_conn = time.time()
        s.sendall(b''.join(b'GET /p%d HTTP/1.1\r\nHost: x\r\n\r\n' % i for i in range(10))); buf = b''; arr = []
        for i in range(10):
            h, buf = read_resp(s, buf); arr.append((time.time() - t_conn) * 1000)
        ts.append(((time.time() - t0) * 1000, arr)); s.close()
    pipe_t = statistics.median(x[0] for x in ts)
print(f'  流水线:10 个资源总共 {pipe_t:.0f} ms(握手 1 RTT + 一次请求响应 1 RTT ≈ 200 ms);第 1 个响应在握手后 {ts[0][1][0]:.0f} ms,第 10 个在 {ts[0][1][9]:.0f} ms')
print(f'  对比:非流水线的 keep-alive {keep_t:.0f} ms;每次新建 {new_t:.0f} ms')

print('== 三:流水线的致命问题——队头阻塞:响应必须按请求的顺序返回。第 1 个请求让服务器处理 600 ms(/slow?ms=600),后面 4 个请求很快。流水线 vs 5 条并行连接(每条一个请求),看每个响应的到达时间。服务器分别用默认(Nagle 开)与 TCP_NODELAY 各做一次')
port2 = lab_port(); stop2 = [False]; serve(port2, stop2, nodelay=True)
def pipe_slow(pt):
    s = socket.create_connection(('127.0.0.1', pt)); t_conn = time.time()
    s.sendall(b'GET /slow?ms=600 HTTP/1.1\r\nHost: x\r\n\r\n' + b''.join(b'GET /fast%d HTTP/1.1\r\nHost: x\r\n\r\n' % i for i in range(4))); buf = b''; arr = []
    for i in range(5):
        h, buf = read_resp(s, buf); arr.append((time.time() - t_conn) * 1000)
    s.close(); return arr
with lossy(loss=0, delay=50, bw=0):
    arr = pipe_slow(port); arr2 = pipe_slow(port2)
    res = [None] * 5; t_start = time.time()
    def one(i):
        sk = socket.create_connection(('127.0.0.1', port2)); path = '/slow?ms=600' if i == 0 else f'/fast{i}'
        sk.sendall(b'GET ' + path.encode() + b' HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n'); read_resp(sk); res[i] = (time.time() - t_start) * 1000; sk.close()
    th = [threading.Thread(target=one, args=(i,)) for i in range(5)]
    for t in th: t.start()
    for t in th: t.join()
print(f'  同一条连接流水线(第 1 个慢),服务器默认(Nagle 开):5 个响应到达时刻(从握手完成起,ms):{[round(x) for x in arr]}')
print(f'  同一条连接流水线(第 1 个慢),服务器 TCP_NODELAY:{[round(x) for x in arr2]}')
print(f'  5 条并行连接(含握手):到达时刻 {[round(x) for x in res]}')
print(f'  快请求在流水线里被拖到 {min(arr2[1:]):.0f} ms(NODELAY)之后,在并行连接里 {min(res[1:]):.0f}~{max(res[1:]):.0f} ms 就拿到了;Nagle 开时后 4 个比第 1 个晚了 {min(arr[1:]) - arr[0]:.0f} ms,NODELAY 时晚了 {min(arr2[1:]) - arr2[0]:.0f} ms')

print('== 四:真实服务器 example.com:80 能不能流水线?3 个请求一次发出,数一数收到几个响应')
req = b'GET / HTTP/1.1\r\nHost: example.com\r\n\r\n'
s = socket.create_connection((PUB, 80), timeout=6); s.settimeout(3); s.sendall(req * 3); buf = b''; t0 = time.time()
try:
    while time.time() - t0 < 3:
        d = s.recv(65536)
        if not d: break
        buf += d
except socket.timeout: pass
n = buf.count(b'HTTP/1.1 200 OK')
print(f'  3 个请求一次发出,3 秒内收到 {len(buf)} 字节,其中 "HTTP/1.1 200 OK" 状态行 {n} 个;状态行们:{re.findall(rb"HTTP/1.1 \d+ [A-Za-z ]+", buf)[:5]}')
s.close()

print('== 五:服务器多久关闭空闲的持久连接?连上 example.com:80,发一个请求,然后什么也不做,每秒检查连接是否还开着(最多等 130 秒)')
s = socket.create_connection((PUB, 80), timeout=6); s.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\n\r\n'); h, rest = read_resp(s)
hd = {k.lower(): v for k, v in (l.split(': ', 1) for l in h.decode().split('\r\n')[1:] if ': ' in l)}
print(f'  响应头里和连接有关的:Connection = {hd.get("connection")},Keep-Alive = {hd.get("keep-alive")}')
t0 = time.time(); s.settimeout(1); closed_at = None
while time.time() - t0 < 130:
    try:
        d = s.recv(100)
        if d == b'': closed_at = time.time() - t0; break
    except socket.timeout: continue
    except Exception as e: closed_at = time.time() - t0; break
print(f'  {"服务器在空闲 %.0f 秒后关闭了连接" % closed_at if closed_at else "130 秒内服务器一直没有关闭连接"}')
s.close(); stop[0] = True; stop2[0] = True
