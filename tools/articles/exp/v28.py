import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v28'); reset()
print('请求体大小限制:nginx 的 client_max_body_size(默认 1m),超限返回 413。上游是我写的原始 TCP 服务,数它在请求头之后一共收到多少字节的请求体(支持 Content-Length 和 chunked 两种),收完回 200。client 是原始 socket。nginx 1.31.6')
STATE = {'bytes': None, 'hits': 0}
def backend(c):
    d = b''
    while b'\r\n\r\n' not in d:
        x = c.recv(65536)
        if not x: return
        d += x
    head, rest = d.split(b'\r\n\r\n', 1); hl = head.decode().lower(); STATE['hits'] += 1; got = len(rest)
    if 'transfer-encoding: chunked' in hl:
        buf = rest
        while not buf.endswith(b'0\r\n\r\n'):
            x = c.recv(65536)
            if not x: break
            buf += x; got = len(buf)
    else:
        cl = int(hl.split('content-length:')[1].split('\r\n')[0]) if 'content-length:' in hl else 0
        while got < cl:
            x = c.recv(65536)
            if not x: break
            got += len(x)
    STATE['bytes'] = got
    try: c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok')
    except Exception: pass
    c.close()
R = Raw(backend)
def conf(extra='', loc='location / { proxy_pass http://u; }'):
    return f'upstream u {{ server 127.0.0.1:{R.port}; }} server {{ listen {{port}}; {extra} {loc} }}'
def post(port, size, chunked=False, path='/', expect=False):
    """返回 (client 看到的结果, 耗时, client 实际发出的字节数)"""
    s = socket.create_connection(('127.0.0.1', port)); s.settimeout(30); t0 = time.perf_counter(); sent = 0
    hd = f'POST {path} HTTP/1.1\r\nHost: x\r\n' + ('Transfer-Encoding: chunked\r\n' if chunked else f'Content-Length: {size}\r\n') + ('Expect: 100-continue\r\n' if expect else '') + 'Connection: close\r\n\r\n'
    resp = b''; err = None
    try:
        s.sendall(hd.encode())
        if expect:
            s.settimeout(1.0)
            try: resp = s.recv(4096)
            except socket.timeout: pass
            s.settimeout(30)
        if not resp.startswith(b'HTTP/1.1 413'):
            blk = b'x' * 65536
            while sent < size:
                n = min(65536, size - sent)
                if chunked: s.sendall(b'%x\r\n' % n + blk[:n] + b'\r\n')
                else: s.sendall(blk[:n])
                sent += n
            if chunked: s.sendall(b'0\r\n\r\n')
    except (BrokenPipeError, ConnectionResetError) as e: err = type(e).__name__
    try:
        while b'\r\n\r\n' not in resp and not err:
            x = s.recv(65536)
            if not x: break
            resp += x
    except (ConnectionResetError, socket.timeout) as e: err = err or type(e).__name__
    s.close(); code = resp.split(b' ')[1].decode() if resp.startswith(b'HTTP/') else None
    return (code or '(没有收到响应)') + (f' + {err}' if err else ''), time.perf_counter() - t0, sent

# ============ 一 ============
print('== 一:Content-Length 超限。client_max_body_size 1m(默认)。POST 的 Content-Length 分别是 0.5 MB / 2 MB / 20 MB / 200 MB。nginx 看到 Content-Length 大于限制,在读请求体之前就回 413。统计 client 最后看到什么,client 实际发出了多少字节请求体,以及上游收到了多少(没到上游就是 0 次)')
rows = []
for mb in (0.5, 2, 20, 200):
    STATE['bytes'] = None; STATE['hits'] = 0
    ng = Nginx('v28a', conf()).start(); r, dt, sent = post(ng.port, int(mb * 1e6)); ng.stop(); time.sleep(0.2)
    rows.append((f'{mb} MB', r, f'{sent / 1e6:.1f} MB', f'{dt:.2f} s', '没到上游' if STATE['hits'] == 0 else f"{STATE['bytes'] / 1e6:.2f} MB"))
table(rows, ['Content-Length', 'client 看到', 'client 实际发出', '耗时', '上游收到的请求体'])
print('  Content-Length 超限的请求,nginx 回 413 之后会“延迟关闭”(lingering close):继续把 client 还在发的请求体读掉丢弃一段时间,所以 client 大多还能收到 413;client 发得快、请求体特别大时,发送可能先于 413 的到达而失败(看 client 实际发出的字节数)')

# ============ 二 ============
print('== 二:chunked 上传没有 Content-Length。client 用 Transfer-Encoding: chunked 上传 5 MB,client_max_body_size 1m。比较 proxy_request_buffering on(默认,nginx 先把请求体收完再转给上游)与 off(边收边转给上游)。统计 client 看到什么,以及上游收到了多少字节的请求体')
rows = []
for name, extra in (('proxy_request_buffering on(默认)', ''), ('proxy_request_buffering off', 'proxy_request_buffering off;')):
    STATE['bytes'] = None; STATE['hits'] = 0
    ng = Nginx('v28b', conf('', f'location / {{ proxy_pass http://u; {extra} }}')).start(); r, dt, sent = post(ng.port, 5_000_000, chunked=True); ng.stop(); time.sleep(0.5)
    rows.append((name, r, f'{sent / 1e6:.1f} MB', '没到上游' if STATE['hits'] == 0 else f"{STATE['bytes'] / 1e6:.2f} MB"))
table(rows, ['配置', 'client 看到', 'client 实际发出', '上游收到的请求体'])
print('  chunked 没有事先声明长度,nginx 只能边读边数,读超过限制才知道超限:缓冲打开时请求体还没转给上游,上游完全不知情;关闭缓冲(边收边转)时,上游已经收到了一部分请求体,然后连接被掐断,上游看到的是残缺的请求')

# ============ 三 ============
print('== 三:按 location 放宽。server 级 client_max_body_size 1m;/upload 这个 location 放宽到 50m。分别向 /api 和 /upload 上传 0.5 MB / 5 MB / 60 MB。再看 Expect: 100-continue 的 client:先发头等 nginx 的 100 再发请求体,5 MB 超限时 client 有没有白白把请求体发完')
rows = []
for sz in (0.5e6, 5e6, 60e6):
    row = [f'{sz / 1e6:g} MB']
    for path in ('/api', '/upload'):
        STATE['hits'] = 0
        ng = Nginx('v28c', conf('client_max_body_size 1m;', 'location /api { proxy_pass http://u; } location /upload { client_max_body_size 50m; proxy_pass http://u; }')).start()
        r, dt, sent = post(ng.port, int(sz), path=path); ng.stop(); time.sleep(0.2); row.append(r)
    rows.append(tuple(row))
table(rows, ['请求体大小', '/api(1m)', '/upload(50m)'])
rows = []
for expect in (False, True):
    ng = Nginx('v28d', conf()).start(); r, dt, sent = post(ng.port, 5_000_000, expect=expect); ng.stop()
    rows.append(('带 Expect: 100-continue' if expect else '不带 Expect', r, f'{sent / 1e6:.1f} MB', f'{dt:.2f} s'))
table(rows, ['client', '看到', 'client 实际发出的请求体', '耗时'])
R.close()
