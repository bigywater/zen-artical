import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v37'); reset()
print('nginx 访问日志里的几个时间:$request_time(从读到请求的第一个字节到把响应最后一个字节写给 client)、$upstream_connect_time(和上游建立连接用了多久)、$upstream_header_time(从发出请求到收到上游响应头)、$upstream_response_time(到收完上游响应)。日志格式把这四个时间、$upstream_addr、$upstream_status 和 $status 写进文件,实验里解析这些行。nginx 1.31.6')
FMT = 'log_format t "$request_time|$upstream_connect_time|$upstream_header_time|$upstream_response_time|$upstream_addr|$upstream_status|$status|$bytes_sent";'
def parse(ng):
    lines = [l for l in (ng.d / 'access.log').read_text().splitlines() if l.strip()]; out = []
    for l in lines:
        rt, uc, uh, ur, ua, us, st, bs = l.split('|'); out.append(dict(rt=rt, uc=uc, uh=uh, ur=ur, ua=ua, us=us, st=st, bs=bs))
    return out
def conf(up, loc='proxy_pass http://u;', extra=''):
    return f'{FMT} access_log {{d}}/access.log t; upstream u {{ {up} }} server {{ listen {{port}}; client_max_body_size 100m; {extra} location / {{ {loc} }} }}'
def ms(x): return '-' if x in ('-', '') else ' / '.join(('-' if v == '-' else f'{float(v) * 1000:.0f}') for v in x.replace(' ', '').split(','))
def slow_client_get(port, total, rate_per_s):
    s = socket.create_connection(('127.0.0.1', port)); s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32768); s.sendall(b'GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n'); got = 0; chunk = 50000
    while True:
        time.sleep(chunk / rate_per_s); d = s.recv(chunk)
        if not d: break
        got += len(d)
    s.close(); return got

# ============ 一 ============
print('== 一:request_time 和 upstream_response_time 为什么不一样。六种情形各发一个请求,读日志里那一行(毫秒)。上游:快(立刻回 5 MB 以内的响应)/ 慢(先 sleep 200 ms)。client:快 / 慢(读 2 MB/s)/ 慢上传(POST 3 MB,1 MB/s)。proxy_buffering 开(默认)或关')
def big_app(size, delay=0.0):
    def app(h):
        n = int(h.headers.get('Content-Length') or 0)
        if n: h.rfile.read(n)
        if delay: time.sleep(delay)
        h.reply(200, b'x' * size)
    return app
rows = []
def one_case(name, app, loc_extra, client_fn, loc='proxy_pass http://u;'):
    B = Svc(app, backlog=64); ng = Nginx('v37a', conf(f'server 127.0.0.1:{B.port};', loc + ' ' + loc_extra)).start(); client_fn(ng.port); time.sleep(0.4); r = parse(ng)[-1]; ng.stop(); B.stop()
    rows.append((name, f"{float(r['rt']) * 1000:.0f}", ms(r['uc']), ms(r['uh']), ms(r['ur']), r['st']))
def fast_get(port): rpc(port, '/', 20.0, keepalive=False)
def post_slow(port, total=3_000_000, rate=1_000_000):
    s = socket.create_connection(('127.0.0.1', port)); s.sendall(f'POST / HTTP/1.1\r\nHost: x\r\nContent-Length: {total}\r\nConnection: close\r\n\r\n'.encode()); sent = 0
    while sent < total:
        n = min(100000, total - sent); s.sendall(b'y' * n); sent += n; time.sleep(n / rate)
    d = b''
    while True:
        x = s.recv(65536)
        if not x: break
        d += x
    s.close()
one_case('(1) 快上游 · 快 client', big_app(100), '', fast_get)
one_case('(2) 慢上游(200 ms)· 快 client', big_app(100, 0.2), '', fast_get)
one_case('(3) 快上游 · 5 MB 响应 · 慢 client(2 MB/s)· buffering on', big_app(5_000_000), '', lambda p: slow_client_get(p, 5_000_000, 2_000_000))
one_case('(4) 同 (3) · proxy_buffering off', big_app(5_000_000), 'proxy_buffering off;', lambda p: slow_client_get(p, 5_000_000, 2_000_000))
one_case('(5) 快上游 · 慢上传(POST 3 MB,1 MB/s)· request_buffering on', big_app(100), '', post_slow)
one_case('(6) 同 (5) · proxy_request_buffering off', big_app(100), 'proxy_request_buffering off;', post_slow)
table(rows, ['情形', '$request_time ms', '$upstream_connect_time ms', '$upstream_header_time ms', '$upstream_response_time ms', '$status'])
print('  $request_time 包含 client 一侧的时间(上传请求体、下载响应体),$upstream_* 只看 nginx 和上游之间。(3) 缓冲打开时,nginx 很快收完上游的 5 MB(upstream_response_time 小),再慢慢发给慢 client(request_time 大):两者的差就是 client 一侧耗掉的时间;(4) 关掉缓冲后上游被拖到 client 的速度,upstream_response_time 也变大。(5) 请求体缓冲打开时,nginx 先收完 3 MB 才去连上游,upstream_* 里不含上传时间;(6) 关掉请求缓冲边收边转,上游的响应时间包含了上传过程')

# ============ 二 ============
print('== 二:重试时日志里的逗号。upstream 里有 A(端口没人监听)和 B(正常 20 ms)。GET 请求先打到 A 失败再重试 B。日志的 $upstream_addr / $upstream_status / $upstream_*_time 会变成逗号分隔的列表,每次尝试一项;还有 $upstream_cache_status 无关。发 4 个请求,看每一行')
B = Svc(lambda h: (time.sleep(0.02), h.reply(200, b'B'))[1]); dead = free_port()
ng = Nginx('v37b', conf(f'server 127.0.0.1:{dead} max_fails=0; server 127.0.0.1:{B.port};', 'proxy_pass http://u; proxy_next_upstream error timeout;')).start()
for i in range(4): rpc(ng.port, '/', 5.0, keepalive=False)
time.sleep(0.3); rs = parse(ng); ng.stop()
table([(f"{float(r['rt']) * 1000:.0f}", r['ua'].replace(f':{dead}', ':A(死的)').replace(f':{B.port}', ':B'), r['us'], ms(r['uc']), ms(r['uh']), ms(r['ur']), r['st']) for r in rs], ['$request_time ms', '$upstream_addr', '$upstream_status', '$upstream_connect_time ms', '$upstream_header_time ms', '$upstream_response_time ms', '$status'])
print('  被轮询到 A 的请求有两项(先 A 后 B):A 那一项的状态是 502(连接被拒时 nginx 自己记的,不是上游真的回了 502),时间项里是 “-” 或 0;只打到 B 的请求只有一项。统计耗时时不能直接把这些字段当数字解析,要先按逗号拆开;同一个请求的 $request_time 是总耗时,不等于各项之和')

# ============ 三 ============
print('== 三:连接、响应头、响应体各占多少。上游是原始 TCP 服务:收到请求后 sleep 150 ms 再发响应头,再 sleep 100 ms 发响应体。分别在 upstream keepalive 开(默认,第 2 个请求复用连接)和每次新建连接(proxy_set_header Connection close)下,各发 3 个请求。看第 1 个和第 2 个请求的 $upstream_connect_time、$upstream_header_time、$upstream_response_time')
def raw_slow(c):
    while True:
        d = b''
        while b'\r\n\r\n' not in d:
            x = c.recv(65536)
            if not x: return
            d += x
        time.sleep(0.15); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n'); time.sleep(0.1); c.sendall(b'hello')
RAWB = Raw(raw_slow); rows = []
for name, loc in (('keepalive(默认)', ''), ('每次新建连接', 'proxy_set_header Connection close;')):
    ng = Nginx('v37c', conf(f'server 127.0.0.1:{RAWB.port};', 'proxy_pass http://u; ' + loc)).start()
    for i in range(3): rpc(ng.port, '/', 5.0, keepalive=False)
    time.sleep(0.3); rs = parse(ng); ng.stop()
    for i, r in enumerate(rs): rows.append((name if i == 0 else '', f'第 {i + 1} 个', f"{float(r['rt']) * 1000:.0f}", ms(r['uc']), ms(r['uh']), ms(r['ur'])))
table(rows, ['上游连接', '请求', '$request_time ms', '$upstream_connect_time ms', '$upstream_header_time ms', '$upstream_response_time ms'])
print('  $upstream_header_time 是从发出请求到收到响应头(这里约 150 多 ms),$upstream_response_time 再加上收响应体的时间(这里约 260 ms)。$upstream_connect_time 在本机环回上建连接不到 1 ms,所以不管复用还是新建都显示 0(或 1),这个实验看不出连接复用对它的影响')
