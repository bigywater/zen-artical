import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import asyncio, struct
tee('v16'); reset()
print('故障注入分三层:TCP 层(在 client 和服务之间放一个代理,延迟、重置、黑洞、限速、切碎)、应用层(服务自己按概率返回错误或变慢)、进程层(kill -9 一个实例)。代理是我用 asyncio 写的一个很小的 TCP 转发器(没有用 Toxiproxy),故障模式可以随时切换')

class Proxy:
    def __init__(s, target):
        s.target, s.port, s.mode, s.arg = target, free_port(), 'pass', 0.0
        s.loop = asyncio.new_event_loop(); ready = threading.Event()
        def run():
            asyncio.set_event_loop(s.loop)
            async def start(): s.srv = await asyncio.start_server(s.handle, '127.0.0.1', s.port)
            s.loop.run_until_complete(start()); ready.set(); s.loop.run_forever()
        threading.Thread(target=run, daemon=True).start(); ready.wait()
    async def pipe(s, r, w, direction):
        try:
            while True:
                data = await (r.read(65536))
                if not data: break
                if s.mode == 'latency': await asyncio.sleep(s.arg)
                if s.mode == 'slicer':
                    for i in range(0, len(data), 1): w.write(data[i:i + 1]); await w.drain(); await asyncio.sleep(0.0005)
                    continue
                if s.mode == 'bandwidth' and direction == 'down':
                    for i in range(0, len(data), 1000): w.write(data[i:i + 1000]); await w.drain(); await asyncio.sleep(1000 / s.arg)
                    continue
                w.write(data); await w.drain()
        except Exception: pass
        finally:
            try: w.close()
            except Exception: pass
    async def handle(s, cr, cw):
        if s.mode == 'reset':
            sock = cw.get_extra_info('socket'); sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)); cw.close(); return
        if s.mode == 'blackhole':
            try: await cr.read(65536); await asyncio.sleep(30)
            except Exception: pass
            return
        try: ur, uw = await asyncio.open_connection('127.0.0.1', s.target)
        except Exception: cw.close(); return
        await asyncio.gather(s.pipe(cr, uw, 'up'), s.pipe(ur, cw, 'down'))
    def set(s, mode, arg=0.0): s.mode, s.arg = mode, arg

# ============ 一 ============
print('== 一:TCP 层的故障长什么样。后端是一个本进程里的 HTTP 服务(回 20 KB 的响应体),client 直接连代理;每种模式发 20 个请求(每个新建连接;“切碎”每个请求要十几秒,只发 3 个),client 的 socket 超时 2 s(注意:这是每次读操作的超时,不是总时长)。统计 client 看到的结果和延迟中位数')
body = b'x' * 20000
S1 = Svc(lambda h: h.reply(200, body)); P = Proxy(S1.port)
def one(timeout=2.0):
    t0 = time.perf_counter(); c = http.client.HTTPConnection('127.0.0.1', P.port, timeout=timeout)
    try:
        c.request('GET', '/'); r = c.getresponse(); d = r.read(); return ('200' if r.status == 200 and len(d) == len(body) else f'残缺响应({len(d)} 字节)'), time.perf_counter() - t0
    except socket.timeout: return '超时', time.perf_counter() - t0
    except ConnectionResetError: return '连接被重置', time.perf_counter() - t0
    except (http.client.RemoteDisconnected, http.client.IncompleteRead, BrokenPipeError): return '连接被对端关闭', time.perf_counter() - t0
    except Exception as e: return type(e).__name__, time.perf_counter() - t0
    finally: c.close()
rows = []
for name, mode, arg in (('直连(不经过代理)', None, 0), ('代理透传', 'pass', 0), ('延迟:每个数据块先等 100 ms', 'latency', 0.1), ('重置:一连上就发 RST', 'reset', 0), ('黑洞:收下请求但不转发、不回复', 'blackhole', 0), ('限速:响应 100 KB/s', 'bandwidth', 100000), ('切碎:每个字节单独发一次', 'slicer', 0)):
    if mode is None:
        res = []
        for _ in range(20):
            t0 = time.perf_counter(); st, b_, dt = rpc(S1.port, '/', 2.0, keepalive=False); res.append(('200' if st == 200 and len(b_) == len(body) else str(st), dt))
    else:
        P.set(mode, arg); res = [one() for _ in range(3 if mode == 'slicer' else 20)]
    cnt = collections.Counter(r[0] for r in res); rows.append((name, dict(cnt), f'{statistics.median([r[1] for r in res]) * 1000:.0f} ms'))
table(rows, ['模式', 'client 看到的结果', '延迟中位数'])
print('  限速和切碎都没有触发 2 s 的超时:socket 超时是“两次收到数据之间最多等多久”,只要对端还在一点一点地发,总耗时可以远远超过超时(切碎时一个请求要十几秒)')

# ============ 二 ============
print('== 二:应用层的故障注入。服务按概率注入:20% 的请求直接回 503;另 20% 的请求多等 300 ms;其余 60% 正常(5 ms)。client 对比两种:不重试(超时 1 s)/ 超时 100 ms + 最多共试 3 次。各 400 个请求(串行);服务端的随机数种子相同,但重试会多消耗随机数,所以两种策略看到的不是逐个请求完全相同的故障,比较的是统计结果')
def run2(policy):
    rng = random.Random(9); faults = []
    def app(h):
        r = rng.random()
        if r < 0.2: h.reply(503, b'x')
        elif r < 0.4: time.sleep(0.3); h.reply(200, b'x')
        else: time.sleep(0.005); h.reply(200, b'x')
    S = Svc(app); res = []; att = 0
    for i in range(400):
        t0 = time.perf_counter(); ok = False
        tries = 1 if policy == 'none' else 3
        for k in range(tries):
            att += 1; st, _, _ = rpc(S.port, '/', 1.0 if policy == 'none' else 0.1)
            if st == 200: ok = True; break
        res.append((ok, time.perf_counter() - t0))
    S.stop(); lat = [r[1] for r in res]
    return sum(1 for r in res if r[0]) / 400, pct(lat, 50), pct(lat, 99), att / 400
rows = []
for pol, name in (('none', '不重试,超时 1 s'), ('retry', '超时 100 ms,最多试 3 次')):
    ok, p50, p99, att = run2(pol); rows.append((name, f'{ok:.1%}', f'{p50 * 1000:.0f} ms', f'{p99 * 1000:.0f} ms', f'{att:.2f}'))
table(rows, ['client 策略', '最终成功', '延迟中位数', 'p99', '平均每个请求发了几次'])

# ============ 三 ============
print('== 三:混沌实验——随机 kill -9 实例。3 个副本(3 个独立的 Python 进程,各占一个端口);混沌线程每 1.5 秒随机 kill -9 一个副本,0.5 秒后在同一个端口重新拉起它(拉起要约 0.1 s);client 以 100 个/秒开环发请求,共 12 秒(1200 个请求)。四种 client:(a) 只连固定的一个副本 / (b) 轮询 3 个副本,不重试 / (c) 轮询 + 连接失败时换下一个副本重试(最多 3 次)/ (d) (c) 再加“摘除”:一个副本失败后 1 秒内不再选它')
REP = HERE / 'vtmp/v16/replica.py'
def start_rep(port): return subprocess.Popen([sys.executable, str(REP), str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def run3(policy):
    ports = [free_port() for _ in range(3)]; procs = [start_rep(p) for p in ports]
    for p in ports: wait_port(p, 10)
    stop = threading.Event(); kills = [0]; rng = random.Random(3)
    def chaos():
        time.sleep(1.0)
        while not stop.is_set():
            i = rng.randrange(3); procs[i].kill(); procs[i].wait(); kills[0] += 1; time.sleep(0.5)
            if stop.is_set(): break
            procs[i] = start_rep(ports[i]); time.sleep(1.0)
    ct = threading.Thread(target=chaos, daemon=True); ct.start()
    rr = [0]; lk = threading.Lock(); bad_until = [0.0] * 3; att = [0]
    def pick(exclude=()):
        with lk:
            for _ in range(3):
                i = rr[0] % 3; rr[0] += 1
                if i in exclude: continue
                if policy == 'eject' and time.perf_counter() < bad_until[i]: continue
                return i
            for i in range(3):
                if i not in exclude: return i
            return 0
    def req(k):
        t0 = time.perf_counter(); tried = set(); tries = 3 if policy in ('retry', 'eject') else 1
        for n in range(tries):
            i = 0 if policy == 'fixed' else pick(tried); tried.add(i)
            with lk: att[0] += 1
            st, _, _ = rpc(ports[i], '/', 0.5, keepalive=False)
            if st == 200: return True, time.perf_counter() - t0
            with lk: bad_until[i] = time.perf_counter() + 1.0
        return False, time.perf_counter() - t0
    out = openloop(req, 100, 12.0, workers=300); stop.set(); ct.join(5)
    for p in procs:
        try: p.kill(); p.wait()
        except Exception: pass
    res = [r for ts, r in out]; lat = [r[1] for r in res if r[0]]
    return sum(1 for r in res if not r[0]) / len(res), pct(lat, 50), pct(lat, 99), att[0] / len(res), kills[0]
rows = []
for pol, name in (('fixed', '(a) 只连固定的一个副本'), ('rr', '(b) 轮询,不重试'), ('retry', '(c) 轮询 + 失败换副本重试'), ('eject', '(d) (c) + 失败的副本 1 秒内不再选')):
    err, p50, p99, att, kills = run3(pol); rows.append((name, f'{err:.1%}', f'{p50 * 1000:.0f} ms', f'{p99 * 1000:.0f} ms', f'{att:.2f}', kills))
table(rows, ['client 策略', '请求失败率', '成功请求延迟中位数', 'p99', '平均每个请求发了几次', 'kill -9 的次数'])
print('  每个副本从被 kill 到重新拉起约有 0.6 s 不可用,约每 1.5 秒一轮;(a) 和 (b) 失败率的期望相同(都是一个副本不可用的时间占比,约 8 次 × 0.6 s ÷ 3 ÷ 12 s ≈ 13%),区别只是 (a) 取决于被杀的恰好是不是它;重试加换副本能把用户可见的失败压到接近 0,摘除让每个请求少白发几次')
