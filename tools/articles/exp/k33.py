import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k33')
cn, _ = up('main')
NS = ns('k33')
def pod(name, cmd, res='    resources: {requests: {memory: 32Mi}, limits: {memory: 64Mi}}\n', image='python:3.12-alpine', vols='', vm=''):
    return f'''apiVersion: v1
kind: Pod
metadata: {{name: {name}, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
{vols}  containers:
  - name: c
    image: {image}
    imagePullPolicy: IfNotPresent
    command: [sh, -c, {json.dumps(cmd)}]
{vm}{res}'''
def cs(name):
    p = kj('get', 'pod', name, '-n', NS); return p, (p['status'].get('containerStatuses') or [{}])[0]
def podcg_events(p):
    node, pcg = pod_cgroup(p); return cgread(node, pcg, 'memory.events').replace('\n', ' ')
print(f'集群 {cn};memory limit 变成 cgroup 的 memory.max:容器(及其所有子进程)的内存用量一超过它,内核的 OOM 杀手就会杀进程——kubelet 只负责报告')

print('== 一:1 号进程自己超出 limit——容器被 OOMKilled(用 sleep 6 让 cgroup 先建好,方便先读参数)')
k('apply', '-f', '-', input=pod('oom1', 'sleep 6; exec python -c \'import time; d = b"x" * (100 * 2**20); time.sleep(3600)\''))
until(lambda: cs('oom1')[1].get('state', {}).get('running'), 30, 0.3); time.sleep(1)
p, c = cs('oom1'); node, cg, cid = container_cgroup(p, 'c')
print(f'  容器启动 1 秒后读 cgroup:memory.max={cgread(node, cg, "memory.max")}({int(cgread(node, cg, "memory.max")) // 2**20} MiB = limit 64Mi);memory.oom.group={cgread(node, cg, "memory.oom.group")}(1 表示 OOM 时整个 cgroup 里的进程一起杀);memory.high={cgread(node, cg, "memory.high")}')
v, dt = until(lambda: cs('oom1')[1].get('lastState', {}).get('terminated'), 40, 0.3)
p, c = cs('oom1'); lt = c['lastState']['terminated']
print(f'  python 分配 100 MiB 后 {dt:.1f} 秒内:lastState.terminated reason={lt["reason"]} exitCode={lt["exitCode"]}(= 128 + 9,SIGKILL);restartCount={c["restartCount"]};Pod 级 memory.events:{podcg_events(p)}')
time.sleep(25); p, c = cs('oom1')
print(f'  又过 25 秒:restartCount={c["restartCount"]};kubectl get STATUS={k("get", "pod", "oom1", "-n", NS)[1].strip().splitlines()[-1].split()[2]};Pod 级 memory.events:{podcg_events(p)}')

print('== 二:sh 作 1 号进程,python 只是子进程——整个容器一起被杀')
k('apply', '-f', '-', input=pod('oom2', 'sleep 3600 & sleep 6; python -c \'import time; d = b"x" * (100 * 2**20); time.sleep(3600)\'; echo "python 退出码 $?"; sleep 3600'))
until(lambda: cs('oom2')[1].get('state', {}).get('running'), 30, 0.3); time.sleep(1)
rc, o = k('exec', 'oom2', '-n', NS, '--', 'ps'); print('  OOM 之前容器里的进程:' + ' | '.join(' '.join(l.split()[:1] + l.split()[3:])[:44] for l in o.splitlines()[1:] if not l.split()[-1] == 'ps'))
ev0 = podcg_events(cs('oom2')[0])
v, dt = until(lambda: cs('oom2')[1].get('lastState', {}).get('terminated'), 40, 0.3)
p, c = cs('oom2'); lt = c['lastState']['terminated']
print(f'  python 子进程分配 100 MiB:{dt:.1f} 秒内容器 lastState.terminated reason={lt["reason"]} exitCode={lt["exitCode"]},restartCount={c["restartCount"]}——PID 1(sh)并没有自己超出内存,整个容器仍被 OOMKilled(memory.oom.group=1)')
print(f'  容器日志里没有“python 退出码”那行(sh 也被一起杀了):{k("logs", "oom2", "-n", NS, "--previous")[1].strip() or "(空)"};Pod 级 memory.events:{podcg_events(p)}')

print('== 三:什么算“用了内存”——内存型 emptyDir 的文件算,磁盘上的文件(页缓存)可以被回收')
for n_, vol in (('oom-tmpfs', '  volumes: [{name: v, emptyDir: {medium: Memory}}]\n'), ('ok-disk', '  volumes: [{name: v, emptyDir: {}}]\n')):
    k('apply', '-f', '-', input=pod(n_, 'sleep 5; dd if=/dev/zero of=/v/blob bs=1M count=100 2>&1; echo dd 结束 $?; sleep 3600', image='busybox:1.36', vols=vol, vm='    volumeMounts: [{name: v, mountPath: /v}]\n'))
seen = []; t0 = time.time()
while time.time() - t0 < 40:
    p, c = cs('oom-tmpfs'); lt = c.get('lastState', {}).get('terminated') or {}
    key = (c.get('restartCount'), lt.get('reason'), lt.get('exitCode'))
    if lt and (not seen or seen[-1][1] != key): seen.append((round(time.time() - t0, 1), key, (lt.get('message') or '')[:300]))
    time.sleep(0.5)
print('  写 100 MiB 到内存型 emptyDir(tmpfs),limit 64Mi:lastState.terminated 的变化:')
for t, (rc_, rs, ec), msg in seen: print(f'    +{t:>4.1f}s restartCount={rc_} reason={rs} exitCode={ec}' + (f' message={msg}' if msg else ''))
p, c = cs('ok-disk'); node, cg, cid = container_cgroup(p, 'c'); st = dict(l.split() for l in cgread(node, cg, 'memory.stat').splitlines())
print(f'  写 100 MiB 到磁盘型 emptyDir:restartCount={c["restartCount"]};日志:{k("logs", "ok-disk", "-n", NS)[1].strip().splitlines()[-1]};memory.current={int(cgread(node, cg, "memory.current")) / 2**20:.0f} MiB(其中 file={int(st["file"]) / 2**20:.0f} MiB shmem={int(st["shmem"]) / 2**20:.0f} MiB anon={int(st["anon"]) / 2**20:.0f} MiB);写了 100 MiB 却只占了 limit 以内,因为页缓存可以被回收')

print('== 四:在线调大 limit——运行中的进程不用重启就能活下来')
k('apply', '-f', '-', input=pod('grow', 'python -u -c \'import time\nL = []\nfor i in range(15):\n    L.append(b"x" * (10 * 2**20)); print("已分配", (i + 1) * 10, "MiB", flush=True); time.sleep(1)\ntime.sleep(3600)\''))
until(lambda: 'MiB' in k('logs', 'grow', '-n', NS)[1], 30, 0.3)
rc, o = k('patch', 'pod', 'grow', '-n', NS, '--subresource=resize', '--type=strategic', '-p', '{"spec":{"containers":[{"name":"c","resources":{"requests":{"memory":"128Mi"},"limits":{"memory":"256Mi"}}}]}}')
print(f'  容器每秒多分配 10 MiB,limit 64Mi;分配刚开始就执行 kubectl patch --subresource=resize 把 limit 调到 256Mi:{o.strip()}')
time.sleep(20); p, c = cs('grow')
print(f'  20 秒后:restartCount={c["restartCount"]};state={list(c["state"])[0]};memory.max={cgread(*container_cgroup(p, "c")[:2], "memory.max") if c["state"].get("running") else "?"};日志最后一行:{k("logs", "grow", "-n", NS)[1].strip().splitlines()[-1]}')
print(f'  spec 里 limit={p["spec"]["containers"][0]["resources"]["limits"]["memory"]};status.containerStatuses[0].resources.limits.memory={c.get("resources", {}).get("limits", {}).get("memory")}')
rmns(NS)
