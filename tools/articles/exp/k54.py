import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k54')
cn, _ = up('sched', cfg=config(workers=4)); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k54')
def pod(name, cmd, vol, res='', node=None):
    nn = f'  nodeName: {node}\n' if node else ''
    return f'''apiVersion: v1
kind: Pod
metadata: {{name: {name}, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
{nn}  containers:
  - name: c
    image: busybox:1.36
    command: [sh, -c, {json.dumps(cmd)}]
    volumeMounts: [{{name: v, mountPath: /v}}]
{res}  volumes:
  - name: v
    emptyDir: {vol}
'''
def ex(name, cmd):
    rc, o = k('exec', name, '-n', NS, '--', 'sh', '-c', cmd); return o.strip()
def running(name, t=40): return until(lambda: kj('get', 'pod', name, '-n', NS)['status'].get('containerStatuses', [{}])[0].get('state', {}).get('running'), t, 0.3)
print(f'集群 {cn};emptyDir 随 Pod 创建、随 Pod 删除,默认放在节点磁盘上,medium: Memory 则是 tmpfs')

print('== 一:生命周期——容器重启数据还在,Pod 删了数据就没了')
k('apply', '-f', '-', input=pod('life', '[ -f /v/seen ] || { touch /v/seen; echo 第一次运行 >> /v/log; sleep 4; exit 1; }; echo 容器重启后又运行 >> /v/log; sleep 3600', '{}')); running('life')
p = kj('get', 'pod', 'life', '-n', NS); node = p['spec']['nodeName']; uid = p['metadata']['uid']
d = f'/var/lib/kubelet/pods/{uid}/volumes/kubernetes.io~empty-dir/v'
print(f'  Pod life 在 {node.replace("kx-sched-", "")} 上;节点上的目录 {d.replace(uid, "<uid>")} 里:{nx(node, f"ls {d}")[1].split()}')
until(lambda: kj('get', 'pod', 'life', '-n', NS)['status']['containerStatuses'][0]['restartCount'] >= 1, 60, 0.3); until(lambda: 'seen' in ex('life', 'ls /v') if kj('get', 'pod', 'life', '-n', NS)['status']['containerStatuses'][0].get('state', {}).get('running') else False, 60, 0.5)
c = kj('get', 'pod', 'life', '-n', NS)['status']['containerStatuses'][0]
print(f'  第一个容器写完文件后自己 exit 1,kubelet 重启了它(restartCount={c["restartCount"]});重启后 /v 里的文件:{ex("life", "ls /v").split()};/v/log 的内容:{ex("life", "cat /v/log").splitlines()}(emptyDir 里的文件跨容器重启保留)')
mt = nx(node, f'ls -d {d}')[1].strip(); print(f'  同一个目录还在节点上:{mt != "" and "是" or "否"}')
k('delete', 'pod', 'life', '-n', NS, '--wait=true', timeout=60)
v, dt = until(lambda: 'No such file' in nx(node, f"ls -d {d} 2>&1")[1], 60, 0.5)
print(f'  删除 Pod 之后节点上的目录:{"消失了(等了 %.1f 秒)" % dt if v else "60 秒内还在"}')
k('apply', '-f', '-', input=pod('life', 'echo 新 Pod 写入 >> /v/log; sleep 3600', '{}', node=node)); running('life')
print(f'  同名 Pod 重新创建(同一个节点)后 /v/log:{ex("life", "cat /v/log").splitlines()}(是一个新的空目录)')
k('delete', 'pod', 'life', '-n', NS, '--wait=true', timeout=60)

print('== 二:medium: Memory——tmpfs,算在容器的内存里')
k('apply', '-f', '-', input=pod('disk', 'sleep 3600', '{}')); k('apply', '-f', '-', input=pod('mem', 'sleep 3600', '{medium: Memory}'))
running('disk'); running('mem')
for n in ('disk', 'mem'):
    print(f'  {n}:/proc/mounts 里 /v 这一行:{ex(n, "grep \" /v \" /proc/mounts")[:90]}')
    print(f'    df /v:{ex(n, "df -k /v | tail -1")}')
node_mem = int(nx(kj('get', 'pod', 'mem', '-n', NS)['spec']['nodeName'], "grep MemTotal /proc/meminfo")[1].split()[1])
print(f'  节点内存 MemTotal={node_mem} KiB(没写 sizeLimit 时 tmpfs 的大小就是整个节点内存)')
def memcur(n):
    p = kj('get', 'pod', n, '-n', NS); node, cg, cid = container_cgroup(p, 'c'); return int(cgread(node, cg, 'memory.current')), node, cg
for n in ('disk', 'mem'):
    b, node, cg = memcur(n); ex(n, 'dd if=/dev/zero of=/v/big bs=1M count=50 2>/dev/null; sync'); time.sleep(2); a, _, _ = memcur(n)
    print(f'  往 {n} 的 /v 写 50 MiB:容器 cgroup 的 memory.current {b // 1024} KiB → {a // 1024} KiB(增加 {(a - b) // 2**20} MiB);文件系统占用 {ex(n, "du -sk /v").split()[0]} KiB')
    st = {l.split()[0]: int(l.split()[1]) for l in cgread(node, cg, 'memory.stat').splitlines()}
    print(f'    memory.stat:anon={st["anon"] // 1024} KiB;file(页缓存)={st["file"] // 1024} KiB;shmem(tmpfs 页)={st["shmem"] // 1024} KiB;file_dirty={st["file_dirty"] // 1024} KiB')
k('delete', 'pod', 'disk', 'mem', '-n', NS, '--wait=true', timeout=60)

print('== 三:Memory 卷 + 容器 memory limit——写到超过 limit 会被 OOMKilled')
res = '    resources: {requests: {memory: 64Mi}, limits: {memory: 64Mi}}\n'
k('apply', '-f', '-', input=pod('memoom', 'sleep 6; dd if=/dev/zero of=/v/big bs=1M count=100; echo 写完; sleep 3600', '{medium: Memory}', res)); running('memoom')
seq = []; t0 = time.time()
while time.time() - t0 < 45:
    c = kj('get', 'pod', 'memoom', '-n', NS)['status']['containerStatuses'][0]; st = c.get('state', {})
    kind = next(iter(st)); r = (st[kind].get('reason') or '') if kind != 'running' else ''
    key = f'{kind}:{r}' if r else kind
    if not seq or seq[-1][1] != key: seq.append((round(time.time() - t0, 1), key, c['restartCount']))
    time.sleep(0.15)
print(f'  limit 64Mi、往 Memory 卷写 100 MiB:容器状态(相对时间秒, 状态, restartCount)依次是 {seq}')
c = kj('get', 'pod', 'memoom', '-n', NS)['status']['containerStatuses'][0]; w = c.get('state', {}).get('waiting', {}); lt = c['lastState'].get('terminated', {})
print(f'  45 秒后 restartCount={c["restartCount"]};state.waiting.reason={w.get("reason")};lastState.terminated.reason={lt.get("reason")};message=…{(lt.get("message") or w.get("message") or "")[-90:]}')
pn = kj('get', 'pod', 'memoom', '-n', NS)['spec']['nodeName']; print(f'  这时 tmpfs 里的数据还在吗:Pod 级内存 memory.current={int(cgread(pn, pod_cgroup(kj("get", "pod", "memoom", "-n", NS))[1], "memory.current")) // 2**20} MiB(容器重启了,tmpfs 的页还留在 Pod 的 cgroup 里)')
k('delete', 'pod', 'memoom', '-n', NS, '--wait=true', timeout=60)

print('== 四:sizeLimit——Memory 卷立刻 ENOSPC,磁盘卷要等 kubelet 周期性检查后驱逐')
k('apply', '-f', '-', input=pod('memsz', 'sleep 3600', '{medium: Memory, sizeLimit: 20Mi}')); running('memsz')
print(f'  Memory 卷 sizeLimit 20Mi:df {ex("memsz", "df -k /v | tail -1")}')
print(f'    写 30 MiB:{ex("memsz", "dd if=/dev/zero of=/v/big bs=1M count=30 2>&1").splitlines()[:3]}')
print(f'    之后 Pod 状态:{kj("get", "pod", "memsz", "-n", NS)["status"]["phase"]},du {ex("memsz", "du -sk /v").split()[0]} KiB')
k('delete', 'pod', 'memsz', '-n', NS, '--wait=true', timeout=60)
k('apply', '-f', '-', input=pod('disksz', 'sleep 3600', '{sizeLimit: 20Mi}')); running('disksz')
print(f'  磁盘卷 sizeLimit 20Mi:df {ex("disksz", "df -k /v | tail -1")[:60]}(df 看到的仍是整块磁盘,sizeLimit 不是文件系统配额)')
print(f'    写 30 MiB:{ex("disksz", "dd if=/dev/zero of=/v/big bs=1M count=30 2>&1 | tail -1")}')
t0 = time.time()
v, dt = until(lambda: kj('get', 'pod', 'disksz', '-n', NS)['status']['phase'] == 'Failed', 150, 1)
p = kj('get', 'pod', 'disksz', '-n', NS)
print(f'  写完之后 {dt:.0f} 秒:phase={p["status"]["phase"]} reason={p["status"].get("reason")};message={p["status"].get("message", "")[:140]}')
ev = [e['reason'] + ': ' + e['message'][:120] for e in kj('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=disksz')['items'] if e['reason'] in ('Evicted', 'Killing')]
print(f'    事件:{ev}')
k('delete', 'pod', '--all', '-n', NS, '--wait=true', timeout=60)
