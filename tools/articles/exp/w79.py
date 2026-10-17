import sys, os, re, struct, threading, statistics, errno, ssl, http.client, hashlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w79'); reset()
ctx = ssl.create_default_context()
HOST = 'www.python.org'; PATH = '/static/img/python-logo.png'
def get(hdrs=None, method='GET', stop_after=None):
    c = http.client.HTTPSConnection(HOST, 443, timeout=8, context=ctx); h = {'Accept-Encoding': 'identity', 'User-Agent': 'w79-test'}; h.update(hdrs or {})
    c.request(method, PATH, headers=h); r = c.getresponse(); b = r.read() if stop_after is None else r.read(stop_after); hd = {k.lower(): v for k, v in r.getheaders()}; st = r.status; c.close(); return st, hd, b
st, h0, full = get(); SIZE = len(full); ETAG = h0['etag']
print(f'== 一:先看资源本身:{HOST}{PATH}:{st},{SIZE} 字节,Accept-Ranges = {h0.get("accept-ranges")},ETag = {ETAG},SHA-256 前 12 位 {hashlib.sha256(full).hexdigest()[:12]}')
print('== 二:Range 请求的各种写法(对这个资源),看状态码、Content-Range、实际收到的字节,以及内容是否与完整资源的对应片段一致')
cases = [('bytes=0-99', 0, 99), ('bytes=1000-1999', 1000, 1999), ('bytes=-100(最后 100 字节)', SIZE - 100, SIZE - 1), (f'bytes={SIZE - 500}-(从某处到结尾)', SIZE - 500, SIZE - 1), (f'bytes=0-{SIZE * 2}(终点超过大小)', 0, SIZE - 1)]
for nm, a, b in cases:
    rng = nm.split('(')[0]; st, hd, body = get({'Range': rng})
    print(f'  Range: {nm:<38}→ {st},Content-Range = {hd.get("content-range")},Content-Length = {hd.get("content-length")},收到 {len(body)} 字节,{"内容一致" if body == full[a:b + 1] else "内容不一致"}')
st, hd, body = get({'Range': f'bytes={SIZE + 10}-{SIZE + 20}'}); print(f'  Range: bytes={SIZE + 10}-{SIZE + 20}(起点超出资源)→ {st},Content-Range = {hd.get("content-range")},消息体 {len(body)} 字节')
st, hd, body = get({'Range': 'bytes=0-99,200-299,1000-1099'}); print(f'  Range: bytes=0-99,200-299,1000-1099(三段)→ {st},Content-Type = {hd.get("content-type")},消息体 {len(body)} 字节;开头 {body[:60]!r}')
st, hd, body = get({'Range': 'items=0-5'}); print(f'  Range: items=0-5(不认识的单位)→ {st},消息体 {len(body)} 字节')
print('== 三:If-Range:“如果资源没变就给我这一段,变了就给整个”。用来在续传时避免把旧片段和新资源拼在一起')
st, hd, body = get({'Range': 'bytes=0-99', 'If-Range': ETAG}); print(f'  If-Range: <当前 ETag> + Range → {st},收到 {len(body)} 字节')
st, hd, body = get({'Range': 'bytes=0-99', 'If-Range': '"old-etag"'}); print(f'  If-Range: "old-etag"(资源已变)+ Range → {st},收到 {len(body)} 字节(服务器忽略 Range,返回完整新资源)')

print('== 四:断点续传:读到一半把连接掐断,再用 Range 接着取。对真实服务器,先只读 6000 字节就关闭连接(模拟下载中断),然后 Range: bytes=6000- 取剩下的,拼起来校验')
st, hd, part = get(stop_after=6000)
print(f'  第一次:状态 {st},只读了 {len(part)} 字节就断开(完整大小 {SIZE})')
st2, hd2, rest = get({'Range': f'bytes={len(part)}-', 'If-Range': ETAG})
joined = part + rest
print(f'  续传:Range: bytes={len(part)}- → {st2},Content-Range = {hd2.get("content-range")},收到 {len(rest)} 字节;拼起来共 {len(joined)} 字节,SHA-256 前 12 位 {hashlib.sha256(joined).hexdigest()[:12]},{"与完整下载一致" if joined == full else "与完整下载不一致"}')
print(f'  对比从头重来:要再传 {SIZE} 字节;续传只传了 {len(rest)} 字节,省了 {(SIZE - len(rest)) / SIZE:.0%}(这里被省掉的只是 {len(part)} 字节)')

print('== 五:并行分段下载:本机服务器(支持 Range),netlab 每方向 50 ms(往返 100 ms)。下载一个 8 MB 的文件,接收缓冲区设成 256 KiB(窗口受限),单连接 vs 4 条连接各取 1/4 vs 8 条连接')
DATA = os.urandom(8_000_000)
def srv(port, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(32); ls.settimeout(0.3)
    def h(c):
        c.settimeout(10)
        try:
            buf = b''
            while b'\r\n\r\n' not in buf: buf += c.recv(65536)
            m = re.search(rb'range: *bytes=(\d+)-(\d+)', buf, re.I); a, b = (int(m.group(1)), int(m.group(2))) if m else (0, len(DATA) - 1)
            body = DATA[a:b + 1]
            c.sendall(b'HTTP/1.1 %s\r\nContent-Length: %d\r\nContent-Range: bytes %d-%d/%d\r\nConnection: close\r\n\r\n' % (b'206 Partial Content' if m else b'200 OK', len(body), a, b, len(DATA)) + body)
        except Exception: pass
        finally: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
def dl(port, a, b, out, i):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144); s.connect(('127.0.0.1', port))
    s.sendall(b'GET / HTTP/1.1\r\nHost: x\r\nRange: bytes=%d-%d\r\n\r\n' % (a, b)); buf = b''
    while b'\r\n\r\n' not in buf: buf += s.recv(65536)
    head, rest = buf.split(b'\r\n\r\n', 1); parts = [rest]; n = len(rest); want = b - a + 1
    while n < want:
        d = s.recv(1 << 20)
        if not d: break
        parts.append(d); n += len(d)
    out[i] = b''.join(parts); s.close()
port = lab_port(); stop = [False]; srv(port, stop); res = {}
with lossy(loss=0, delay=50, bw=0):
    for nconn in (1, 4, 8):
        ts = []
        for rep in range(2):
            out = [None] * nconn; sz = len(DATA); step_ = sz // nconn; t0 = time.time()
            th = [threading.Thread(target=dl, args=(port, i * step_, (sz - 1) if i == nconn - 1 else (i + 1) * step_ - 1, out, i)) for i in range(nconn)]
            for t in th: t.start()
            for t in th: t.join()
            ts.append(time.time() - t0); ok = b''.join(out) == DATA
        res[nconn] = (statistics.mean(ts), ok)
stop[0] = True
for n_, (t, ok) in res.items(): print(f'  {n_} 条连接:{t:.2f} 秒,{len(DATA) / t / 1e6:.1f} MB/s,拼接结果{"正确" if ok else "错误"}')
print(f'  4 条连接比 1 条快 {res[1][0] / res[4][0]:.1f} 倍,8 条比 1 条快 {res[1][0] / res[8][0]:.1f} 倍(窗口受限的单条连接吞吐 ≈ 256 KiB ÷ 100 ms = 2.6 MB/s;多连接相当于把窗口加起来)')
