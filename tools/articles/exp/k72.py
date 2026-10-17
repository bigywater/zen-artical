import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k72')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k72')
W = 'kx-main-worker'
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: hello, namespace: {NS}, labels: {{app: hello}}}}
spec:
  nodeName: {W}
  terminationGracePeriodSeconds: 0
  containers:
  - name: main
    image: busybox:1.36
    command: [sh, -c, "i=0; while true; do echo line-$i; echo err-$i >&2; i=$((i+1)); sleep 1; done"]
    resources: {{limits: {{memory: 64Mi, cpu: 100m}}}}
  - name: side
    image: busybox:1.36
    command: [sleep, "3600"]
''')
k('wait', '--for=condition=Ready', 'pod/hello', '-n', NS, '--timeout=90s'); time.sleep(3)
pod = kj('get', 'pod', 'hello', '-n', NS); uid = pod['metadata']['uid']
def cr(c): return nx(W, c, raw=True)[1].strip()
print(f'集群 {cn};节点上的容器运行时是 containerd {cr("containerd --version | cut -d\" \" -f3")};kubelet 通过 CRI(gRPC)和它说话,crictl 是同一个 CRI 的命令行客户端')

print('== 一:kubectl 的一个 Pod,在节点上是什么')
print(f'  kubectl get pod hello:{len(pod["spec"]["containers"])} 个容器(main、side)')
rc, o = nx(W, f"crictl pods --name '^hello$' -o json"); sb = json.loads(o)['items'][0]; sid = sb['id']
print(f'  crictl pods:1 个沙箱(sandbox)id={sid[:12]}… state={sb["state"]};labels 里 io.kubernetes.pod.name={sb["labels"]["io.kubernetes.pod.name"]} io.kubernetes.pod.namespace={sb["labels"]["io.kubernetes.pod.namespace"]} io.kubernetes.pod.uid={sb["labels"]["io.kubernetes.pod.uid"][:8]}…(= kubectl 的 uid:{sb["labels"]["io.kubernetes.pod.uid"] == uid})')
rc, o = nx(W, f"crictl ps -a --pod {sid} -o json"); cs = json.loads(o)['containers']
print(f'  crictl ps --pod {sid[:12]}…:{[(c["metadata"]["name"], c["state"].replace("CONTAINER_", ""), c["id"][:12]) for c in cs]}')
st = {c["name"]: c["containerID"] for c in pod["status"]["containerStatuses"]}
print(f'  kubectl 里 status.containerStatuses[main].containerID={st["main"][:20]}…;和 crictl 里 main 的 id 一致:{any(st["main"].endswith(c["id"]) for c in cs if c["metadata"]["name"] == "main")}')
side_id = [c['id'] for c in cs if c['metadata']['name'] == 'side'][0]; main_id = [c['id'] for c in cs if c['metadata']['name'] == 'main'][0]
pids = {'沙箱(pause)': json.loads(nx(W, f'crictl inspectp {sid}')[1])['info']['pid'], 'main': json.loads(nx(W, f'crictl inspect {main_id}')[1])['info']['pid'], 'side': json.loads(nx(W, f'crictl inspect {side_id}')[1])['info']['pid']}
rc, o = nx(W, 'ps -o pid,ppid,args -p ' + ','.join(str(v) for v in pids.values())); print(f'  节点上(宿主机视角)这个 Pod 的三个进程 {pids}:'); [print('    ' + re.sub(r"\s+", " ", l)[:110]) for l in o.strip().splitlines()]
rc, o = nx(W, f'ps -o pid,args --ppid {pids["main"]} 2>/dev/null | tail -n +2 | head -2'); sh_children = o.strip().splitlines()
rc, o = nx(W, f'ps -o pid,ppid,args -p $(ps -o ppid= -p {pids["main"]} | tr -d " ")'); print(f'  main 的父进程是 containerd-shim(每个沙箱一个 shim,管着 pause 和这个 Pod 的所有容器):{re.sub(chr(10), " | ", " ".join(x.strip()[:100] for x in o.strip().splitlines()[1:]))}')

print('== 二:containerd 里的同一批对象')
rc, o = nx(W, 'ctr namespaces ls'); print(f'  ctr namespaces ls:{o.split()[2:] if o else o}(kubelet 用的 containerd 命名空间是 k8s.io)')
rc, o = nx(W, f'ctr -n k8s.io containers ls | grep -c .'); n_ctr = o.strip()
rc, o = nx(W, f'ctr -n k8s.io tasks ls'); tasks = [l.split() for l in o.strip().splitlines()[1:]]
rc, o = nx(W, "crictl ps -a -q | wc -l"); rc2, o2 = nx(W, "crictl pods -q | wc -l")
print(f'  ctr -n k8s.io containers ls 共 {int(n_ctr) - 1} 行;crictl ps -a 共 {o.strip()} 个容器 + crictl pods 共 {o2.strip()} 个沙箱——沙箱在 containerd 眼里也是一个容器(pause),所以两者加起来对得上:{int(n_ctr) - 1 == int(o.strip()) + int(o2.strip())}')
main_id = [c['id'] for c in cs if c['metadata']['name'] == 'main'][0]
ins = json.loads(nx(W, f'crictl inspect {main_id}')[1]); sp = ins['info']['runtimeSpec']
print(f'  crictl inspect main:pid={ins["info"]["pid"]};runtime={ins["info"].get("runtimeType")};snapshotter={ins["info"].get("snapshotter")};image={ins["status"]["image"]["image"]};cgroupsPath={sp["linux"]["cgroupsPath"][:70]};memory.limit={sp["linux"]["resources"]["memory"]["limit"]};cpu.quota/period={sp["linux"]["resources"]["cpu"]["quota"]}/{sp["linux"]["resources"]["cpu"]["period"]}')
print(f'    memLimit=67108864 即 64Mi,cpuQuota=10000(微秒/100000 周期)即 100m——kubelet 把 resources 翻译成 OCI 运行时配置')

print('== 三:日志是谁写到哪的')
d = f'{NS}_hello_{uid}'
rc, o = nx(W, f'ls /var/log/pods/{d}/main/ && tail -4 /var/log/pods/{d}/main/0.log')
print(f'  /var/log/pods/{d.replace(uid, "<uid>")}/main/:{o.strip().splitlines()[0]}')
print('  0.log 的格式(时间戳 流 标记 内容):'); [print('    ' + l) for l in o.strip().splitlines()[1:]]
rc, o = nx(W, 'for f in /var/log/containers/hello_*; do echo "$(basename $f | cut -c1-40)… -> $(readlink $f | sed s#/var/log/pods/#…/#)"; done'); print(f'  /var/log/containers/ 里的符号链接(kubectl logs 最终读的就是它指向的文件):'); [print('    ' + re.sub(r'[0-9a-f]{8}-[0-9a-f-]{27}', '<uid>', x)[:150]) for x in o.strip().splitlines()]
rc, o = nx(W, f'crictl logs --tail 2 {main_id} 2>&1'); print(f'  crictl logs --tail 2:{o.strip().splitlines()}')

print('== 四:crictl 能做的“运维”操作')
rc, o = nx(W, f"crictl exec {main_id} sh -c 'echo 在 main 容器里: hostname=$(hostname) uid=$(id -u) pid1=$(cat /proc/1/comm)'"); print(f'  crictl exec:{o.strip()}')
stj = json.loads(nx(W, f'crictl stats -o json --id {main_id}')[1])['stats'][0]; print(f'  crictl stats main:cpu 累计 {int(stj["cpu"]["usageCoreNanoSeconds"]["value"]) // 1000000} ms;内存 working set {int(stj["memory"]["workingSetBytes"]["value"]) // 1024} KiB')
rc, o = nx(W, 'crictl images | head -4'); print('  crictl images(节选):'); [print('    ' + re.sub(r"\s+", " ", l)[:100]) for l in o.strip().splitlines()]
nx(W, f'crictl stop {main_id}'); v, dt = until(lambda: kj('get', 'pod', 'hello', '-n', NS)['status']['containerStatuses'][0]['restartCount'] >= 1, 40, 0.3)
c0 = kj('get', 'pod', 'hello', '-n', NS)['status']['containerStatuses'][0]
print(f'  用 crictl stop 停掉 main:kubelet {dt:.1f} 秒内就重启了它(restartCount={c0["restartCount"]}),新的 containerID 以 {c0["containerID"][13:25]} 开头,和原来的 {main_id[:12]} {"不同" if not c0["containerID"].endswith(main_id) else "相同"}')
k('delete', 'ns', NS, '--wait=false')
