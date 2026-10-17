import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k45')
cn, _ = up('main')
NS = ns('k45')
def dep(name, replicas, env, strat='', min_ready=0, delay=3):
    return f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: {name}, namespace: {NS}}}
spec:
  replicas: {replicas}
  minReadySeconds: {min_ready}
{strat}  selector: {{matchLabels: {{app: {name}}}}}
  template:
    metadata: {{labels: {{app: {name}}}}}
    spec:
      terminationGracePeriodSeconds: 2
      containers:
      - name: c
        image: busybox:1.36
        env: [{{name: V, value: {env}}}]
        command: [sh, -c, "sleep 3600"]
        readinessProbe: {{exec: {{command: ["true"]}}, initialDelaySeconds: {delay}, periodSeconds: 1}}
'''
def snap(name):
    ps = kj('get', 'pods', '-n', NS, '-l', f'app={name}')['items']; tot = 0; rd = 0; old = 0; new = 0
    for p in ps:
        if p['metadata'].get('deletionTimestamp'): continue
        tot += 1; v = next((e['value'] for e in p['spec']['containers'][0]['env'] if e['name'] == 'V'), '?')
        if v == 'v2': new += 1
        else: old += 1
        if any(c['type'] == 'Ready' and c['status'] == 'True' for c in p['status'].get('conditions', [])): rd += 1
    return tot, rd, old, new
def rollout(name, replicas, strat, min_ready=0, secs=90):
    k('apply', '-f', '-', input=dep(name, replicas, 'v1', strat, min_ready)); until(lambda: kj('get', 'deploy', name, '-n', NS)['status'].get('readyReplicas') == replicas, 90); time.sleep(2)
    t0 = time.time(); k('apply', '-f', '-', input=dep(name, replicas, 'v2', strat, min_ready)); seq = []; last = None
    while time.time() - t0 < secs:
        s = snap(name)
        if s != last: seq.append((round(time.time() - t0, 1), s)); last = s
        if s[3] == replicas and s[0] == replicas and s[1] == replicas and time.time() - t0 > 3: break
        time.sleep(0.15)
    mx = max(s[0] for t, s in seq); mn = min(s[1] for t, s in seq)
    return seq, mx, mn, seq[-1][0]
print(f'集群 {cn};Deployment 滚动更新由 maxSurge(最多比期望多几个)与 maxUnavailable(最多少几个可用)两个参数控制;百分比的取整方向不同')
CASES = [('d-default', 6, '', '默认(25% / 25%)'), ('d-s1u0', 6, '  strategy: {type: RollingUpdate, rollingUpdate: {maxSurge: 1, maxUnavailable: 0}}\n', 'maxSurge 1 / maxUnavailable 0'), ('d-s0u1', 6, '  strategy: {type: RollingUpdate, rollingUpdate: {maxSurge: 0, maxUnavailable: 1}}\n', 'maxSurge 0 / maxUnavailable 1'), ('d-s100', 6, '  strategy: {type: RollingUpdate, rollingUpdate: {maxSurge: "100%", maxUnavailable: 0}}\n', 'maxSurge 100% / maxUnavailable 0')]
print('== 一:6 个副本,改一个环境变量触发更新——四种参数下 Pod 总数的峰值、可用数的谷值与耗时(就绪探针延迟 3 秒)')
res = {}
for nm, rep, st, desc in CASES:
    seq, mx, mn, total = rollout(nm, rep, st); res[nm] = (mx, mn, total)
    print(f'  {desc}:Pod 总数峰值 {mx}(期望 6,多出 {mx - 6});Ready 的最低值 {mn}(少了 {6 - mn});全部换完用了 {total:.1f} 秒')
    k('delete', 'deploy', nm, '-n', NS, '--wait=true', timeout=60)
print('  默认的 25% 在 6 个副本上:maxSurge 向上取整 = ceil(1.5) = 2,maxUnavailable 向下取整 = floor(1.5) = 1,所以峰值 8、谷值 5')

print('== 二:一次更新的完整时间线(默认参数,6 个副本)——(总数, Ready, 旧, 新)')
seq, mx, mn, total = rollout('d-trace', 6, '')
for t, s in seq[:14]: print(f'    +{t:5.1f}s 总数={s[0]} Ready={s[1]} 旧={s[2]} 新={s[3]}')
rs = kj('get', 'rs', '-n', NS, '-l', 'app=d-trace')['items']
print('  更新后的 ReplicaSet:' + '; '.join(f'{r["metadata"]["name"][-10:]} replicas={r["spec"]["replicas"]} 版本={r["metadata"]["annotations"].get("deployment.kubernetes.io/revision")}' for r in sorted(rs, key=lambda r: int(r['metadata']['annotations'].get('deployment.kubernetes.io/revision', 0)))))
k('delete', 'deploy', 'd-trace', '-n', NS, '--wait=true', timeout=60)

print('== 三:Recreate——先全部停掉再重建,中间有一段完全不可用的时间')
seq, mx, mn, total = rollout('d-recreate', 6, '  strategy: {type: Recreate}\n')
zero = [t for t, s in seq if s[1] == 0]
print(f'  Recreate:Pod 总数峰值 {mx}(没有多出来的),Ready 最低值 {mn};Ready=0 的状态从 +{zero[0]:.1f}s 持续到 +{seq[-1][0] - 0:.1f}s 附近;全部换完用了 {total:.1f} 秒')
print('  时间线(总数, Ready, 旧, 新):' + ' → '.join(f'{s}@{t}s' for t, s in seq[:8]))
k('delete', 'deploy', 'd-recreate', '-n', NS, '--wait=true', timeout=60)

print('== 四:minReadySeconds——新 Pod Ready 之后还要“稳定”几秒才算可用')
for nm, mr in (('m0', 0), ('m5', 5)):
    seq, mx, mn, total = rollout(nm, 4, '  strategy: {type: RollingUpdate, rollingUpdate: {maxSurge: 1, maxUnavailable: 0}}\n', min_ready=mr)
    print(f'  minReadySeconds={mr}、4 个副本、maxSurge 1 / maxUnavailable 0:全部换完用了 {total:.1f} 秒')
    k('delete', 'deploy', nm, '-n', NS, '--wait=true', timeout=60)
rmns(NS)
