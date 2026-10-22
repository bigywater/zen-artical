import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import queue
tee('v8'); reset()
def nerr(): print(f'  (连接类错误 {ERRORS["error"]} 次;不是超时,应为 0)')
print('舱壁(bulkhead):给每个依赖单独划定资源,一个依赖慢了不能把别的依赖饿死。下面的“服务”是一个 20 个工作线程的小池子,处理两类请求:A 类调用快的依赖 D1(10 ms),B 类调用 D2;D2 在 2 秒之后每个请求挂住 2 秒才返回。client 以 100 个/秒的开环速率发请求(70% 是 A、30% 是 B),共 8 秒,client 等 1 秒就放弃')

# ============ 一 ============
print('== 一:共享线程池 vs 舱壁。三种做法:共享 = 20 个线程一个队列;信号量舱壁 = 仍然 20 个线程一个队列,但 B 类调用 D2 之前要先拿一个信号量(最多 5 个同时在调 D2),拿不到立刻失败;独立线程池 = A 类 14 个线程、B 类 6 个线程各有各的队列(B 的队列最多排 10 个,满了立刻失败)。只统计 D2 变慢之后(第 3 到 8 秒)到达的请求')
def run1(mode, seed=3):
    t0 = [0.0]
    def d1(h): time.sleep(0.01); h.reply(200, b'x')
    def d2(h):
        time.sleep(2.0 if time.perf_counter() - t0[0] >= 2.0 else 0.02); h.reply(200, b'x')
    D1 = Svc(d1); D2 = Svc(d2)
    qa = queue.Queue(); qb = queue.Queue() if mode == 'pool' else qa; sem = threading.Semaphore(5); stop = threading.Event()
    def do(kind):
        if kind == 'A': st, _, _ = rpc(D1.port, '/', 3.0); return 200 if st == 200 else 500
        if mode == 'sem':
            if not sem.acquire(blocking=False): return 503
            try: st, _, _ = rpc(D2.port, '/', 3.0)
            finally: sem.release()
        else: st, _, _ = rpc(D2.port, '/', 3.0)
        return 200 if st == 200 else 500
    def worker(q):
        while not stop.is_set():
            try: kind, box = q.get(timeout=0.1)
            except queue.Empty: continue
            box['code'] = do(kind); box['done'] = time.perf_counter(); box['ev'].set()
    nA, nB = (14, 6) if mode == 'pool' else (20, 0)
    ths = [threading.Thread(target=worker, args=(qa,), daemon=True) for _ in range(nA)] + ([threading.Thread(target=worker, args=(qb,), daemon=True) for _ in range(nB)] if mode == 'pool' else [])
    [t.start() for t in ths]; rng = random.Random(seed); kinds = ['A' if rng.random() < 0.7 else 'B' for _ in range(800)]
    def submit(i):
        kind = kinds[i]; box = {'ev': threading.Event(), 'code': None}; t1 = time.perf_counter()
        if mode == 'pool' and kind == 'B' and qb.qsize() >= 10: return kind, 503, 0.0
        (qb if (mode == 'pool' and kind == 'B') else qa).put((kind, box))
        ok = box['ev'].wait(1.0)
        return kind, (box['code'] if ok else 'timeout'), time.perf_counter() - t1
    t0[0] = time.perf_counter(); res = openloop(submit, 100, 8, workers=700); stop.set(); D1.stop(); D2.stop()
    late = [(ts, r) for ts, r in res if ts >= 3.0]; out = {}
    for k in 'AB':
        rs = [r for ts, r in late if r[0] == k]; n = len(rs)
        ok = [r[2] for r in rs if r[1] == 200]
        out[k] = (n, len(ok) / n if n else 0, pct(ok, 50) if ok else float('nan'), pct(ok, 99) if ok else float('nan'), sum(1 for r in rs if r[1] == 503), sum(1 for r in rs if r[1] == 'timeout'))
    return out
rows = []
for name, mode in (('共享线程池', 'shared'), ('信号量舱壁(D2 ≤ 5 个)', 'sem'), ('独立线程池(14 + 6)', 'pool')):
    o = run1(mode); a, b = o['A'], o['B']
    rows.append((name, f'{a[0]}', f'{a[1]:.1%}', (f'{a[2] * 1000:.0f} ms' if a[2] == a[2] else '-'), (f'{a[3] * 1000:.0f} ms' if a[3] == a[3] else '-'), f'{b[0]}', f'{b[1]:.1%}', b[4], b[5]))
table(rows, ['做法', 'A 类请求数', 'A 类 1 s 内成功', 'A 类成功的中位数', 'A 类 p99', 'B 类请求数', 'B 类 1 s 内成功', 'B 类被立刻拒绝', 'B 类超时'])
nerr()

# ============ 二 ============
print('== 二:Java 线程池满了怎么办。ThreadPoolExecutor(核心 2 个线程、最多 4 个、队列容量 4),主线程一次提交 20 个任务,每个任务睡 200 ms。四种内置的拒绝策略:能容纳的是 4 个线程 + 4 个排队 = 8 个,多出来的 12 个怎么处理由策略决定')
JD = TT / 'v8j'; JD.mkdir(exist_ok=True)
(JD / 'Reject.java').write_text('''import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
public class Reject {
    public static void main(String[] a) throws Exception {
        Map<String, RejectedExecutionHandler> ps = new LinkedHashMap<>();
        ps.put("AbortPolicy", new ThreadPoolExecutor.AbortPolicy());
        ps.put("CallerRunsPolicy", new ThreadPoolExecutor.CallerRunsPolicy());
        ps.put("DiscardPolicy", new ThreadPoolExecutor.DiscardPolicy());
        ps.put("DiscardOldestPolicy", new ThreadPoolExecutor.DiscardOldestPolicy());
        for (var e : ps.entrySet()) {
            ThreadPoolExecutor ex = new ThreadPoolExecutor(2, 4, 60, TimeUnit.SECONDS, new ArrayBlockingQueue<>(4), e.getValue());
            List<Integer> done = Collections.synchronizedList(new ArrayList<>()); AtomicInteger onMain = new AtomicInteger();
            int rejected = 0; long blocked = 0; long t0 = System.nanoTime();
            for (int i = 0; i < 20; i++) {
                final int id = i; long s = System.nanoTime();
                try {
                    ex.execute(() -> { try { Thread.sleep(200); } catch (InterruptedException x) {} done.add(id); if (Thread.currentThread().getName().equals("main")) onMain.incrementAndGet(); });
                } catch (RejectedExecutionException x) { rejected++; }
                blocked += System.nanoTime() - s;
            }
            long submitDone = System.nanoTime() - t0;
            ex.shutdown(); ex.awaitTermination(30, TimeUnit.SECONDS);
            List<Integer> d = new ArrayList<>(done); Collections.sort(d);
            System.out.println(e.getKey() + "|" + d.size() + "|" + rejected + "|" + onMain.get() + "|" + (submitDone / 1000000) + "|" + d);
        }
    }
}
''')
out = sh(f'cd {JD} && java Reject.java', timeout=120)
rows = []
for l in out.splitlines():
    if '|' not in l: continue
    n, ex_, rej, onmain, sub, ids = l.split('|'); rows.append((n, ex_, rej, 20 - int(ex_) - int(rej), onmain, f'{sub} ms', ids))
table(rows, ['策略', '执行了的任务', '抛出 RejectedExecutionException', '悄悄丢掉的', '其中在提交者(main)线程里执行', '提交完 20 个任务用了', '执行了的任务编号'])
print('  AbortPolicy 把拒绝变成异常交给调用方处理;CallerRunsPolicy 让提交者自己执行,所以提交会被拖慢(这是一种背压),但提交者线程也被占住;DiscardPolicy 悄悄丢最新的;DiscardOldestPolicy 悄悄丢队列里最老的(编号靠前的排队任务没有执行)')

# ============ 三 ============
print('== 三:网关上的连接被慢上游占满。nginx 1.31.6,worker_connections = 64(一个代理请求要占 client 一条 + 上游一条,共 2 条),一个路由 /slow 的上游每个请求挂 3 秒,另一个路由 /fast 的上游马上回。40 个客户端线程不断请求 /slow(失败就 50 ms 后重来);同时另一个探测线程每 100 ms 请求一次 /fast,共 5 秒。比较:不做隔离 / 给 /slow 加 limit_conn(同时最多 6 个,多的立刻回 503)')
def run3(isolate):
    ERRORS.clear()
    def slow(h): time.sleep(3.0); h.reply(200, b'x')
    def fast(h): h.reply(200, b'x')
    SL = Svc(slow, backlog=256); FA = Svc(fast)
    lim = 'limit_conn_zone "slow" zone=slowz:1m;' if isolate else ''
    lc = 'limit_conn slowz 6; limit_conn_status 503;' if isolate else ''
    ng = Nginx('v8n', f"""upstream slow {{ server 127.0.0.1:{SL.port}; }} upstream fast {{ server 127.0.0.1:{FA.port}; }} {lim}
  server {{ listen {{port}}; location /fast {{ proxy_pass http://fast; }} location /slow {{ {lc} proxy_pass http://slow; }} }}""", extra_main='').start()
    # worker_connections 在 events 块里:改写配置
    txt = (ng.d / 'nginx.conf').read_text().replace('worker_connections 1024', 'worker_connections 64'); (ng.d / 'nginx.conf').write_text(txt); ng.stop(); time.sleep(0.3)
    ng.p = None; ng.start()
    stop = threading.Event(); cnt = collections.Counter(); lk = threading.Lock()
    def slow_cl():
        while not stop.is_set():
            st, _, dt = rpc(ng.port, '/slow', 1.0, keepalive=False)
            with lk: cnt['slow_' + str(st)] += 1
            time.sleep(0.05)
    ths = [threading.Thread(target=slow_cl, daemon=True) for _ in range(40)]; [t.start() for t in ths]; time.sleep(0.5)
    lat = []; res = collections.Counter(); t1 = time.perf_counter()
    while time.perf_counter() - t1 < 5:
        st, _, dt = rpc(ng.port, '/fast', 1.0, keepalive=False); res[st] += 1
        if st == 200: lat.append(dt)
        time.sleep(0.1)
    stop.set(); err = (ng.d / 'err.log').read_text(); ng.stop(); SL.stop(); FA.stop()
    n_err = err.count('worker_connections are not enough')
    return res, lat, cnt, n_err
rows = []
for name, iso in (('不做隔离', False), ('/slow 加 limit_conn 6', True)):
    res, lat, cnt, n_err = run3(iso); tot = sum(res.values())
    rows.append((name, tot, f"{res.get(200, 0) / tot:.0%}", f"{pct(lat, 50) * 1000:.1f} ms" if lat else '-', f"{pct(lat, 99) * 1000:.1f} ms" if lat else '-', {k: v for k, v in res.items() if k != 200}, cnt.get('slow_503', 0), n_err))
table(rows, ['配置', '/fast 探测次数', '/fast 成功', '成功的中位数', 'p99', '/fast 的失败类型(error = 连接被拒或重置)', '/slow 被立刻 503 的次数', 'error.log 里 worker_connections are not enough 的行数'])
print('  limit_conn 的计数键用的是常量字符串 "slow":最初我用了 $server_name,这个 server 块没有写 server_name,变量值是空串,而 nginx 不统计键为空的请求,结果 limit_conn 悄悄没有任何效果(20 个并发请求全部 200)')
