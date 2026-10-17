import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c34')
img('python:3.12-alpine')
purge()
BURN = r'''
import os, time, sys, multiprocessing as mp
def usage():
    for l in open("/sys/fs/cgroup/cpu.stat"):
        if l.startswith("usage_usec"): return int(l.split()[1])
def spin(end):
    while time.time() < end: pass
if __name__ == "__main__":
    dur = float(os.environ.get("DUR", "6")); n = int(os.environ.get("PROCS", "4"))
    u0 = usage(); t0 = time.time()
    ps = [mp.Process(target=spin, args=(t0 + dur,)) for _ in range(n)]
    [p.start() for p in ps]; [p.join() for p in ps]
    el = time.time() - t0; u1 = usage()
    print("%.2f" % ((u1 - u0) / 1e6 / el), flush=True)
'''
d = ctx('c34', {'burn.py': BURN, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY burn.py /burn.py\nCMD ["python","/burn.py"]\n'})
rc, o = build(d, 'bwlab-c34', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
ncpu = int(out('info', '--format', '{{.NCPU}}'))
print(f'== 一:--cpus 限制容器能用多少个 CPU(Docker Desktop 虚拟机有 {ncpu} 个 CPU;Docker Engine 29.8.2)')
def cg(opts):
    rc, o = dk('run', '--rm', *LAB, *opts, 'bwlab-c34', 'sh', '-c', 'echo cpu.max=$(cat /sys/fs/cgroup/cpu.max) cpu.weight=$(cat /sys/fs/cgroup/cpu.weight)')
    return o.strip()
for label, opts in (('不限制', []), ('--cpus 0.5', ['--cpus', '0.5']), ('--cpus 1', ['--cpus', '1']), ('--cpus 2', ['--cpus', '2']), ('--cpu-quota 25000(周期默认 100000)', ['--cpu-quota', '25000'])):
    rc, o = dk('run', '--rm', *LAB, '-e', 'PROCS=%d' % (ncpu + 2), *opts, 'bwlab-c34')
    print(f'  {label}:cgroup 里 {cg(opts)};用 {ncpu + 2} 个进程满负荷跑 6 秒,平均占用 {o.strip()} 个 CPU')
print('== 二:--cpu-shares 只在争抢时起作用')
rc, o = dk('run', '--rm', *LAB, '--cpu-shares', '2', '-e', 'PROCS=2', 'bwlab-c34')
print(f'  只有这一个容器、--cpu-shares 2(最低权重)、2 个满负荷进程:平均占用 {o.strip()} 个 CPU(没有竞争时 shares 不限制)')
print('  两个容器钉在同一个 CPU(--cpuset-cpus 0)上同时满负荷跑:')
for a, b in ((1024, 1024), (1024, 512), (1024, 256), (2048, 256)):
    n1, n2 = f'bwlab-c34-a{a}', f'bwlab-c34-b{b}'
    dk('run', '-d', '--name', n1, *LAB, '--cpuset-cpus', '0', '--cpu-shares', str(a), '-e', 'PROCS=2', '-e', 'DUR=6', 'bwlab-c34')
    dk('run', '-d', '--name', n2, *LAB, '--cpuset-cpus', '0', '--cpu-shares', str(b), '-e', 'PROCS=2', '-e', 'DUR=6', 'bwlab-c34')
    dk('wait', n1, n2, timeout=60)
    ua = float(dk('logs', n1)[1].strip().splitlines()[-1]); ub = float(dk('logs', n2)[1].strip().splitlines()[-1])
    w = lambda n: out('exec', n, 'cat', '/sys/fs/cgroup/cpu.weight') if False else ''
    print(f'    shares {a} 对 {b}:占用 {ua:.2f} 对 {ub:.2f} 个 CPU,实际比例 {ua / ub:.2f};shares 比例 {a / b:.2f}')
    dk('rm', '-f', n1, n2)
W = {}
for sh in (256, 512, 1024, 2048):
    rc, o = dk('run', '--rm', *LAB, '--cpu-shares', str(sh), 'bwlab-c34', 'sh', '-c', 'cat /sys/fs/cgroup/cpu.weight'); W[sh] = int(o.strip())
print('  --cpu-shares 换算成 cgroup v2 的 cpu.weight:' + ',  '.join(f'{k} → {v}' for k, v in W.items()) + '(不带参数时是 100)')
print('  用 cpu.weight 算出的比例:1024:512 = %.2f,1024:256 = %.2f,2048:256 = %.2f' % (W[1024] / W[512], W[1024] / W[256], W[2048] / W[256]))
purge()
