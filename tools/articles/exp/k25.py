import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k25')
cn, _ = up('main')
NS = ns('k25')
ts = lambda s: datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
def pods(*names): return {n: kj('get', 'pod', n, '-n', NS) for n in names}
print(f'集群 {cn};CrashLoopBackOff 不是 Pod 的失败状态,而是 kubelet 在两次重启之间的等待:每次崩溃后等待时间翻倍,上限 5 分钟')
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: crash, namespace: {NS}}}
spec:
  containers:
  - {{name: c, image: busybox:1.36, command: [sh, -c, "echo started; sleep 1; exit 1"]}}
---
apiVersion: v1
kind: Pod
metadata: {{name: mixed, namespace: {NS}}}
spec:
  containers:
  - {{name: good, image: busybox:1.36, command: [sleep, "3600"]}}
  - {{name: bad, image: busybox:1.36, command: [sh, -c, "exit 2"]}}
---
apiVersion: v1
kind: Pod
metadata: {{name: never, namespace: {NS}}}
spec:
  restartPolicy: Never
  containers: [{{name: c, image: busybox:1.36, command: [sh, -c, "exit 1"]}}]
''')
print('== 一:重启之间的等待时间——每次崩溃后观察到的 (崩溃时刻 → 下一次启动) 间隔')
t_start = time.time(); rows = {}; last = {}; waiting_seq = []; stat_seq = []
while time.time() - t_start < 345:
    p = kj('get', 'pod', 'crash', '-n', NS)
    cs = p['status'].get('containerStatuses', [{}])[0]
    rc_ = cs.get('restartCount', 0); st = cs.get('state', {}); wn = ('waiting:' + st['waiting'].get('reason', '')) if 'waiting' in st else ('running' if 'running' in st else 'terminated:' + st['terminated'].get('reason', ''))
    if not waiting_seq or waiting_seq[-1][1] != wn: waiting_seq.append((round(time.time() - t_start, 1), wn, rc_))
    sc = k('get', 'pod', 'crash', '-n', NS)[1].strip().splitlines()[-1].split()[2]
    if not stat_seq or stat_seq[-1][1] != sc: stat_seq.append((round(time.time() - t_start, 1), sc))
    lt = cs.get('lastState', {}).get('terminated'); 
    if lt and 'running' in st: rows[rc_] = (ts(lt['startedAt']), ts(lt['finishedAt']), ts(st['running']['startedAt']))
    time.sleep(1)
print(f'  Pod crash(容器 sleep 1 后 exit 1,restartPolicy 默认 Always)共观察 {time.time() - t_start:.0f} 秒,restartCount 到 {max(rows) if rows else 0}:')
prev_start = None; first = None
for n in sorted(rows):
    s, f, nx_ = rows[n]
    if first is None: first = s
    print(f'    第 {n} 次重启:上一个容器 运行 {f - s:.0f} 秒后崩溃,等了 {nx_ - f:.0f} 秒才启动新容器(新容器启动时刻 距 Pod 第一次启动 {nx_ - first:.0f} 秒)')
print('  容器 state 的变化(每秒读一次,只记变化):' + ' → '.join(f'{w}(+{t:.0f}s)' for t, w, _ in waiting_seq))
print('  kubectl get pod 的 STATUS 列的变化:' + ' → '.join(f'{w}(+{t:.0f}s)' for t, w in stat_seq))
ev = (kj('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=crash') or {}).get('items', [])
for e in ev:
    if e['reason'] == 'BackOff': print(f'  事件 BackOff:count={e.get("count")};{e["message"]}')

print('== 二:多容器 Pod——崩溃的容器各自退避,好的容器不受影响')
p = kj('get', 'pod', 'mixed', '-n', NS)
print(f'  Pod mixed(good 一直运行,bad 立刻 exit 2):phase={p["status"]["phase"]};kubectl get 的 STATUS=' + k('get', 'pod', 'mixed', '-n', NS)[1].strip().splitlines()[-1].split()[2] + ';READY=' + k('get', 'pod', 'mixed', '-n', NS)[1].strip().splitlines()[-1].split()[1])
for cs in p['status']['containerStatuses']:
    print(f'    容器 {cs["name"]}:restartCount={cs["restartCount"]} state={list(cs["state"])[0]}' + (f'({cs["state"]["waiting"].get("reason")})' if 'waiting' in cs['state'] else '') + f' ready={cs["ready"]}')

print('== 三:restartPolicy=Never 的 Pod 崩溃之后不重启,所以没有 CrashLoopBackOff')
p = kj('get', 'pod', 'never', '-n', NS); cs = p['status']['containerStatuses'][0]
print(f'  Pod never:phase={p["status"]["phase"]};restartCount={cs["restartCount"]};state=terminated(exitCode={cs["state"]["terminated"]["exitCode"]});kubectl get STATUS={k("get", "pod", "never", "-n", NS)[1].strip().splitlines()[-1].split()[2]}')

print('== 四:删除再建一个同样的 Pod——等待时间是从头开始的')
k('delete', 'pod', 'crash', '-n', NS, '--wait=true', timeout=60)
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: crash, namespace: {NS}}}\nspec:\n  containers:\n  - {{name: c, image: busybox:1.36, command: [sh, -c, "echo started; sleep 1; exit 1"]}}\n')
t0 = time.time(); r2 = {}
while time.time() - t0 < 50:
    p = kj('get', 'pod', 'crash', '-n', NS); cs = p['status'].get('containerStatuses', [{}])[0]; st = cs.get('state', {}); lt = cs.get('lastState', {}).get('terminated')
    if lt and 'running' in st: r2[cs['restartCount']] = (ts(lt['finishedAt']), ts(st['running']['startedAt']))
    time.sleep(1)
print('  重新创建的 Pod crash 前 50 秒:' + ';'.join(f'第 {n} 次重启前等了 {b - a:.0f} 秒' for n, (a, b) in sorted(r2.items())) + '(又是从最短的等待开始,不是接着之前的 5 分钟)')
rmns(NS)
