import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k47')
cn, _ = up('main')
NS = ns('k47')
def pod(name, labels='app: r'):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}, labels: {{{labels}}}}}\nspec:\n  terminationGracePeriodSeconds: 0\n  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n'
def rs(name, replicas, sel='app: r', extra_label=''):
    return f'apiVersion: apps/v1\nkind: ReplicaSet\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  replicas: {replicas}\n  selector: {{matchLabels: {{{sel}}}}}\n  template:\n    metadata: {{labels: {{{sel}{extra_label}}}}}\n    spec:\n      terminationGracePeriodSeconds: 0\n      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n'
def pods(sel='app=r'): return {p['metadata']['name']: p for p in kj('get', 'pods', '-n', NS, '-l', sel)['items']}
def owner(p):
    o = [r for r in p['metadata'].get('ownerReferences', [])]; return f'{o[0]["kind"]}/{o[0]["name"]}(controller={o[0].get("controller")})' if o else '(没有所有者)'
def show(sel='app=r'):
    return '; '.join(f'{n}→{owner(p)}' for n, p in sorted(pods(sel).items()) if not p['metadata'].get('deletionTimestamp'))
print(f'集群 {cn};ReplicaSet 靠 selector 找自己的 Pod,并且只“收养”没有控制器所有者的 Pod')

print('== 一:先有一个标签匹配的裸 Pod,再创建 replicas=2 的 ReplicaSet——收养它,只再创建 1 个')
k('apply', '-f', '-', input=pod('stray')); until(lambda: 'stray' in pods(), 30); time.sleep(2)
uid0 = pods()['stray']['metadata']['uid']; print(f'  裸 Pod stray(标签 app=r):{show()}')
k('apply', '-f', '-', input=rs('rs-a', 2)); time.sleep(5)
print(f'  创建 rs-a(replicas=2,selector app=r)之后:{show()}')
print(f'  stray 的 uid 没变:{pods()["stray"]["metadata"]["uid"] == uid0};总共 {len([p for p in pods().values() if not p["metadata"].get("deletionTimestamp")])} 个 Pod(收养 1 个 + 新建 1 个);rs-a status:replicas={kj("get", "rs", "rs-a", "-n", NS)["status"]["replicas"]} readyReplicas={kj("get", "rs", "rs-a", "-n", NS)["status"].get("readyReplicas")}')
k('scale', 'rs/rs-a', '-n', NS, '--replicas=1'); time.sleep(5)
print(f'  把 rs-a 缩到 1:{show()}(被删掉的是哪一个由 ReplicaSet 按规则选,这次保留的是上面那一个)')
k('scale', 'rs/rs-a', '-n', NS, '--replicas=2'); time.sleep(4)

print('== 二:改标签 = 脱离 ReplicaSet——它会立刻补一个新的,被“放生”的 Pod 成了孤儿')
names = sorted(pods()); victim = names[0]
k('label', 'pod', victim, '-n', NS, 'app=other', '--overwrite'); time.sleep(4)
print(f'  把 {victim} 的标签 app 改成 other:app=r 的 Pod:{show()}')
print(f'    {victim} 现在:{owner(pods("app=other")[victim])},仍在运行;ReplicaSet 补了一个新的(共 {len(pods())} 个 app=r)')
k('label', 'pod', victim, '-n', NS, 'app=r', '--overwrite'); time.sleep(5)
print(f'  再把标签改回 app=r(它没有所有者了,而 ReplicaSet 现在有 3 个匹配的):{show()}')
print(f'    ReplicaSet 删掉了多余的一个;{victim} 还在吗:{victim in pods()}')

print('== 三:--cascade=orphan 删除 ReplicaSet,新的 ReplicaSet 接管同样的 Pod(uid 不变)')
uids = {n: p['metadata']['uid'] for n, p in pods().items() if not p['metadata'].get('deletionTimestamp')}
k('delete', 'rs', 'rs-a', '-n', NS, '--cascade=orphan'); time.sleep(3)
print(f'  删除 rs-a(orphan):Pod {show()}')
k('apply', '-f', '-', input=rs('rs-b', 2)); time.sleep(4)
uids2 = {n: p['metadata']['uid'] for n, p in pods().items() if not p['metadata'].get('deletionTimestamp')}
print(f'  创建 rs-b(同样的 selector):{show()};Pod 的 uid 全都没变:{uids == uids2}(没有重建)')

print('== 四:已经有控制器所有者的 Pod 不会被收养——两个 selector 一样的 ReplicaSet 各管各的')
k('delete', 'rs', 'rs-b', '-n', NS, '--wait=true', timeout=60); k('delete', 'pod', '-l', 'app=r', '-n', NS, '--wait=true', timeout=60)
k('apply', '-f', '-', input=rs('rs-x', 2)); time.sleep(3); k('apply', '-f', '-', input=rs('rs-y', 2)); time.sleep(5)
print(f'  rs-x、rs-y 都是 replicas=2、selector app=r:总共 {len(pods())} 个 Pod:{show()}')
print(f'    rs-x status.replicas={kj("get", "rs", "rs-x", "-n", NS)["status"]["replicas"]};rs-y status.replicas={kj("get", "rs", "rs-y", "-n", NS)["status"]["replicas"]}(各自只数自己所有的 Pod)')
k('apply', '-f', '-', input=pod('stray2')); t0 = time.time(); seq = []; last = None
while time.time() - t0 < 6:
    p = kj('get', 'pod', 'stray2', '-n', NS)
    cur = 'NotFound' if not p else (owner(p) + (' 已被设上 deletionTimestamp' if p['metadata'].get('deletionTimestamp') else ''))
    if cur != last: seq.append((round(time.time() - t0, 1), cur)); last = cur
    if cur == 'NotFound': break
    time.sleep(0.1)
print('  再创建一个标签匹配的裸 Pod stray2(现在 rs-x、rs-y 都已经满足 replicas=2):' + ' → '.join(f'{c}(+{t}s)' for t, c in seq))
evs = [e for e in kj('get', 'events', '-n', NS)['items'] if 'stray2' in e.get('message', '')]
print(f'    ReplicaSet 的事件里提到 stray2 的:' + (' | '.join(f'{e["involvedObject"]["name"]} {e["reason"]}: {e["message"]}' for e in evs) or '(没有)'))
print(f'    最后:{show()}(总共 {len(pods())} 个,仍然是 4 个)')
rmns(NS)
