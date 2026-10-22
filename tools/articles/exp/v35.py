import sys, os, atexit; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [p for p in sys.path if os.path.basename(p) != 'exp']      # exp/ 里有 gRPC 系列的 h2.py,不去掉的话 import h2 会把它当成模块执行(还会覆盖 out/h2.txt)
from msl import *
tee('v35'); reset()
def netlab(*a): return sh('sudo -n /Library/netlab/netlab ' + ' '.join(str(x) for x in a))
atexit.register(lambda: netlab('off'))
print('client 到网关用 HTTP/2,网关到上游用 HTTP/1.1。nginx 1.31.6(listen 端口加 http2 on,明文 h2c,client 用 curl 的 --http2-prior-knowledge);curl 8.7.1。上游是我写的原始 TCP HTTP/1.1 服务,每个请求先 sleep 再回 1 个小响应,同时数在途的连接数。“并发”指同时在途的请求数')
state = {'cur': 0, 'peak': 0, 'conns': 0, 'delay': 0.1, 'size': 2}
slk = threading.Lock()
def backend(c):
    with slk: state['conns'] += 1; state['cur'] += 1; state['peak'] = max(state['peak'], state['cur'])
    c.settimeout(60)
    try:
        while True:
            d = b''
            while b'\r\n\r\n' not in d:
                x = c.recv(65536)
                if not x: return
                d += x
            time.sleep(state['delay']); body = b'x' * state['size']
            c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n' % len(body) + body)
    except Exception: pass
    finally:
        with slk: state['cur'] -= 1
        try: c.close()
        except Exception: pass
R = Raw(backend, backlog=512)
def conf(extra='', up='', port=None):
    return f'upstream u {{ server 127.0.0.1:{R.port} max_fails=0; {up} }} server {{ listen {{port}}; http2 on; {extra} location / {{ proxy_pass http://u; }} }}'
def curl(port, n, mode, parallel):
    """返回 (总耗时, 每个传输的 time_total 列表, 状态码计数)"""
    flags = ['--http2-prior-knowledge'] if mode == 'h2' else ['--http1.1']
    cmd = ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code} %{time_total}\n'] + flags + (['--parallel', '--parallel-immediate', '--parallel-max', str(parallel)] if parallel else []) + [f'http://127.0.0.1:{port}/?n=[1-{n}]']
    t0 = time.perf_counter(); r = subprocess.run(cmd, capture_output=True, text=True, timeout=300); wall = time.perf_counter() - t0
    rows = [l.split() for l in r.stdout.strip().splitlines() if l.strip()]
    return wall, [float(x[1]) for x in rows], collections.Counter(x[0] for x in rows)

# ============ 一 ============
print('== 一:并发能力。60 个请求,上游每个要 0.1 s。client 的三种方式:(a) HTTP/1.1,一条连接依次发(curl 复用同一条连接,串行);(b) HTTP/1.1,最多 6 条并行连接;(c) HTTP/2,一条连接上并行 60 个流。统计总耗时,以及上游同时在处理的请求峰值、nginx 一共向上游建立了多少条连接')
rows = []
for name, mode, par_ in (('(a) HTTP/1.1,1 条连接串行', 'h1', 0), ('(b) HTTP/1.1,6 条并行连接', 'h1', 6), ('(c) HTTP/2,1 条连接 60 个并行流', 'h2', 60)):
    state.update(cur=0, peak=0, conns=0); ng = Nginx('v35a', conf()).start(); wall, ts, cnt = curl(ng.port, 60, mode, par_); time.sleep(0.3); ng.stop()
    rows.append((name, f'{wall:.2f} s', dict(cnt), state['peak'], state['conns']))
table(rows, ['client 方式', '60 个请求总耗时', '状态码', '上游同时在途的请求峰值', 'nginx 向上游建立的连接数'])

# ============ 二 ============
print('== 二:http2_max_concurrent_streams。curl 遇到流数上限时会自己再开新连接,看不出上限的作用,所以这一节用 h2 库(4.3.0)写的最小 HTTP/2 client:只开 1 条连接,一次性提交 300 个请求,严格遵守服务端 SETTINGS 里的 MAX_CONCURRENT_STREAMS(超过的请求等已有的流结束再发)。上游每个请求 0.1 s。nginx 的 http2_max_concurrent_streams 分别是 32 / 128(默认)/ 512。统计总耗时、client 看到的服务端上限、上游同时在途的请求峰值和 nginx 向上游建立的连接数')
import h2.connection, h2.config, h2.events
def h2_burst(port, n):
    s = socket.create_connection(('127.0.0.1', port)); s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    conn = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True, header_encoding='utf-8')); conn.initiate_connection(); s.sendall(conn.data_to_send())
    pending = list(range(n)); done = 0; active = set(); limit = None; t0 = time.perf_counter(); status = collections.Counter()
    def send_more():
        nonlocal limit
        lim = conn.remote_settings.max_concurrent_streams; limit = lim
        while pending and len(active) < lim:
            i = pending.pop(0); sid = conn.get_next_available_stream_id(); conn.send_headers(sid, [(':method', 'GET'), (':path', f'/?n={i}'), (':scheme', 'http'), (':authority', 'x')], end_stream=True); active.add(sid)
        s.sendall(conn.data_to_send())
    s.settimeout(30)
    while done < n:
        data = s.recv(65536)
        if not data: break
        for ev in conn.receive_data(data):
            if isinstance(ev, h2.events.RemoteSettingsChanged) or isinstance(ev, h2.events.SettingsAcknowledged): pass
            if isinstance(ev, h2.events.ResponseReceived): status[dict(ev.headers).get(':status')] += 1
            if isinstance(ev, h2.events.StreamEnded): active.discard(ev.stream_id); done += 1
        s.sendall(conn.data_to_send()); send_more()
    wall = time.perf_counter() - t0; s.close(); return wall, limit, status
rows = []
for ms in (32, 128, 512):
    state.update(cur=0, peak=0, conns=0, delay=0.1, size=2); ng = Nginx('v35b', conf(f'http2_max_concurrent_streams {ms};')).start(); wall, lim, st = h2_burst(ng.port, 300); time.sleep(0.3); ng.stop()
    rows.append((ms, lim, f'{wall:.2f} s', dict(st), state['peak'], state['conns']))
table(rows, ['http2_max_concurrent_streams', 'client 看到的上限', '300 个请求总耗时', '状态码', '上游同时在途峰值', 'nginx 向上游建立的连接数'])
print('  HTTP/2 的并发流数受服务端公布的上限约束:超过的流要等已有的流结束才能开始,所以总耗时大约是 ⌈300 ÷ 上限⌉ 个 0.1 s;上游是 HTTP/1.1,每个并行的流占一条上游连接,上游的峰值并发等于同时在途的流数(受上限约束)')

# ============ 三 ============
print('== 三:TCP 丢包下的队头阻塞。client 到 nginx 这一段在 lo0 上加 3% 丢包、每个方向 2 ms 延迟(dummynet,只作用于端口 9400–9499;nginx 监听在这个范围里)。100 个请求,每个响应 100 KB(上游先 sleep 10 ms),三种 client:HTTP/1.1 一条连接串行 / HTTP/1.1 6 条并行连接 / HTTP/2 一条连接 100 个并行流。每种做 3 轮,取总耗时的中位数,同时报告各请求完成时间的 p50 和 p99(从 curl 的 time_total 取)')
state.update(delay=0.01, size=100_000)
def lab_port():
    for p in range(9420, 9499):
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1', p)) != 0: return p
    raise RuntimeError('没有空闲的 9400-9499 端口')
rows = []
for loss in (0, 3):
    for name, mode, par_ in (('HTTP/1.1,1 条连接串行', 'h1', 0), ('HTTP/1.1,6 条并行连接', 'h1', 6), ('HTTP/2,1 条连接', 'h2', 100)):
        walls = []; p50s = []; p99s = []
        for rnd in range(3):
            lp = lab_port(); ng = Nginx('v35c', conf(), port=lp).start()
            if loss: netlab('on', loss, 2, 0)
            try: wall, ts, cnt = curl(lp, 100, mode, par_)
            finally:
                if loss: netlab('off')
                ng.stop()
            walls.append(wall); p50s.append(pct(ts, 50)); p99s.append(pct(ts, 99))
        rows.append((f'{loss}%', name, f'{statistics.median(walls):.2f} s', f'{min(walls):.2f} ~ {max(walls):.2f} s', f'{statistics.median(p50s):.2f} s', f'{statistics.median(p99s):.2f} s'))
table(rows, ['丢包率', 'client 方式', '100 个请求总耗时(中位数)', '3 轮范围', '请求完成时间 p50', 'p99'])
base = {}
for r in rows:
    if r[0] == '0%': base[r[1]] = float(r[2].split()[0])
print('  丢包后总耗时相对无丢包时的倍数:' + ';'.join(f'{r[1]} {float(r[2].split()[0]) / base[r[1]]:.1f} 倍' for r in rows if r[0] == '3%') + '。HTTP/2 的所有流共用一条 TCP 连接,一个包丢了,这条连接上所有流的后续数据都要等重传(TCP 层的队头阻塞);HTTP/1.1 的多条连接各自独立。看倍数而不是绝对值:这个实验里 HTTP/2 在有丢包时的绝对耗时仍然最短,但它相对无丢包时变慢得更多')
netlab('off')
