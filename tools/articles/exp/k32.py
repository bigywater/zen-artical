import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k32')
cn, _ = up('main')
NS = ns('k32')
NODE = 'kx-main-worker'
def pod(name, procs, res='', cmd=None, extra=''):
    c = cmd or f'for i in $(seq {procs}); do (while :; do :; done) & done; wait'
    return f'''apiVersion: v1
kind: Pod
metadata: {{name: {name}, namespace: {NS}}}
spec:
  nodeName: {NODE}
  terminationGracePeriodSeconds: 0
  containers:
  - name: c
    image: busybox:1.36
    command: [sh, -c, "{c}"]
{res}'''
def stat(name):
    p = kj('get', 'pod', name, '-n', NS); node, cg, cid = container_cgroup(p, 'c')
    st = dict(l.split() for l in cgread(node, cg, 'cpu.stat').splitlines()); return {k_: int(v) for k_, v in st.items()}, cg
def window(name, secs=10):
    a, cg = stat(name); t0 = time.time(); time.sleep(secs); b, _ = stat(name); dt = time.time() - t0
    return {k_: b[k_] - a[k_] for k_ in b}, dt
def ready(*ns_): until(lambda: all((kj('get', 'pod', n, '-n', NS) or {}).get('status', {}).get('phase') == 'Running' for n in ns_), 60); time.sleep(2)
print(f'集群 {cn};requests 变成 cgroup 的 cpu.weight(竞争时按比例分),limits 变成 cpu.max(每 100ms 周期里最多能跑多少);超过 limit 就被限流(throttled),cpu.stat 里有计数')

print('== 一:limit 200m 的容器跑一个死循环——用掉的 CPU 时间被限制在 20%')
k('apply', '-f', '-', input=pod('lim200', 1, '    resources: {requests: {cpu: 100m}, limits: {cpu: 200m}}\n')); ready('lim200')
w, dt = window('lim200', 10); p = kj('get', 'pod', 'lim200', '-n', NS); node, cg, cid = container_cgroup(p, 'c')
print(f'  cpu.max={cgread(node, cg, "cpu.max")}(每 100000 微秒的周期里最多 20000 微秒);cpu.weight={cgread(node, cg, "cpu.weight")}')
print(f'  {dt:.1f} 秒的窗口里:用掉 CPU {w["usage_usec"] / 1e6:.2f} 秒(= {w["usage_usec"] / 1e6 / dt * 100:.0f}% 个核);nr_periods={w["nr_periods"]} nr_throttled={w["nr_throttled"]}({w["nr_throttled"] / max(w["nr_periods"], 1) * 100:.0f}% 的周期被限流);throttled_usec={w["throttled_usec"] / 1e6:.2f} 秒')

print('== 二:没有 limit 的容器可以吃满核——limit 才是上限')
k('apply', '-f', '-', input=pod('free4', 4, '    resources: {requests: {cpu: 100m}}\n')); k('apply', '-f', '-', input=pod('lim1', 4, '    resources: {requests: {cpu: 100m}, limits: {cpu: "1"}}\n')); ready('free4', 'lim1')
for n_, d in (('free4', '4 个死循环,没有 limit'), ('lim1', '4 个死循环,limit 1 核')):
    w, dt = window(n_, 10); p = kj('get', 'pod', n_, '-n', NS); node, cg, cid = container_cgroup(p, 'c')
    print(f'  {n_}({d}):cpu.max={cgread(node, cg, "cpu.max")};{dt:.1f} 秒用掉 CPU {w["usage_usec"] / 1e6:.1f} 秒(平均 {w["usage_usec"] / 1e6 / dt:.2f} 个核);被限流的周期占 {w["nr_throttled"] / max(w["nr_periods"], 1) * 100:.0f}%')
k('delete', 'pod', 'free4', 'lim1', 'lim200', '-n', NS, '--wait=true', timeout=60)

print('== 三:只有 requests、没有 limit——竞争时按 cpu.weight 的比例分(两个容器在同一个节点上把核吃满)')
k('apply', '-f', '-', input=pod('small', 12, '    resources: {requests: {cpu: 100m}}\n')); k('apply', '-f', '-', input=pod('big', 12, '    resources: {requests: {cpu: 400m}}\n')); ready('small', 'big')
ps = kj('get', 'pod', 'small', '-n', NS); pb = kj('get', 'pod', 'big', '-n', NS)
node, cgs, _ = container_cgroup(ps, 'c'); _, cgb, _ = container_cgroup(pb, 'c')
def both():
    rc, o = nx(node, f"head -1 {cgs}/cpu.stat; head -1 {cgb}/cpu.stat; head -1 /proc/stat", raw=True); L = o.strip().splitlines()
    return int(L[0].split()[1]), int(L[1].split()[1]), sum(int(x) for x in L[2].split()[1:]) - int(L[2].split()[4])
a = both(); time.sleep(12); b = both(); ds, db = b[0] - a[0], b[1] - a[1]; busy = (b[2] - a[2]) / 100
print(f'  small(requests 100m,12 个死循环)cpu.weight={cgread(node, cgs, "cpu.weight")};big(requests 400m,12 个死循环)cpu.weight={cgread(node, cgb, "cpu.weight")}')
print(f'  同一次读取里取两个容器的 cpu.stat,间隔 12 秒:small 用了 {ds / 1e6:.1f} 秒 CPU,big 用了 {db / 1e6:.1f} 秒 CPU,比例 big/small = {db / max(ds, 1):.2f}(两个 cpu.weight 的比例是 {int(cgread(node, cgb, "cpu.weight")) / int(cgread(node, cgs, "cpu.weight")):.2f});合计 {(ds + db) / 1e6:.0f} 秒 ≈ {(ds + db) / 1e6 / 12:.1f} 个核,节点共有 {ko("get", "node", NODE, "-o", "jsonpath={.status.capacity.cpu}")} 个核,整台节点的忙碌时间是 {busy:.0f} 秒)')
k('delete', 'pod', 'small', 'big', '-n', NS, '--wait=true', timeout=60)

print('== 四:限流让同一件事变慢——同样的计算在不同 limit 下花的墙钟时间')
work = "awk 'BEGIN{for(i=0;i<20000000;i++)x+=i; print x}' > /dev/null"
for n_, lim in (('w-free', ''), ('w-500', '500m'), ('w-100', '100m')):
    res = '    resources: {limits: {cpu: %s}}\n' % lim if lim else ''
    cmd = f's=$(cut -d\\" \\" -f1 /proc/uptime); {work}; e=$(cut -d\\" \\" -f1 /proc/uptime); echo elapsed $s $e; sleep 3600'
    k('apply', '-f', '-', input=pod(n_, 1, res, cmd=cmd))
time.sleep(1); ready('w-free', 'w-500', 'w-100')
def elapsed(n_):
    v, _ = until(lambda: 'elapsed' in k('logs', n_, '-n', NS)[1], 120, 1); o = k('logs', n_, '-n', NS)[1]
    m = re.search(r'elapsed ([\d.]+) ([\d.]+)', o); return float(m.group(2)) - float(m.group(1)) if m else None
for n_, d in (('w-free', '没有 limit'), ('w-500', 'limit 500m'), ('w-100', 'limit 100m')):
    e = elapsed(n_); print(f'  {n_}({d}):awk 做 2000 万次加法的墙钟时间 {e:.1f} 秒' if e else f'  {n_}:没有得到结果')
rmns(NS)
