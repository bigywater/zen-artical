import sys, os, re, struct, threading, statistics, errno, ssl, http.client, gzip, zlib, brotli, zstandard; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w80'); reset()
ctx = ssl.create_default_context()
def get(host, path, ae, https=True):
    c = http.client.HTTPSConnection(host, 443, timeout=10, context=ctx) if https else http.client.HTTPConnection(host, 80, timeout=10)
    c.request('GET', path, headers={'Accept-Encoding': ae, 'User-Agent': 'w80-test'}); r = c.getresponse(); b = r.read(); h = {k.lower(): v for k, v in r.getheaders()}; c.close(); return r.status, h, b
def dec(enc, b):
    if enc == 'gzip': return gzip.decompress(b)
    if enc == 'br': return brotli.decompress(b)
    if enc == 'zstd': return zstandard.ZstdDecompressor().decompressobj().decompress(b)
    if enc == 'deflate': return zlib.decompress(b)
    return b

print('== 一:服务器按 Accept-Encoding 选压缩方式。对两个真实服务器的几个资源,依次发 identity、gzip、br、zstd、deflate 和 "gzip, br, zstd",看 Content-Encoding 和实际字节')
for host, path, https, nm in (('www.python.org', '/static/css/style.css', True, 'python.org 的 CSS(文本)'), ('example.com', '/', False, 'example.com 首页(HTML)')):
    print(f'  {nm}:')
    base = None
    for ae in ('identity', 'gzip', 'br', 'zstd', 'deflate', 'gzip, br, zstd'):
        st, h, b = get(host, path, ae, https); enc = h.get('content-encoding'); raw = dec(enc, b)
        if base is None: base = raw
        print(f'    Accept-Encoding: {ae:<16}→ Content-Encoding = {str(enc):<5} 传输 {len(b):>7} 字节,解压后 {len(raw):>7} 字节,{"与 identity 内容一致" if raw == base else "内容不同"};Vary = {h.get("vary")}')
st, h, b = get('www.python.org', '/', 'identity'); print(f'  python.org 首页 /:发 Accept-Encoding: identity,响应的 Content-Encoding = {h.get("content-encoding")},{len(b)} 字节(服务器没有听从 identity,依旧发 gzip;它的 Vary 只写了 {h.get("vary")})')

print('== 二:q 值与特殊写法:对 example.com 首页,看 Accept-Encoding 的权重怎么影响选择')
for ae in ('gzip;q=0.5, br;q=1', 'br;q=0.1, gzip;q=0.9', 'br;q=0, gzip', 'gzip;q=0, br;q=0', '*', '*;q=0', 'identity;q=0', 'compress', 'GZIP'):
    try:
        st, h, b = get('example.com', '/', ae, False); print(f'  Accept-Encoding: {ae:<22}→ {st},Content-Encoding = {str(h.get("content-encoding")):<5},{len(b)} 字节')
    except Exception as e: print(f'  Accept-Encoding: {ae:<22}→ 失败 {type(e).__name__}')

print('== 三:压缩算法与级别:用本机把 python.org 的 CSS(349113 字节)压一遍,看压缩后大小和耗时(压缩 / 解压,本机单线程)')
raw = get('www.python.org', '/static/css/style.css', 'identity')[2]
print('    算法 / 级别         压缩后字节    比例     压缩耗时   解压耗时')
rows = []
def tm(f, n=3):
    ts = []
    for i in range(n):
        t0 = time.perf_counter(); r = f(); ts.append(time.perf_counter() - t0)
    return r, min(ts) * 1000
for nm, c, d in (('gzip -1', lambda: gzip.compress(raw, 1), gzip.decompress), ('gzip -6(常用默认)', lambda: gzip.compress(raw, 6), gzip.decompress), ('gzip -9', lambda: gzip.compress(raw, 9), gzip.decompress),
                 ('brotli q1', lambda: brotli.compress(raw, quality=1), brotli.decompress), ('brotli q5', lambda: brotli.compress(raw, quality=5), brotli.decompress), ('brotli q11(最高)', lambda: brotli.compress(raw, quality=11), brotli.decompress),
                 ('zstd -1', lambda: zstandard.ZstdCompressor(level=1).compress(raw), lambda b: zstandard.ZstdDecompressor().decompress(b, max_output_size=len(raw) * 2)), ('zstd -3(默认)', lambda: zstandard.ZstdCompressor(level=3).compress(raw), lambda b: zstandard.ZstdDecompressor().decompress(b, max_output_size=len(raw) * 2)), ('zstd -19', lambda: zstandard.ZstdCompressor(level=19).compress(raw), lambda b: zstandard.ZstdDecompressor().decompress(b, max_output_size=len(raw) * 2))):
    z, tc = tm(c); _, td = tm(lambda: d(z)); rows.append((nm, len(z), tc, td))
    print(f'    {nm:<18} {len(z):>10}  {len(z) / len(raw):>6.1%}   {tc:>8.1f} ms  {td:>6.1f} ms')
print(f'  原始 {len(raw)} 字节;真实服务器的 gzip 版本是 125147 字节(第一节),相当于本机的哪个级别附近:{min(rows[:3], key=lambda r: abs(r[1] - 125147))[0]}')

print('== 四:已经压缩过的数据再压一次没有收益:同一个压缩算法对不同类型的数据')
png = get('www.python.org', '/static/img/python-logo.png', 'identity')[2]; rnd = os.urandom(100000); gz_of_css = gzip.compress(raw, 6)
for nm, data in (('CSS 文本', raw), ('PNG 图片(已压缩格式)', png), ('随机字节', rnd), ('已经 gzip 过的 CSS', gz_of_css)):
    g = gzip.compress(data, 6); b = brotli.compress(data, quality=5)
    print(f'  {nm:<22} 原始 {len(data):>7} 字节 → gzip {len(g):>7}({len(g) / len(data):>6.1%}),brotli q5 {len(b):>7}({len(b) / len(data):>6.1%})')

print('== 五:压缩划不划算取决于链路:本机服务器把这个 CSS 以原样 / gzip -6 / brotli q5 三种形式发出,在三种带宽下(netlab,每方向延迟 20 ms)测下载 + 解压的总时间')
variants = {'raw': (raw, None), 'gzip': (gzip.compress(raw, 6), 'gzip'), 'brotli': (brotli.compress(raw, quality=5), 'br')}
def srv(port, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(16); ls.settimeout(0.3)
    def h(c):
        try:
            buf = b''
            while b'\r\n\r\n' not in buf: buf += c.recv(65536)
            v = re.search(rb'x-variant: *(\S+)', buf, re.I).group(1).decode(); body, enc = variants[v]
            c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: %d\r\n%sConnection: close\r\n\r\n' % (len(body), (b'Content-Encoding: ' + enc.encode() + b'\r\n') if enc else b'') + body)
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
def fetch_local(v):
    t0 = time.perf_counter(); s = socket.create_connection(('127.0.0.1', port)); s.sendall(b'GET / HTTP/1.1\r\nHost: x\r\nX-Variant: ' + v.encode() + b'\r\n\r\n'); buf = b''
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
    s.close(); head, body = buf.split(b'\r\n\r\n', 1); t1 = time.perf_counter()
    enc = re.search(rb'content-encoding: *(\S+)', head, re.I); out = dec(enc.group(1).decode() if enc else None, body); t2 = time.perf_counter()
    assert out == raw
    return (t1 - t0) * 1000, (t2 - t1) * 1000, len(body)
print('    带宽                原样(raw)         gzip -6           brotli q5      (每格:下载 ms + 解压 ms = 总 ms)')
for label, bw in (('1 Mbit/s', 1000), ('10 Mbit/s', 10000), ('1000 Mbit/s', 0)):
    cells = []
    with lossy(loss=0, delay=20, bw=bw):
        for v in variants:
            r = [fetch_local(v) for _ in range(2)]; d_ = min(x[0] for x in r); e_ = min(x[1] for x in r); cells.append(f'{d_:6.0f} + {e_:4.1f} = {d_ + e_:6.0f}')
    print(f'    {label:<12}  ' + '   '.join(cells))
stop[0] = True
