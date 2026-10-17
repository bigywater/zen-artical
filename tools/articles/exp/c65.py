import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c65')
img('alpine:3.20')
purge()
def health(n):
    j = json.loads(out('inspect', '--format', '{{json .State.Health}}', n))
    return j
def timeline(n, until, maxs=30):
    t0 = time.time(); seq = []; last = None
    while time.time() - t0 < maxs:
        h = health(n)['Status'] if health(n) else 'none'
        if h != last: seq.append((h, time.time() - t0)); last = h
        if until(h): break
        time.sleep(0.2)
    return seq
def fmt(seq): return ' → '.join(f'{s}({t:.1f}s)' for s, t in seq)
print('== 一:检查命令从失败到成功:starting → healthy(Docker Engine 29.8.2)')
n = 'bwlab-c65a'
dk('run', '-d', '--name', n, *LAB, '--health-cmd', 'test -f /tmp/ready', '--health-interval', '1s', '--health-timeout', '1s', '--health-retries', '3', 'alpine:3.20', 'sh', '-c', 'sleep 4; touch /tmp/ready; sleep 120')
seq = timeline(n, lambda h: h == 'healthy'); print(f'  容器 sleep 4 秒后才创建 /tmp/ready,interval=1s:状态变化 {fmt(seq)}')
h = health(n); print(f'  Health 对象的字段:{sorted(h.keys())};FailingStreak={h["FailingStreak"]};最近一次日志:ExitCode={h["Log"][-1]["ExitCode"]} Output={h["Log"][-1]["Output"]!r}')
print(f'  docker ps 的 STATUS 列:{out("ps", "--filter", f"name={n}", "--format", "{{.Status}}")}')
dk('rm', '-f', n)
print('== 二:检查一直失败:多久变成 unhealthy')
n = 'bwlab-c65b'
dk('run', '-d', '--name', n, *LAB, '--health-cmd', 'exit 1', '--health-interval', '1s', '--health-timeout', '1s', '--health-retries', '3', 'alpine:3.20', 'sleep', '120')
seq = timeline(n, lambda h: h == 'unhealthy'); print(f'  --health-cmd "exit 1" interval=1s retries=3:状态变化 {fmt(seq)}')
h = health(n); print(f'  FailingStreak={h["FailingStreak"]};日志条数={len(h["Log"])};容器 Status={out("inspect", "--format", "{{.State.Status}}", n)}(unhealthy 但仍在运行)')
dk('rm', '-f', n)
print('== 三:检查命令超时')
n = 'bwlab-c65c'
dk('run', '-d', '--name', n, *LAB, '--health-cmd', 'sleep 5', '--health-interval', '1s', '--health-timeout', '1s', '--health-retries', '1', 'alpine:3.20', 'sleep', '120')
seq = timeline(n, lambda h: h == 'unhealthy'); print(f'  --health-cmd "sleep 5" --health-timeout 1s retries=1:状态变化 {fmt(seq)}')
h = health(n); print(f'  日志:ExitCode={h["Log"][-1]["ExitCode"]} Output={h["Log"][-1]["Output"]!r}')
dk('rm', '-f', n)
print('== 四:--health-start-period 期间的失败不计入')
for sp in ('0s', '6s'):
    n = 'bwlab-c65d' + sp
    dk('run', '-d', '--name', n, *LAB, '--health-cmd', 'exit 1', '--health-interval', '1s', '--health-timeout', '1s', '--health-retries', '2', '--health-start-period', sp, 'alpine:3.20', 'sleep', '120')
    seq = timeline(n, lambda h: h == 'unhealthy', maxs=20); print(f'  start-period={sp}(一直失败,retries=2):状态变化 {fmt(seq)}')
    dk('rm', '-f', n)
print('== 五:unhealthy 的容器会被重启吗,docker events 里是什么')
n = 'bwlab-c65e'
t1 = int(time.time()) - 1
dk('run', '-d', '--name', n, *LAB, '--restart', 'always', '--health-cmd', 'exit 1', '--health-interval', '1s', '--health-retries', '2', 'alpine:3.20', 'sleep', '120')
timeline(n, lambda h: h == 'unhealthy'); time.sleep(4)
rc, o = dk('events', '--since', str(t1), '--until', str(int(time.time()) + 1), '--filter', f'container={n}', '--format', '{{.Action}}', timeout=30)
print('  --restart always 且健康检查一直失败:' + f'RestartCount={out("inspect", "--format", "{{.RestartCount}}", n)};Status={out("inspect", "--format", "{{.State.Status}}", n)};events:' + ' → '.join(dict.fromkeys(l.strip() for l in o.splitlines() if l.strip() and not l.startswith('exec_'))))
dk('rm', '-f', n)
purge()
