import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v38'); reset()
print('用 Go 1.27.1 标准库的 net/http/httputil.ReverseProxy 手写反向代理(vtmp/v38/main.go,约 70 行)。用命令行参数切换 Director / Rewrite 的写法、错误处理、Transport 参数。后端是本进程里的 Python 服务,client 是 Python。对照第 17 篇 nginx 的默认行为')
BIN = str(HERE / 'vtmp/v38proxy')
def start_proxy(backend_port, **kw):
    p = free_port(); args = [BIN, '-port', str(p), '-backend', f'127.0.0.1:{backend_port}'] + [x for k, v in kw.items() for x in (f'-{k}', str(v))]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); wait_port(p, 10); return proc, p
def echo(h):
    h.reply(200, json.dumps({'line': f'{h.command} {h.path} {h.request_version}', 'host': h.headers.get('Host'), 'xff': h.headers.get('X-Forwarded-For'), 'xfh': h.headers.get('X-Forwarded-Host'), 'xfp': h.headers.get('X-Forwarded-Proto'), 'conn': h.headers.get('Connection'), 'keep': h.headers.get('Keep-Alive'), 'te': h.headers.get('Te'), 'ua': h.headers.get('User-Agent'), 'xf_in': h.headers.get('X-Fake')}).encode(), {'Connection': 'keep-alive', 'Keep-Alive': 'timeout=5', 'X-Backend': 'b'})
B = Svc(echo)
def get(port, headers, path='/p?x=1'):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        c.request('GET', path, headers=headers); r = c.getresponse(); d = r.read(); return r.status, dict(r.getheaders()), d
    finally: c.close()

# ============ 一 ============
print('== 一:Director / Rewrite 对请求头的处理。client 发 GET /p?x=1,带 Host: shop.test、X-Forwarded-For: 6.6.6.6(伪造)、X-Forwarded-Host: evil、Connection: keep-alive, X-Fake、Keep-Alive: timeout=9、Te: trailers、X-Fake: 1。四种写法,后端看到什么')
rows = []
for mode in ('director', 'director-host', 'rewrite-nox', 'rewrite'):
    proc, p = start_proxy(B.port, mode=mode); st, hd, d = get(p, {'Host': 'shop.test', 'X-Forwarded-For': '6.6.6.6', 'X-Forwarded-Host': 'evil', 'Connection': 'keep-alive, X-Fake', 'Keep-Alive': 'timeout=9', 'Te': 'trailers', 'X-Fake': '1'}); proc.kill(); j = json.loads(d)
    rows.append((mode, j['host'], j['xff'], j['xfh'], j['xfp'], j['keep'], j['te'], j['xf_in']))
table(rows, ['写法', '后端看到的 Host', 'X-Forwarded-For', 'X-Forwarded-Host', 'X-Forwarded-Proto', 'Keep-Alive', 'Te', 'X-Fake(Connection 里点名的逐跳头)'])
print('  Director 写法:不改 req.Host,所以后端看到的是 client 的 Host(shop.test);ReverseProxy 自己追加 X-Forwarded-For(在 client 带的值后面加上 client 地址,伪造的 6.6.6.6 仍保留在最左边);director-host 把 req.Host 也改成后端地址。Rewrite 写法(Go 1.20 起):SetURL 会把 Host 设成后端的;X-Forwarded-* 不会自动加(rewrite-nox 里 client 带的 X-Forwarded-* 被丢掉,不转发),SetXForwarded 才会按“覆盖”的方式设置它们(伪造的 6.6.6.6 不再出现)。逐跳头 Keep-Alive、Te(除 trailers 外)以及 Connection 里点名的头(X-Fake)都被去掉了')

# ============ 二 ============
print('== 二:错误处理。四种后端故障:(a) 后端端口没人监听;(b) 后端 1 s 后才回响应头,代理设了 ResponseHeaderTimeout 300 ms;(c) 后端发了响应头和一半响应体(Content-Length 100,只给 10 字节)就断开;(d) client 在后端还在处理时就关闭了连接,后端有没有看到取消。比较默认的 ErrorHandler 与自定义的 ErrorHandler(返回 503 + JSON)')
def late(c):
    read_req(c); time.sleep(1.0)
    try: c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok')
    except Exception: pass
def partial(c):
    read_req(c); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n0123456789'); c.close()
cancel_seen = []
def slow_watch(c):
    read_req(c); t0 = time.perf_counter()
    c.settimeout(2.0)
    try:
        x = c.recv(1)
        cancel_seen.append(('收到 EOF' if not x else '收到数据', round(time.perf_counter() - t0, 2)))
    except socket.timeout: cancel_seen.append(('2 s 内没发现 client 取消', 2.0))
RL, RP, RW = Raw(late), Raw(partial), Raw(slow_watch)
dead = free_port(); rows = []
for errh in ('default', 'custom'):
    row = [errh]
    for port in (dead, RL.port, RP.port):
        proc, p = start_proxy(port, errh=errh, rht=300); c = http.client.HTTPConnection('127.0.0.1', p, timeout=5)
        try:
            c.request('GET', '/'); r = c.getresponse(); d = r.read(); row.append(f'{r.status} {d[:40].decode(errors="replace").strip()!r}')
        except Exception as e: row.append(f'{type(e).__name__}')
        c.close(); proc.kill()
    rows.append(tuple(row))
table(rows, ['ErrorHandler', '(a) 后端不可达', '(b) 响应头超过 300 ms', '(c) 响应体只发了一半'])
proc, p = start_proxy(RW.port); s = socket.create_connection(('127.0.0.1', p)); s.sendall(b'GET / HTTP/1.1\r\nHost: x\r\n\r\n'); time.sleep(0.3); s.close(); time.sleep(2.3); proc.kill()
print('  (d) client 关闭连接之后,后端那一侧:', cancel_seen[-1] if cancel_seen else '没有记录')
print('  默认 ErrorHandler 对所有传输错误回 502 Bad Gateway(响应体为空),超时和连接被拒没有区别;自定义 ErrorHandler 可以换成 503 加 JSON。(c) 后端发了一半响应体就断开时,两种 ErrorHandler 的结果一样:client 的 HTTP 库抛 RemoteDisconnected,一个字节的响应都没收到,不是一个 5xx(我的解释:ReverseProxy 在拷贝响应体出错时用 panic(http.ErrAbortHandler) 直接中断,响应头还在代理的写缓冲里没有发出去;这个解释没有单独验证)。(d) client 一关连接,后端那边很快就读到 EOF,说明代理把取消传给了后端')

# ============ 三 ============
print('== 三:Transport 的连接池。Go 的 http.Transport 的 MaxIdleConnsPerHost 默认是 2。50 个并发线程共发 2000 个请求(后端处理 5 ms)。比较 -idle 2(默认)与 -idle 100:后端 accept 了多少条连接')
conns = []
def count_backend(c):
    conns.append(1)
    c.settimeout(30)
    try:
        while True:
            d = b''
            while b'\r\n\r\n' not in d:
                x = c.recv(65536)
                if not x: return
                d += x
            time.sleep(0.005); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok')
    except Exception: pass
RC = Raw(count_backend, backlog=512); rows = []
for idle in (2, 100):
    conns.clear(); proc, p = start_proxy(RC.port, idle=idle); res = par(lambda i: rpc(p, '/', 10.0)[0], list(range(2000)), 50); proc.kill(); time.sleep(0.3)
    rows.append((f'MaxIdleConnsPerHost = {idle}', collections.Counter(res).get(200, 0), len(conns), f'{1 - len(conns) / 2000:.1%}'))
table(rows, ['Transport', '成功', '后端 accept 的连接数', '连接复用率'])
print('  idle=2 时,并发 50 个请求用完之后,只有 2 条连接会被留在池子里,其余的立刻关掉,下一批请求又要新建;idle=100 之后连接几乎全部复用。和 nginx 的 upstream keepalive N 是同一类问题(见第 23 篇),只是 Go 的默认值更小')

# ============ 四 ============
print('== 四:流式响应要不要 FlushInterval。后端是原始 TCP 服务,每 0.3 s 发一个 chunk(chunked,没有 Content-Length),共 5 个,Content-Type: text/plain。代理 FlushInterval 为 0(默认)和 -1(每次写都立刻 flush)。看 client 什么时候收到第 1 个和第 5 个 chunk')
def chunky(c):
    read_req(c); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nTransfer-Encoding: chunked\r\n\r\n')
    for i in range(5):
        c.sendall(b'5\r\nchunk\r\n'); time.sleep(0.3)
    c.sendall(b'0\r\n\r\n'); c.close()
RK = Raw(chunky); rows = []
for fl in (0, -1):
    proc, p = start_proxy(RK.port, flush=fl); s = socket.create_connection(('127.0.0.1', p)); s.sendall(b'GET / HTTP/1.1\r\nHost: x\r\n\r\n'); t0 = time.perf_counter(); buf = b''; times = []
    while True:
        d = s.recv(65536)
        if not d: break
        buf += d
        body = buf.split(b'\r\n\r\n', 1)[1] if b'\r\n\r\n' in buf else b''
        while body.count(b'chunk') > len(times): times.append(time.perf_counter() - t0)
        if buf.endswith(b'0\r\n\r\n'): break
    s.close(); proc.kill(); rows.append((f'FlushInterval = {fl}', f'{times[0]:.2f} s' if times else '-', f'{times[-1]:.2f} s' if times else '-', len(times)))
table(rows, ['配置', '第 1 个 chunk 收到', '第 5 个 chunk 收到', '收到的 chunk 数'])
print('  两个配置的到达时刻几乎一样:据我对 Go 源码里 flushInterval 函数的记忆,ReverseProxy 对 ContentLength 为 -1(如 chunked)的响应和 Content-Type 是 text/event-stream 的响应总是立刻 flush,FlushInterval 只对其它响应起作用;这里只验证了 chunked 这一种,没有单独测 SSE,也没有读源码核对')
