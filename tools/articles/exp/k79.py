import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k79')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k79')
W = 'kx-main-worker'
def cr(c): return nx(W, c)[1].strip()
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: duo, namespace: {NS}}}
spec:
  nodeName: {W}
  terminationGracePeriodSeconds: 0
  containers:
  - name: a
    image: busybox:1.36
    command: [sh, -c, "echo hi > /tmp/a-file; exec httpd -f -p 8080 -h /tmp"]
  - name: b
    image: busybox:1.36
    command: [sleep, "3600"]
''')
k('wait', '--for=condition=Ready', 'pod/duo', '-n', NS, '--timeout=60s'); time.sleep(2)
def ids():
    sid = cr(f"crictl pods --name '^duo$' --namespace {NS} -q | head -1")
    pods = json.loads(cr(f'crictl inspectp {sid}'))
    cs = {c['metadata']['name']: c['id'] for c in json.loads(cr(f'crictl ps --pod {sid} -o json'))['containers']}
    pid = {'pause': pods['info']['pid']}
    for n, i in cs.items(): pid[n] = json.loads(cr(f'crictl inspect {i}'))['info']['pid']
    return sid, cs, pid
sid, cs, pid = ids()
def nsid(p, kind): return cr(f'readlink /proc/{p}/ns/{kind}').split('[')[1].rstrip(']')
print(f'集群 {cn};Pod duo 有两个容器 a(httpd :8080)和 b(sleep);节点上还有第三个“容器”:沙箱里的 pause')
print(f'  节点上的进程 PID:{pid}')

print('== 一:谁和谁共享哪个命名空间')
print(f'  {"命名空间":<8}{"pause":>12}{"a":>12}{"b":>12}   a==pause?  b==pause?')
for kind in ('net', 'ipc', 'uts', 'pid', 'mnt', 'cgroup', 'user'):
    r = [nsid(pid[x], kind) for x in ('pause', 'a', 'b')]
    print(f'  {kind:<8}{r[0]:>12}{r[1]:>12}{r[2]:>12}   {"相同" if r[1] == r[0] else "不同":<9}  {"相同" if r[2] == r[0] else "不同"}')
print('  结论:net / ipc / uts 三个由 pause 创建并共享;pid、mnt、cgroup 每个容器自己一份(默认)')
pp = pid['pause']; cmd_ = cr(f'cat /proc/{pp}/cmdline | tr "\\0" " "'); st_ = cr(f'grep State /proc/{pp}/status'); rss_ = cr(f'grep VmRSS /proc/{pp}/status')
print(f'  pause 进程:{cmd_};{" ".join(st_.split())};{" ".join(rss_.split())}(几乎不占资源)')
rc, o = nx(W, "crictl images | grep -i pause"); print(f'  pause 镜像:{re.sub(chr(32) + "+", " ", o.strip())}')

print('== 二:同一个网络命名空间的后果')
rc, o = k('exec', 'duo', '-n', NS, '-c', 'b', '--', 'sh', '-c', 'wget -qO- -T 2 http://127.0.0.1:8080/a-file'); print(f'  容器 b 用 localhost:8080 访问容器 a 的 httpd:{o.strip()!r}')
rc, o = k('exec', 'duo', '-n', NS, '-c', 'b', '--', 'sh', '-c', 'httpd -f -p 8080 -h /tmp 2>&1; echo "退出码 $?"'); print(f'  容器 b 也想监听 8080:{" ".join(o.split())[:120]}')
rc, o = k('exec', 'duo', '-n', NS, '-c', 'a', '--', 'sh', '-c', 'ip -o -4 addr show eth0 | awk "{print \\$4}"'); rc2, o2 = k('exec', 'duo', '-n', NS, '-c', 'b', '--', 'sh', '-c', 'ip -o -4 addr show eth0 | awk "{print \\$4}"'); print(f'  两个容器看到的 eth0 地址:a={o.strip()} b={o2.strip()}(同一个)')
rc, o = k('exec', 'duo', '-n', NS, '-c', 'b', '--', 'cat', '/tmp/a-file'); print(f'  文件系统各是各的:b 读 /tmp/a-file → {" ".join(o.split())[:80]}')
rc, o = k('exec', 'duo', '-n', NS, '-c', 'b', '--', 'ps'); print(f'  进程各是各的:b 里 ps 只看到 {len(o.strip().splitlines()) - 1} 个进程(自己的 sleep 和 ps)')

print('== 三:容器重启 vs 沙箱重启——IP 是跟着 pause 走的')
ip0 = kj('get', 'pod', 'duo', '-n', NS)['status']['podIP']; uid0 = kj('get', 'pod', 'duo', '-n', NS)['metadata']['uid']
nx(W, f"crictl stop {cs['a']}"); v, dt = until(lambda: kj('get', 'pod', 'duo', '-n', NS)['status']['containerStatuses'][0]['restartCount'] >= 1, 40, 0.3); time.sleep(2)
p = kj('get', 'pod', 'duo', '-n', NS); print(f'  只停容器 a:{dt:.1f} 秒内 kubelet 重启它(restartCount={p["status"]["containerStatuses"][0]["restartCount"]});Pod IP {ip0} → {p["status"]["podIP"]}(没变,pause 还活着,网络命名空间还在)')
sid2, cs2, pid2 = ids(); old_pause = pid2['pause']
nx(W, f'kill -9 {old_pause}'); t0 = time.time()
v, dt = until(lambda: json.loads(cr(f"crictl pods --name '^duo$' --namespace {NS} -o json"))['items'][0]['state'] == 'SANDBOX_READY' and cr(f"crictl pods --name '^duo$' --namespace {NS} -q | head -1") != sid2, 60, 0.5)
time.sleep(5); p = kj('get', 'pod', 'duo', '-n', NS)
print(f'  直接 kill -9 pause 进程(PID {old_pause}):kubelet {dt:.1f} 秒内新建了一个沙箱(id {sid2[:8]}… → {cr(f"crictl pods --name ^duo$ --namespace {NS} -q | head -1")[:8]}…);Pod IP {ip0} → {p["status"]["podIP"]};两个容器的 restartCount={[c["restartCount"] for c in p["status"]["containerStatuses"]]};Pod uid 不变:{p["metadata"]["uid"] == uid0}')
k('delete', 'ns', NS, '--wait=false')
