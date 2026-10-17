import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k81')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36'); load('nginx:1.27-alpine')
NS = ns('k81')
W, CP = 'kx-main-worker', 'kx-main-control-plane'
def nip(n): return next(a['address'] for a in kj('get', 'node', n)['status']['addresses'] if a['type'] == 'InternalIP')
def pod(name, extra='', image='busybox:1.36', cmd='[sleep, "3600"]', ports=''):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  nodeName: {W}\n  terminationGracePeriodSeconds: 0\n{extra}  containers:\n  - {{name: c, image: {image}, imagePullPolicy: IfNotPresent, command: {cmd}{ports}}}\n---\n'
k('apply', '-f', '-', input=pod('plain') + pod('hnet', '  hostNetwork: true\n') + pod('hpid', '  hostPID: true\n') + pod('hipc', '  hostIPC: true\n') + pod('hnet-dns', '  hostNetwork: true\n  dnsPolicy: ClusterFirstWithHostNet\n'))
for p_ in ('plain', 'hnet', 'hpid', 'hipc', 'hnet-dns'): k('wait', '--for=condition=Ready', f'pod/{p_}', '-n', NS, '--timeout=60s')
def ex(p_, cmd): return k('exec', p_, '-n', NS, '--', 'sh', '-c', cmd)[1].strip()
print(f'集群 {cn};Pod 默认拥有自己的 net / pid / ipc / uts 命名空间。hostNetwork / hostPID / hostIPC 让它改用节点的。节点 worker IP {nip(W)}')

print('== 一:命名空间编号对照(Pod 里 /proc/self/ns/* 对比节点)')
node_ns = {x: nx(W, f'readlink /proc/1/ns/{x}')[1].strip().split('[')[1].rstrip(']') for x in ('net', 'pid', 'ipc', 'uts', 'mnt')}
print(f'  {"":<10}' + ''.join(f'{x:>13}' for x in node_ns) + '   与节点相同的')
print(f'  {"节点":<10}' + ''.join(f'{v:>13}' for v in node_ns.values()))
for p_ in ('plain', 'hnet', 'hpid', 'hipc'):
    r = {x: ex(p_, f'readlink /proc/self/ns/{x}').split('[')[1].rstrip(']') for x in node_ns}
    print(f'  {p_:<10}' + ''.join(f'{v:>13}' for v in r.values()) + '   ' + ','.join(x for x in node_ns if r[x] == node_ns[x]))

print('== 二:hostNetwork——Pod 就是节点的网络')
print(f'  plain 的 IP={kj("get", "pod", "plain", "-n", NS)["status"]["podIP"]};hnet 的 IP={kj("get", "pod", "hnet", "-n", NS)["status"]["podIP"]}(= 节点 IP:{kj("get", "pod", "hnet", "-n", NS)["status"]["podIP"] == nip(W)})')
print(f'  hnet 里的 hostname={ex("hnet", "hostname")}(节点名);plain 里的 hostname={ex("plain", "hostname")}(Pod 名)')
print(f'  hnet 里 ip addr 的网卡数 {ex("hnet", "ip -o link | wc -l")},plain 里 {ex("plain", "ip -o link | wc -l")}')
NSTAT = r"netstat -lnt 2>/dev/null | grep -E ':(10250|10248|10256) ' | head -3 | tr -s ' '"
r1 = ex('hnet', NSTAT)
print(f'  hnet 里 netstat 能看到节点上 kubelet 等已经在监听的端口:{r1!r}')
rc, o = k('exec', 'hnet', '-n', NS, '--', 'sh', '-c', 'nc -l -p 10250 2>&1; echo "退出码 $?"'); print(f'  hnet 里再监听 10250:{" ".join(o.split())[:100]}')
rc, o = k('exec', 'plain', '-n', NS, '--', 'sh', '-c', 'timeout 1 nc -l -p 10250 2>&1; echo "退出码 $?"'); print(f'  plain 里监听 10250:{" ".join(o.split())[:100]}(自己的网络命名空间,不冲突)')
NSL = 'nslookup kubernetes.default.svc.cluster.local 2>&1 | tail -3'
a_ = ex('hnet', NSL); b_ = ex('hnet-dns', NSL); ns1 = ex('hnet', 'grep nameserver /etc/resolv.conf | head -1'); ns2 = ex('hnet-dns', 'grep nameserver /etc/resolv.conf | head -1')
print(f'  DNS:hnet(dnsPolicy 默认 ClusterFirst,hostNetwork 下实际退回 Default)的 {ns1};解析 kubernetes.default:{" ".join(a_.split())[:120]}')
print(f'    hnet-dns(dnsPolicy: ClusterFirstWithHostNet)的 {ns2};解析:{" ".join(b_.split())[:120]}')

print('== 三:hostPID 与 hostIPC')
n_plain = int(ex('plain', 'ps | wc -l')); n_hpid = int(ex('hpid', 'ps | wc -l'))
print(f'  plain 里 ps 的行数 {n_plain};hpid 里 {n_hpid}(节点上的所有进程)')
PSG = r"ps -o pid,args | grep -E 'kubelet|containerd' | grep -v grep | head -3 | cut -c1-90"
print(f'  hpid 里能看到节点上的进程:{ex("hpid", PSG)!r}')
print(f'  hpid 里 PID 1:{ex("hpid", "cat /proc/1/comm")}(节点的 init;plain 里的 PID 1 是 {ex("plain", "cat /proc/1/comm")})')
print(f'  hipc 与节点共享 IPC 命名空间(见上表的 ipc 列编号相同);plain 的 ipc 编号与节点不同')

print('== 四:hostPort——只映射端口,不共享网络')
k('apply', '-f', '-', input=pod('hport', image='nginx:1.27-alpine', cmd='[nginx, "-g", "daemon off;"]', ports=', ports: [{containerPort: 80, hostPort: 8081}]'))
k('wait', '--for=condition=Ready', 'pod/hport', '-n', NS, '--timeout=60s'); time.sleep(2)
rc, o = nx(CP, f'curl -s -m 3 -o /dev/null -w "%{{http_code}}" http://{nip(W)}:8081/'); print(f'  Pod hport(hostPort: 8081,nginx 监听 80)在 worker 上;从控制面节点访问 {nip(W)}:8081 → HTTP {o.strip()}')
rc, o = nx(W, "iptables-save -t nat 2>/dev/null | grep -E 'CNI-HOSTPORT-DNAT|8081' | grep -v '^:' | head -4"); print('  worker 的 nat 表里(portmap 插件写的):'); [print('    ' + x[:150]) for x in o.strip().splitlines()]
print(f'  hport 的 Pod IP={kj("get", "pod", "hport", "-n", NS)["status"]["podIP"]}(仍是 Pod 自己的 IP,不是节点 IP);容器里 ip 网卡数 {ex("hport", "ip -o link | wc -l")}')
k('apply', '-f', '-', input=pod('hport2', image='nginx:1.27-alpine', cmd='[nginx, "-g", "daemon off;"]', ports=', ports: [{containerPort: 80, hostPort: 8081}]')); time.sleep(5)
p2 = kj('get', 'pod', 'hport2', '-n', NS); print(f'  同一个节点上第二个要 hostPort 8081 的 Pod:phase={p2["status"]["phase"]};{[(c["type"], c.get("reason"), c.get("message", "")[:90]) for c in p2["status"].get("conditions", []) if c["status"] != "True"][:1] or p2["status"].get("reason")}')
rc, o = k('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=hport2'); print(f'    事件:{[re.sub(chr(32) + "+", " ", l)[:150] for l in o.strip().splitlines()[1:3]]}')
k('delete', 'ns', NS, '--wait=false')
