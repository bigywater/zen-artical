import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v36'); reset()
print('gRPC 穿过 nginx 1.31.6:用 grpc_pass(不是 proxy_pass)。服务和客户端是 Go 写的(google.golang.org/grpc v1.84.0,用的是 gRPC 系列里的 Demo 服务:Unary 和 ServerStream),明文 h2c(没有 TLS)。上游是两个 gRPC 服务 A、B(各回自己的名字)')
BIN = str(HERE / 'vtmp/v36bin')
def start_server(name):
    p = free_port(); proc = subprocess.Popen([BIN, 'server', str(p), name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); wait_port(p, 10); return proc, p
SA, pa = start_server('A'); SB, pb_ = start_server('B')
def run(*args, timeout=60):
    r = subprocess.run([BIN] + [str(a) for a in args], capture_output=True, text=True, timeout=timeout); return r.stdout.strip().splitlines()
def fmt_unary(lines): return '; '.join(l[7:] for l in lines if l.startswith('RESULT '))
def conf(extra_srv='', loc='grpc_pass grpc://u;', up=None):
    ups = up or f'server 127.0.0.1:{pa} max_fails=0;'
    return f'upstream u {{ {ups} }} server {{ listen {{port}}; http2 on; {extra_srv} location / {{ {loc} }} }}'

# ============ 一 ============
print('== 一:基本配置。四种 nginx 写法,各做一次 Unary 和一次 ServerStream(3 条消息,间隔 100 ms):(a) http2 on + grpc_pass grpc://;(b) 监听口没开 http2(只有 HTTP/1.1)+ grpc_pass;(c) http2 on + proxy_pass http://(把 gRPC 当普通 HTTP 反代);(d) 直连上游作对照')
rows = []
for name, mk in (('(a) http2 on + grpc_pass', lambda: Nginx('v36a', conf())), ('(b) 没开 http2 + grpc_pass', lambda: Nginx('v36a', conf().replace('http2 on;', ''))), ('(c) http2 on + proxy_pass', lambda: Nginx('v36a', conf(loc='proxy_pass http://u;'))), ('(d) 直连上游', None)):
    if mk: ng = mk().start(); addr = f'127.0.0.1:{ng.port}'
    else: ng = None; addr = f'127.0.0.1:{pa}'
    u = fmt_unary(run('unary', addr, 1, 0, 'hi', 5000)); s = run('stream', addr, 100, 3, 5000)
    rows.append((name, u, s[0].replace('STREAM ', '') if s else '')); 
    if ng: ng.stop()
table(rows, ['配置', 'Unary 结果', 'ServerStream 结果'])

# ============ 二 ============
print('== 二:超时。grpc_read_timeout 设成 1 s(默认 60 s)。三种调用:(a) Unary,上游处理 1.5 s;(b) ServerStream,每条消息间隔 0.5 s,共 4 条(总共 2 s,但每次读之间只隔 0.5 s);(c) ServerStream,每条消息间隔 1.5 s,共 2 条。看 client 得到的 gRPC 状态码和消息数')
ng = Nginx('v36b', conf('grpc_read_timeout 1s;')).start(); addr = f'127.0.0.1:{ng.port}'; rows = []
rows.append(('(a) Unary,上游 1.5 s', fmt_unary(run('unary', addr, 1, 0, 'sleep:1500', 10000)), '-'))
s = run('stream', addr, 500, 4, 10000)[0].replace('STREAM ', ''); rows.append(('(b) 间隔 0.5 s × 4 条', '-', s))
s = run('stream', addr, 1500, 2, 10000)[0].replace('STREAM ', ''); rows.append(('(c) 间隔 1.5 s × 2 条', '-', s))
ng.stop()
table(rows, ['调用', 'Unary 结果', 'ServerStream 结果'])
print('  grpc_read_timeout 和 proxy_read_timeout 一样,管的是“两次读到上游数据之间的间隔”:(b) 每次只隔 0.5 s,整个流 2 s 也没有超时;(a) 和 (c) 第一次读就等了 1.5 s,nginx 超时后回 HTTP 504,Go 的 gRPC 库把它翻译成 Unavailable(消息里带着 504)')

# ============ 三 ============
print('== 三:负载均衡。client 开一条 HTTP/2 连接,顺序发 100 个 Unary。upstream 里有 A、B 两个 gRPC 服务。比较:直连 A(只有一个后端,对照)/ client 只用一条连接直连 nginx(nginx 对每个请求独立地选上游)/ nginx 配 least_conn / ip_hash(所有请求来自 127.0.0.1)')
rows = []
for name, up in (('nginx 轮询', f'server 127.0.0.1:{pa} max_fails=0; server 127.0.0.1:{pb_} max_fails=0;'), ('nginx least_conn', f'least_conn; server 127.0.0.1:{pa} max_fails=0; server 127.0.0.1:{pb_} max_fails=0;'), ('nginx ip_hash', f'ip_hash; server 127.0.0.1:{pa} max_fails=0; server 127.0.0.1:{pb_} max_fails=0;')):
    ng = Nginx('v36c', conf(up=up)).start(); rows.append((name, fmt_unary(run('unary', f'127.0.0.1:{ng.port}', 100, 0, 'hi', 5000)))); ng.stop()
rows.append(('client 直连 A(没有 nginx)', fmt_unary(run('unary', f'127.0.0.1:{pa}', 100, 0, 'hi', 5000))))
table(rows, ['配置', '100 个 Unary 的分布(OK:服务名 次数)'])
print('  client 到 nginx 只有一条长连接,但 nginx 对每个 gRPC 调用(HTTP/2 的每个流)独立选择上游,所以轮询时请求被平均分到两个后端——不像 client 直连时那样,长连接把所有调用钉在一个后端上(见 gRPC 系列里 client 侧负载均衡的陷阱)')

# ============ 四 ============
print('== 四:消息大小。client_max_body_size 默认 1m。gRPC 的 Unary 带 payload:0.5 MB / 2 MB / 6 MB;上游允许 64 MB。比较 nginx 默认、client_max_body_size 10m、client_max_body_size 0(不限制)。看 client 的状态码')
rows = []
for name, extra in (('默认(client_max_body_size 1m)', ''), ('client_max_body_size 10m', 'client_max_body_size 10m;'), ('client_max_body_size 0', 'client_max_body_size 0;')):
    ng = Nginx('v36d', conf(extra)).start(); addr = f'127.0.0.1:{ng.port}'; row = [name]
    for mb in (0.5, 2, 6):
        row.append(fmt_unary(run('unary', addr, 1, int(mb * 1e6), 'hi', 20000)))
    rows.append(tuple(row)); ng.stop()
table(rows, ['配置', '0.5 MB', '2 MB', '6 MB'])
print('  grpc_pass 的请求体也受 client_max_body_size 限制(默认 1m);超限时 nginx 回 HTTP 413,Go 的 gRPC 库把它翻译成 Unknown(消息是 unexpected HTTP status code received from server: 413),不是 ResourceExhausted 之类一眼看得出原因的错误')
SA.kill(); SB.kill()
