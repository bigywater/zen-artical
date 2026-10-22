import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v21'); reset()
print('nginx 的“超时三件套”:proxy_connect_timeout(和上游建立连接)、proxy_send_timeout(两次向上游写数据之间的间隔)、proxy_read_timeout(两次从上游读数据之间的间隔)。三个超时都不是“整个请求的总时长”。上游用我写的原始 socket 服务扮演各种坏行为;nginx 1.31.6 的 error.log 记录触发的是哪一个')

class Raw:
    """原始 TCP 服务:每个连接交给 handler(conn)。"""
    def __init__(s, handler, backlog=128, rcvbuf=None):
        s.sock = socket.socket(); s.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if rcvbuf: s.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
        s.port = free_port(); s.sock.bind(('127.0.0.1', s.port)); s.sock.listen(backlog); s.handler = handler; s.stop = False; s.conns = []
        threading.Thread(target=s.loop, daemon=True).start()
    def loop(s):
        while not s.stop:
            try: c, _ = s.sock.accept()
            except Exception: return
            s.conns.append(c); threading.Thread(target=s.safe, args=(c,), daemon=True).start()
    def safe(s, c):
        try: s.handler(c)
        except Exception: pass
    def close(s):
        s.stop = True
        for c in s.conns:
            try: c.close()
            except Exception: pass
        try: s.sock.close()
        except Exception: pass
def read_req(c):
    d = b''
    while b'\r\n\r\n' not in d:
        x = c.recv(65536)
        if not x: return None
        d += x
    return d
OK = b'HTTP/1.1 200 OK\\r\\nContent-Length: 8\\r\\nConnection: close\\r\\n\\r\\n'.replace(b'\\\\r\\\\n', b'\\r\\n')
HDR = b'HTTP/1.1 200 OK\r\nContent-Length: 8\r\nConnection: close\r\n\r\n'
def silent(c): read_req(c); time.sleep(60)
def late_header(c): read_req(c); time.sleep(1.5); c.sendall(HDR + b'12345678'); c.close()
def drip(c):
    read_req(c); c.sendall(HDR)
    for i in range(8): time.sleep(0.4); c.sendall(b'x')
    c.close()
def mid_stall(c):
    read_req(c); c.sendall(HDR + b'1234'); time.sleep(1.5)
    try: c.sendall(b'5678'); c.close()
    except Exception: pass
def noread(c): time.sleep(60)
def conf(up, extra=''):
    return f'upstream u {{ {up} }} server {{ listen {{port}}; client_max_body_size 100m; location / {{ proxy_pass http://u; {extra} }} }}'
def req(port, method='GET', body=None, timeout=15.0):
    t0 = time.perf_counter(); c = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        c.request(method, '/', body=body); r = c.getresponse(); d = r.read(); return r.status, len(d), time.perf_counter() - t0
    except Exception as e: return type(e).__name__, 0, time.perf_counter() - t0
    finally: c.close()
def errlines(ng, key):
    return [l.split('] ', 1)[1][:150] if '] ' in l else l for l in (ng.d / 'err.log').read_text().splitlines() if key in l and '[error]' in l][:2]

# ============ 一 ============
print('== 一:三个超时分别在什么时候触发。三个超时都设成 1 s。(1) 连接:上游地址是 192.0.2.1(保留的文档地址,SYN 发出去没有任何回应);(2) 发送:POST 30 MB,上游 accept 之后从不读;(3) 读取:上游收完请求后一声不吭。统计 client 等了多久、拿到什么状态码,以及 error.log 里的原因')
rows = []
# (1) 连接:连一个不可路由的保留地址(192.0.2.1,TEST-NET-1,SYN 发出去没有任何回应)
ng = Nginx('v21a', conf('server 192.0.2.1:80 max_fails=0;', 'proxy_connect_timeout 1s; proxy_send_timeout 1s; proxy_read_timeout 1s;')).start()
st, n, dt = req(ng.port); rows.append(('(1) 连接', st, f'{dt:.2f} s', ' | '.join(errlines(ng, 'upstream')))); ng.stop()
# (2) 发送
R2 = Raw(noread, rcvbuf=4096)
ng = Nginx('v21b', conf(f'server 127.0.0.1:{R2.port};', 'proxy_connect_timeout 1s; proxy_send_timeout 1s; proxy_read_timeout 1s; proxy_request_buffering on;')).start()
st, n, dt = req(ng.port, 'POST', b'x' * 30_000_000, 30.0); rows.append(('(2) 发送', st, f'{dt:.2f} s(含 client 把 30 MB 交给 nginx 的时间)', ' | '.join(errlines(ng, 'upstream')))); ng.stop(); R2.close()
# (3) 读取
R3 = Raw(silent)
ng = Nginx('v21c', conf(f'server 127.0.0.1:{R3.port};', 'proxy_connect_timeout 1s; proxy_send_timeout 1s; proxy_read_timeout 1s;')).start()
st, n, dt = req(ng.port); rows.append(('(3) 读取', st, f'{dt:.2f} s', ' | '.join(errlines(ng, 'upstream')))); ng.stop(); R3.close()
table(rows, ['超时', 'client 看到', 'client 等了', 'error.log 里的原因'])

# ============ 二 ============
print('== 二:读取超时是“两次读之间的间隔”。proxy_read_timeout = 1 s;三种上游行为:(a) 先一声不吭 1.5 s 再回完整响应;(b) 马上发响应头,然后每 0.4 s 发 1 个字节,共 8 个字节(总共 3.2 s);(c) 发响应头和 4 个字节,停 1.5 s,再发剩下的 4 个字节')
rows = []
for name, h in (('(a) 先沉默 1.5 s 再回', late_header), ('(b) 头先到,之后每 0.4 s 一个字节', drip), ('(c) 头和 4 字节先到,停 1.5 s', mid_stall)):
    R = Raw(h); ng = Nginx('v21d', conf(f'server 127.0.0.1:{R.port};', 'proxy_read_timeout 1s;')).start()
    st, n, dt = req(ng.port); rows.append((name, st, f'{n} 字节(声明 8)', f'{dt:.2f} s', ' | '.join(errlines(ng, 'upstream'))[:140])); ng.stop(); R.close()
table(rows, ['上游行为', 'client 看到的状态码', 'client 收到的响应体', 'client 等了', 'error.log'])
print('  (b) 整个响应花了 3.2 s,但每次读之间最多隔 0.4 s,从来没触发 1 s 的读取超时;(c) 响应头已经发给 client(状态码 200)之后上游才卡住,nginx 无法再改状态码,只能把连接断掉,client 收到的是残缺的响应体')

# ============ 三 ============
print('== 三:超时和重试叠加。两个上游都“先沉默 1.5 s 再回”,proxy_read_timeout = 1 s;proxy_next_upstream error timeout(默认)会换下一个上游;两个 server 都写了 max_fails=0,免得超时之后被摘除,影响下一次测量。比较:默认 / 加 proxy_next_upstream_tries 1 / 加 proxy_next_upstream_timeout 1500ms;GET 与 POST(POST 默认不会在请求已发出后重试)')
R1, R2 = Raw(late_header), Raw(late_header)
up = f'server 127.0.0.1:{R1.port} max_fails=0; server 127.0.0.1:{R2.port} max_fails=0;'
rows = []
for name, extra in (('默认', ''), ('next_upstream_tries 1', 'proxy_next_upstream_tries 1;'), ('next_upstream_timeout 1500ms', 'proxy_next_upstream_timeout 1500ms;'), ('next_upstream_timeout 800ms', 'proxy_next_upstream_timeout 800ms;')):
    ng = Nginx('v21e', conf(up, 'proxy_read_timeout 1s; ' + extra)).start()
    g = req(ng.port); p = req(ng.port, 'POST', b'a=1'); ng.stop()
    rows.append((name, f'{g[0]} · {g[2]:.2f} s', f'{p[0]} · {p[2]:.2f} s'))
table(rows, ['配置', 'GET:状态码 · 等了', 'POST:状态码 · 等了'])
R1.close(); R2.close()
print('  默认配置下 GET 先在第一个上游等满 1 s 超时,再去第二个上游又等满 1 s,client 一共等了约两倍的读取超时;POST 请求已经发给上游,出错后默认不再重试(非幂等),所以只等一个读取超时;next_upstream_tries 1 让 GET 也只试一次。proxy_next_upstream_timeout 限制的是“还允许换上游重试的时间窗”,不是总时长:设 1500ms 时第二次尝试在 1.0 s 开始(窗口还没过),它仍然跑满自己的 1 s 读取超时,总共还是约 2 s;设 800ms 时 1.0 s 已经超出窗口,不再换上游,总共约 1 s')
