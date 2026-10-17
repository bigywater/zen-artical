import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k63')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k63')
def slices(svc): return kj('get', 'endpointslices', '-n', NS, '-l', f'kubernetes.io/service-name={svc}')['items']
def dep(name, n, grace=0, extra=''):
    return f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: {name}, namespace: {NS}}}
spec:
  replicas: {n}
  selector: {{matchLabels: {{app: {name}}}}}
  template:
    metadata: {{labels: {{app: {name}}}}}
    spec:
      terminationGracePeriodSeconds: {grace}
      containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]{extra}}}]
---
apiVersion: v1
kind: Service
metadata: {{name: {name}, namespace: {NS}}}
spec: {{selector: {{app: {name}}}, ports: [{{port: 80}}]}}
'''
print(f'集群 {cn};EndpointSlice 是 Service 后端的存储对象:每个切片最多 100 个后端(默认),由 kube-controller-manager 的 endpointslice 控制器维护')

print('== 一:一个 Service 自动对应的 EndpointSlice')
k('apply', '-f', '-', input=dep('s3', 3)); k('rollout', 'status', 'deploy/s3', '-n', NS, '--timeout=90s'); time.sleep(3)
sl = slices('s3'); s = sl[0]
print(f'  Service s3 有 {len(sl)} 个 EndpointSlice;名字 {s["metadata"]["name"]};labels={ {k_: v for k_, v in s["metadata"]["labels"].items()} }')
print(f'  addressType={s["addressType"]};ports={[ (p.get("name"), p["port"], p["protocol"]) for p in s["ports"]]};ownerReferences={[(o["kind"], o["name"]) for o in s["metadata"].get("ownerReferences", [])]}')
e = s['endpoints'][0]; print(f'  endpoints[0]:addresses={e["addresses"]};conditions={e["conditions"]};nodeName={e.get("nodeName")};targetRef={e["targetRef"]["kind"]}/{e["targetRef"]["name"][:18]}…')
print(f'  共 {len(s["endpoints"])} 个 endpoint,与 Pod 数一致:{len(s["endpoints"]) == 3}')
ep0 = kj('get', 'endpoints', 's3', '-n', NS); print(f'  旧的 Endpoints 对象 s3 也还在,含 {sum(len(x.get("addresses", [])) for x in ep0["subsets"])} 个地址(kubectl 会提示 v1 Endpoints is deprecated in v1.33+,由控制器同时维护)')

print('== 二:后端多了会拆成多个切片(默认每片最多 100 个)')
k('scale', 'deploy/s3', '-n', NS, '--replicas=205'); t0 = time.time()
v, dt = until(lambda: sum(len(x['endpoints']) for x in slices('s3')) == 205, 240, 2)
sl = slices('s3'); print(f'  扩到 205 个副本,{dt:.0f} 秒后所有 Pod 都进了切片:{len(sl)} 个 EndpointSlice,各含 {sorted([len(x["endpoints"]) for x in sl], reverse=True)} 个 endpoint')
ep = kj('get', 'endpoints', 's3', '-n', NS); o = json.dumps(ep, separators=(',', ':')); n_addr = sum(len(x.get('addresses', [])) for x in ep['subsets'])
print(f'  同一个 Service 的 Endpoints 对象:{n_addr} 个地址,JSON {len(o)} 字节;其中最大的一个 EndpointSlice(100 个 endpoint)的 JSON {max(len(json.dumps(x, separators=(',', ':'))) for x in sl)} 字节')

print('== 三:一个 Pod 变化只更新一个切片')
before = {x['metadata']['name']: x['metadata']['resourceVersion'] for x in slices('s3')}
ep_rv = kj('get', 'endpoints', 's3', '-n', NS)['metadata']['resourceVersion']
victim = kj('get', 'pods', '-n', NS, '-l', 'app=s3')['items'][0]['metadata']['name']
k('delete', 'pod', victim, '-n', NS, '--wait=true', timeout=60); time.sleep(5)
after = {x['metadata']['name']: x['metadata']['resourceVersion'] for x in slices('s3')}
changed = [n for n in after if before.get(n) != after[n]]
print(f'  删掉 1 个 Pod 之后(Deployment 会补一个新的):{len(changed)} 个 EndpointSlice 的 resourceVersion 变了(共 {len(after)} 个);Endpoints 对象 resourceVersion {ep_rv} → {kj("get", "endpoints", "s3", "-n", NS)["metadata"]["resourceVersion"]}')
print(f'  watch 的客户端(kube-proxy)收到更新时:Endpoints 要整个对象({len(o)} 字节)重发一遍,EndpointSlice 只重发变了的那个切片(约 {max(len(json.dumps(x, separators=(',', ':'))) for x in sl)} 字节)')
k('scale', 'deploy/s3', '-n', NS, '--replicas=3'); until(lambda: sum(len(x['endpoints']) for x in slices('s3')) == 3, 120, 2)
print(f'  缩回 3 个副本:切片数 {len(slices("s3"))}(空的切片会被回收,可能保留一个)')

print('== 四:Pod 终止期间的 conditions——ready=false 但 serving=true')
k('apply', '-f', '-', input=dep('t4', 2, grace=40)); k('rollout', 'status', 'deploy/t4', '-n', NS, '--timeout=90s'); time.sleep(3)
pod = kj('get', 'pods', '-n', NS, '-l', 'app=t4')['items'][0]; pn = pod['metadata']['name']; pip = pod['status']['podIP']
def cond(): 
    for x in slices('t4'):
        for e in x['endpoints']:
            if e['addresses'] == [pip]: return e['conditions']
    return None
print(f'  Pod {pn[:16]}… 终止前 endpoint 条件:{cond()}')
k('delete', 'pod', pn, '-n', NS, '--wait=false'); time.sleep(3)
print(f'  删除后 3 秒(sleep 作 1 号进程不理 SIGTERM,要等 40 秒的 terminationGracePeriod):{cond()}')
c_slices = slices('t4'); print(f'    Service 的另一个 Pod 的条件仍是 ready:{[e["conditions"] for x in c_slices for e in x["endpoints"] if e["addresses"] != [pip]][:1]}')
t0 = time.time(); v, dt = until(lambda: cond() is None, 80, 1)
print(f'    {dt:.0f} 秒后这个 endpoint 从切片里消失(Pod 真正退出)')
k('delete', 'ns', NS, '--wait=false')
