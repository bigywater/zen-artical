import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c35')
img('python:3.12-alpine')
purge()
APP = r'''
import os, time, sys, statistics, multiprocessing as mp
def stat():
    d = {}
    for l in open("/sys/fs/cgroup/cpu.stat"):
        k, v = l.split(); d[k] = int(v)
    return d
def work(ms):
    end = time.thread_time() + ms / 1000
    while time.thread_time() < end: pass
def seq(ms, n):
    s0 = stat(); lat = []
    for _ in range(n):
        t0 = time.perf_counter(); work(ms); lat.append((time.perf_counter() - t0) * 1000)
        time.sleep(0.003)
    s1 = stat()
    lat.sort()
    return lat, {k: s1[k] - s0[k] for k in ("nr_periods", "nr_throttled", "throttled_usec")}
def par_task(ms): work(ms)
if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "seq":
        ms, n = float(sys.argv[2]), int(sys.argv[3])
        lat, d = seq(ms, n)
        print("p50=%.1f p95=%.1f max=%.1f nr_periods=%d nr_throttled=%d throttled_ms=%.0f" % (lat[len(lat)//2], lat[int(len(lat)*0.95)], lat[-1], d["nr_periods"], d["nr_throttled"], d["throttled_usec"]/1000))
    else:
        ms, procs = float(sys.argv[2]), int(sys.argv[3]); walls = []
        s0 = stat()
        for _ in range(10):
            t0 = time.perf_counter()
            ps = [mp.Process(target=par_task, args=(ms,)) for _ in range(procs)]
            [p.start() for p in ps]; [p.join() for p in ps]
            walls.append((time.perf_counter() - t0) * 1000); time.sleep(0.25)
        s1 = stat(); walls.sort()
        print("10 次的墙钟时间 最快=%.0f 中位=%.0f 最慢=%.0f ms nr_throttled=%d throttled_ms=%.0f" % (walls[0], walls[5], walls[-1], s1["nr_throttled"]-s0["nr_throttled"], (s1["throttled_usec"]-s0["throttled_usec"])/1000))
'''
d = ctx('c35', {'app.py': APP, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY app.py /app.py\nENTRYPOINT ["python","/app.py"]\n'})
rc, o = build(d, 'bwlab-c35', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def go(label, opts, *args):
    rc, o = dk('run', '--rm', *LAB, *opts, 'bwlab-c35', *args, timeout=180)
    print(f'  {label}:{o.strip().splitlines()[-1]}')
print('== 一:一次只干 30 ms CPU 活的串行任务,各 100 次(单位 ms;Docker Engine 29.8.2)')
go('不限制', [], 'seq', '30', '100')
go('--cpus 0.5(配额 50 ms / 周期 100 ms)', ['--cpus', '0.5'], 'seq', '30', '100')
go('--cpus 0.5,周期改成 10 ms(配额 5 ms / 周期 10 ms)', ['--cpu-period', '10000', '--cpu-quota', '5000'], 'seq', '30', '100')
print('== 二:一次只干 5 ms CPU 活的任务,配额充裕')
go('--cpus 0.5,5 ms 的任务', ['--cpus', '0.5'], 'seq', '5', '100')
print('== 三:多进程并行的任务:4 个进程各干 40 ms(共 160 ms CPU),重复 10 次')
go('不限制', [], 'par', '40', '4')
go('--cpus 1', ['--cpus', '1'], 'par', '40', '4')
go('--cpus 4', ['--cpus', '4'], 'par', '40', '4')
purge()
