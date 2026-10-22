import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v71'); reset()
print('Prometheus 的抓取模型:pull、间隔与过期。Prometheus 3.15.0(自己起的),抓取我写的暴露 /metrics 的 Python 服务。看采样时间戳的抖动、目标消失之后数据什么时候“过期”(staleness 标记与 query.lookback-delta)、抓取超时、以及比抓取间隔更短命的任务会不会被抓到')
def cfg(targets, interval, timeout=None, extra_job=''):
    return f'''global:
  scrape_interval: {interval}s
  evaluation_interval: {interval}s
scrape_configs:
  - job_name: lab
    {f"scrape_timeout: {timeout}s" if timeout else ""}
    {extra_job}
    static_configs:
      - targets: [{", ".join(repr(t) for t in targets)}]
'''
class Exposer:
    def __init__(self, payload, delay=0.0):
        self.payload = payload; self.delay = delay; self.svc = Svc(self.app, 'm'); self.port = self.svc.port
    def app(self, h):
        if self.delay: time.sleep(self.delay)
        p = self.payload() if callable(self.payload) else self.payload; h.reply(200, p, {'Content-Type': 'text/plain; version=0.0.4'})
    def stop(self): self.svc.stop()
def has(prom, q):
    r = prom.query(q); return bool(r)
def wait_data(prom, q, timeout=40.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if has(prom, q): return True
        time.sleep(0.3)
    return False

# ============ 一 ============
print('== 一:采样时间戳。抓取间隔分别是 1 s 和 5 s,运行 60 s 之后读 up 的原始样本,看相邻样本的时间间隔(应该等于抓取间隔)的分布')
rows = []
for iv in (1, 5):
    ex = Exposer(b'# TYPE m gauge\nm 1\n'); prom = Prom(f'v71a{iv}', cfg([f'127.0.0.1:{ex.port}'], iv)).start(); wait_data(prom, 'm'); time.sleep(60 if iv == 1 else 62)
    ts = [t for t, v in prom.query('up[3m]')[0]['values']]; d = [(b - a) * 1000 for a, b in zip(ts, ts[1:])]
    rows.append((f'{iv} s', len(ts), f'{min(d):.0f}', f'{statistics.median(d):.0f}', f'{max(d):.0f}', f'{statistics.pstdev(d):.1f}')); prom.stop(); ex.stop()
table(rows, ['抓取间隔', '样本数', '相邻样本间隔 最小(ms)', '中位(ms)', '最大(ms)', '标准差(ms)'])
print('  Prometheus 按固定的间隔调度抓取(每个 target 有一个由哈希决定的起始偏移,不会所有 target 同时抓取);相邻样本的间隔几乎恰好等于抓取间隔,偏差在几毫秒以内')

# ============ 二 ============
print('== 二:数据什么时候“过期”。把 --query.lookback-delta 设成 30 s(默认是 5 分钟,这里缩短是为了在一次实验里测完),抓取间隔 2 s。四种情形,看查询 m(即时查询)从什么时候起查不到:(a)target 进程停了(连接被拒);(b)target 还在,但 m{id="b"} 这条序列不再出现在 /metrics 里;(c)target 的 /metrics 里给样本带了显式时间戳,然后 target 停了;(d)不带时间戳的 target 停了(对照,和 (a) 相同)')
def run_stale(case):
    state = {'b': True}; stamp = lambda: int(time.time() * 1000)
    def payload():
        if case == 'c': return f'# TYPE m gauge\nm{{id="c"}} 1 {stamp()}\n'.encode()
        lines = '# TYPE m gauge\nm{id="a"} 1\n'
        if state['b']: lines += 'm{id="b"} 1\n'
        return lines.encode()
    ex = Exposer(payload); prom = Prom('v71b' + case, cfg([f'127.0.0.1:{ex.port}'], 2), flags=['--query.lookback-delta=30s']).start()
    sel = {'a': 'm{id="a"}', 'b': 'm{id="b"}', 'c': 'm{id="c"}', 'd': 'm{id="a"}'}[case]
    assert wait_data(prom, sel); time.sleep(6)
    t0 = time.time()
    if case in ('a', 'c', 'd'): ex.stop()
    else: state['b'] = False
    gone = None
    while time.time() - t0 < 60:
        if not has(prom, sel): gone = time.time() - t0; break
        time.sleep(0.1)
    up = prom.query('up'); upv = up[0]['value'][1] if up else '-'
    prom.stop()
    try: ex.stop()
    except Exception: pass
    return gone, upv
rows = []
for case, name in (('a', '(a)target 进程停了'), ('b', '(b)target 还在,一条序列消失'), ('c', '(c)样本带显式时间戳,target 停了'), ('d', '(d)对照:不带时间戳,target 停了')):
    g, upv = run_stale(case); rows.append((name, f'{g:.1f} s' if g is not None else '60 s 内一直能查到', upv))
table(rows, ['情形', '从停止/消失到即时查询查不到', '那时 up 的值'])
print('  抓取失败(a)或者序列从成功的抓取结果里消失(b)时,Prometheus 在下一次抓取时写一个 staleness 标记,即时查询马上查不到(不超过一个抓取间隔);带显式时间戳的样本没有 staleness 标记,要等 lookback-delta 过去才查不到')

# ============ 三 ============
print('== 三:抓取超时。抓取间隔 5 s,scrape_timeout 2 s。target 的响应延迟分别是 0.5 s、1.5 s、3 s。各运行 25 s,看 up、scrape_duration_seconds 的值,以及 m 有没有样本')
rows = []
for delay in (0.5, 1.5, 3.0):
    ex = Exposer(b'# TYPE m gauge\nm 1\n', delay=delay); prom = Prom(f'v71c{int(delay * 10)}', cfg([f'127.0.0.1:{ex.port}'], 5, 2)).start(); time.sleep(27)
    up = prom.query('up'); dur = prom.query('scrape_duration_seconds'); m = prom.query('count_over_time(m[1m])')
    rows.append((f'{delay} s', up[0]['value'][1] if up else '-', f'{float(dur[0]["value"][1]):.2f} s' if dur else '-', m[0]['value'][1] if m else '0(没有样本)', len(prom.query('up[1m]')[0]['values']) if up else 0)); prom.stop(); ex.stop()
table(rows, ['target 响应延迟', 'up', 'scrape_duration_seconds', '近 1 分钟 m 的样本数', '近 1 分钟 up 的样本数'])
print('  响应超过 scrape_timeout 的抓取算失败:up 变成 0,这次的数据一条都不收(m 没有样本),但 up 和 scrape_duration_seconds 这些元数据照样记录')

# ============ 四 ============
print('== 四:比抓取间隔更短命的任务。40 个批处理任务:20 个只活 2 s、20 个活 12 s,启动时刻各自在 100 s 内均匀随机(固定种子);每个任务活着的时候在自己的端口上暴露一个 gauge job_value,并通过 file_sd 文件登记给 Prometheus(登记和取消登记都是实时的,file_sd 刷新间隔设 1 s)。抓取间隔 5 s。100 多秒之后统计:两类任务各有几个被抓到过,活 12 s 的任务从登记到第一个样本用了多久、各被抓到几次')
fsd = TT / 'v71_targets.json'; fsd.write_text('[]')
cfg4 = f'''global:
  scrape_interval: 5s
scrape_configs:
  - job_name: batch
    file_sd_configs:
      - files: ['{fsd}']
        refresh_interval: 1s
'''
prom = Prom('v71d', cfg4).start(); rnd = random.Random(12)
plan = [(f's{i}', rnd.uniform(2, 98), 2.0) for i in range(20)] + [(f'l{i}', rnd.uniform(2, 98), 12.0) for i in range(20)]
active = {}; lk = threading.Lock(); T0 = time.time(); regt = {}
def write_sd():
    with lk: fsd.write_text(json.dumps([{'targets': [f'127.0.0.1:{svc.port}'], 'labels': {'jobid': jid}} for jid, svc in active.items()]))
def runjob(jid, st, life):
    time.sleep(max(0, T0 + st - time.time())); svc = Svc(lambda h: h.reply(200, b'# TYPE job_value gauge\njob_value 1\n', {'Content-Type': 'text/plain; version=0.0.4'}), jid)
    with lk: active[jid] = svc
    write_sd(); regt[jid] = time.time(); time.sleep(life)
    with lk: active.pop(jid, None)
    write_sd(); svc.stop()
ths = [threading.Thread(target=runjob, args=p) for p in plan]
for t in ths: t.start()
for t in ths: t.join()
time.sleep(8)
raw = {r['metric']['jobid']: [float(t) for t, v in r['values']] for r in prom.query('job_value[5m]')}
sshort = [k for k in raw if k.startswith('s')]; slong = [k for k in raw if k.startswith('l')]
delay = [raw[k][0] - regt[k] for k in slong]; cnt = [len(raw[k]) for k in slong]
print(f'  活 2 s 的 20 个任务里被抓到过的有 {len(sshort)} 个;活 12 s 的 20 个任务里被抓到过的有 {len(slong)} 个')
if slong: print(f'  被抓到的活 12 s 的任务:从登记到第一个样本 最小 {min(delay):.1f} s、中位 {statistics.median(delay):.1f} s、最大 {max(delay):.1f} s;每个任务被抓到 {min(cnt)}~{max(cnt)} 次(中位 {statistics.median(cnt):.0f} 次)')
print('  抓取间隔只是一个因素:新登记的 target 从写入 file_sd 文件到出现第一个样本要等几秒(上面的“登记到第一个样本”那一行;延迟的构成我印象里是服务发现的更新有批量节流加上 target 自己的第一次抓取,没有逐项验证),任务比这个延迟还短就一次都抓不到。这类任务应该主动把指标推给 Pushgateway 之类的中间层,或者在退出前自己上报')
prom.stop()
print('ERRORS', dict(ERRORS))
