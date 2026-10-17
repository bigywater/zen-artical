import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k44')
cn, _ = up('sched', cfg=config(workers=4)); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k44')
def sts(name='web', replicas=4, env='v1', update='', policy='OrderedReady', probe='true', delay=2):
    return f'''apiVersion: v1
kind: Service
metadata: {{name: {name}, namespace: {NS}}}
spec: {{clusterIP: None, selector: {{app: {name}}}, ports: [{{port: 80}}]}}
---
apiVersion: apps/v1
kind: StatefulSet
metadata: {{name: {name}, namespace: {NS}}}
spec:
  serviceName: {name}
  replicas: {replicas}
  podManagementPolicy: {policy}
{update}  selector: {{matchLabels: {{app: {name}}}}}
  template:
    metadata: {{labels: {{app: {name}}}}}
    spec:
      terminationGracePeriodSeconds: 1
      containers:
      - name: c
        image: busybox:1.36
        env: [{{name: V, value: {env}}}]
        command: [sh, -c, "sleep 3600"]
        readinessProbe: {{exec: {{command: [sh, -c, "{probe}"]}}, initialDelaySeconds: {delay}, periodSeconds: 1}}
'''
def pods(name='web'): return {p['metadata']['name']: p for p in kj('get', 'pods', '-n', NS, '-l', f'app={name}')['items']}
def ready(p): return any(c['type'] == 'Ready' and c['status'] == 'True' for c in p['status'].get('conditions', [])) and not p['metadata'].get('deletionTimestamp')
def revs(name='web'):
    ps = pods(name); return {n: p['metadata']['labels'].get('controller-revision-hash', '?')[-6:] for n, p in sorted(ps.items())}
def env_of(name='web'):
    return {n: next((e['value'] for e in p['spec']['containers'][0].get('env', []) if e['name'] == 'V'), '?') for n, p in sorted(pods(name).items())}
def status(name='web'):
    s = kj('get', 'sts', name, '-n', NS)['status']; return f'currentRevision={s.get("currentRevision", "")[-6:]} updateRevision={s.get("updateRevision", "")[-6:]} currentReplicas={s.get("currentReplicas")} updatedReplicas={s.get("updatedReplicas")} readyReplicas={s.get("readyReplicas")}'
def wait_all(name='web', n=4, t=90): until(lambda: len([p for p in pods(name).values() if ready(p)]) == n, t)
def watch_update(name, apply_yaml, secs=60, done=None):
    """应用新模板,记录每个 Pod 的 uid 变化(被替换)的先后和时间。"""
    uid0 = {n: p['metadata']['uid'] for n, p in pods(name).items()}; t0 = time.time(); k('apply', '-f', '-', input=apply_yaml); seen = {}
    while time.time() - t0 < secs:
        for n, p in pods(name).items():
            if n in uid0 and p['metadata']['uid'] != uid0[n] and n not in seen and ready(p): seen[n] = time.time() - t0
        if done and done(seen): break
        time.sleep(0.2)
    return seen
print(f'集群 {cn};StatefulSet 的更新:先 Pod 模板变了才触发,默认 RollingUpdate 从最大序号开始逐个替换,每个 Ready 之后才换下一个')

print('== 一:RollingUpdate(默认)——从大序号到小序号,一次一个')
k('apply', '-f', '-', input=sts()); wait_all(); print(f'  初始 4 个副本:revision={revs()};{status()}')
seen = watch_update('web', sts(env='v2'), 90, lambda s: len(s) == 4)
print('  改 env V=v2 触发更新,各个 Pod 被替换成新 Pod 并 Ready 的时刻:' + ';'.join(f'{n} +{t:.1f}s' for n, t in sorted(seen.items(), key=lambda x: x[1])))
print(f'  更新后:revision={revs()};env={env_of()};{status()}')

print('== 二:partition——只更新序号 ≥ partition 的 Pod(金丝雀)')
k('delete', 'sts', 'web', '-n', NS, '--wait=true', timeout=90)
k('apply', '-f', '-', input=sts(env='v1')); wait_all()
part = '  updateStrategy: {type: RollingUpdate, rollingUpdate: {partition: 2}}\n'
seen = watch_update('web', sts(env='v2', update=part), 60, lambda s: len(s) == 2); time.sleep(5)
print(f'  partition=2、改 env V=v2:被替换的 Pod {sorted(seen)};env={env_of()};{status()}')
k('patch', 'sts', 'web', '-n', NS, '--type=merge', '-p', '{"spec":{"updateStrategy":{"rollingUpdate":{"partition":0}}}}'); wait_all(); time.sleep(8)
print(f'  把 partition 改成 0:env={env_of()};{status()}')

print('== 三:OnDelete——模板变了也不动,删一个才换一个')
k('delete', 'sts', 'web', '-n', NS, '--wait=true', timeout=90)
od = '  updateStrategy: {type: OnDelete}\n'
k('apply', '-f', '-', input=sts(env='v1', update=od)); wait_all()
k('apply', '-f', '-', input=sts(env='v2', update=od)); time.sleep(8)
print(f'  改 env V=v2 后 8 秒:env={env_of()};{status()}')
k('delete', 'pod', 'web-1', '-n', NS, '--wait=true', timeout=60); wait_all(); time.sleep(2)
print(f'  手动删掉 web-1 之后:env={env_of()};{status()}')

print('== 四:更新到一个坏模板——卡住,以及修好模板之后怎么办')
k('delete', 'sts', 'web', '-n', NS, '--wait=true', timeout=90)
k('apply', '-f', '-', input=sts(env='v1')); wait_all()
k('apply', '-f', '-', input=sts(env='bad', probe='exit 1')); time.sleep(20)
ps = pods(); print(f'  更新成一个就绪探针永远失败的模板:20 秒后 env={env_of()};ready 的 Pod {sorted(n for n, p in ps.items() if ready(p))};{status()}')
print(f'    web-3 是新的但不 Ready,更新停在这里:web-2、web-1、web-0 都还是旧模板(没有继续)')
t0 = time.time(); k('apply', '-f', '-', input=sts(env='v3')); time.sleep(25)
ps = pods(); print(f'  再把模板改成好的(env V=v3):25 秒后 env={env_of()};ready 的 Pod {sorted(n for n, p in ps.items() if ready(p))};{status()}')
print('    web-3 仍然是坏的 bad:StatefulSet 控制器不会替换一个不健康的 Pod,哪怕模板已经改好了——必须手动删掉它')
t0 = time.time(); k('delete', 'pod', 'web-3', '-n', NS, '--wait=true', timeout=60)
v, dt = until(lambda: set(env_of().values()) == {'v3'} and len([p for p in pods().values() if ready(p)]) == 4, 90, 0.5)
print(f'  手动删掉 web-3 之后 {dt:.0f} 秒:env={env_of()};{status()}(更新继续从 web-3 往 web-0 推进完成)')
rmns(NS)
