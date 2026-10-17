import sys, os, re, time, json, base64; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k16')
cn, _ = up('main')
NS = ns('k16')
def etcdctl(*a):
    return k('exec', '-n', 'kube-system', f'etcd-{cn}-control-plane', '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', *a, raw=True)
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: crash, namespace: {NS}}}\nspec:\n  containers: [{{name: c, image: "busybox:1.36", command: ["sh", "-c", "echo boom; exit 1"]}}]\n')
t_start = time.time()
def evs(api='v1'):
    if api == 'v1': return (kj('get', 'events', '-n', NS) or {}).get('items', [])
    return json.loads(ko('get', '--raw', f'/apis/events.k8s.io/v1/namespaces/{NS}/events') or '{"items":[]}')['items']
def table(items):
    rows = sorted([(e['reason'], e.get('type'), e.get('count', 1), e.get('firstTimestamp'), e.get('lastTimestamp'), e['metadata']['name']) for e in items], key=lambda r: r[3] or '')
    return rows
print(f'集群 {cn};Pod crash 的容器启动后立刻 exit 1,kubelet 会按退避时间不停地重启它,并产生一串事件')

print('== 一:同一种事件重复发生——不会产生新对象,而是同一个 Event 的 count 增加')
time.sleep(20)
snap1 = table(evs()); e_t1 = time.time() - t_start
print(f'  {e_t1:.0f} 秒时 kubectl get events -n {NS} 有 {len(snap1)} 个 Event 对象:')
for r in snap1: print(f'    reason={r[0]:<10} type={r[1]:<8} count={r[2]} first={r[3]} last={r[4]}')
time.sleep(max(0, 100 - (time.time() - t_start)))
snap2 = table(evs()); e_t2 = time.time() - t_start
print(f'  {e_t2:.0f} 秒时有 {len(snap2)} 个 Event 对象:')
for r in snap2: print(f'    reason={r[0]:<10} type={r[1]:<8} count={r[2]} first={r[3]} last={r[4]}')
n1 = {r[5]: r[2] for r in snap1}; same = [r for r in snap2 if r[5] in n1 and r[2] > n1[r[5]]]
print(f'  同一个 Event 对象(名字不变)count 变大的有 {len(same)} 个:' + ', '.join(f'{r[0]} {n1[r[5]]}→{r[2]}' for r in same))

print('== 二:同一个事件,两套 API 里的样子(v1 Event 与 events.k8s.io/v1)')
e1 = next(e for e in evs() if e['reason'] == 'BackOff')
name = e1['metadata']['name']
e2 = next(e for e in evs('events.k8s.io') if e['metadata']['name'] == name)
print(f'  事件对象 {name}(reason={e1["reason"]})')
print(f'    core/v1:       count={e1.get("count")} firstTimestamp={e1.get("firstTimestamp")} lastTimestamp={e1.get("lastTimestamp")} source={e1.get("source")} reportingComponent={e1.get("reportingComponent") or "(空)"} involvedObject={e1["involvedObject"]["kind"]}/{e1["involvedObject"]["name"]}')
print(f'    events.k8s.io: eventTime={e2.get("eventTime")} series={e2.get("series")} deprecatedCount={e2.get("deprecatedCount")} deprecatedFirstTimestamp={e2.get("deprecatedFirstTimestamp")} reportingController={e2.get("reportingController") or "(空)"} regarding={e2["regarding"]["kind"]}/{e2["regarding"]["name"]}')
print('  两套 API 读的是同一份存储:' + str(e1['metadata']['uid'] == e2['metadata']['uid']) + '(uid 相同)')

print('== 三:事件的保留时间——etcd 里每个事件 key 绑着一个 lease')
key = f'/registry/events/{NS}/{name}'
rc, o = etcdctl('get', key, '-w', 'json')
kv = json.loads(o)['kvs'][0]; lease = kv.get('lease', 0)
print(f'  etcd key {key}:lease={"非 0(%x)" % lease if lease else 0}')
rc, o = etcdctl('lease', 'timetolive', hex(lease)[2:] if False else format(lease, 'x'))
print(f'  etcdctl lease timetolive:{o.strip()}')
rc, o = etcdctl('get', '/registry/pods/kube-system/', '--prefix', '--keys-only', '-w', 'json')
k0 = json.loads(o)['kvs'][0]
print(f'  对比:一个 Pod 的 key({base64.b64decode(k0["key"]).decode()})的 lease={k0.get("lease", 0)}(没有过期时间)')
rc, o = k('get', 'pods', '-n', 'kube-system', '-o', 'name', 'x', raw=True) if False else (0, '')
rc, o = k('describe', 'pod', '-n', 'kube-apiserver', raw=True) if False else (0, '')

print('== 四:事件和对象各过各的——Pod 删除之后事件还在,直到过期')
k('delete', 'pod', 'crash', '-n', NS, '--wait=true', timeout=90)
time.sleep(2)
items = evs()
print(f'  Pod crash 已经删除({k("get", "pod", "crash", "-n", NS)[1].strip()});kubectl get events 仍然有 {len(items)} 个对象,involvedObject 都指向 {sorted({e["involvedObject"]["name"] for e in items})}')
rc, o = k('events', '-n', NS, '--for', 'pod/crash'); print('  kubectl events --for pod/crash:' + ' | '.join(l.strip()[:120] for l in o.strip().splitlines()[:4]))
rc, o = k('describe', 'pod', 'crash', '-n', NS); print(f'  kubectl describe pod crash:{o.strip()[:80]}')
rmns(NS)
