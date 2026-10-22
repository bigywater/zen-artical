import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v24'); reset()
print('proxy_buffering 决定 nginx 要不要先把上游的响应收下来(放进内存缓冲区,放不下写临时文件),再按 client 的速度发给 client。默认是 on。上游是我写的原始 TCP 服务,nginx 1.31.6')
def chunked_backend(n_chunks, chunk_bytes, interval, extra_hdr=b''):
    def h(c):
        read_req(c)
        c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\n' + extra_hdr + b'\r\n')
        for i in range(n_chunks):
            body = (b'%04d' % i) + b'x' * (chunk_bytes - 4); c.sendall(b'%x\r\n' % len(body) + body + b'\r\n'); time.sleep(interval)
        c.sendall(b'0\r\n\r\n'); c.close()
    return Raw(h)
def stream_times(port, gzip=False):
    """原始 socket 读 chunked 响应,记录每次 recv 的时刻和累计字节数;返回 (首次收到响应体数据的时刻, 收到一半字节的时刻, 全部收完的时刻, recv 次数)"""
    s = socket.create_connection(('127.0.0.1', port)); s.settimeout(30); t0 = time.perf_counter()
    s.sendall(b'GET / HTTP/1.1\r\nHost: x\r\n' + (b'Accept-Encoding: gzip\r\n' if gzip else b'') + b'\r\n')
    buf = b''; ev = []
    while True:
        d = s.recv(65536)
        if not d: break
        buf += d; ev.append((time.perf_counter() - t0, len(buf)))
        if buf.endswith(b'0\r\n\r\n'): break
    s.close(); total = ev[-1][1]; hdr = buf.index(b'\r\n\r\n') + 4
    first = next(t for t, n in ev if n > hdr + 10); half = next(t for t, n in ev if n >= hdr + (total - hdr) / 2)
    return first, half, ev[-1][0], len(ev)

# ============ 一 ============
print('== 一:流式响应(比如 SSE)。上游每 0.2 s 发一个数据块,共 10 个,总共约 1.8 s。看 client 什么时候收到响应体的第一批数据、收到一半字节、收完。数据块 100 字节 / 16 KB 两种大小;配置:proxy_buffering on(默认)/ off / 上游发 X-Accel-Buffering: no(on 的配置下)/ 打开 gzip(对 text/event-stream 压缩,client 发 Accept-Encoding: gzip)')
rows = []
for size in (100, 16384):
    for name, extra, up_hdr, gz in (('buffering on(默认)', '', b'', False), ('buffering off', 'proxy_buffering off;', b'', False), ('on + 上游发 X-Accel-Buffering: no', '', b'X-Accel-Buffering: no\r\n', False), ('on + gzip on(压缩 text/event-stream)', 'gzip on; gzip_types text/event-stream;', b'', True)):
        R = chunked_backend(10, size, 0.2, up_hdr); ng = Nginx('v24a', f'upstream u {{ server 127.0.0.1:{R.port}; }} server {{ listen {{port}}; location / {{ proxy_pass http://u; {extra} }} }}').start()
        f, h, c, n = stream_times(ng.port, gz); ng.stop(); R.close()
        rows.append((f'{size} 字节', name, f'{f:.2f} s', f'{h:.2f} s', f'{c:.2f} s', n))
table(rows, ['数据块大小', '配置', '收到第一批响应体', '收到一半字节', '收完', 'recv 次数'])

# ============ 二 ============
print('== 二:慢 client。上游要发 40 MB,用 64 KB 一个块往 socket 里写;client 很慢,只读约 5 MB/s(每 10 ms 读 50 KB),所以 client 需要约 8 s 才能收完。统计上游把 40 MB 全部写完用了多久(= 这条上游连接被占用的时间),以及 nginx 的 worker 进程打开的临时文件(proxy_temp_path 下;nginx 打开后立刻 unlink 目录项,所以用 lsof 看大小)最大有多大。比较 proxy_buffering on(默认,proxy_max_temp_file_size 默认 1024m)/ on + proxy_max_temp_file_size 0(不写临时文件)/ off')
def big_backend(done):
    def h(c):
        read_req(c); body = b'x' * 40_000_000
        c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n' % len(body)); t0 = time.perf_counter()
        for i in range(0, len(body), 65536): c.sendall(body[i:i + 65536])
        done.append(time.perf_counter() - t0); c.close()
    return Raw(h)
def slow_client(port):
    s = socket.create_connection(('127.0.0.1', port)); s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536); s.sendall(b'GET / HTTP/1.1\r\nHost: x\r\n\r\n'); t0 = time.perf_counter(); got = 0
    while got < 40_000_000:
        time.sleep(0.01); d = s.recv(50000)
        if not d: break
        got += len(d)
    s.close(); return time.perf_counter() - t0
rows = []
for name, extra in (('buffering on(默认)', ''), ('on + proxy_max_temp_file_size 0', 'proxy_max_temp_file_size 0;'), ('buffering off', 'proxy_buffering off;')):
    done = []; R = big_backend(done); ng = Nginx('v24b', f'upstream u {{ server 127.0.0.1:{R.port}; }} server {{ listen {{port}}; location / {{ proxy_pass http://u; {extra} }} }}').start()
    mx = [0]; stop = threading.Event()
    def watch():
        # nginx 打开临时文件后立刻 unlink 目录项,目录里看不到;用 lsof 看 worker 进程打开的、路径在 proxy_temp_path 下的文件大小
        pid = (ng.d / 'nginx.pid').read_text().strip()
        while not stop.is_set():
            try:
                kids = subprocess.run(['pgrep', '-P', pid], capture_output=True, text=True).stdout.split()
                out = subprocess.run(['lsof', '-nP', '-p', ','.join(kids)], capture_output=True, text=True).stdout
                for l in out.splitlines():
                    if '/pt/' in l:
                        p = l.split(); mx[0] = max(mx[0], int(p[6]) if p[6].isdigit() else 0)
            except Exception: pass
            time.sleep(0.2)
    th = threading.Thread(target=watch, daemon=True); th.start(); tc = slow_client(ng.port); stop.set(); th.join(2); time.sleep(0.3)
    rows.append((name, f'{done[0]:.1f} s' if done else '没写完', f'{tc:.1f} s', f'{mx[0] / 1e6:.1f} MB')); ng.stop(); R.close()
table(rows, ['配置', '上游写完 40 MB 用了', 'client 收完用了', 'worker 打开的临时文件最大'])
print('  缓冲打开且允许写临时文件时,看“上游写完”那一列:nginx 把响应整个收下来(放进 proxy_temp_path 下的临时文件,最后一列是它的大小;nginx 打开后立刻 unlink 目录项,目录里看不到,所以用 lsof 量),上游连接早早释放,client 再慢也只占 nginx 的磁盘。不允许写临时文件或关掉缓冲时,上游被拖到接近 client 的速度(上游写完的时间接近 client 收完的时间,差的部分是内核 socket 缓冲吸收的)')
