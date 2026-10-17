import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k60')
cn, _ = up('main')
load('busybox:1.36')
def ex(ns_, name, cmd):
    rc, o = k('exec', name, '-n', ns_, '--', 'sh', '-c', cmd); return o.strip()
def watchers():
    rc, o = k('get', '--raw', '/metrics', raw=True); tot = 0
    for l in o.splitlines():
        if l.startswith('apiserver_longrunning_requests{') and 'resource="configmaps"' in l and 'verb="WATCH"' in l and 'scope="resource"' in l: tot += int(float(l.split()[-1]))
    return tot
print(f'集群 {cn};immutable: true 的 ConfigMap/Secret 创建后 data 不能再改;kubelet 因此不用再 watch 它们')
NS = ns('k60')

print('== 一:不可变——能改什么、不能改什么')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: ConfigMap\nmetadata: {{name: fixed, namespace: {NS}, labels: {{a: "1"}}}}\ndata: {{level: info}}\nimmutable: true\n')
rc, o = k('patch', 'cm', 'fixed', '-n', NS, '--type=merge', '-p', '{"data":{"level":"debug"}}'); print(f'  改 data:退出码 {rc};{o.strip()[:200]}')
rc, o = k('patch', 'cm', 'fixed', '-n', NS, '--type=merge', '-p', '{"data":{"new":"x"}}'); print(f'  新增一个键:退出码 {rc};{o.strip()[:200]}')
rc, o = k('patch', 'cm', 'fixed', '-n', NS, '--type=merge', '-p', '{"immutable":false}'); print(f'  把 immutable 改回 false:退出码 {rc};{o.strip()[:200]}')
rc, o = k('patch', 'cm', 'fixed', '-n', NS, '--type=merge', '-p', '{"metadata":{"labels":{"a":"2"},"annotations":{"x":"y"}}}'); print(f'  改 labels/annotations:退出码 {rc};{o.strip()[:100]}(元数据仍可改)')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: ConfigMap\nmetadata: {{name: mutable, namespace: {NS}}}\ndata: {{level: info}}\n')
rc, o = k('patch', 'cm', 'mutable', '-n', NS, '--type=merge', '-p', '{"immutable":true}'); print(f'  可变的 ConfigMap 补上 immutable: true:退出码 {rc};{o.strip()[:100]}(可以单向锁定)')
rc, o = k('patch', 'cm', 'mutable', '-n', NS, '--type=merge', '-p', '{"data":{"level":"debug"}}'); print(f'    锁定之后再改 data:退出码 {rc}')

print('== 二:改内容只能删了重建——运行中的 Pod 不会看到新值')
k('delete', 'cm', 'fixed', 'mutable', '-n', NS)
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: ConfigMap\nmetadata: {{name: fixed, namespace: {NS}}}\ndata: {{level: info}}\nimmutable: true\n---\napiVersion: v1\nkind: ConfigMap\nmetadata: {{name: mutable, namespace: {NS}}}\ndata: {{level: info}}\n---\napiVersion: v1\nkind: Pod\nmetadata: {{name: app, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n  containers:\n  - name: c\n    image: busybox:1.36\n    command: [sleep, "3600"]\n    volumeMounts: [{{name: f, mountPath: /f}}, {{name: m, mountPath: /m}}]\n  volumes:\n  - {{name: f, configMap: {{name: fixed}}}}\n  - {{name: m, configMap: {{name: mutable}}}}\n')
until(lambda: kj('get', 'pod', 'app', '-n', NS)['status'].get('containerStatuses', [{}])[0].get('state', {}).get('running'), 60, 0.3)
print(f'  初始:/f/level={ex(NS, "app", "cat /f/level")!r}(immutable);/m/level={ex(NS, "app", "cat /m/level")!r}(可变)')
k('delete', 'cm', 'fixed', '-n', NS); k('apply', '-f', '-', input=f'apiVersion: v1\nkind: ConfigMap\nmetadata: {{name: fixed, namespace: {NS}}}\ndata: {{level: debug}}\nimmutable: true\n')
k('patch', 'cm', 'mutable', '-n', NS, '--type=merge', '-p', '{"data":{"level":"debug"}}')
t0 = time.time(); v, dt = until(lambda: ex(NS, 'app', 'cat /m/level') == 'debug', 150, 1)
print(f'  删除重建 immutable 的 fixed(值 debug),同时 patch 可变的 mutable 为 debug:可变的那个 {dt:.0f} 秒后 /m/level=debug')
time.sleep(max(0, 100 - (time.time() - t0)))
print(f'    等了 {time.time() - t0:.0f} 秒:/f/level={ex(NS, "app", "cat /f/level")!r}(immutable 的 ConfigMap 被删后重建,挂载的文件依然是旧值);/m/level={ex(NS, "app", "cat /m/level")!r}')
k('delete', 'pod', 'app', '-n', NS, '--wait=true', timeout=60)

print('== 三:对 apiserver 的 watch 数量——20 个 Pod 各挂 1 个自己的 ConfigMap')
def mk(ns_, imm, n=20):
    docs = []
    for i in range(n):
        docs.append(f'apiVersion: v1\nkind: ConfigMap\nmetadata: {{name: c{i}, namespace: {ns_}}}\ndata: {{k: v{i}}}\n' + ('immutable: true\n' if imm else ''))
        docs.append(f'apiVersion: v1\nkind: Pod\nmetadata: {{name: p{i}, namespace: {ns_}}}\nspec:\n  terminationGracePeriodSeconds: 0\n  containers:\n  - {{name: c, image: busybox:1.36, command: [sleep, "3600"], volumeMounts: [{{name: v, mountPath: /v}}]}}\n  volumes: [{{name: v, configMap: {{name: c{i}}}}}]\n')
    return '---\n'.join(docs)
base = watchers(); print(f'  基线:按名字 watch 单个 ConfigMap 的长连接数(apiserver_longrunning_requests,verb=WATCH、scope=resource) {base}')
res = {}
for label, imm in (('可变', False), ('immutable', True)):
    ns_ = ns('k60' + ('i' if imm else 'm'))
    w0 = watchers(); k('apply', '-f', '-', input=mk(ns_, imm))
    ok, dt = until(lambda: sum(1 for p in kj('get', 'pods', '-n', ns_)['items'] if p['status'].get('phase') == 'Running') == 20, 120, 1); time.sleep(10)
    w1 = watchers(); res[label] = w1 - w0
    print(f'  {label}的 20 个 ConfigMap + 20 个 Pod({dt:.0f} 秒全部 Running):按名字 watch ConfigMap 的连接数 {w0} → {w1}(增加 {w1 - w0})')
    k('delete', 'ns', ns_, '--wait=true', timeout=120); time.sleep(5)
print(f'  差别:可变 +{res["可变"]},immutable +{res["immutable"]}')
k('delete', 'ns', NS, '--wait=false')
