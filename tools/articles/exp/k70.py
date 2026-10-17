import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k70')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k70')
W = 'kx-main-worker'
def pod(name, node=W):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  nodeName: {node}\n  terminationGracePeriodSeconds: 0\n  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n---\n'
def running(*names): return until(lambda: all(kj('get', 'pod', n, '-n', NS)['status'].get('phase') == 'Running' for n in names), 60, 0.3)
def ip(n): return kj('get', 'pod', n, '-n', NS)['status']['podIP']
print(f'集群 {cn};Pod 的网络由 CNI 插件在“创建 Pod 沙箱”时配置:kubelet 通过 containerd 调用 /etc/cni/net.d 里配置的插件')

print('== 一:CNI 配置与 IPAM')
rc, o = nx(W, 'cat /etc/cni/net.d/10-kindnet.conflist'); c = json.loads(o)
print(f'  节点 worker 上的 /etc/cni/net.d/10-kindnet.conflist:name={c["name"]};插件链 {[p["type"] for p in c["plugins"]]}')
p0 = c['plugins'][0]; print(f'  第一个插件 {p0["type"]}:ipam={p0["ipam"]["type"]},dataDir={p0["ipam"]["dataDir"]},ranges={p0["ipam"]["ranges"]},routes={p0["ipam"]["routes"]},mtu={p0.get("mtu")}')
for n in kj('get', 'nodes')['items']:
    print(f'  节点 {n["metadata"]["name"].replace("kx-main-", "")}:spec.podCIDR={n["spec"].get("podCIDR")};  这个节点上 CNI 配置里的 subnet={json.loads(nx(n["metadata"]["name"], "cat /etc/cni/net.d/10-kindnet.conflist")[1])["plugins"][0]["ipam"]["ranges"][0][0]["subnet"]}')

print('== 二:IP 是怎么分配的——host-local 在磁盘上记账')
rc, o = nx(W, 'ls /run/cni-ipam-state/kindnet/'); before = o.split()
k('apply', '-f', '-', input=pod('a') + pod('b') + pod('c')); running('a', 'b', 'c'); time.sleep(1)
ips = [ip(n) for n in 'abc']
rc, o = nx(W, 'ls /run/cni-ipam-state/kindnet/'); after = o.split()
print(f'  worker 上 3 个新 Pod 的 IP:{ips}(都在 {c["plugins"][0]["ipam"]["ranges"][0][0]["subnet"]} 里,从上一个分配的地址继续往后)')
print(f'  /run/cni-ipam-state/kindnet/ 里每个已分配的 IP 一个文件,外加 last_reserved_ip.0 记录上次分配到哪:{sorted(set(after) - set(before))}')
rc, o = nx(W, f'cat /run/cni-ipam-state/kindnet/{ips[0]}; echo; cat /run/cni-ipam-state/kindnet/last_reserved_ip.0'); l = o.strip().splitlines()
print(f'  文件 {ips[0]} 的内容(记录占用它的沙箱 ID 前 12 位):{l[0][:12]}…;last_reserved_ip.0={l[-1]}')
k('delete', 'pod', 'b', '-n', NS, '--wait=true', timeout=60); t0 = time.time()
v, dt = until(lambda: ips[1] not in nx(W, 'ls /run/cni-ipam-state/kindnet/')[1].split(), 60, 0.3)
print(f'  删除 Pod b({ips[1]}):API 对象消失后又过了 {dt:.1f} 秒,IPAM 里这个 IP 的文件才被删掉(CNI 的 DEL 在容器停止之后才执行)')
k('apply', '-f', '-', input=pod('d')); running('d'); print(f'  新建 Pod d 的 IP:{ip("d")}(没有立刻回收 {ips[1]},而是继续往后分配;地址用完一圈后才会复用)')

print('== 三:一对 veth——Pod 里的 eth0 和节点上的 vethXXXX')
cid = nx(W, f"crictl pods --name '^a$' --namespace {NS} -q")[1].strip().splitlines()[0]
pid = nx(W, f"crictl inspectp {cid} | jq -r .info.pid")[1].strip()
rc, o = nx(W, f'nsenter -t {pid} -n ip -br addr show eth0; nsenter -t {pid} -n ip route; nsenter -t {pid} -n ip -d link show eth0 | head -3'); print('  Pod a 的网络命名空间里:'); [print('    ' + re.sub(r'\s+', ' ', l)[:150]) for l in o.strip().splitlines()]
rc, o = nx(W, f"nsenter -t {pid} -n ip -o link show eth0"); m = re.match(r'(\d+): eth0@if(\d+)', o.strip()); ifidx, peer = m.group(1), m.group(2)
rc, o = nx(W, f"ip -o link | grep '^{peer}:'"); host = o.strip().split(':')[1].strip() if o.strip() else '?'
print(f'  Pod 里 eth0 的 ifindex={ifidx},它的对端是 ifindex={peer};节点上 ifindex={peer} 的网卡:{host}(名字里的 @if{ifidx} 又指回 Pod 里的 eth0,两头互指)')
hostveth = host.split('@')[0]
rc, o = nx(W, f'ip route | grep "^{ips[0]} "'); print(f'  节点上通往这个 Pod 的路由:{o.strip()}(/32 主机路由,直接指向它的 veth {hostveth},没有网桥)')
rc, o = nx(W, 'ip -br link | grep -c "^veth"'); nv = int(o.strip()); rc, o = nx(W, "crictl pods --state ready -q | wc -l")
print(f'  worker 上 veth 数 {nv};就绪的 Pod 沙箱数 {o.strip()}(其中 hostNetwork 的 Pod 没有 veth)')

print('== 四:Pod 删除后 veth 和路由消失')
cidd = nx(W, f"crictl pods --name '^d$' --namespace {NS} -q")[1].strip().splitlines()[0]; dip = ip('d')
rc, o = nx(W, f'ip route | grep -c "^{dip} "'); print(f'  Pod d({dip})存在时节点上到它的路由 {o.strip()} 条')
k('delete', 'pod', 'd', '-n', NS, '--wait=true', timeout=60)
v, dt = until(lambda: nx(W, f'ip route | grep -c "^{dip} "')[1].strip() == '0', 60, 0.3)
print(f'  Pod d 的 API 对象消失后又过 {dt:.1f} 秒,到它的路由才没有(CNI DEL 之后 veth 被删,路由跟着消失);veth 数 {nv} → {nx(W, "ip -br link | grep -c ^veth")[1].strip()};IPAM 里 {dip} 的文件{"还在" if dip in nx(W, "ls /run/cni-ipam-state/kindnet/")[1].split() else "已释放"}')
k('delete', 'ns', NS, '--wait=false')
