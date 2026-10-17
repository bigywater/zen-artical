import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests
tee('p1')
d = pdir('p1'); CERT, KEY = make_cert(d)
BODY = b'x' * 200
def ok(h): h.reply(200, BODY)

def bench(url, n, rounds, verify):
    """A:每次 requests.get;B:同一个 Session。两种做法交替跑 rounds 轮,返回每次请求的平均毫秒列表。"""
    A, B = [], []
    for r in range(rounds):
        order = ['A', 'B'] if r % 2 == 0 else ['B', 'A']
        for w in order:
            t0 = time.perf_counter()
            if w == 'A':
                for _ in range(n): requests.get(url, verify=verify)
            else:
                with requests.Session() as s:
                    for _ in range(n): s.get(url, verify=verify)
            (A if w == 'A' else B).append(ms(t0) / n)
    return A, B

def line(tag, xs): return f'  {tag}:每轮平均 {", ".join(f"{x:.2f}" for x in xs)} ms;中位数 {median(xs):.2f} ms'

print('== 一:HTTP,每次 requests.get 与同一个 Session(各 300 次请求,交替跑 5 轮)')
with Srv(ok) as s:
    A, B = bench(s.url('/'), 300, 5, True)
    print(line('每次 requests.get', A)); print(line('同一个 Session  ', B))
    print(f'  服务器共接受了 {s.n_conn} 条连接,收到 {len(s.log)} 个请求(5 轮 × 2 种做法 × 300 = 3000 个请求)')
    print(f'  两种做法的耗时比(每次新建 / Session)= {median(A) / median(B):.2f}')
with Srv(ok) as s:
    for _ in range(300): requests.get(s.url('/'))
    print(f'  单独统计:300 次 requests.get → 服务器接受 {s.n_conn} 条连接,每条连接上的请求数 {sorted(set(s.conns.values()))}')
with Srv(ok) as s:
    with requests.Session() as ss:
        for _ in range(300): ss.get(s.url('/'))
    print(f'  单独统计:一个 Session 发 300 次 → 服务器接受 {s.n_conn} 条连接,每条连接上的请求数 {sorted(set(s.conns.values()))}')

print('== 二:HTTPS(本机自签名证书,每次新建连接要做完整的 TLS 握手;各 150 次请求,交替跑 5 轮)')
with Srv(ok, tls=(CERT, KEY)) as s:
    A, B = bench(s.url('/'), 150, 5, CERT)
    print(line('每次 requests.get', A)); print(line('同一个 Session  ', B))
    print(f'  服务器共接受了 {s.n_conn} 条连接,收到 {len(s.log)} 个请求(5 × 2 × 150 = 1500)')
    print(f'  两种做法的耗时比(每次新建 / Session)= {median(A) / median(B):.2f}')

print('== 三:Session 复用连接的前提是上一个响应已经读完(stream=True 的三种用法,各发 4 次请求)')
def run3(mode):
    with Srv(ok) as s, requests.Session() as ss:
        keep = []
        for i in range(4):
            r = ss.get(s.url('/'), stream=True)
            if mode == 'read': r.content
            elif mode == 'close': r.close()
            else: keep.append(r)   # 不读也不关,但一直持有
        return s.n_conn, sorted(s.conns.values())
for mode, desc in (('none', 'stream=True,不读也不关'), ('read', 'stream=True,读完 r.content'), ('close', 'stream=True,不读直接 r.close()')):
    n, per = run3(mode)
    print(f'  {desc} → 服务器接受 {n} 条连接;各连接上的请求数 {per}')

print('== 四:连接什么时候会被关掉:服务器通知并关闭、客户端请求关闭、服务器无视客户端的请求')
def closing(h): h.reply(200, BODY, close=True)
with Srv(closing) as s, requests.Session() as ss:
    for _ in range(5): ss.get(s.url('/'))
    print(f'  服务器每次回 Connection: close 并关闭:Session 发 5 次 → 服务器接受 {s.n_conn} 条连接,各连接上的请求数 {sorted(s.conns.values())}')
def honor(h):
    c = 'close' in (h.headers.get('Connection') or '').lower()
    h.reply(200, BODY, close=c)
with Srv(honor) as s, requests.Session() as ss:
    for _ in range(5): ss.get(s.url('/'), headers={'Connection': 'close'})
    print(f'  客户端发 Connection: close,服务器照办(回 Connection: close 并关闭):Session 发 5 次 → {s.n_conn} 条连接,各连接上的请求数 {sorted(s.conns.values())}')
def ignore(h):
    h.close_connection = False   # 服务器无视请求头,继续保持连接
    h.reply(200, BODY)
with Srv(ignore) as s, requests.Session() as ss:
    for _ in range(5): ss.get(s.url('/'), headers={'Connection': 'close'})
    print(f'  客户端发 Connection: close,但服务器无视并保持连接:Session 发 5 次 → {s.n_conn} 条连接,各连接上的请求数 {sorted(s.conns.values())}')
purge()
