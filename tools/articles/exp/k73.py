import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k73')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
W = 'kx-main-worker'
def cr(c, **kw): return nx(W, c, **kw)[1].strip()
print(f'集群 {cn};CRI(Container Runtime Interface)是 kubelet 和容器运行时之间的 gRPC 接口:RuntimeService(沙箱和容器)+ ImageService(镜像)')

print('== 一:kubelet 怎么找到运行时')
print(f'  kubelet 配置 /var/lib/kubelet/config.yaml:{cr("grep containerRuntimeEndpoint /var/lib/kubelet/config.yaml")}')
print(f'  crictl 配置 /etc/crictl.yaml:{cr("cat /etc/crictl.yaml")}')
print(f'  这个 socket 是 gRPC 服务端:{cr("ls -la /run/containerd/containerd.sock | cut -c1-60")}')
v = cr('crictl version').splitlines(); print(f'  crictl version(通过 CRI 的 Version 调用拿到):{[x.strip() for x in v]}')
nd = kj('get', 'node', W)['status']['nodeInfo']; print(f'  kubectl get node 的 status.nodeInfo.containerRuntimeVersion={nd["containerRuntimeVersion"]}(kubelet 把 CRI Version 的结果写进了 Node 对象)')
info = json.loads(cr('crictl info')); st = info['status']['conditions']; print(f'  crictl info 的运行时状态 conditions:{[(c["type"], c["status"]) for c in st]}')
print(f'  CRI 里的两个服务(从 containerd 的 cri 插件看):{cr("crictl info | jq -r \".config.containerd.defaultRuntimeName, .config.containerd.runtimes.runc.runtimeType, .config.cni.confDir\" | tr \"\\n\" \" \"")}')

print('== 二:自己扮演 kubelet——按 CRI 的顺序手动起一个 Pod')
pod_json = {'metadata': {'name': 'manual', 'namespace': 'cri-demo', 'uid': 'manual-uid-0001', 'attempt': 1}, 'log_directory': '/tmp/cri-demo-logs', 'linux': {'cgroup_parent': 'system.slice'}}
ctr_json = {'metadata': {'name': 'main'}, 'image': {'image': 'busybox:1.36'}, 'command': ['sh', '-c', 'echo hello-from-cri; hostname; sleep 3600'], 'log_path': 'main.log', 'linux': {}}
nx(W, 'mkdir -p /tmp/cri-demo-logs'); nx(W, f"echo '{json.dumps(pod_json)}' > /tmp/pod.json; echo '{json.dumps(ctr_json)}' > /tmp/ctr.json")
def sandbox_state(sid): return cr(f"crictl pods --id {sid} -o json | jq -r '.items[0].state'")
def manual():
    t = {}; t0 = time.time(); sid = cr('crictl runp /tmp/pod.json 2>/dev/null').splitlines()[-1]; t['RunPodSandbox'] = time.time() - t0
    t0 = time.time(); cid = cr(f'crictl create {sid} /tmp/ctr.json /tmp/pod.json 2>/dev/null').splitlines()[-1]; t['CreateContainer'] = time.time() - t0
    t0 = time.time(); cr(f'crictl start {cid}'); t['StartContainer'] = time.time() - t0
    return sid, cid, t
sid, cid, t = manual(); t_run = time.time()
print(f'  crictl runp(RunPodSandbox)→ 沙箱 {sid[:12]}…,用时 {t["RunPodSandbox"]:.2f} 秒;crictl create(CreateContainer)→ 容器 {cid[:12]}…,{t["CreateContainer"]:.2f} 秒;crictl start(StartContainer),{t["StartContainer"]:.2f} 秒')
isp = json.loads(cr(f'crictl inspectp {sid}')); print(f'  刚建好的沙箱:state={isp["status"]["state"]};IP={isp["status"]["network"]["ip"]}(CNI 已经配好)')
v, dt = until(lambda: sandbox_state(sid) != 'SANDBOX_READY', 30, 0.2)
print(f'  kubelet 在运行时,这个沙箱存活了 {time.time() - t_run:.1f} 秒后变成 {sandbox_state(sid)}——API Server 里没有这个 Pod,kubelet 把运行时里它不认识的 Pod 当作孤儿清掉')
cr(f'crictl rmp -f {sid} 2>/dev/null')
print('  现在先停掉 kubelet(systemctl stop kubelet),再来一遍:')
nx(W, 'systemctl stop kubelet'); time.sleep(1)
sid, cid, t = manual(); t_run = time.time(); time.sleep(8)
lg = cr(f"crictl logs {cid} 2>/dev/null").splitlines(); isp = json.loads(cr(f'crictl inspectp {sid}'))
print(f'    8 秒后沙箱仍是 {isp["status"]["state"]},IP={isp["status"]["network"]["ip"]};容器日志 {lg}(第二行是 hostname,沙箱没设时取节点名)')
print(f'    kubectl 看得到它吗:{[p["metadata"]["name"] for p in kj("get", "pods", "-A")["items"] if "manual" in p["metadata"]["name"]] or "看不到,API Server 里没有这个 Pod"};crictl pods 里:{cr("crictl pods --name manual -o json | jq -r \".items[0].metadata.name + \\\" \\\" + .items[0].labels[\\\"io.kubernetes.pod.namespace\\\"]\"")}')
t0 = time.time(); nx(W, 'systemctl start kubelet')
v, dt = until(lambda: sandbox_state(sid) != 'SANDBOX_READY', 60, 0.3)
print(f'    重新启动 kubelet 后 {dt:.1f} 秒,这个沙箱被清掉了(状态 {sandbox_state(sid)})')
cr(f'crictl rmp -f {sid} 2>/dev/null'); print(f'    清理后 crictl pods 里还有 manual 吗:{bool(cr("crictl pods --name manual -q"))}')

print('== 三:运行时 NetworkReady 变成 false,节点会变成 NotReady')
conf = cr('ls /etc/cni/net.d/'); nx(W, 'mv /etc/cni/net.d/10-kindnet.conflist /root/10-kindnet.conflist.bak'); t0 = time.time()
def net_cond(): return [(c['type'], c['status']) for c in json.loads(cr('crictl info'))['status']['conditions'] if c['type'] == 'NetworkReady']
def node_ready(): return next(c for c in kj('get', 'node', W)['status']['conditions'] if c['type'] == 'Ready')
v, dt1 = until(lambda: net_cond() == [('NetworkReady', False)], 60, 0.5); print(f'  把 CNI 配置文件挪走后 {dt1:.1f} 秒:crictl info 的 NetworkReady=false;{[ (c["type"], c["reason"], c["message"][:70]) for c in json.loads(cr("crictl info"))["status"]["conditions"] if c["type"] == "NetworkReady"]}')
v, dt2 = until(lambda: node_ready()['status'] != 'True', 120, 1); r = node_ready()
print(f'  节点 Ready 条件变成 {r["status"]} 用了 {dt2:.1f} 秒(从挪走配置算起):reason={r["reason"]};message={r["message"][:140]}')
pods_now = [(p['metadata']['name'], p['status']['phase']) for p in kj('get', 'pods', '-n', 'kube-system', '--field-selector', f'spec.nodeName={W}')['items']]
print(f'  这时该节点上已经在运行的系统 Pod:{pods_now}(已有的容器不受影响,只是新 Pod 起不来)')
nx(W, 'mv /root/10-kindnet.conflist.bak /etc/cni/net.d/10-kindnet.conflist'); t0 = time.time(); time.sleep(20)
print(f'  用 mv 把配置文件放回去,20 秒后 NetworkReady={net_cond()}(containerd 的配置目录监听没有发现“移入”的文件,仍是 false)')
nx(W, 'cp /etc/cni/net.d/10-kindnet.conflist /root/k.bak; cat /root/k.bak > /etc/cni/net.d/10-kindnet.conflist; rm /root/k.bak'); t0 = time.time()
v, dt4 = until(lambda: net_cond() == [('NetworkReady', True)], 30, 0.3); v, dt3 = until(lambda: node_ready()['status'] == 'True', 120, 1)
print(f'  改成重新写入文件内容(cat > 原文件):{dt4:.1f} 秒后 NetworkReady=true,{dt3:.1f} 秒后节点恢复 Ready')
