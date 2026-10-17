import sys, os, time, json, re, threading, hashlib, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from kazoo.recipe.watchers import DataWatch, ChildrenWatch
tee('z87'); R = {}
n = Node('z87', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); adm = client('127.0.0.1:7300')
adm.create('/gray/rule', json.dumps({'percent': 0, 'v': 'v1->v2'}).encode(), makepath=True); adm.ensure_path('/gray/override'); adm.ensure_path('/gray/errors')
N = 200
class Inst:
    def __init__(self, i):
        self.id = f'inst-{i:03d}'; self.c = client('127.0.0.1:7300'); self.bucket = int(hashlib.md5(self.id.encode()).hexdigest(), 16) % 100
        self.rule = {'percent': 0}; self.over = False; self.t = time.perf_counter(); self.state = False; self.changed = time.perf_counter()
        DataWatch(self.c, '/gray/rule', self._rule); DataWatch(self.c, f'/gray/override/{self.id}', self._ov)
    def _upd(self):
        new = self.over or self.bucket < self.rule['percent']
        if new != self.state: self.state = new; self.changed = time.perf_counter()
    def _rule(self, d, s):
        if d: self.rule = json.loads(d); self._upd()
    def _ov(self, d, s): self.over = d is not None; self._upd()
I = [Inst(i) for i in range(N)]; time.sleep(1.0)
def frac(): return sum(1 for x in I if x.state)
def setp(p):
    t0 = time.perf_counter(); adm.set('/gray/rule', json.dumps({'percent': p, 'v': 'v1->v2'}).encode())
    while time.perf_counter() - t0 < 5:
        if frac() == sum(1 for x in I if x.bucket < p or x.over): break
        time.sleep(0.002)
    time.sleep(0.05); return (time.perf_counter() - t0) * 1000
print(f'== 一:{N} 个实例按「实例号哈希 % 100 < percent」决定是否用新版本。逐级放量 0 → 5 → 20 → 50 → 100:实际用新版本的实例数与收敛时间')
R['ramp'] = []; sets = {}
for p in (0, 5, 20, 50, 100):
    ms = setp(p); f = frac(); sets[p] = {x.id for x in I if x.state}; R['ramp'].append(dict(p=p, n=f, ms=ms)); print(f'  percent={p:>3}:{f:>3} / {N} 个实例在用新版本({f / N * 100:.1f}%);收敛耗时 {ms:.1f} ms')
print(f'  放量是单调的(5% 时的实例,20% 时仍在新版本里;20% ⊂ 50% ⊂ 100%):{sets[5] <= sets[20] <= sets[50] <= sets[100]}')
R['mono'] = sets[5] <= sets[20] <= sets[50] <= sets[100]
print()
print('== 二:回到 0%(一键回滚):所有实例回到旧版本要多久')
t0 = time.perf_counter(); adm.set('/gray/rule', json.dumps({'percent': 0}).encode())
while frac() and time.perf_counter() - t0 < 5: time.sleep(0.001)
rb = (time.perf_counter() - t0) * 1000; last = max(x.changed for x in I) - t0
print(f'  percent=0 后 {frac()} 个实例仍在新版本;最后一个实例切回旧版本 {last*1000:.1f} ms 之后'); R['rollback_ms'] = last * 1000
print()
print('== 三:指定实例灰度(白名单):给 3 个内部测试实例建 /gray/override/<id>,percent 保持 0')
for k in (3, 77, 150): adm.create(f'/gray/override/inst-{k:03d}', b'1')
time.sleep(0.3); on = sorted(x.id for x in I if x.state); print(f'  percent=0,在用新版本的实例:{on}'); R['override'] = on
for k in (3, 77, 150): adm.delete(f'/gray/override/inst-{k:03d}')
time.sleep(0.3); print(f'  删除白名单节点后,在用新版本的实例数 = {frac()}')
print()
print('== 四:自动回滚:放量到 20% 时,新版本实例开始上报错误(在 /gray/errors 下建临时节点),控制者发现错误实例 ≥ 5 个就把 percent 设回 0')
stop = threading.Event(); ctl = {}
def watch_errs():
    ev = threading.Event()
    while not stop.is_set():
        kids = adm.get_children('/gray/errors', watch=lambda e: ev.set())
        if len(kids) >= 5:
            adm.set('/gray/rule', json.dumps({'percent': 0}).encode()); ctl['t'] = time.perf_counter(); ctl['errs'] = len(kids); return
        ev.wait(1); ev.clear()
th = threading.Thread(target=watch_errs); th.start()
setp(20); on = [x for x in I if x.state]; print(f'  放量到 20%:{len(on)} 个实例在用新版本;它们之中有 8 个开始出错')
t0 = time.perf_counter()
for x in on[:8]: x.c.create(f'/gray/errors/{x.id}', b'', ephemeral=True)
th.join(10)
while frac() and time.perf_counter() - t0 < 8: time.sleep(0.001)
ttr = (max(x.changed for x in I) - t0) * 1000
print(f'  控制者在看到 {ctl.get("errs")}  个错误节点时(阈值 5)回滚;从第一个错误上报到所有实例回到旧版本共 {ttr:.0f} ms;仍在用新版本的实例 = {frac()}')
R['auto'] = dict(errs=ctl.get('errs'), ms=ttr, left=frac())
stop.set()
for x in I: x.c.stop()
adm.stop(); n.stop(); save('z87', R); os._exit(0)
