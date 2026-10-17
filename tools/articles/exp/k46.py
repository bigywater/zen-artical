import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k46')
cn, _ = up('main')
NS = ns('k46')
def dep(name='app', env='v1', limit=None, extra=''):
    return f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: {name}, namespace: {NS}}}
spec:
  replicas: 2
{("  revisionHistoryLimit: %s" % limit + chr(10)) if limit is not None else ""}  selector: {{matchLabels: {{app: {name}}}}}
  template:
    metadata: {{labels: {{app: {name}}}}}
    spec:
      terminationGracePeriodSeconds: 0
      containers:
      - name: c
        image: busybox:1.36
        env: [{{name: V, value: {env}}}]
        command: [sh, -c, "sleep 3600"]
{extra}'''
def rss(name='app'):
    items = kj('get', 'rs', '-n', NS, '-l', f'app={name}')['items']
    return sorted(((int(r['metadata']['annotations'].get('deployment.kubernetes.io/revision', 0)), r['metadata']['name'][-5:], r['spec']['replicas'], next((e['value'] for e in r['spec']['template']['spec']['containers'][0]['env'] if e['name'] == 'V'), '?')) for r in items))
def settle(name='app'): until(lambda: kj('get', 'deploy', name, '-n', NS)['status'].get('updatedReplicas') == 2 and kj('get', 'deploy', name, '-n', NS)['status'].get('readyReplicas') == 2 and kj('get', 'deploy', name, '-n', NS)['status'].get('replicas') == 2, 60); time.sleep(2)
print(f'集群 {cn};Deployment 的“历史”就是它名下的 ReplicaSet:每个 Pod 模板版本一个 ReplicaSet,revision 记在注解里')
print('== 一:每次改模板多一个 ReplicaSet,旧的缩到 0 但保留')
k('apply', '-f', '-', input=dep(env='v1')); settle()
for v in ('v2', 'v3', 'v4'): k('apply', '-f', '-', input=dep(env=v)); settle()
print('  4 个版本之后的 ReplicaSet(revision, 名字后缀, replicas, env V):' + '; '.join(str(x) for x in rss()))
rc, o = k('rollout', 'history', 'deploy/app', '-n', NS); print('  kubectl rollout history:'); [print('    ' + l) for l in o.strip().splitlines()]
rc, o = k('rollout', 'history', 'deploy/app', '-n', NS, '--revision=2'); print('  kubectl rollout history --revision=2(那一版的 Pod 模板):' + ' | '.join(l.strip() for l in o.strip().splitlines() if 'V:' in l or 'Image' in l or 'Environment' in l or 'revision' in l.lower()))

print('== 二:回滚(rollout undo)——不是倒退,而是把旧 ReplicaSet 当成最新一版')
rc, o = k('rollout', 'undo', 'deploy/app', '-n', NS, '--to-revision=2'); print(f'  kubectl rollout undo --to-revision=2:{o.strip().splitlines()[0]}(另外 kubectl 打印了一条 Warning:这个 Deployment 是用 kubectl apply 管理的,undo 不会更新 last-applied 注解,之后再 apply 要小心)'); settle()
print('  之后的 ReplicaSet:' + '; '.join(str(x) for x in rss()))
print('  (revision 2 的 ReplicaSet 被重新启用并改成了最新的 revision 5,而不是新建;当前运行的 env=' + ko('get', 'pods', '-n', NS, '-l', 'app=app', '-o', 'jsonpath={.items[0].spec.containers[0].env[0].value}') + ')')
rc, o = k('rollout', 'undo', 'deploy/app', '-n', NS); settle(); print(f'  不带 --to-revision 再 undo 一次:回到上一个版本;ReplicaSet:' + '; '.join(str(x) for x in rss()))

print('== 三:revisionHistoryLimit——只保留这么多个旧 ReplicaSet')
k('delete', 'deploy', 'app', '-n', NS, '--wait=true', timeout=60)
k('apply', '-f', '-', input=dep(env='v1', limit=2)); settle()
for v in ('v2', 'v3', 'v4', 'v5', 'v6'): k('apply', '-f', '-', input=dep(env=v, limit=2)); settle()
print('  revisionHistoryLimit=2 改了 5 次之后的 ReplicaSet:' + '; '.join(str(x) for x in rss()) + '(当前这个加最近 2 个旧的,更早的被删掉了)')
rc, o = k('rollout', 'undo', 'deploy/app', '-n', NS, '--to-revision=1'); print(f'  想回滚到已经被删掉的 revision 1:退出码 {rc};{" | ".join(l for l in o.strip().splitlines() if not l.startswith("Warning"))[:160]}')
k('delete', 'deploy', 'app', '-n', NS, '--wait=true', timeout=60)

print('== 四:change-cause 注解与 pause——把几次修改合成一次发布')
k('apply', '-f', '-', input=dep(env='v1')); settle()
k('annotate', 'deploy/app', '-n', NS, 'kubernetes.io/change-cause=初始版本 v1', '--overwrite')
k('apply', '-f', '-', input=dep(env='v2')); k('annotate', 'deploy/app', '-n', NS, 'kubernetes.io/change-cause=升级到 v2', '--overwrite'); settle()
rc, o = k('rollout', 'history', 'deploy/app', '-n', NS); print('  写了 kubernetes.io/change-cause 注解之后的 rollout history:'); [print('    ' + l) for l in o.strip().splitlines()]
k('rollout', 'pause', 'deploy/app', '-n', NS)
k('apply', '-f', '-', input=dep(env='v3')); k('set', 'env', 'deploy/app', '-n', NS, 'EXTRA=1'); time.sleep(5)
print(f'  rollout pause 之后连续改了两次模板(env V=v3、再加 EXTRA=1):ReplicaSet 仍是 {len(rss())} 个,Pod 没动:' + '; '.join(str(x) for x in rss()))
k('rollout', 'resume', 'deploy/app', '-n', NS); settle(); print(f'  rollout resume 之后:{len(rss())} 个 ReplicaSet,两次修改合成了一次发布:' + '; '.join(str(x) for x in rss()))
rmns(NS)
