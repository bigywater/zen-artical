import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v23'); reset()
print('nginx 到上游的长连接(keepalive)。后端是我写的原始 TCP HTTP/1.1 服务(支持 keep-alive,能数它 accept 了多少条连接,能设置空闲多久就关连接)。“复用率”= 1 − 后端 accept 的连接数 ÷ 请求数。nginx 1.31.6,单 worker 进程')
RESP = b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok'
RESP_CLOSE = b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok'
HEADS = []
def make_backend(idle=60.0):
    """规规矩矩的 HTTP/1.1 服务:请求是 HTTP/1.0 或带 Connection: close 时,回完就关连接并在响应里写 Connection: close"""
    R = None
    def h(c):
        c.settimeout(idle)
        try:
            while True:
                d = b''
                while b'\r\n\r\n' not in d:
                    x = c.recv(65536)
                    if not x: return
                    d += x
                head = d.split(b'\r\n\r\n')[0].decode(); HEADS.append(head)
                closing = 'HTTP/1.0' in head.split('\r\n')[0] or 'connection: close' in head.lower()
                if closing: c.sendall(RESP_CLOSE); return
                c.sendall(RESP)
        except Exception: pass
        finally:
            try: c.close()
            except Exception: pass
    R = Raw(h); return R
def conf(R, up_extra='', loc_extra=''):
    return f'upstream u {{ server 127.0.0.1:{R.port} max_fails=0; {up_extra} }} server {{ listen {{port}}; location / {{ proxy_pass http://u; {loc_extra} }} }}'
def drive(ng, n, conc):
    def one(i): return rpc(ng.port, '/', 5.0)[0]
    return collections.Counter(par(one, list(range(n)), conc))

# ============ 一 ============
print('== 一:不同写法下 nginx 到上游的连接复用。后端按规矩办事:请求是 HTTP/1.0 或带 Connection: close 时,回完就关连接。顺序发 1000 个请求(一次一个),统计后端 accept 的连接数,以及 nginx 发来的请求头(请求行 + 是否有 Connection 头)。四种配置:(a) 只有 proxy_pass;(b) proxy_http_version 1.0;(c) proxy_set_header Connection close;(d) upstream 里加 keepalive 16 + proxy_http_version 1.1 + Connection ""(教科书写法)')
rows = []
for name, up, loc in (('(a) 只有 proxy_pass', '', ''), ('(b) proxy_http_version 1.0', '', 'proxy_http_version 1.0;'), ('(c) proxy_set_header Connection close', '', 'proxy_set_header Connection close;'), ('(d) keepalive 16 + HTTP/1.1 + Connection ""', 'keepalive 16;', 'proxy_http_version 1.1; proxy_set_header Connection "";')):
    HEADS.clear(); R = make_backend(); ng = Nginx('v23a', conf(R, up, loc)).start(); cnt = drive(ng, 1000, 1); time.sleep(0.3); n = len(R.conns); ng.stop(); R.close()
    h0 = HEADS[0].split('\r\n'); conn_h = [x for x in h0 if x.lower().startswith('connection')]
    rows.append((name, dict(cnt), n, f'{1 - n / 1000:.1%}', h0[0] + (' + ' + conn_h[0] if conn_h else ' (没有 Connection 头)')))
table(rows, ['配置', '状态码', '后端 accept 的连接数', '复用率', 'nginx 发给后端的请求行与 Connection 头'])
print('  nginx 1.31.6 里,什么都不配时就已经是 HTTP/1.1 且复用到上游的连接(教科书里“必须同时配 HTTP/1.1、Connection 空串和 keepalive”是旧版本的默认值,我没有测旧版本);只有显式退回 HTTP/1.0 或发 Connection: close 才会每个请求新建连接')

# ============ 二 ============
print('== 二:keepalive 池的大小和并发的关系。upstream 里 keepalive N(每个 worker 进程最多缓存 N 条空闲连接);并发 C 个 client 线程共发 3000 个请求。统计后端 accept 的连接数(复用率 = 1 − 连接数 ÷ 3000)。另外 keepalive_requests 默认 1000(一条连接最多处理这么多个请求),这里再加一行把它设成 100')
rows = []
for n_k in (2, 8, 32):
    row = [f'keepalive {n_k}']
    for conc in (1, 8, 32):
        R = make_backend(); ng = Nginx('v23b', conf(R, f'keepalive {n_k};', 'proxy_http_version 1.1; proxy_set_header Connection "";')).start(); drive(ng, 3000, conc); time.sleep(0.3); n = len(R.conns); ng.stop(); R.close()
        row.append(f'{n} 条({1 - n / 3000:.1%})')
    rows.append(tuple(row))
R = make_backend(); ng = Nginx('v23b', conf(R, 'keepalive 32; keepalive_requests 100;', 'proxy_http_version 1.1; proxy_set_header Connection "";')).start(); drive(ng, 3000, 1); time.sleep(0.3); n = len(R.conns); ng.stop(); R.close()
rows.append(('keepalive 32 + keepalive_requests 100', f'{n} 条({1 - n / 3000:.1%})', '-', '-'))
table(rows, ['配置', '并发 1', '并发 8', '并发 32'])
print('  keepalive N 只缓存“空闲”连接:并发比 N 大时,多出来的请求处理完之后连接放不进池子(池子满了)就会被关掉,下一个请求又得新建;并发不超过 N 时,连接几乎全部复用')

# ============ 三 ============
print('== 三:后端比 nginx 先关空闲连接。后端在连接空闲 0.3 s 之后关闭它;nginx 的 keepalive_timeout 是默认的 60 s。client 顺序发请求,请求之间停顿 gap(秒)。单个 upstream server(没有别的上游可换),GET。每个 gap 发 60 个请求。统计 client 看到的状态码和 error.log 里 “upstream prematurely closed connection” 的次数。gap 要么远小于 0.3 s、要么远大于 0.3 s、要么正好在 0.3 s 附近(0.27 到 0.33 之间均匀随机)')
rows = []
for name, gapf in (('0.1 s', lambda: 0.1), ('0.6 s', lambda: 0.6), ('0.27 到 0.33 s 随机', lambda: random.uniform(0.27, 0.33))):
    R = make_backend(idle=0.3); ng = Nginx('v23c', conf(R, 'keepalive 16;', '')).start(); cnt = collections.Counter(); random.seed(5)
    for i in range(60):
        cnt[rpc(ng.port, '/', 5.0, keepalive=False)[0]] += 1; time.sleep(gapf())
    err = (ng.d / 'err.log').read_text(); pm = err.count('prematurely closed'); n = len(R.conns); rows.append((name, dict(cnt), pm, n)); ng.stop(); R.close()
table(rows, ['请求间隔 gap', 'client 看到的状态码(60 个)', 'error.log: upstream prematurely closed connection 次数', '后端 accept 的连接数'])
print('  三种 gap 下的 60 个请求都没有失败,包括 gap 在 0.3 s 附近的那一组(最后一列的连接数介于 1 和 60 之间,说明有的连接被复用、有的在被后端关掉之后重建了)。人们常说的“后端先关了空闲连接,nginx 还往里发请求,于是出现偶发 502”,在这个实验里没有复现;它需要请求恰好和对端的关闭同时发生,我没有去构造这个窗口,所以这里不下结论')
