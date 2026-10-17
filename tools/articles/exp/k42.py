import sys, os, re, time, json, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k42')
cn, dt_up = up('sched', cfg=config(workers=4))
load('busybox:1.36'); wait_nodes_ready()
NODES = ['kx-sched-worker', 'kx-sched-worker2', 'kx-sched-worker3', 'kx-sched-worker4']
NS = ns('k42')
def ds(name='ds', env='v1', strat='', sel='', delay=0, grace=3):
    return f'''apiVersion: apps/v1
kind: DaemonSet
metadata: {{name: {name}, namespace: {NS}}}
spec:
  selector: {{matchLabels: {{app: {name}}}}}
{strat}  template:
    metadata: {{labels: {{app: {name}}}}}
    spec:
      terminationGracePeriodSeconds: {grace}
{sel}      containers:
      - name: c
        image: busybox:1.36
        env: [{{name: V, value: {env}}}]
        command: [sh, -c, "sleep 3600"]
        readinessProbe: {{exec: {{command: ["true"]}}, initialDelaySeconds: {delay}, periodSeconds: 1}}
'''
def pods(name='ds'):
    return {p['metadata']['name']: p for p in kj('get', 'pods', '-n', NS, '-l', f'app={name}')['items']}
def pnodes(name='ds'): return sorted(p['spec'].get('nodeName', '?').replace('kx-sched-', '') for p in pods(name).values() if not p['metadata'].get('deletionTimestamp'))
print(f'集群 {cn}(1 控制面 + 4 个 worker)')
print('== 一:每个符合条件的节点一个 Pod——DaemonSet 控制器给 Pod 加的东西')
k('apply', '-f', '-', input=ds()); until(lambda: len(pnodes()) == 4, 60); time.sleep(3)
print(f'  DaemonSet ds 创建后 Pod 所在节点:{pnodes()}(控制面有污点,没有被选中)')
d = kj('get', 'ds', 'ds', '-n', NS); print(f'  status:desiredNumberScheduled={d["status"]["desiredNumberScheduled"]} currentNumberScheduled={d["status"]["currentNumberScheduled"]} numberReady={d["status"]["numberReady"]} updatedNumberScheduled={d["status"].get("updatedNumberScheduled")}')
p = next(iter(pods().values()))
print(f'  某个 Pod 的 spec.nodeName={p["spec"]["nodeName"].replace("kx-sched-", "")};控制器加的 affinity:{json.dumps(p["spec"]["affinity"], ensure_ascii=False)}')
print(f'  控制器加的 tolerations:' + '; '.join(f'{t["key"]}:{t["effect"]}' for t in p['spec']['tolerations']))

print('== 二:用 nodeSelector 限定范围——给节点打标签,Pod 立刻出现;去掉标签,Pod 立刻被删')
k('delete', 'ds', 'ds', '-n', NS, '--wait=true', timeout=60)
k('apply', '-f', '-', input=ds('dsel', sel='      nodeSelector: {k42: \"yes\"}\n')); time.sleep(4); print(f'  DaemonSet dsel(nodeSelector k42=yes),还没有节点有这个标签:Pod 在 {pnodes("dsel")}')
t0 = time.time(); k('label', 'node', NODES[1], 'k42=yes'); v, dt = until(lambda: 'worker2' in pnodes('dsel'), 20, 0.1)
print(f'  给 worker2 打标签后 {dt:.1f} 秒,Pod 出现在 {pnodes("dsel")}')
k('label', 'node', NODES[2], 'k42=yes'); until(lambda: len(pnodes('dsel')) == 2, 20, 0.1)
t0 = time.time(); k('label', 'node', NODES[1], 'k42-'); v, dt = until(lambda: 'worker2' not in pnodes('dsel'), 30, 0.1)
print(f'  再给 worker3 打标签,然后去掉 worker2 的标签:{dt:.1f} 秒后 Pod 在 {pnodes("dsel")}(不匹配的节点上的 Pod 被删除)')
k('label', 'node', NODES[2], 'k42-'); k('delete', 'ds', 'dsel', '-n', NS, '--wait=true', timeout=60)

print('== 三:NoExecute 污点——DaemonSet 的 Pod 只自带对 not-ready / unreachable 等的容忍')
k('apply', '-f', '-', input=ds()); until(lambda: len(pnodes()) == 4, 60); time.sleep(2)
t0 = time.time(); k('taint', 'node', NODES[0], 'k42=x:NoSchedule')
time.sleep(3); print(f'  worker 打上 k42=x:NoSchedule:已有的 Pod 还在:{pnodes()}')
k('taint', 'node', NODES[0], 'k42-'); k('taint', 'node', NODES[0], 'k42=x:NoExecute'); v, dt = until(lambda: 'worker' not in pnodes(), 20, 0.1)
time.sleep(3); print(f'  换成 NoExecute 污点:{dt:.1f} 秒后 worker 上的 Pod 被驱逐,{"DaemonSet 没有把它重建(新建的 Pod 同样容忍不了):Pod 在 " + str(pnodes()) if "worker" not in pnodes() else "仍然在"}')
d = kj('get', 'ds', 'ds', '-n', NS); print(f'    DaemonSet 状态:desired={d["status"]["desiredNumberScheduled"]} current={d["status"]["currentNumberScheduled"]}(控制器知道 worker 不再符合条件)')
k('taint', 'node', NODES[0], 'k42-'); v, dt = until(lambda: 'worker' in pnodes(), 20, 0.1); print(f'  去掉污点后 {dt:.1f} 秒,worker 上又有了 Pod:{pnodes()}')
k('delete', 'ds', 'ds', '-n', NS, '--wait=true', timeout=60)

print('== 四:更新策略——RollingUpdate 的 maxUnavailable,与 OnDelete')
def rollout(name, env, secs=40):
    before = {p['metadata']['name']: p['spec']['nodeName'] for p in pods(name).values()}
    t0 = time.time(); k('apply', '-f', '-', input=ds(name, env, strat=STRAT[name], delay=3)); seq = []; last = None
    while time.time() - t0 < secs:
        d = kj('get', 'ds', name, '-n', NS)['status']; cur = (d.get('updatedNumberScheduled', 0), d.get('numberReady', 0), d.get('numberUnavailable', 0))
        if cur != last: seq.append((round(time.time() - t0, 1), cur)); last = cur
        if cur[0] == 4 and cur[1] == 4: break
        time.sleep(0.2)
    return seq
STRAT = {'ru1': '  updateStrategy: {type: RollingUpdate, rollingUpdate: {maxUnavailable: 1}}\n', 'ru2': '  updateStrategy: {type: RollingUpdate, rollingUpdate: {maxUnavailable: 2}}\n', 'od': '  updateStrategy: {type: OnDelete}\n'}
for nm in ('ru1', 'ru2'):
    k('apply', '-f', '-', input=ds(nm, 'v1', strat=STRAT[nm], delay=3)); until(lambda: kj('get', 'ds', nm, '-n', NS)['status'].get('numberReady') == 4, 60); time.sleep(2)
    seq = rollout(nm, 'v2'); print(f'  {nm}(maxUnavailable={nm[-1]}):改了环境变量触发更新,(updatedNumberScheduled, numberReady, numberUnavailable) 的变化:' + ' → '.join(f'{c}@{t}s' for t, c in seq) + f';共 {seq[-1][0]} 秒')
    k('delete', 'ds', nm, '-n', NS, '--wait=true', timeout=60)
k('apply', '-f', '-', input=ds('od', 'v1', strat=STRAT['od'], delay=1)); until(lambda: kj('get', 'ds', 'od', '-n', NS)['status'].get('numberReady') == 4, 60)
old = {p['metadata']['name'] for p in pods('od').values()}
k('apply', '-f', '-', input=ds('od', 'v2', strat=STRAT['od'], delay=1)); time.sleep(6)
d = kj('get', 'ds', 'od', '-n', NS)['status']; cur = {p['metadata']['name'] for p in pods('od').values()}
print(f'  OnDelete:改了模板 6 秒后 updatedNumberScheduled={d.get("updatedNumberScheduled", 0)}/{d["desiredNumberScheduled"]},Pod 没变(旧 Pod 全在:{old == cur})')
victim = sorted(old)[0]; k('delete', 'pod', victim, '-n', NS, '--wait=true', timeout=60); time.sleep(5); d = kj('get', 'ds', 'od', '-n', NS)['status']
print(f'  手动删掉其中一个 Pod 之后:updatedNumberScheduled={d.get("updatedNumberScheduled", 0)}/{d["desiredNumberScheduled"]}(只有被删掉重建的那个换成了新模板)')
rmns(NS)
