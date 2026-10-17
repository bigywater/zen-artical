import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k104')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k104')
W = 'kx-main-worker'
def short(o, n=2, w=320): return [re.sub(r'\s+', ' ', l)[:w] for l in o.strip().splitlines() if l.strip()][:n]
def pod(name, cmd, res, vol='', vm='', node=W):
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  nodeName: {node}\n  terminationGracePeriodSeconds: 0\n  containers:\n  - name: c\n    image: busybox:1.36\n    command: [sh, -c, {json.dumps(cmd)}]\n    resources: {{{res}}}\n{vm}{vol}'
print(f'集群 {cn};ephemeral-storage 是节点本地磁盘上的临时空间:容器可写层、emptyDir(磁盘型)、容器日志都算在内。可以像 CPU / 内存一样写 requests 和 limits')

print('== 一:节点的容量和调度')
n = kj('get', 'node', W)['status']; print(f'  节点 worker:capacity.ephemeral-storage={n["capacity"]["ephemeral-storage"]};allocatable.ephemeral-storage={n["allocatable"]["ephemeral-storage"]}(= capacity,没有预留)')
print(f'  对照 df:节点上 /var 所在文件系统总大小 {nx(W, "df -k /var | tail -1 | awk \'{print $2}\'")[1].strip()} KiB(和 capacity 同一个来源:kubelet 的 imagefs/nodefs)')
rc, o = k('apply', '-f', '-', input=pod('huge', 'sleep 3600', 'requests: {ephemeral-storage: 100Ti}', node='').replace('  nodeName: \n', '')); time.sleep(5)
p = kj('get', 'pod', 'huge', '-n', NS); print(f'  requests.ephemeral-storage: 100Ti 的 Pod:phase={p["status"]["phase"]};{[(c["type"], c.get("reason"), c.get("message", "")[:140]) for c in p["status"].get("conditions", []) if c["status"] == "False"]}')
k('delete', 'pod', 'huge', '-n', NS, '--wait=false')

print('== 二:写容器的可写层超过 limit')
k('apply', '-f', '-', input=pod('layer', 'sleep 5; dd if=/dev/zero of=/fill bs=1M count=120 2>/dev/null; echo 写完; sleep 3600', 'requests: {ephemeral-storage: 20Mi}, limits: {ephemeral-storage: 50Mi}')); t0 = time.time()
def gone_or_failed(n):
    p = kj('get', 'pod', n, '-n', NS)
    return (not p) or p['status'].get('phase') == 'Failed'
v, dt = until(lambda: gone_or_failed('layer'), 240, 2)
p = kj('get', 'pod', 'layer', '-n', NS); print(f'  写 120 MiB 到容器根文件系统(limit 50Mi):{time.time() - t0:.0f} 秒后 phase={p["status"]["phase"]},reason={p["status"].get("reason")};message={p["status"].get("message")!r}')
rc, ev = k('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=layer'); print(f'  事件:{[re.sub(chr(32) + "+", " ", l)[:200] for l in ev.strip().splitlines() if "Evict" in l][:2]}')
print(f'  被驱逐的 Pod 对象还在(Failed),容器已被杀;kubectl get 的 STATUS={k("get", "pod", "layer", "-n", NS, "--no-headers")[1].split()[2]}')

print('== 三:写 emptyDir 超过 Pod 总 limit')
VOL = '  volumes: [{name: d, emptyDir: {}}]\n'; VM = ''
k('apply', '-f', '-', input=pod('edir', 'sleep 5; dd if=/dev/zero of=/data/fill bs=1M count=120 2>/dev/null; echo 写完; sleep 3600', 'requests: {ephemeral-storage: 20Mi}, limits: {ephemeral-storage: 50Mi}', vol=VOL).replace('    resources:', '    volumeMounts: [{name: d, mountPath: /data}]\n    resources:')); t0 = time.time()
v, dt = until(lambda: gone_or_failed('edir'), 240, 2); p = kj('get', 'pod', 'edir', '-n', NS)
print(f'  写 120 MiB 到 emptyDir(Pod 总 limit 50Mi):{time.time() - t0:.0f} 秒后 phase={p["status"]["phase"]},reason={p["status"].get("reason")};message={p["status"].get("message")!r}')

print('== 四:内存型 emptyDir 不算 ephemeral-storage')
k('apply', '-f', '-', input=pod('memdir', 'sleep 5; dd if=/dev/zero of=/data/fill bs=1M count=120 2>/dev/null; echo 写完; sleep 3600', 'requests: {ephemeral-storage: 20Mi}, limits: {ephemeral-storage: 50Mi}', vol='  volumes: [{name: d, emptyDir: {medium: Memory}}]\n').replace('    resources:', '    volumeMounts: [{name: d, mountPath: /data}]\n    resources:')); t0 = time.time()
time.sleep(100)
p = kj('get', 'pod', 'memdir', '-n', NS); print(f'  写 120 MiB 到 medium: Memory 的 emptyDir(ephemeral-storage limit 50Mi):{time.time() - t0:.0f} 秒后 phase={p["status"]["phase"]}(没有被驱逐;这部分算内存,不算 ephemeral-storage)')
print(f'  对照 df:容器里 /data 的文件系统 {k("exec", "memdir", "-n", NS, "--", "sh", "-c", "df -k /data | tail -1 | awk \'{print $1}\'")[1].strip()}')
k('delete', 'ns', NS, '--wait=false')
