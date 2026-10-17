import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c29')
img('alpine:3.20')
purge()
def state(n): return json.loads(out('inspect', '--format', '{{json .}}', n))
print('== 一:不同重启策略 × 退出码,等 5 秒后的状态(Docker Engine 29.8.2)')
rows = []
for pol in ('no', 'on-failure:2', 'always', 'unless-stopped'):
    for code in (0, 1):
        n = f'bwlab-c29-{pol.replace(":", "")}-{code}'
        dk('run', '-d', '--name', n, *LAB, '--restart', pol, 'alpine:3.20', 'sh', '-c', f'exit {code}')
        rows.append((pol, code, n))
time.sleep(5)
for pol, code, n in rows:
    j = state(n); s = j['State']
    print(f'  --restart {pol:15s} 命令 exit {code}:Status={s["Status"]:10s} RestartCount={j["RestartCount"]}')
for pol, code, n in rows: dk('rm', '-f', n)
print('== 二:退避时间:always + 总是失败的命令,每次启动的时间间隔')
t1 = int(time.time()) - 1
n = 'bwlab-c29-bo'
dk('run', '-d', '--name', n, *LAB, '--restart', 'always', 'alpine:3.20', 'sh', '-c', 'exit 1')
time.sleep(14)
j = state(n); cnt = j['RestartCount']
dk('rm', '-f', n)
t2 = int(time.time()) + 1
rc, o = dk('events', '--since', str(t1), '--until', str(t2), '--filter', f'container={n}', '--filter', 'event=start', '--format', '{{.TimeNano}}', timeout=60)
ts = [int(x) for x in o.split()]
iv = [(b - a) / 1e6 for a, b in zip(ts, ts[1:])]
print(f'  14 秒内共启动 {len(ts)} 次,RestartCount={cnt}')
print(f'  相邻两次 start 的间隔(ms):{[round(x) for x in iv]}')
print(f'  每个间隔与前一个的比值:{[round(b / a, 2) for a, b in zip(iv, iv[1:])]}')
print('== 三:docker stop 一个 always 的容器,它会被重新拉起吗')
n = 'bwlab-c29-st'
dk('run', '-d', '--name', n, *LAB, '--restart', 'always', 'alpine:3.20', 'sleep', '600')
dk('stop', '-t', '1', n); time.sleep(3)
print(f'  docker stop 3 秒后:Status={state(n)["State"]["Status"]}(手动停止的容器不会被重启策略拉起)')
dk('start', n); time.sleep(1)
print(f'  docker start 之后:Status={state(n)["State"]["Status"]}')
dk('kill', n); time.sleep(3)
j = state(n)
print(f'  docker kill 之后 3 秒:Status={j["State"]["Status"]} RestartCount={j["RestartCount"]}(docker kill 之后没有被重新拉起)')
dk('update', '--restart', 'no', n); dk('kill', n); time.sleep(1)
print(f'  docker update --restart no 之后再 kill:Status={state(n)["State"]["Status"]};策略现在是 {out("inspect", "--format", "{{.HostConfig.RestartPolicy.Name}}", n)}')
dk('rm', '-f', n)
print('== 四:on-failure 的次数上限与 --rm 的冲突')
n = 'bwlab-c29-of'
dk('run', '-d', '--name', n, *LAB, '--restart', 'on-failure:3', 'alpine:3.20', 'sh', '-c', 'exit 1'); time.sleep(5)
j = state(n); print(f'  on-failure:3 + 总失败:Status={j["State"]["Status"]} RestartCount={j["RestartCount"]}(1 次原始启动加 3 次重启共 4 次执行)')
dk('rm', '-f', n)
rc, o = dk('run', '--rm', '--restart', 'always', 'alpine:3.20', 'true'); print(f'  --rm 与 --restart always 同时用 → 退出码 {rc};{next((l for l in o.splitlines() if "docker:" in l), o)[:110]}')
purge()
