import sys, os, re, struct, threading, statistics, errno, ssl, http.client, email.utils, gzip, hashlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w78'); reset()
ctx = ssl.create_default_context()
def fetch(host, path, hdrs=None, https=True):
    c = http.client.HTTPSConnection(host, 443, timeout=8, context=ctx) if https else http.client.HTTPConnection(host, 80, timeout=8)
    h = {'Accept-Encoding': 'identity', 'User-Agent': 'w78-test'}; h.update(hdrs or {})
    c.request('GET', path, headers=h); r = c.getresponse(); b = r.read(); hd = {k.lower(): v for k, v in r.getheaders()}; c.close()
    hlen = len(f'HTTP/1.1 {r.status} {r.reason}\r\n'.encode()) + sum(len(k) + len(v) + 4 for k, v in r.getheaders()) + 2
    return r.status, hd, b, hlen
def pd(s): return email.utils.parsedate_to_datetime(s).timestamp()

print('== 一:真实服务器响应里和缓存有关的头部,以及据此算出的“新鲜期”')
st, h1, b1, hl1 = fetch('www.python.org', '/static/img/python-logo.png')
print(f'  www.python.org 的 logo:{st},{len(b1)} 字节;Cache-Control = {h1.get("cache-control")};ETag = {h1.get("etag")};Last-Modified = {h1.get("last-modified")};Date = {h1.get("date")};Age = {h1.get("age")}')
mx = int(re.search(r'max-age=(\d+)', h1['cache-control']).group(1)); age = int(h1['age'])
print(f'  新鲜期:max-age {mx} 秒 − Age {age} 秒(这份响应已经在 CDN 里待了这么久)= 还剩 {mx - age} 秒 ≈ {(mx - age) / 86400:.1f} 天;浏览器缓存里的这份副本再活这么久之内都不用联网')
st, h2, b2, hl2 = fetch('example.com', '/')
lm = pd(h2['last-modified']); dt = pd(h2['date'])
print(f'  example.com 首页:{st},{len(b2)} 字节;Cache-Control = {h2.get("cache-control")};ETag = {h2.get("etag")};Last-Modified = {h2.get("last-modified")};Age = {h2.get("age")}')
print(f'  没有 Cache-Control、也没有 Expires,只有 Last-Modified:缓存可以用“启发式新鲜期”= 10% × (Date − Last-Modified) = 10% × {dt - lm:.0f} 秒 = {0.1 * (dt - lm):.0f} 秒 ≈ {0.1 * (dt - lm) / 3600:.1f} 小时(RFC 9111 建议的做法,各缓存实现不同)')

print('== 二:条件请求:带上之前拿到的验证器,问“你变了没有”。对 python.org 的 logo,各种 If-* 请求头的结果')
etag = h1['etag']; lmv = h1['last-modified']
rows = [('If-None-Match: <当前 ETag>', {'If-None-Match': etag}), ('If-None-Match: "不存在的 ETag"', {'If-None-Match': '"deadbeef"'}), ('If-Modified-Since: <Last-Modified>', {'If-Modified-Since': lmv}), ('If-Modified-Since: 一年前', {'If-Modified-Since': email.utils.formatdate(pd(lmv) - 365 * 86400, usegmt=True)}), ('两个都带(ETag 正确、日期过旧)', {'If-None-Match': etag, 'If-Modified-Since': email.utils.formatdate(pd(lmv) - 365 * 86400, usegmt=True)})]
print('    条件                                状态     消息体   头部字节  响应总字节')
tot200 = None
for nm, hh in [('(无条件)', {})] + rows:
    st, hd, b, hl = fetch('www.python.org', '/static/img/python-logo.png', hh)
    if not hh: tot200 = hl + len(b)
    print(f'    {nm:<34} {st:<7} {len(b):>7}  {hl:>7}   {hl + len(b):>8}')
st304, hd304, b304, hl304 = fetch('www.python.org', '/static/img/python-logo.png', {'If-None-Match': etag})
print(f'  304 Not Modified 的响应只带头部({hl304} 字节):它仍然带有 {sorted(k for k in hd304 if k in ("etag", "cache-control", "last-modified", "age", "date", "vary"))},缓存据此刷新副本的新鲜期;省下 {tot200 - (hl304 + len(b304))} 字节({(tot200 - hl304) / tot200:.1%})')
st, hd, b, hl = fetch('example.com', '/', {'If-Modified-Since': h2['last-modified']})
print(f'  example.com 用 If-Modified-Since: <它自己的 Last-Modified> → {st},消息体 {len(b)} 字节(它没有 ETag,只能靠日期验证)')

print('== 三:缓存策略的效果:本机服务器,netlab 每方向 50 ms(往返 100 ms)。一个 50 KB 的资源,每隔 0.4 秒访问一次,共 10 次,四种服务器配置,客户端是我写的一个遵守 Cache-Control: max-age 和 ETag 的最小缓存')
body = os.urandom(50000); ETAG = '"v1"'
def srv(port, stop, mode):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(16); ls.settimeout(0.3)
    def h(c):
        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1); c.settimeout(5); buf = b''
        try:
            while True:
                while b'\r\n\r\n' not in buf:
                    d = c.recv(65536)
                    if not d: return
                    buf += d
                head, buf = buf.split(b'\r\n\r\n', 1); inm = re.search(rb'if-none-match: *(\S+)', head, re.I)
                cc = {'none': b'', 'maxage': b'Cache-Control: max-age=60\r\n', 'etag': b'Cache-Control: no-cache\r\n', 'short': b'Cache-Control: max-age=1\r\n'}[mode]
                tag = b'ETag: ' + ETAG.encode() + b'\r\n' if mode in ('etag', 'short') else b''
                if inm and inm.group(1).decode() == ETAG and tag:
                    c.sendall(b'HTTP/1.1 304 Not Modified\r\n' + tag + cc + b'\r\n')
                else:
                    c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: %d\r\n' % len(body) + tag + cc + b'\r\n' + body)
        except Exception: pass
        finally: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
class Cache:
    def __init__(self, port): self.s = socket.create_connection(('127.0.0.1', port)); self.entry = None; self.buf = b''; self.net = 0; self.reqs = 0
    def get(self):
        now = time.time()
        if self.entry and self.entry['fresh_until'] > now: return 'hit', 0
        req = b'GET /a HTTP/1.1\r\nHost: x\r\n' + (b'If-None-Match: ' + self.entry['etag'] + b'\r\n' if self.entry and self.entry['etag'] else b'') + b'\r\n'
        self.s.sendall(req); self.reqs += 1
        while b'\r\n\r\n' not in self.buf: self.buf += self.s.recv(65536)
        head, rest = self.buf.split(b'\r\n\r\n', 1); st = int(head.split()[1]); n = int(re.search(rb'content-length: *(\d+)', head, re.I).group(1)) if st == 200 else 0
        while len(rest) < n: rest += self.s.recv(65536)
        self.buf = rest[n:]; self.net += len(head) + 4 + n
        m = re.search(rb'max-age=(\d+)', head); fresh = int(m.group(1)) if m else 0; et = re.search(rb'etag: *(\S+)', head, re.I)
        self.entry = {'fresh_until': time.time() + fresh, 'etag': et.group(1) if et else None}
        return ('304' if st == 304 else '200'), n
results = {}
with lossy(loss=0, delay=50, bw=0):
    for mode, nm in (('none', '无任何缓存头'), ('maxage', 'max-age=60'), ('etag', 'no-cache + ETag(每次都验证)'), ('short', 'max-age=1 + ETag')):
        port = lab_port(); stop = [False]; srv(port, stop, mode); c = Cache(port); log = []; lat = []
        for i in range(10):
            t0 = time.time(); r, n = c.get(); lat.append((time.time() - t0) * 1000); log.append(r); time.sleep(0.4)
        results[nm] = (log, lat, c.net, c.reqs); stop[0] = True
print('    配置                             每次的结果                                    总网络字节   发出请求数   延迟(ms,每次)')
for nm, (log, lat, net, reqs) in results.items():
    print(f'    {nm:<30} {"/".join(log):<42} {net:>9}   {reqs:>6}      {[round(x) for x in lat]}')
print('  “无任何缓存头”时客户端缓存没有可用的新鲜期,也没有验证器,每次都要重新下载整个 50 KB;max-age 内的访问完全不联网(延迟 0 ms);no-cache + ETag 每次都联网验证,但只付一个往返的延迟和很小的字节')

print('== 四:Vary:缓存键要把“影响响应内容的请求头”算进去。本机服务器对同一个 URL 根据 Accept-Encoding 返回压缩或不压缩的内容。用两种缓存键的共享缓存(代理)对比:只用 URL 做键,和用 URL + Vary 里列出的请求头做键')
plain = b'hello ' * 200; gz = gzip.compress(plain)
def origin(accept):
    if 'gzip' in accept: return {'ce': 'gzip', 'body': gz, 'vary': True}
    return {'ce': None, 'body': plain, 'vary': True}
for nm, keyer in (('只用 URL 做缓存键', lambda url, acc: url), ('URL + Vary: Accept-Encoding 做缓存键', lambda url, acc: (url, 'gzip' in acc))):
    cache = {}; outs = []
    for who, acc in (('甲(支持 gzip)', 'gzip, deflate'), ('乙(只收明文)', 'identity')):
        k = keyer('/a.js', acc)
        if k not in cache: cache[k] = origin(acc)
        e = cache[k]
        outs.append(f'{who}拿到 {"gzip 压缩的" if e["ce"] else "明文"} {len(e["body"])} 字节' + ('(乙收到了无法解读的压缩数据!)' if (e['ce'] and 'gzip' not in acc) else ''))
    print(f'  {nm}:' + ';'.join(outs) + f';缓存里存了 {len(cache)} 份')
