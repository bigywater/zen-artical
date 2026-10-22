import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
from websockets.sync.server import serve
from websockets.sync.client import connect
import websockets.exceptions as wse
tee('v25'); reset()
print('长连接穿过网关:WebSocket(websockets 17.2 的同步 server / client)和 SSE(原始 socket 写事件流)。nginx 1.31.6。WebSocket 服务回显收到的文本;“穿过网关”要让 nginx 把 Upgrade 握手转给上游并在握手之后当作隧道转发')
def ws_server():
    def handler(ws):
        try:
            for m in ws: ws.send(m)
        except Exception: pass
    port = free_port(); srv = serve(handler, '127.0.0.1', port, ping_interval=None); threading.Thread(target=srv.serve_forever, daemon=True).start(); wait_port(port, 10); return srv, port
def conf(port, loc):
    return f'upstream u {{ server 127.0.0.1:{port}; }} server {{ listen {{port}}; location / {{ proxy_pass http://u; {loc} }} }}'
UP = 'proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";'
srv, wport = ws_server()

# ============ 一 ============
print('== 一:握手要不要配 Upgrade。四种 nginx 配置去连 WebSocket 上游:(a) 只有 proxy_pass;(b) 只转发 Upgrade 头、Connection 保持默认;(c) 完整写法(proxy_http_version 1.1、Upgrade、Connection upgrade);(d) 直连上游作对照。成功后发 200 个文本消息测一来一回的往返时间')
rows = []
for name, loc in (('(a) 只有 proxy_pass', ''), ('(b) 只转发 Upgrade 头', 'proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade;'), ('(c) 完整写法', UP), ('(d) 直连上游', None)):
    if loc is None: url = f'ws://127.0.0.1:{wport}/'; ng = None
    else: ng = Nginx('v25a', conf(wport, loc)).start(); url = f'ws://127.0.0.1:{ng.port}/'
    try:
        with connect(url, open_timeout=3) as ws:
            lat = []
            for i in range(200):
                t0 = time.perf_counter(); ws.send('hi'); ws.recv(); lat.append(time.perf_counter() - t0)
            rows.append((name, '握手成功(101)', f'{statistics.median(lat) * 1000:.2f} ms', f'{pct(lat, 99) * 1000:.2f} ms'))
    except Exception as e:
        rows.append((name, f'{type(e).__name__}: {str(e)[:60]}', '-', '-'))
    if ng: ng.stop()
table(rows, ['配置', '结果', '往返中位数', 'p99'])

# ============ 二 ============
print('== 二:空闲超时。proxy_read_timeout = 2 s(默认是 60 s)。连接建立后:(a) 不发任何消息;(b) 客户端每 0.5 s 发一个 WebSocket ping 帧;(c) 每 1.5 s 发一个 ping;(d) 每 2.5 s 发一个 ping。观察连接是否在 7 秒内被关闭,以及什么时候被关闭')
rows = []
for name, iv in (('(a) 不发任何东西', None), ('(b) 每 0.5 s 一个 ping', 0.5), ('(c) 每 1.5 s 一个 ping', 1.5), ('(d) 每 2.5 s 一个 ping', 2.5)):
    ng = Nginx('v25b', conf(wport, UP + ' proxy_read_timeout 2s;')).start(); t0 = time.perf_counter(); closed = None; code = None
    try:
        with connect(f'ws://127.0.0.1:{ng.port}/', open_timeout=3, ping_interval=None) as ws:
            next_ping = iv
            while time.perf_counter() - t0 < 7.0:
                if iv is not None and time.perf_counter() - t0 >= next_ping:
                    ws.ping(); next_ping += iv
                try: ws.recv(timeout=0.05)
                except TimeoutError: pass
    except wse.ConnectionClosed as e:
        closed = time.perf_counter() - t0; code = e.rcvd.code if e.rcvd else 1006
    except Exception as e: closed = time.perf_counter() - t0; code = type(e).__name__
    rows.append((name, f'{closed:.1f} s 被关闭(关闭码 {code})' if closed else '7 秒内一直保持'))
    ng.stop()
table(rows, ['客户端', '结果'])
print('  proxy_read_timeout 管的是“两次从上游读到数据之间的间隔”:WebSocket 的 ping 帧由 client 发给上游,上游回 pong,pong 到了才算 nginx 读到数据,所以心跳间隔要比 proxy_read_timeout 短(这里 0.5 s 和 1.5 s 都小于 2 s,2.5 s 大于)')

# ============ 三 ============
print('== 三:SSE 里 client 断开之后上游多久才知道。上游是个原始 TCP 服务,每 0.2 s 写一个事件;client 在 1 s 时关闭连接。统计上游从 client 关闭起,多久之后发现写失败。比较:直连上游 / 经过 nginx(默认)/ 经过 nginx 加 proxy_ignore_client_abort on')
def sse_backend(rec):
    def h(c):
        read_req(c); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\n\r\n'); t_start = time.perf_counter(); i = 0
        while time.perf_counter() - t_start < 8.0:
            ev = b'data: %d\n\n' % i
            try: c.sendall(b'%x\r\n' % len(ev) + ev + b'\r\n')
            except Exception: rec['fail_at'] = time.perf_counter(); return
            i += 1; time.sleep(0.2)
        rec['fail_at'] = None
    return h
rows = []
for name, mode in (('直连上游', None), ('经过 nginx(默认)', ''), ('经过 nginx + proxy_ignore_client_abort on', 'proxy_ignore_client_abort on;')):
    rec = {}; R = Raw(sse_backend(rec)); ng = Nginx('v25c', conf(R.port, mode)).start() if mode is not None else None
    port = ng.port if ng else R.port; s = socket.create_connection(('127.0.0.1', port)); s.sendall(b'GET / HTTP/1.1\r\nHost: x\r\n\r\n'); time.sleep(1.0)
    t_close = time.perf_counter(); s.close()
    t_wait = time.perf_counter()
    while time.perf_counter() - t_wait < 9.0 and 'fail_at' not in rec: time.sleep(0.02)
    fa = rec.get('fail_at')
    rows.append((name, f'{fa - t_close:.2f} s' if fa else (f'{9.0:.0f} s 内没有发现(上游一直写到结束)' if 'fail_at' not in rec else '写到结束也没有失败')))
    if ng: ng.stop()
    R.close()
table(rows, ['路径', 'client 关闭之后,上游发现写失败用了'])

# ============ 四 ============
print('== 四:长连接占用的连接数。nginx 的 worker_connections = 64;每个 WebSocket 经过 nginx 要占两条(client 一条、上游一条)。同时建立 45 个 WebSocket 并保持,看有多少个成功握手、有多少个失败,以及 error.log 里 worker_connections are not enough 的行数。对照直连上游')
def hold(url, n):
    ok = []; fail = collections.Counter(); lk = threading.Lock(); stop = threading.Event()
    def one(i):
        try:
            with connect(url, open_timeout=3, close_timeout=1) as ws:
                ws.send('x'); ws.recv(timeout=2)
                with lk: ok.append(i)
                stop.wait(3.0)
        except Exception as e:
            with lk: fail[type(e).__name__] += 1
    ths = [threading.Thread(target=one, args=(i,)) for i in range(n)]; [t.start() for t in ths]; time.sleep(2.0); held = len(ok); stop.set(); [t.join() for t in ths]
    return held, dict(fail)
ng = Nginx('v25d', conf(wport, UP)).start(); txt = (ng.d / 'nginx.conf').read_text().replace('worker_connections 1024', 'worker_connections 64'); (ng.d / 'nginx.conf').write_text(txt); ng.stop(); time.sleep(0.3); ng.p = None; ng.start()
held, fail = hold(f'ws://127.0.0.1:{ng.port}/', 45); nlog = (ng.d / 'err.log').read_text().count('worker_connections are not enough'); ng.stop()
held_d, fail_d = hold(f'ws://127.0.0.1:{wport}/', 45)
table([('经过 nginx(worker_connections 64)', 45, held, fail, nlog), ('直连上游', 45, held_d, fail_d, '-')], ['路径', '尝试建立', '成功握手并保持', '失败的类型', 'error.log: not enough'])
srv.shutdown()
