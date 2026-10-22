import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import queue
tee('v13'); reset()
print('服务模型:4 个工作线程,每个请求 sleep 20 ms(理论容量 200 个/秒,实测约 160 个/秒:sleep 与线程调度本身还要花时间),请求先进一个队列;client 开环地发请求并最多等 500 ms(截止时间),超时就放弃(但已经在队列里或正在处理的请求,服务端并不知道,除非服务端自己检查截止时间)。“成功”= 在 500 ms 内拿到 200。这一篇的服务端和 client 都在本进程里,请求是 Python 对象,没有经过网络')

class Srv:
    def __init__(s, policy, qmax=50, check_deadline=False, workers=4, svc=0.02):
        s.policy, s.qmax, s.chk, s.svc = policy, qmax, check_deadline, svc; s.q = collections.deque(); s.cv = threading.Condition(); s.stop = False; s.rng = random.Random(1)
        s.stats = collections.Counter(); s.ths = [threading.Thread(target=s.work, daemon=True) for _ in range(workers)]; [t.start() for t in s.ths]
    def finish(s, r, code): r['code'] = code; r['ev'].set()
    def submit(s, r):
        with s.cv:
            if s.policy != 'unbounded' and len(s.q) >= s.qmax:
                pol = s.policy
                if pol == 'tail': s.finish(r, 503); s.stats['shed'] += 1; return
                if pol in ('head', 'lifo'): old = s.q.popleft(); s.finish(old, 503); s.stats['shed'] += 1
                elif pol == 'random': i = s.rng.randrange(len(s.q)); old = s.q[i]; del s.q[i]; s.finish(old, 503); s.stats['shed'] += 1
                elif pol == 'prio':
                    low = [i for i, x in enumerate(s.q) if not x['hi']]
                    if r['hi'] and low: i = low[0]; old = s.q[i]; del s.q[i]; s.finish(old, 503); s.stats['shed'] += 1
                    else: s.finish(r, 503); s.stats['shed'] += 1; return
            s.q.append(r); s.cv.notify()
    def work(s):
        while True:
            with s.cv:
                while not s.q and not s.stop: s.cv.wait(0.1)
                if s.stop: return
                r = s.q.pop() if s.policy == 'lifo' else s.q.popleft()
            if s.chk and time.perf_counter() > r['deadline'] - s.svc: s.finish(r, 504); s.stats['expired'] += 1; continue
            time.sleep(s.svc); s.stats['processed'] += 1
            if time.perf_counter() > r['deadline']: s.stats['wasted'] += 1
            s.finish(r, 200)

def drive(srv, rate, dur=6.0, hi_frac=0.2, seed=5):
    rng = random.Random(seed); his = [rng.random() < hi_frac for _ in range(int(rate * dur) + 5)]
    def one(i):
        t0 = time.perf_counter(); r = {'ev': threading.Event(), 'code': None, 'hi': his[i], 'deadline': t0 + 0.5}
        srv.submit(r); ok = r['ev'].wait(0.5); dt = time.perf_counter() - t0
        return ('ok' if ok and r['code'] == 200 else 'rej' if ok and r['code'] == 503 else 'exp' if ok else 'timeout'), dt, r['hi']
    res = openloop(one, rate, dur, workers=800); return [r for ts, r in res if ts >= 1.0]
def stat(res):
    n = len(res); ok = [r for r in res if r[0] == 'ok']; dts = [r[1] for r in ok]
    hi = [r for r in res if r[2]]; lo = [r for r in res if not r[2]]
    return n, len(ok), (pct(dts, 50) if dts else float('nan')), (pct(dts, 99) if dts else float('nan')), sum(1 for r in hi if r[0] == 'ok') / max(1, len(hi)), sum(1 for r in lo if r[0] == 'ok') / max(1, len(lo))
fm = lambda x: '-' if x != x else f'{x * 1000:.0f} ms'

# ============ 一 ============
print('== 一:过载时的吞吐曲线。到达速率从 100 到 800 个/秒(理论容量 200/s,实测约 160/s),每个速率跑 6 秒,统计第 1 秒之后到达的请求。两种服务端:无保护 = 无界 FIFO 队列;有保护 = 队列最多 50 个,队满拒绝新请求,出队时发现已经过了截止时间(或剩余不够处理一次)就丢掉。“成功速率”= 500 ms 内成功的请求数 ÷ 统计的秒数(5 秒)')
rows = []
for rate in (100, 200, 300, 400, 600, 800):
    row = [f'{rate}/s']
    for pol, kw in (('unbounded', {}), ('tail', {'check_deadline': True})):
        srv = Srv(pol, **kw); res = drive(srv, rate); srv.stop = True
        n, ok, p50, p99, _, _ = stat(res); row += [f'{ok / 5:.0f}/s', fm(p99), srv.stats['wasted'] if pol == 'unbounded' else srv.stats['expired'] + srv.stats['shed']]
    rows.append(tuple(row))
table(rows, ['到达速率', '无保护:成功速率', 'p99', '白干(处理完时已超时)', '有保护:成功速率', 'p99', '丢掉的(拒绝 + 过期)'])

# ============ 二 ============
print('== 二:队满时丢哪一个。到达 400 个/秒(约为实测容量的 2.5 倍),其中 20% 是高优先级(比如结账),80% 是低优先级;队列容量 50。六种做法:无界 FIFO(不丢);队满拒绝新请求(tail-drop);队满丢最老的(head-drop);LIFO(后进先出处理,队满丢最老的);队满随机丢一个;按优先级丢(队满时丢最老的低优先级,高优先级才能挤掉低优先级)。这一节的服务端都不检查截止时间')
rows = []
for name, pol in (('无界 FIFO', 'unbounded'), ('tail-drop', 'tail'), ('head-drop', 'head'), ('LIFO + 丢最老的', 'lifo'), ('随机丢', 'random'), ('按优先级丢', 'prio')):
    srv = Srv(pol); res = drive(srv, 400); srv.stop = True; n, ok, p50, p99, hiok, look = stat(res)
    rows.append((name, f'{ok / 5:.0f}/s', fm(p50), fm(p99), f'{hiok:.0%}', f'{look:.0%}', srv.stats['wasted']))
table(rows, ['做法', '成功速率', '成功请求延迟中位数', 'p99', '高优先级成功比例', '低优先级成功比例', '白干(处理完时已超时)'])

# ============ 三 ============
print('== 三:背压。两级流水线:上游每秒产生 500 个任务,下游每个任务 sleep 5 ms(单线程,理论容量 200 个/秒,实测约 160 个/秒),中间用队列连接,跑 6 秒。无界队列:上游不受影响,队列越积越长;有界队列(容量 100)+ 满了就阻塞上游的 put。统计每秒的队列长度、任务在队列里的等待时间,以及上游实际能生产多少个')
def run3(bounded):
    q = queue.Queue(maxsize=100 if bounded else 0); stop = threading.Event(); lens = []; waits = []; produced = [0]; consumed = [0]
    def prod():
        t0 = time.perf_counter(); i = 0
        while time.perf_counter() - t0 < 6.0:
            tgt = t0 + i / 500; d = tgt - time.perf_counter()
            if d > 0: time.sleep(d)
            q.put(time.perf_counter()); produced[0] += 1; i += 1
        stop.set()
    def cons():
        while not (stop.is_set() and q.empty()):
            try: ts = q.get(timeout=0.1)
            except queue.Empty: continue
            waits.append(time.perf_counter() - ts); time.sleep(0.005); consumed[0] += 1
            if stop.is_set() and time.perf_counter() - T0 > 8.0: return
    def sampler():
        while not stop.is_set(): lens.append(q.qsize()); time.sleep(1.0)
    T0 = time.perf_counter(); ths = [threading.Thread(target=f) for f in (prod, cons, sampler)]; [t.start() for t in ths]; [t.join() for t in ths]
    return produced[0], lens, waits[:consumed[0]], q.qsize()
rows = []
for bounded in (False, True):
    produced, lens, waits, left = run3(bounded)
    rows.append(('有界(100)+阻塞 put' if bounded else '无界', produced, f'{produced / 6:.0f}/s', lens, fm(pct(waits[-300:], 50)), fm(max(waits)), left))
table(rows, ['队列', '上游 6 秒生产了', '上游实际速率', '每秒的队列长度', '最后 300 个任务排队时间的中位数', '最长排队时间', '上游停止时队里还剩'])
print('  有界队列把下游的慢直接传导给上游:上游被 put 阻塞,速率降到下游的处理能力;无界队列把这个差额存起来,变成越来越长的排队时间(和内存)')
