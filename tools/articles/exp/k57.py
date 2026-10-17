import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k57')
cn, _ = up('main')
load('busybox:1.36')
NS = ns('k57')
def ex(name, cmd, c='c'):
    rc, o = k('exec', name, '-n', NS, '-c', c, '--', 'sh', '-c', cmd); return o.strip()
def running(name, t=60): return until(lambda: all(s.get('state', {}).get('running') for s in kj('get', 'pod', name, '-n', NS)['status'].get('containerStatuses', [{}])), t, 0.3)
def setcm(v): k('apply', '-f', '-', input=f'apiVersion: v1\nkind: ConfigMap\nmetadata: {{name: cfg, namespace: {NS}}}\ndata:\n  app.conf: {v}\n  other.conf: other\n')
print(f'集群 {cn};volumeMounts.subPath 把卷里的一个子路径单独挂到一个位置;ConfigMap 更新时,subPath 挂载的文件不会被更新')
setcm('v1')
POD = f'''apiVersion: v1
kind: Pod
metadata: {{name: sp, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  containers:
  - name: c
    image: busybox:1.36
    command: [sleep, "3600"]
    volumeMounts:
    - {{name: cfg, mountPath: /whole}}
    - {{name: cfg, mountPath: /etc/app.conf, subPath: app.conf}}
  volumes:
  - name: cfg
    configMap: {{name: cfg}}
'''
k('apply', '-f', '-', input=POD); running('sp')

print('== 一:改 ConfigMap——整体挂载会更新,subPath 挂载不会')
print(f'  初始:/whole/app.conf={ex("sp", "cat /whole/app.conf")!r};/etc/app.conf={ex("sp", "cat /etc/app.conf")!r}')
setcm('v2'); ok, dt = until(lambda: ex('sp', 'cat /whole/app.conf') == 'v2', 150, 0.5)
print(f'  改成 v2:整体挂载的 /whole/app.conf {dt:.0f} 秒后变成 v2')
time.sleep(60)
print(f'  再等 60 秒(总共 {dt + 60:.0f} 秒):/whole/app.conf={ex("sp", "cat /whole/app.conf")!r};/etc/app.conf={ex("sp", "cat /etc/app.conf")!r}(subPath 的文件一直是 v1)')

print('== 二:两种挂载在容器里长什么样')
print('  ls -la /whole:'); [print('    ' + l) for l in ex('sp', 'ls -la /whole').splitlines() if 'app.conf' in l or 'other.conf' in l or '..data' in l]
print('  ls -la /etc/app.conf:'); print('    ' + ex('sp', 'ls -la /etc/app.conf'))
mi = ex('sp', 'grep -E " /whole | /etc/app.conf " /proc/self/mountinfo')
for l in mi.splitlines():
    f = l.split(); print(f'  mountinfo:挂载点 {f[4]};来源路径 …/{f[3].split("/pods/")[1].split("/", 1)[1] if "/pods/" in f[3] else f[3]}')
p = kj('get', 'pod', 'sp', '-n', NS); node = p['spec']['nodeName']; uid = p['metadata']['uid']
print(f'  节点上卷目录里的 ..data 现在指向:{nx(node, f"readlink /var/lib/kubelet/pods/{uid}/volumes/kubernetes.io~configmap/cfg/..data")[1].strip()};目录里 app.conf 的内容 {nx(node, f"cat /var/lib/kubelet/pods/{uid}/volumes/kubernetes.io~configmap/cfg/app.conf")[1].strip()!r}')

print('== 三:想让 subPath 的文件变——重建容器(重启容器就行)')
nodeid = p['status']['containerStatuses'][0]['containerID'].split('//')[1]
nx(node, f'crictl stop {nodeid[:12]} 2>&1 | tail -1'); until(lambda: kj('get', 'pod', 'sp', '-n', NS)['status']['containerStatuses'][0]['restartCount'] >= 1, 60, 0.3); running('sp')
print(f'  容器重启后(restartCount=1,Pod 没重建):/etc/app.conf={ex("sp", "cat /etc/app.conf")!r}(新容器启动时从卷里重新取了 v2)')

print('== 四:subPath 的另一个用途——只挂一个文件,不遮住目录里的其他文件')
POD2 = f'''apiVersion: v1
kind: Pod
metadata: {{name: sp2, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  containers:
  - name: c
    image: busybox:1.36
    command: [sleep, "3600"]
    volumeMounts:
    - {{name: cfg, mountPath: /var/app.conf, subPath: app.conf}}
  volumes:
  - name: cfg
    configMap: {{name: cfg}}
'''
k('apply', '-f', '-', input=POD2); running('sp2')
print(f'  没挂卷时 /var 里有:{ex("sp2", "ls /var | grep -v app.conf").split()}')
POD3 = POD2.replace('sp2', 'sp3').replace('/var/app.conf, subPath: app.conf', '/var, readOnly: true')
k('apply', '-f', '-', input=POD3); running('sp3')
print(f'  把整个卷挂到 /var 之后 /var 里只剩:{ex("sp3", "ls /var").split()}(原来的内容被遮住)')
print(f'  用 subPath 挂单个文件到 /var/app.conf 后 /var 里有:{ex("sp2", "ls /var").split()}(原来的文件都在,多了 app.conf)')

print('== 五:subPathExpr——用环境变量给每个 Pod 一个独立子目录')
POD4 = lambda n: f'''apiVersion: v1
kind: Pod
metadata: {{name: {n}, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  nodeName: {node}
  containers:
  - name: c
    image: busybox:1.36
    command: [sh, -c, "echo $POD_NAME >> /logs/out.log; sleep 3600"]
    env: [{{name: POD_NAME, valueFrom: {{fieldRef: {{fieldPath: metadata.name}}}}}}]
    volumeMounts: [{{name: shared, mountPath: /logs, subPathExpr: $(POD_NAME)}}]
  volumes:
  - name: shared
    hostPath: {{path: /tmp/k57-shared, type: DirectoryOrCreate}}
'''
for n in ('w1', 'w2'): k('apply', '-f', '-', input=POD4(n)); running(n)
time.sleep(1)
print(f'  两个 Pod 共用节点上的 hostPath /tmp/k57-shared,各自 subPathExpr=$(POD_NAME):节点上 {nx(node, "cd /tmp/k57-shared && for d in *; do echo $d/out.log=$(cat $d/out.log); done")[1].split()}')
nx(node, 'rm -rf /tmp/k57-shared')
k('delete', 'pod', '--all', '-n', NS, '--wait=true', timeout=60)
