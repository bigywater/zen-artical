import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k71')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36'); load('nginx:1.27-alpine')
NS = ns('k71')
CP, WA, WB = 'kx-main-control-plane', 'kx-main-worker', 'kx-main-worker2'
def nip(n): return next(a['address'] for a in kj('get', 'node', n)['status']['addresses'] if a['type'] == 'InternalIP')
IP = {n: nip(n) for n in (CP, WA, WB)}
CIDR = {n['metadata']['name']: n['spec']['podCIDR'] for n in kj('get', 'nodes')['items']}
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: ConfigMap
metadata: {{name: ngx, namespace: {NS}}}
data:
  default.conf: |
    server {{ listen 80; location / {{ default_type text/plain; return 200 "client=$remote_addr\\n"; }} }}
---
apiVersion: v1
kind: Pod
metadata: {{name: srv, namespace: {NS}}}
spec:
  nodeName: {WB}
  terminationGracePeriodSeconds: 0
  containers:
  - name: c
    image: nginx:1.27-alpine
    imagePullPolicy: IfNotPresent
    volumeMounts: [{{name: cfg, mountPath: /etc/nginx/conf.d}}]
  volumes: [{{name: cfg, configMap: {{name: ngx}}}}]
---
apiVersion: v1
kind: Pod
metadata: {{name: far, namespace: {NS}}}
spec:
  nodeName: {WA}
  terminationGracePeriodSeconds: 0
  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
---
apiVersion: v1
kind: Pod
metadata: {{name: near, namespace: {NS}}}
spec:
  nodeName: {WB}
  terminationGracePeriodSeconds: 0
  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]
''')
for p_ in ('srv', 'far', 'near'): k('wait', '--for=condition=Ready', f'pod/{p_}', '-n', NS, '--timeout=90s')
PIP = {p_: kj('get', 'pod', p_, '-n', NS)['status']['podIP'] for p_ in ('srv', 'far', 'near')}
def ex(p_, c): return k('exec', p_, '-n', NS, '--', 'sh', '-c', c)[1].strip()
print(f'集群 {cn};srv({PIP["srv"]},在 worker2)是服务端;far({PIP["far"]},在 worker)跨节点访问它;near({PIP["near"]},也在 worker2)同节点访问它')
print(f'  各节点:{ {n.replace("kx-main-", ""): (IP[n], CIDR[n]) for n in IP} }')

print('== 一:跨节点靠节点上的路由表——没有隧道')
for n in (WA, WB):
    rc, o = nx(n, 'ip route | grep -v veth'); print(f'  {n.replace("kx-main-", "")} 的路由(去掉每个 Pod 的 /32):'); [print('    ' + l) for l in o.strip().splitlines()]
rc, o = nx(WA, "ip -br link | grep -v '^veth' | awk '{print $1, $2}'"); print(f'  worker 上除 veth 以外的网卡:{o.strip().replace(chr(10), "; ")}(没有 vxlan / geneve / wireguard 之类的隧道设备;tunl0、gre0 等是内核自带的、状态 DOWN 的兜底设备)')
print(f'  Pod far 里去往 {PIP["srv"]} 的路由:{ex("far", f"ip route get {PIP[chr(115)+chr(114)+chr(118)]}")}')

print('== 二:不做 NAT——服务端看到的是真实的 Pod IP')
print(f'  far 访问 srv:{ex("far", f"wget -qO- -T 3 http://{PIP[chr(115)+chr(114)+chr(118)]}:80")}(far 的 IP 是 {PIP["far"]}——没有被 SNAT)')
print(f'  near 访问 srv:{ex("near", f"wget -qO- -T 3 http://{PIP[chr(115)+chr(114)+chr(118)]}:80")}')
rc, o = nx(WA, 'iptables-save -t nat 2>/dev/null | grep -i -E "masq" | grep -v KUBE-MARK | sed -e "s/-m comment --comment \\"[^\\"]*\\" //" | head -4'); print(f'  worker 上的 MASQUERADE 规则:{[x.strip()[:140] for x in o.strip().splitlines()]}')
print('  (这类规则只对“目的不在集群 Pod 网段”的流量做 SNAT,Pod 到 Pod 的流量不受影响)')

print('== 三:跨节点比同节点多一跳的延迟')
def rtt(p_, target):
    o = ex(p_, f'ping -c 30 -i 0.05 -q {target} 2>&1 | tail -2'); m = re.search(r'= ([\d.]+)/([\d.]+)/([\d.]+)', o); return (m.group(2), m.group(3)) if m else (o[:60], '')
rn = rtt("near", PIP["srv"]); rf = rtt("far", PIP["srv"])
print(f'  near → srv(同节点):平均 {rn[0]} ms,最大 {rn[1]} ms')
print(f'  far → srv(跨节点):平均 {rf[0]} ms,最大 {rf[1]} ms(ping 30 个包;kind 的“节点”都是同一台机器上的容器,所以延迟本来就很小)')

print('== 四:路由没了就断——kindnet 会把它补回来')
rc, o = nx(WA, f'ip route | grep "^{CIDR[WB]} "'); route = o.strip(); print(f'  worker 上去往 worker2 网段的路由:{route}')
print(f'  现在 far → srv:{ex("far", f"wget -qO- -T 2 http://{PIP[chr(115)+chr(114)+chr(118)]}:80 2>&1 | head -c 40")}')
nx(WA, f'ip route del {CIDR[WB]}'); t0 = time.time()
print(f'  手动删除这条路由后立刻再访问:{ex("far", f"wget -qO- -T 2 http://{PIP[chr(115)+chr(114)+chr(118)]}:80 2>&1 | head -c 60")!r}')
def back(): return nx(WA, f'ip route | grep -c "^{CIDR[WB]} "')[1].strip() == '1'
v, dt = until(back, 120, 0.5)
print(f'  等待 kindnet 重新装上路由:{"%.1f 秒后路由回来了" % dt if v else "120 秒内没有回来"};之后 far → srv:{ex("far", f"wget -qO- -T 2 http://{PIP[chr(115)+chr(114)+chr(118)]}:80 2>&1 | head -c 40")}')
k('delete', 'ns', NS, '--wait=false')
