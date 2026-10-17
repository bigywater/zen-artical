import sys, os, re, time, json, yaml; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k14')
cn, _ = up('main')
for n in ('k14a', 'k14b', 'k14c'): k('delete', 'ns', n, '--ignore-not-found', '--wait=true', timeout=120)
k('delete', 'apiservice', 'v1beta1.k14.example.com', '--ignore-not-found')
def stuck_ns(name, extra=''):
    k('create', 'ns', name)
    k('create', '-f', '-', input=yaml.dump({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'blocker', 'namespace': name, 'finalizers': ['example.com/block']}}))
def conds(name):
    j = kj('get', 'ns', name) or {}
    return j, {c['type']: c for c in j.get('status', {}).get('conditions', [])}
print(f'集群 {cn};命名空间删除是异步的:先把 phase 置为 Terminating,namespace 控制器逐个清理里面的资源,清空后才摘掉 spec.finalizers 里的 kubernetes')

print('== 一:命名空间里有个带 finalizer 的对象——卡住了,看哪个字段说明原因')
stuck_ns('k14a')
rc, o = k('delete', 'ns', 'k14a', '--wait=false'); print(f'  kubectl delete ns k14a --wait=false:{o.strip()}')
time.sleep(6)
j, c = conds('k14a')
print(f'  6 秒后 kubectl get ns k14a:' + k('get', 'ns', 'k14a')[1].strip().replace('\\n', ' | '))
print(f'  status.phase={j["status"]["phase"]};spec.finalizers={j["spec"].get("finalizers")};deletionTimestamp={"有" if j["metadata"].get("deletionTimestamp") else "无"}')
for t, x in sorted(c.items()): print(f'    condition {t}: status={x["status"]} reason={x["reason"]} message={x["message"][:170]}')

print('== 二:摘掉对象的 finalizer,命名空间自己完成删除')
t0 = time.time()
k('patch', 'cm', 'blocker', '-n', 'k14a', '--type=merge', '-p', '{"metadata":{"finalizers":null}}')
v, dt = until(lambda: not kj('get', 'ns', 'k14a'), 60, 0.2)
print(f'  摘掉 blocker 的 finalizer 之后,命名空间 {"在 %.1f 秒内消失" % dt if v else "仍在"}')

print('== 三:另一类原因——某个 API 组不可用(APIService 的后端找不到),namespace 控制器无法枚举资源')
k('apply', '-f', '-', input='''apiVersion: apiregistration.k8s.io/v1
kind: APIService
metadata: {name: v1beta1.k14.example.com}
spec: {group: k14.example.com, version: v1beta1, groupPriorityMinimum: 100, versionPriority: 10, insecureSkipTLSVerify: true, service: {name: no-such-svc, namespace: default, port: 443}}
''')
time.sleep(4)
print('  kubectl get apiservice v1beta1.k14.example.com:' + k('get', 'apiservice', 'v1beta1.k14.example.com')[1].strip().replace('\n', ' | '))
k('create', 'ns', 'k14b'); k('create', 'cm', 'plain', '-n', 'k14b', '--from-literal=a=1')
k('delete', 'ns', 'k14b', '--wait=false'); time.sleep(8)
j, c = conds('k14b')
print(f'  命名空间 k14b 里只有一个普通 ConfigMap,没有 finalizer;8 秒后 phase={j.get("status", {}).get("phase", "(已经不存在)")}')
for t, x in sorted(c.items()): print(f'    condition {t}: status={x["status"]} reason={x["reason"]} message={x["message"][:200]}')
t0 = time.time(); k('delete', 'apiservice', 'v1beta1.k14.example.com')
v, dt = until(lambda: not kj('get', 'ns', 'k14b'), 90, 0.5)
print(f'  删掉这个 APIService 之后,k14b {"在 %.1f 秒内消失" % dt if v else "仍然卡住"}')

print('== 四:强行摘掉命名空间自己的 finalizer(/finalize)——命名空间没了,里面的对象却留在 etcd 里')
stuck_ns('k14c')
k('delete', 'ns', 'k14c', '--wait=false'); time.sleep(4)
j = kj('get', 'ns', 'k14c'); j['spec']['finalizers'] = []
rc, o = k('replace', '--raw', '/api/v1/namespaces/k14c/finalize', '-f', '-', input=json.dumps(j))
time.sleep(2)
print(f'  kubectl replace --raw /api/v1/namespaces/k14c/finalize(把 spec.finalizers 清空):退出码 {rc};命名空间还在吗 {bool(kj("get", "ns", "k14c"))}')
rc, o = k('exec', '-n', 'kube-system', f'etcd-{cn}-control-plane', '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', 'get', '/registry/configmaps/k14c/', '--prefix', '--keys-only', raw=True)
print(f'  etcd 里 /registry/configmaps/k14c/ 下还剩:{[l for l in o.splitlines() if l.startswith("/registry")]}')
k('create', 'ns', 'k14c')
print(f'  重新创建同名命名空间 k14c 后 kubectl get cm -n k14c:{k("get", "cm", "-n", "k14c")[1].strip().replace(chr(10), " | ")}')
k('patch', 'cm', 'blocker', '-n', 'k14c', '--type=merge', '-p', '{"metadata":{"finalizers":null}}')
for n in ('k14a', 'k14b', 'k14c'): k('delete', 'ns', n, '--ignore-not-found', '--wait=false')
