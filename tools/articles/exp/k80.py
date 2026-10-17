import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k80')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k80')
def pod(name, share):
    return f'''apiVersion: v1
kind: Pod
metadata: {{name: {name}, namespace: {NS}}}
spec:
  shareProcessNamespace: {str(share).lower()}
  terminationGracePeriodSeconds: 0
  containers:
  - {{name: app, image: busybox:1.36, command: [sleep, "3600"]}}
  - {{name: side, image: busybox:1.36, command: [sleep, "3601"]}}
---
'''
k('apply', '-f', '-', input=pod('iso', False) + pod('shared', True))
for p_ in ('iso', 'shared'): k('wait', '--for=condition=Ready', f'pod/{p_}', '-n', NS, '--timeout=60s')
def ex(p_, c, cmd): return k('exec', p_, '-n', NS, '-c', c, '--', 'sh', '-c', cmd)[1].strip()
def ps(p_, c): return [re.sub(r'\s+', ' ', l.strip())[:60] for l in ex(p_, c, 'ps -o pid,stat,args').splitlines()[1:]]
print(f'集群 {cn};shareProcessNamespace: true 让 Pod 里所有容器放进同一个 PID 命名空间。对照两个 Pod:iso(默认)和 shared(true),各有 app 和 side 两个容器')

print('== 一:ps 看到什么')
print(f'  iso 的 side 容器里 ps:{ps("iso", "side")}')
print(f'  shared 的 side 容器里 ps:{ps("shared", "side")}')
print(f'  shared 里的 PID 1 是 {ex("shared", "side", "cat /proc/1/comm")}——pause 成了整个 Pod 的 init,容器进程的 PID 不再从 1 开始')

print('== 二:跨容器的访问')
pid_app = [l.split()[0] for l in ps('shared', 'side') if 'sleep 3600' in l][0]
rc, o = k('exec', 'shared', '-n', NS, '-c', 'side', '--', 'sh', '-c', f'ls /proc/{pid_app}/root/ | head -4 | tr "\\n" " "; echo; cat /proc/{pid_app}/cmdline | tr "\\0" " "; echo; ls -l /proc/{pid_app}/cwd')
print(f'  在 side 里通过 /proc/{pid_app}/root 看 app 容器的根目录:{" | ".join(l.strip()[:80] for l in o.strip().splitlines()[:3])}')
rc, o = k('exec', 'shared', '-n', NS, '-c', 'side', '--', 'sh', '-c', f'kill -TERM {pid_app}; sleep 1; echo "kill 的返回码 $?"'); time.sleep(3)
p = kj('get', 'pod', 'shared', '-n', NS); cs = {c['name']: c for c in p['status']['containerStatuses']}
print(f'  在 side 里 kill -TERM app 的 sleep 进程:app 容器 restartCount={cs["app"]["restartCount"]},lastState={list(cs["app"].get("lastState", {}).keys())};side 的 restartCount={cs["side"]["restartCount"]}(跨容器发信号可以,杀掉的容器会被 kubelet 按 restartPolicy 重启)')
rc, o = k('exec', 'iso', '-n', NS, '-c', 'side', '--', 'sh', '-c', 'kill -TERM 1; echo rc=$?; sleep 2; ps -o pid,args | head -3'); time.sleep(2); cs_ = {c["name"]: c for c in kj("get", "pod", "iso", "-n", NS)["status"]["containerStatuses"]}
print(f'  对照 iso 的 side 里对自己的 PID 1(sleep)kill -TERM:{" / ".join(x.strip() for x in o.strip().splitlines()[:3])};side 的 restartCount={cs_["side"]["restartCount"]}(没有被杀:容器里的 PID 1 对没有处理函数的信号默认忽略)')

print('== 三:僵尸进程谁来收')
ORPH = 'for i in 1 2 3 4 5; do (sleep 0.1 &) ; done; sleep 1; ps -o pid,ppid,stat,args | grep -E "Z|defunct" | grep -v grep | wc -l'
n_iso = ex('iso', 'app', ORPH); n_shared = ex('shared', 'app', ORPH)
print(f'  在 app 容器里启动 5 个“孤儿”短命进程(父进程立刻退出,孤儿被 PID 1 收养,结束后需要 PID 1 来 wait):')
print(f'    iso(PID 1 是 sleep,不会 wait):僵尸进程 {n_iso} 个;PID 1 是 {ex("iso", "app", "cat /proc/1/comm")}')
print(f'    shared(PID 1 是 pause,会 wait):僵尸进程 {n_shared} 个;PID 1 是 {ex("shared", "app", "cat /proc/1/comm")}')
print(f'    iso 里的僵尸:{[l for l in ps("iso", "app") if "Z" in l.split()[1] or "defunct" in l][:3]}')

print('== 四:代价与限制')
rc, o2 = k('get', 'pod', 'shared', '-n', NS, '-o', 'jsonpath={.spec.shareProcessNamespace}'); print(f'  Pod spec.shareProcessNamespace={o2}')
print(f'  容器重启后 PID 会变:app 重启前 sleep 3600 的 PID 是 {pid_app},重启后是 {[l.split()[0] for l in ps("shared", "side") if "sleep 3600" in l]}')
pid_new = [l.split()[0] for l in ps('shared', 'side') if 'sleep 3600' in l][0]
print(f'  从 side 读 app 的 /proc/{pid_new}/environ:{ex("shared", "side", f"cat /proc/{pid_new}/environ 2>&1 | tr \"\\0\" \" \" | head -c 90")!r}(同一用户 root,可以读;非 root 或不同 UID 的容器会被拒)')
k('delete', 'ns', NS, '--wait=false')
