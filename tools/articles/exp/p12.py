import sys, os, ssl, socket, asyncio; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests, aiohttp, warnings; warnings.filterwarnings('ignore')
from curl_cffi import requests as cr
tee('p12')
d = pdir('p12'); CERTS = {a: make_cert(d, alg=a) for a in ('ec256', 'ec384', 'rsa2048', 'rsa4096')}
REQ = b'GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n'

def client_ctx(maxv=None):
    c = ssl.create_default_context(); c.check_hostname = False; c.verify_mode = ssl.CERT_NONE
    if maxv: c.maximum_version = maxv
    return c

def one(ctx, port, sess):
    t0 = time.perf_counter(); raw = socket.create_connection(('127.0.0.1', port)); t1 = time.perf_counter()
    s = ctx.wrap_socket(raw, server_hostname='127.0.0.1', session=sess); t2 = time.perf_counter()
    s.sendall(REQ)
    s.recv(65536)   # 响应很小,一次就收完;读到这里立刻取会话(为什么不读到 EOF 再取,见第一节)
    t3 = time.perf_counter(); ses = s.session; re = s.session_reused; s.close()
    return (t1 - t0) * 1000, (t2 - t1) * 1000, (t3 - t2) * 1000, ses, re

def bench(port, maxv=None, n=300):
    """交替做 完整握手 / 会话复用 各 n 次,返回两组 (connect, handshake, request) 的中位数。"""
    ctx = client_ctx(maxv); full, res = [], []; sess = None
    _, _, _, sess, _ = one(ctx, port, None)
    ok_reuse = []
    for i in range(n):
        if i % 2 == 0:
            a = one(ctx, port, None); full.append(a[:3])
        b = one(ctx, port, sess); res.append(b[:3]); ok_reuse.append(b[4]); sess = b[3] or sess
        if i % 2 == 1:
            a = one(ctx, port, None); full.append(a[:3])
    m = lambda L, k: median([x[k] for x in L])
    return [(m(L, 0), m(L, 1), m(L, 2)) for L in (full, res)], sum(ok_reuse) / len(ok_reuse)

print('== 一:先弄清一件事:会话票据什么时候才可复用(第 1 次连接取会话,第 2 次连接带上它;TLS 1.3,EC P-256 证书)')
def clean_close(h):
    h.reply(200, b'ok', close=True)
    try: h.connection.settimeout(1.0); h.connection.unwrap()   # 先发 TLS 的 close_notify,再关 TCP
    except Exception: pass
def probe(fn, mode):
    with Srv(fn, tls=CERTS['ec256']) as sv:
        ctx = client_ctx(); res = []
        for _ in range(2):
            raw = socket.create_connection(('127.0.0.1', sv.port)); s = ctx.wrap_socket(raw, server_hostname='127.0.0.1', session=res[-1] if res else None)
            s.sendall(REQ)
            if mode == 'early': s.recv(65536)
            else:
                while s.recv(65536): pass
            res.append(s.session); re = s.session_reused; s.close()
        return re
for srv_label, fn in (('服务器直接关 TCP(不发 close_notify)', None), ('服务器先发 close_notify 再关', clean_close)):
    for mode, lab in (('early', '客户端收到响应就立刻取会话'), ('eof', '客户端一直读到 EOF 再取会话')):
        print(f'  {srv_label};{lab} → 第 2 次连接复用了会话:{probe(fn, mode)}')

print('== 二:一次 HTTPS 请求的时间花在哪:TCP 连接、TLS 握手、发请求收响应(椭圆曲线 P-256 证书,TLS 1.3,本机回环,各 300 次)')
with Srv(tls=CERTS['ec256']) as sv:
    (f, r), frac = bench(sv.port)
    for lab, x in (('完整握手', f), ('会话复用', r)):
        tot = sum(x)
        print(f'  {lab}:TCP 连接 {x[0]:.3f} ms + TLS 握手 {x[1]:.3f} ms + 请求/响应 {x[2]:.3f} ms = {tot:.3f} ms;握手占 {x[1] / tot * 100:.0f}%')
    print(f'  复用那组里,客户端确认会话被复用的比例 {frac * 100:.0f}%')
    print(f'  握手耗时:复用 / 完整 = {r[1] / f[1]:.2f}')

print('== 三:证书的密钥类型对完整握手的影响(服务器要签名):各 200 次,TLS 1.3')
print(f'  {"证书":<10}{"完整握手":>10}{"会话复用":>10}')
for a in ('ec256', 'ec384', 'rsa2048', 'rsa4096'):
    with Srv(tls=CERTS[a]) as sv:
        (f, r), frac = bench(sv.port, n=200)
        print(f'  {a:<10}{f[1]:>8.3f} ms{r[1]:>8.3f} ms')

print('== 四:TLS 1.2 与 TLS 1.3 的握手(EC P-256 证书,本机回环没有网络延迟,所以看不出往返次数的差别)各 200 次')
with Srv(tls=CERTS['ec256']) as sv:
    for lab, v in (('TLS 1.3', None), ('限制到 TLS 1.2', ssl.TLSVersion.TLSv1_2)):
        (f, r), frac = bench(sv.port, v, 200)
        print(f'  {lab}:完整握手 {f[1]:.3f} ms,会话复用 {r[1]:.3f} ms(复用成功比例 {frac * 100:.0f}%)')

print('== 五:各个客户端库在"每个请求新建连接"时,服务器看到有几个连接是复用了 TLS 会话的(20 次请求)')
cert = CERTS['ec256'][0]
def stat(sv):
    L = sv.log; return f'服务器收到 {len(L)} 个请求,其中复用了 TLS 会话的 {sum(1 for x in L if x["reused"])} 个,连接数 {sv.n_conn}'
with Srv(tls=CERTS['ec256']) as sv:
    for _ in range(20): requests.get(sv.url('/'), verify=False)
    print(f'  requests.get ×20:{stat(sv)}')
with Srv(tls=CERTS['ec256']) as sv:
    s = requests.Session()
    for _ in range(20): s.get(sv.url('/'), verify=False, headers={'Connection': 'close'})
    print(f'  同一个 requests.Session,每次 Connection: close ×20:{stat(sv)}')
with Srv(tls=CERTS['ec256']) as sv:
    s = cr.Session(verify=False)
    for _ in range(20): s.get(sv.url('/'), headers={'Connection': 'close'})
    print(f'  curl_cffi Session,每次 Connection: close ×20:{stat(sv)}')
with Srv(tls=CERTS['ec256']) as sv:
    for _ in range(20): cr.get(sv.url('/'), verify=False)
    print(f'  curl_cffi.requests.get ×20(每次新建 Session):{stat(sv)}')
with Srv(tls=CERTS['ec256']) as sv:
    async def aio():
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(force_close=True, ssl=False)) as s:
            for _ in range(20):
                async with s.get(sv.url('/')) as r: await r.read()
    asyncio.run(aio())
    print(f'  aiohttp,force_close=True ×20:{stat(sv)}')
purge()
