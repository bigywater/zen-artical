import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k56')
cn, _ = up('main')
load('busybox:1.36')
NS = ns('k56')
def ex(name, cmd):
    rc, o = k('exec', name, '-n', NS, '--', 'sh', '-c', cmd); return o.strip()
def running(name, t=60): return until(lambda: kj('get', 'pod', name, '-n', NS)['status'].get('containerStatuses', [{}])[0].get('state', {}).get('running'), t, 0.3)
def setcm(v): k('apply', '-f', '-', input=f'apiVersion: v1\nkind: ConfigMap\nmetadata: {{name: cfg, namespace: {NS}}}\ndata:\n  level: {v}\n')
POD = f'''apiVersion: v1
kind: Pod
metadata: {{name: app, namespace: {NS}}}
spec:
  terminationGracePeriodSeconds: 0
  containers:
  - name: c
    image: busybox:1.36
    command: [sh, -c, "[ -f /tmp/seen ] || {{ touch /tmp/seen; sleep 3600; }}; sleep 3600"]
    env: [{{name: LEVEL, valueFrom: {{configMapKeyRef: {{name: cfg, key: level}}}}}}]
    volumeMounts: [{{name: cfg, mountPath: /etc/cfg}}]
  volumes: [{{name: cfg, configMap: {{name: cfg}}}}]
'''
print(f'集群 {cn};ConfigMap 被改之后:挂载的文件会被 kubelet 同步更新,环境变量不会')
setcm('v1'); k('apply', '-f', '-', input=POD); running('app')

print('== 一:改 ConfigMap——文件什么时候变,环境变量变不变')
print(f'  初始:环境变量 LEVEL={ex("app", "echo $LEVEL")!r};文件 /etc/cfg/level={ex("app", "cat /etc/cfg/level")!r}')
delays = []
for i, v in enumerate(('v2', 'v3', 'v4')):
    t0 = time.time(); setcm(v)
    ok, dt = until(lambda: ex('app', 'cat /etc/cfg/level') == v, 150, 0.5); delays.append(round(dt, 1))
    time.sleep(2)
print(f'  连续改 3 次 ConfigMap(v2 → v3 → v4),从 apply 到容器里读到新内容的延迟(秒):{delays}')
print(f'  此时环境变量 LEVEL={ex("app", "echo $LEVEL")!r}(进程启动时就固定了,之后不会再变);文件 /etc/cfg/level={ex("app", "cat /etc/cfg/level")!r}')

print('== 二:文件是怎么“原子”换掉的——..data 符号链接')
def tree(): return ex('app', 'cd /etc/cfg; for f in ..data level; do echo "$f -> $(readlink $f)"; done; ls -d ..20* | tr "\\n" " "; echo; ls -i ..data/level | cut -d" " -f1')
before = tree().splitlines(); print('  更新前:'); [print('    ' + l) for l in before]
setcm('v5'); ok, dt = until(lambda: ex('app', 'cat /etc/cfg/level') == 'v5', 150, 0.5)
after = tree().splitlines(); print(f'  更新后({dt:.0f} 秒):'); [print('    ' + l) for l in after]
print(f'  旧的时间戳目录是否还在:{before[2].strip().split()[0] in after[2]}')

print('== 三:环境变量什么时候才更新——容器重启(不是 Pod 重建也行)')
pod0 = kj('get', 'pod', 'app', '-n', NS); uid0 = pod0['metadata']['uid']
print(f'  现在 ConfigMap 里 level={kj("get", "cm", "cfg", "-n", NS)["data"]["level"]!r},容器环境变量 LEVEL={ex("app", "echo $LEVEL")!r}')
node = pod0['spec']['nodeName']; cid = pod0['status']['containerStatuses'][0]['containerID'].split('//')[1]
nx(node, f'crictl stop {cid[:12]} 2>&1 | tail -1')
until(lambda: kj('get', 'pod', 'app', '-n', NS)['status']['containerStatuses'][0]['restartCount'] >= 1, 60, 0.3); running('app')
p = kj('get', 'pod', 'app', '-n', NS)
print(f'  用 crictl 停掉容器、kubelet 重启它(restartCount={p["status"]["containerStatuses"][0]["restartCount"]},Pod uid 没变:{p["metadata"]["uid"] == uid0})后:LEVEL={ex("app", "echo $LEVEL")!r}(重启时重新读 ConfigMap)')

print('== 四:删掉 ConfigMap——已经挂上的文件还在')
k('delete', 'cm', 'cfg', '-n', NS); time.sleep(5)
print(f'  删除 ConfigMap 后 5 秒:Pod phase={kj("get", "pod", "app", "-n", NS)["status"]["phase"]};文件 /etc/cfg/level={ex("app", "cat /etc/cfg/level")!r}')
time.sleep(100)
print(f'  100 秒后:Pod phase={kj("get", "pod", "app", "-n", NS)["status"]["phase"]};文件 /etc/cfg/level={ex("app", "cat /etc/cfg/level")!r}(kubelet 同步失败只是产生 FailedMount 事件,不会清掉文件)')
ev = [e['reason'] + ': ' + e['message'][:100] for e in kj('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=app')['items'] if e['reason'] in ('FailedMount',)]
print(f'    事件里的 FailedMount:{ev[-1:] or "(没有)"}')
k('delete', 'pod', 'app', '-n', NS, '--wait=true', timeout=60)
