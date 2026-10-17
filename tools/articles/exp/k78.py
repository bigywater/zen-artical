import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k78')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36'); load('nginx:1.27-alpine')
NS = ns('k78')
W = 'kx-main-worker'
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: Pod
metadata: {{name: app, namespace: {NS}}}
spec:
  nodeName: {W}
  terminationGracePeriodSeconds: 0
  containers:
  - name: main
    image: nginx:1.27-alpine
    imagePullPolicy: IfNotPresent
    env: [{{name: SECRET_MODE, value: prod}}]
    securityContext: {{readOnlyRootFilesystem: true, runAsNonRoot: false}}
    volumeMounts: [{{name: tmp, mountPath: /tmp}}, {{name: cache, mountPath: /var/cache/nginx}}, {{name: run, mountPath: /var/run}}]
  volumes: [{{name: tmp, emptyDir: {{}}}}, {{name: cache, emptyDir: {{}}}}, {{name: run, emptyDir: {{}}}}]
''')
k('wait', '--for=condition=Ready', 'pod/app', '-n', NS, '--timeout=60s')
def dbg(*a, timeout=90): return k('debug', '-n', NS, *a, timeout=timeout)
print(f'集群 {cn};kubectl debug 有三种用法:给运行中的 Pod 加临时容器、复制一份 Pod 来调试、起一个能看到整个节点的 Pod')
print(f'  被调试的 Pod app:主容器 nginx:1.27-alpine,readOnlyRootFilesystem=true;当前 spec.ephemeralContainers={kj("get", "pod", "app", "-n", NS)["spec"].get("ephemeralContainers")}')

print('== 一:临时容器——往运行中的 Pod 里加一个调试容器')
rc, o = dbg('app', '--image=busybox:1.36', '--container=dbg1', '--', 'sh', '-c', 'echo "进程列表(没有 --target):"; ps; echo "我的 /etc/os-release 来自:"; head -1 /etc/os-release 2>/dev/null || echo busybox-image')
time.sleep(5)
print(f'  kubectl debug app --image=busybox:1.36 --container=dbg1:退出码 {rc};{o.strip().splitlines()[:2]}')
rc, lg = k('logs', 'app', '-n', NS, '-c', 'dbg1'); print('  dbg1 的输出(没有 --target,不共享进程命名空间):'); [print('    ' + re.sub(r"\s+", " ", l)[:110]) for l in lg.strip().splitlines()[:6]]
rc, o = dbg('app', '--image=busybox:1.36', '--container=dbg2', '--target=main', '--', 'sh', '-c', 'ps | head -8; ls /proc/1/root/etc/nginx | head -3')
time.sleep(5); rc, lg = k('logs', 'app', '-n', NS, '-c', 'dbg2'); print('  dbg2(--target=main,加入主容器的进程命名空间)的输出:'); [print('    ' + re.sub(r"\s+", " ", l)[:110]) for l in lg.strip().splitlines()[:16]]
p = kj('get', 'pod', 'app', '-n', NS); ec = p['spec']['ephemeralContainers']
print(f'  Pod 的 spec.ephemeralContainers:{[(e["name"], e["image"], e.get("targetContainerName")) for e in ec]};status.ephemeralContainerStatuses:{[(e["name"], list(e["state"].keys())[0], e["state"].get("terminated", {}).get("reason")) for e in p["status"].get("ephemeralContainerStatuses", [])]}')
print(f'  主容器 restartCount={p["status"]["containerStatuses"][0]["restartCount"]}(加临时容器不会重启 Pod);Pod uid 不变')
rc, o = k('patch', 'pod', 'app', '-n', NS, '--type=json', '-p', '[{"op":"remove","path":"/spec/ephemeralContainers/0"}]'); print(f'  想删除一个临时容器(patch remove):退出码 {rc};{o.strip().splitlines()[0][:330]}')
rc, o = k('patch', 'pod', 'app', '-n', NS, '--type=merge', '-p', '{"spec":{"ephemeralContainers":[{"name":"x","image":"busybox:1.36","resources":{"limits":{"cpu":"100m"}}}]}}'); print(f'  直接 patch 加一个带 resources 的临时容器:退出码 {rc};{" ".join(o.strip().splitlines()[:3])[:260]}')

print('== 二:复制一份 Pod 来调试')
rc, o = dbg('app', '--copy-to=app-copy', '--container=main', '--image=busybox:1.36', '--', 'sleep', '3600'); time.sleep(5)
cp = kj('get', 'pod', 'app-copy', '-n', NS); print(f'  kubectl debug app --copy-to=app-copy --image=busybox:1.36 -- sleep 3600:退出码 {rc};副本 app-copy 的 main 容器 image={cp["spec"]["containers"][0]["image"]},command={cp["spec"]["containers"][0].get("command")};原 Pod app 的 main image={p["spec"]["containers"][0]["image"]}(原 Pod 没动)')
print(f'  副本是一个独立的 Pod:ownerReferences={cp["metadata"].get("ownerReferences")};labels={cp["metadata"].get("labels")}(原 Pod 也没有标签);nodeName={cp["spec"].get("nodeName")}(原 Pod 在 {p["spec"]["nodeName"]},副本由调度器重新选了节点)')
rc, o = dbg('app', '--copy-to=app-share', '--share-processes', '--image=busybox:1.36', '--container=dbg3', '--', 'sleep', '3600'); time.sleep(5)
cs = kj('get', 'pod', 'app-share', '-n', NS); print(f'  --share-processes 的副本 app-share:shareProcessNamespace={cs["spec"].get("shareProcessNamespace")};容器 {[c["name"] for c in cs["spec"]["containers"]]}')
rc, o = k('exec', 'app-share', '-n', NS, '-c', 'dbg3', '--', 'ps'); print(f'  在 dbg3 里 ps:{[re.sub(chr(32) + "+", " ", l)[:70] for l in o.strip().splitlines()[:5]]}(能看到 main 的 nginx 进程)')
k('delete', 'pod', 'app-copy', 'app-share', '-n', NS, '--wait=false')

print('== 三:调试节点——一个能看到整个节点的 Pod')
rc, o = k('debug', f'node/{W}', '--image=busybox:1.36', '--profile=sysadmin', '--', 'sh', '-c', 'chroot /host sh -c "hostname; crictl ps | wc -l; ls /etc/kubernetes/manifests | head -2; cat /etc/os-release | head -1"', timeout=90)
print(f'  kubectl debug node/{W.replace("kx-main-", "")} --image=busybox:1.36 -- chroot /host …:退出码 {rc};{o.strip().splitlines()[0][:150]}')
time.sleep(5)
nd = [p_ for p_ in kj('get', 'pods', '-n', 'default')['items'] if p_['metadata']['name'].startswith('node-debugger')]
if nd:
    nd = nd[0]; spec = nd['spec']
    print(f'  生成的 Pod {nd["metadata"]["name"][:32]}…(命名空间 default):nodeName={spec["nodeName"].replace("kx-main-", "")};hostNetwork={spec.get("hostNetwork")};hostPID={spec.get("hostPID")};hostIPC={spec.get("hostIPC")};volumes={[(v["name"], v.get("hostPath", {}).get("path")) for v in spec["volumes"] if v.get("hostPath")]};容器 securityContext={spec["containers"][0].get("securityContext")}')
    rc, lg = k('logs', nd['metadata']['name'], '-n', 'default'); print('  在节点根目录里 chroot 后执行的输出:'); [print('    ' + l[:110]) for l in lg.strip().splitlines()[:6]]
    k('delete', 'pod', nd['metadata']['name'], '-n', 'default', '--wait=false')

print('== 四:--profile 决定调试容器的权限')
for prof in ('general', 'baseline', 'restricted', 'netadmin', 'sysadmin'):
    nm = f'prof-{prof}'; rc, o = dbg('app', '--image=busybox:1.36', f'--container={nm}', f'--profile={prof}', '--', 'sleep', '1')
    time.sleep(2); p = kj('get', 'pod', 'app', '-n', NS); e = next((x for x in p['spec'].get('ephemeralContainers', []) if x['name'] == nm), None)
    print(f'  --profile={prof}:{(e or {}).get("securityContext")}' if e else f'  --profile={prof}:退出码 {rc};{o.strip().splitlines()[-1][:150]}')
k('delete', 'ns', NS, '--wait=false')
