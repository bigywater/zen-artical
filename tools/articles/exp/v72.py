import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v72'); reset()
print('rate()、increase()、irate() 与计数器重置。Prometheus 3.15.0(自己起的),抓取我写的服务,服务里的 counter 按设定的速度增长,所以真实增量已知。看 increase 为什么对整数 counter 给出小数、窗口比抓取间隔太短时 rate 为什么没有结果、irate 与 rate 的差别,以及两种“重启时丢增量”的情形')
def cfg(targets, interval):
    return f'''global:
  scrape_interval: {interval}s
  evaluation_interval: {interval}s
scrape_configs:
  - job_name: lab
    static_configs:
      - targets: [{", ".join(repr(t) for t in targets)}]
'''
class Exposer:
    def __init__(self, fn): self.fn = fn; self.svc = Svc(lambda h: h.reply(200, self.fn().encode(), {'Content-Type': 'text/plain; version=0.0.4'}), 'm'); self.port = self.svc.port
    def stop(self): self.svc.stop()
def val(prom, q, t=None):
    r = prom.query(q, t=t); return float(r[0]['value'][1]) if r else None
def wait_data(prom, q, timeout=40.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if prom.query(q): return True
        time.sleep(0.3)
    return False

# ============ 一~三 共用同一次运行 ============
st = {'steady': 0.0, 'sparse': 0.0, 'burst': 0.0}
def body(): return f'# TYPE c_steady counter\nc_steady {st["steady"]}\n# TYPE c_sparse counter\nc_sparse {st["sparse"]}\n# TYPE c_burst counter\nc_burst {st["burst"]}\n'
ex = Exposer(body); prom = Prom('v72a', cfg([f'127.0.0.1:{ex.port}'], 5)).start(); assert wait_data(prom, 'c_steady')
T0 = time.time(); stop = threading.Event()
def driver():
    k = 0
    while not stop.is_set():
        st['steady'] += 10                       # 每秒 +10
        if k % 20 == 10: st['sparse'] += 1       # 每 20 s +1
        if k % 20 in (10, 11): st['burst'] += 1000   # 每 20 s 里有 2 s,每秒 +1000
        k += 1; time.sleep(max(0, T0 + k - time.time()))
th = threading.Thread(target=driver); th.start(); time.sleep(max(0, T0 + 160 - time.time())); stop.set(); th.join(); time.sleep(6)
t_end = T0 + 150; ts = [t_end - 5 * i for i in range(17)]

print('== 一:increase() 的外推。counter c_steady 每秒 +10(任何 60 s 窗口里的真实增量都是 600);c_sparse 每 20 s +1(任何 60 s 窗口里的真实增量是 3)。抓取间隔 5 s,在 17 个不同的时刻(间隔 5 s)查询 increase(c[1m]),看结果的范围')
rows = []
for name, true in (('c_steady', 600), ('c_sparse', 3)):
    vs = [val(prom, f'increase({name}[1m])', t) for t in ts]; vs = [v for v in vs if v is not None]
    rows.append((name, true, len(vs), f'{min(vs):.2f}', f'{max(vs):.2f}', f'{statistics.mean(vs):.2f}'))
table(rows, ['counter', '60 s 窗口里的真实增量', '得到结果的时刻数', 'increase 最小', 'increase 最大', 'increase 平均'])
print('  increase() 用窗口内第一个和最后一个样本之间的增量,按窗口边界与样本的距离做线性外推;外推之后整数 counter 也会得到小数,单个窗口的结果会偏离真实值,取平均更接近真实值')

print('== 二:窗口与抓取间隔。抓取间隔 5 s。对 c_steady 在同一个时刻查询 rate(c_steady[W]),W 取 5 s、10 s、15 s、20 s、30 s;真实速率是 10/s')
rows = []
for W in (5, 10, 15, 20, 30):
    n = prom.query(f'count_over_time(c_steady[{W}s])', t=t_end); r = val(prom, f'rate(c_steady[{W}s])', t_end)
    rows.append((f'{W} s', int(float(n[0]['value'][1])) if n else 0, f'{r:.2f}' if r is not None else '(没有结果)'))
table(rows, ['窗口 W', '窗口内的样本数', 'rate(c_steady[W])'])
print('  rate() / increase() 至少要窗口里有两个样本才能算;窗口恰好等于抓取间隔时可能只有一个样本,返回空;窗口里只有两三个样本时结果受外推和抓取时刻的影响很大,所以窗口至少要取抓取间隔的几倍')

print('== 三:irate 与 rate。c_burst 每 20 s 里有 2 s 每秒 +1000(其余时间不增长)。在最后 80 s 里每 5 s 取一个时刻,比较 irate(c_burst[30s])(只用窗口里最后两个样本)和 rate(c_burst[30s])(整个窗口的平均)的取值')
iv = [val(prom, 'irate(c_burst[30s])', t_end - 5 * i) for i in range(17)]; rv = [val(prom, 'rate(c_burst[30s])', t_end - 5 * i) for i in range(17)]
iv = [x for x in iv if x is not None]; rv = [x for x in rv if x is not None]
table([('irate(c_burst[30s])', f'{min(iv):.1f}', f'{max(iv):.1f}', f'{statistics.pstdev(iv):.1f}', len(iv)), ('rate(c_burst[30s])', f'{min(rv):.1f}', f'{max(rv):.1f}', f'{statistics.pstdev(rv):.1f}', len(rv))], ['函数', '最小(/s)', '最大(/s)', '标准差', '取值的时刻数'])
print(f'  整个周期(20 s)里平均每秒 +{2000 / 20:.0f}。irate 反映抓取到的最近两点之间的瞬时速度,变化剧烈,适合看当前的尖峰;rate 对整个窗口平均,更平滑,适合告警和长期趋势')
prom.stop(); ex.stop()

# ============ 四 ============
print('== 四:抓取空窗里重启。counter 每秒 +100,抓取间隔 2 s。进程在第 11 s 刚增加完之后崩溃(此时 counter 是 1100,但最后一次成功的抓取早于这次增加),第 16 s 重新启动(counter 从 0 开始),继续每秒 +100,运行到第 40 s。崩溃到重启之间 target 的抓取失败(503)。比较:两个进程实际增加的总量、Prometheus 抓到的第一个样本之前已有的增量(不可能被 increase 算进去)、崩溃前最后一次抓到的值,和 increase() 的结果')
s4 = {'v': 0.0, 'alive': True, 'actual': 0.0}
def app4(h):
    if not s4['alive']: h.reply(503, b'down'); return
    h.reply(200, f'# TYPE c counter\nc {s4["v"]}\n'.encode(), {'Content-Type': 'text/plain; version=0.0.4'})
svc4 = Svc(app4, 'm4'); prom = Prom('v72b', cfg([f'127.0.0.1:{svc4.port}'], 2)).start(); assert wait_data(prom, 'up'); time.sleep(2)
T0 = time.time(); s4['v'] = 0.0; crash_val = None
for sec in range(40):
    if sec == 16: s4['alive'] = True; s4['v'] = 0.0
    if s4['alive']: s4['v'] += 100; s4['actual'] += 100
    if sec == 11: s4['alive'] = False; crash_val = s4['v']
    time.sleep(max(0, T0 + sec + 1 - time.time()))
time.sleep(2.5)
raw = [(float(t), float(v)) for t, v in prom.query('c[2m]')[0]['values']]
inc = val(prom, 'increase(c[2m])'); first = raw[0][1]; last_before = max(v for t, v in raw if v > 0 and t < T0 + 16 and v <= crash_val)
observable = s4['actual'] - first - (crash_val - last_before)
print(f'  两个进程实际增加的总量 {s4["actual"]:.0f}(崩溃前 {crash_val:.0f} + 重启后 {s4["v"]:.0f});Prometheus 抓到的第一个样本是 {first:.0f};崩溃前最后一次成功抓到的值是 {last_before:.0f},崩溃时是 {crash_val:.0f},这 {crash_val - last_before:.0f} 的增量永远没有被抓到。所以 increase 能反映的上限是 实际总量 − 第一个样本的值 − 没被抓到的增量 = {s4["actual"]:.0f} − {first:.0f} − {crash_val - last_before:.0f} = {observable:.0f}')
print(f'  increase(c[2m]) = {inc:.0f},与上限 {observable:.0f} 的差是 {inc - observable:+.0f}(increase 会对窗口两端做外推,这个差我没有逐项拆解);崩溃前后没被抓到的那 {crash_val - last_before:.0f} 个增量无法从 Prometheus 里找回')
print(f'  样本序列(时间相对第 0 s,值):' + ' '.join(f'{t - T0:.0f}s:{v:.0f}' for t, v in raw if T0 + 2 <= t <= T0 + 40))
prom.stop(); svc4.stop()

# ============ 五 ============
print('== 五:重启后增长得比崩溃前的值还快。counter 每秒 +10,抓取间隔 2 s。某次抓取抓到 counter = 200 之后,进程立刻重启,新进程在下一次抓取之前一口气增长到 300(例如重启后批量处理积压),下一次抓取看到 300。比较 Prometheus 的 increase 与实际新增的量')
s5 = {'v': 0.0}
svc5 = Svc(lambda h: h.reply(200, f'# TYPE c counter\nc {s5["v"]}\n'.encode(), {'Content-Type': 'text/plain; version=0.0.4'}), 'm5'); prom = Prom('v72c', cfg([f'127.0.0.1:{svc5.port}'], 2)).start(); assert wait_data(prom, 'up'); time.sleep(1)
T0 = time.time()
for sec in range(20):
    s5['v'] += 10; time.sleep(max(0, T0 + sec + 1 - time.time()))
# 把 counter 推到 200,等被抓到,再“重启”并一口气到 300
s5['v'] = 200.0
while True:
    r = prom.query('c')
    if r and float(r[0]['value'][1]) == 200.0: break
    time.sleep(0.2)
t_mark = time.time(); pre = s5['v']; s5['v'] = 0.0; s5['v'] = 300.0; true_after = 300.0 - 0.0
time.sleep(5)
raw = [(float(t), float(v)) for t, v in prom.query('c[1m]')[0]['values']]; tail = [(t, v) for t, v in raw if t >= t_mark - 2]
w = int(time.time() - t_mark + 6)
inc = val(prom, f'increase(c[{w}s])'); resets = val(prom, f'resets(c[{w}s])')
print(f'  抓到的样本:' + ' '.join(f'{t - t_mark:+.1f}s:{v:.0f}' for t, v in tail) + f';重启前最后抓到 {pre:.0f},重启后新进程实际增加 {true_after:.0f}(0 → 300);Prometheus 看到 200 → 300,没有出现“值变小”,resets() = {resets}。窗口里 200 → 300 这一段的增量是 100,真实新增是 300,少算了 {true_after - 100:.0f}')
prom.stop(); svc5.stop()
print('ERRORS', dict(ERRORS))
