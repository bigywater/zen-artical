import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v22'); reset()
print('proxy_next_upstream 决定“上游出了什么问题时,nginx 把请求换给下一个上游重试”。可选的条件:error(连接/读写出错)、timeout、invalid_header、http_500/502/503/504/403/404/429、non_idempotent、off。默认是 error timeout。上游 A 总是以某种方式出问题,上游 B 总是正常,nginx 1.31.6,proxy_read_timeout = 1 s,两个 server 都写了 max_fails=0')
HDR = b'HTTP/1.1 200 OK\r\nContent-Length: 1\r\nConnection: close\r\n\r\n'
def status_app(code): return lambda h: h.reply(code, b'A%d' % code)
def refuse_port():
    p = free_port(); return p
def sleeper(c): read_req(c); time.sleep(1.8); c.sendall(HDR + b'A'); c.close()
def garbage(c): read_req(c); c.sendall(b'NOT-HTTP garbage\r\n\r\n'); c.close()
def badheader(c): read_req(c); c.sendall(b'HTTP/1.1 200 OK\r\nthis line has no colon\r\nContent-Length: 1\r\n\r\nA'); c.close()
def reset(c):
    read_req(c); c.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b'\x01\x00\x00\x00\x00\x00\x00\x00'); c.close()
def half_then_close(c):
    read_req(c); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\nxx'); c.close()
FAIL = [('连接被拒', 'refuse'), ('读响应超时(沉默 1.8 s)', 'sleeper'), ('连接被重置(收到请求后 RST)', 'reset'), ('状态行就不是 HTTP(整行垃圾)', 'garbage'), ('状态行正常,但有一行响应头没有冒号', 'badheader'), ('HTTP 500', 500), ('HTTP 502', 502), ('HTTP 503', 503), ('HTTP 504', 504), ('HTTP 404', 404), ('响应头发完后只给 2 个字节的响应体就断开(Content-Length 100)', 'half')]
SETTINGS = [('默认 (error timeout)', 'error timeout'), ('+ http_500', 'error timeout http_500'), ('+ http_502 http_503 http_504', 'error timeout http_502 http_503 http_504'), ('+ invalid_header', 'error timeout invalid_header'), ('+ http_404', 'error timeout http_404'), ('off', 'off')]
good = Svc(lambda h: h.reply(200, b'B'))
def start_a(kind):
    if kind == 'refuse': return None, free_port()
    if isinstance(kind, int): s = Svc(status_app(kind)); return s, s.port
    h = {'sleeper': sleeper, 'garbage': garbage, 'badheader': badheader, 'reset': reset, 'half': half_then_close}[kind]; r = Raw(h); return r, r.port
def close(x):
    if x is None: return
    try: x.stop() if hasattr(x, 'stop') and callable(x.stop) else x.close()
    except Exception: pass

# ============ 一 ============
print('== 一:哪些问题会被换到下一个上游重试。对每种 A 的故障 × 每种 proxy_next_upstream 设置发一个 GET,看 client 最后拿到的是 B 的应答(表中写 B,表示被重试了)还是 A 那里出的错(写状态码,表示没有重试)')
rows = []
for fname, kind in FAIL:
    a, ap = start_a(kind); row = [fname]
    for sname, nu in SETTINGS:
        ng = Nginx('v22a', f'upstream u {{ server 127.0.0.1:{ap} max_fails=0; server 127.0.0.1:{good.port} max_fails=0; }} server {{ listen {{port}}; location / {{ proxy_pass http://u; proxy_next_upstream {nu}; proxy_read_timeout 1s; proxy_connect_timeout 1s; }} }}').start()
        # 保证第一个选到 A:轮询的第一个请求给第一个 server
        c = http.client.HTTPConnection('127.0.0.1', ng.port, timeout=6.0)
        try: c.request('GET', '/'); r = c.getresponse(); b = r.read(); st = r.status
        except Exception as e: b, st = b'', type(e).__name__
        c.close(); ng.stop()
        row.append('B(重试了)' if b == b'B' else str(st))
    rows.append(tuple(row)); close(a)
table(rows, ['A 的故障'] + [s[0] for s in SETTINGS])
print('  默认 error timeout 只处理“连接/读写出错”和“超时”:HTTP 5xx 的应答是上游认真回的,nginx 默认原样转给 client;要重试 5xx 必须显式加 http_5xx;invalid_header(状态行正常、但某行响应头不合法)在默认下不重试,client 收到 nginx 的 502;如果连状态行都不是 HTTP,nginx 按 HTTP/0.9 的简单响应处理,把那一行原样当作响应体转给 client,client 的 HTTP 库抛 BadStatusLine,换上游的 invalid_header 也不会触发;off 关掉所有重试;响应头已经发给 client 之后(最后一行)无论怎么配都不能换上游')

# ============ 二 ============
print('== 二:非幂等请求的风险。A 收到 POST /orders 后先把订单记下来,再“处理”1.8 s 才回(超过 proxy_read_timeout 1 s);B 是正常的订单服务。100 个 POST,每个带唯一的订单号。比较默认(POST 已经发给上游就不重试)与加 non_idempotent(允许重试 POST)')
def run2(extra):
    a_log, b_log = [], []
    def a_app(h):
        n = int(h.headers.get('Content-Length') or 0); body = h.rfile.read(n); a_log.append(body); time.sleep(1.8); h.reply(200, b'A')
    def b_app(h):
        n = int(h.headers.get('Content-Length') or 0); body = h.rfile.read(n); b_log.append(body); h.reply(200, b'B')
    A = Svc(a_app, backlog=256); B = Svc(b_app)
    ng = Nginx('v22b', f'upstream u {{ server 127.0.0.1:{A.port} max_fails=0; server 127.0.0.1:{B.port} max_fails=0; }} server {{ listen {{port}}; location / {{ proxy_pass http://u; proxy_read_timeout 1s; {extra} }} }}').start()
    res = par(lambda i: (lambda c: (c.request('POST', '/orders', body=f'order={i}'.encode()), c.getresponse())[1].status)(http.client.HTTPConnection('127.0.0.1', ng.port, timeout=10)), list(range(100)), 20)
    ng.stop(); A.stop(); B.stop(); time.sleep(1.0)
    both = set(a_log) & set(b_log)
    return collections.Counter(res), len(set(a_log)), len(set(b_log)), len(both), len(set(a_log) | set(b_log))
rows = []
for name, extra in (('默认', ''), ('proxy_next_upstream error timeout non_idempotent;', 'proxy_next_upstream error timeout non_idempotent;')):
    cnt, na, nb, dup, uniq = run2(extra); rows.append((name, dict(cnt), na, nb, dup, uniq))
table(rows, ['配置', 'client 看到的状态码', '订单被 A 记下', '订单被 B 记下', '同一个订单被 A 和 B 都记下(重复创建)', '共有多少个订单被记下过'])
print('  默认配置下,client 约一半的请求(落在 A 的)拿到 504,但这些订单其实已经被 A 记下了(client 以为失败,实际成功);non_idempotent 让 nginx 在超时后把 POST 重发给 B,client 拿到 200,代价是同一个订单在 A 和 B 都被创建一次。解决办法是让 POST 带幂等键,而不是靠网关的重试策略')

# ============ 三 ============
print('== 三:换几次。三个上游 A1、A2、A3 都回 503,B 不在池里;proxy_next_upstream error timeout http_503。比较默认(试遍所有上游)/ proxy_next_upstream_tries 2 / tries 1。发 30 个请求,统计每个请求打到上游的总次数')
hits = [0, 0, 0]; apps = []
for i in range(3):
    def mk(i):
        def app(h): hits[i] += 1; h.reply(503, b'x')
        return app
    apps.append(Svc(mk(i)))
rows = []
for name, extra in (('默认', ''), ('tries 2', 'proxy_next_upstream_tries 2;'), ('tries 1', 'proxy_next_upstream_tries 1;')):
    for i in range(3): hits[i] = 0
    ng = Nginx('v22c', 'upstream u { %s } server { listen {port}; location / { proxy_pass http://u; proxy_next_upstream error timeout http_503; %s } }' % (' '.join(f'server 127.0.0.1:{a.port} max_fails=0;' for a in apps), extra)).start()
    sts = collections.Counter(rpc(ng.port, '/', 5.0, keepalive=False)[0] for _ in range(30)); ng.stop()
    rows.append((name, dict(sts), sum(hits), f'{sum(hits) / 30:.1f}', hits[:]))
table(rows, ['配置', 'client 看到的状态码', '上游收到的总次数', '平均每个请求', 'A1 / A2 / A3 各收到'])
