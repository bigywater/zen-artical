import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k55')
cn, _ = up('main')
load('busybox:1.36')
NS = ns('k55')
def ex(name, cmd):
    rc, o = k('exec', name, '-n', NS, '--', 'sh', '-c', cmd); return o.strip()
def running(name, t=60): return until(lambda: kj('get', 'pod', name, '-n', NS)['status'].get('containerStatuses', [{}])[0].get('state', {}).get('running'), t, 0.3)
def pod(name, sources, extra=''):
    return f'''apiVersion: v1
kind: Pod
metadata: {{name: {name}, namespace: {NS}, labels: {{app: demo}}}}
spec:
  terminationGracePeriodSeconds: 0
  containers:
  - name: c
    image: busybox:1.36
    command: [sleep, "3600"]
    resources: {{requests: {{cpu: 250m}}}}
    volumeMounts: [{{name: all, mountPath: /etc/all, readOnly: true}}]
  volumes:
  - name: all
    projected:
{extra}      sources:
{sources.replace(chr(10) + '    ', chr(10) + '      ').replace('    -', '      -', 1) if False else ''.join('  ' + l for l in sources.splitlines(True))}'''
print(f'集群 {cn};projected 卷把多个来源(Secret、ConfigMap、Downward API、ServiceAccountToken)合并成同一个目录挂进容器')
k('create', 'secret', 'generic', 'db', '-n', NS, '--from-literal=password=s3cret', '--from-literal=user=admin')
k('create', 'configmap', 'app', '-n', NS, '--from-literal=mode=prod', '--from-literal=level=info')

print('== 一:四种来源合并成一个目录')
src = '''    - secret: {name: db, items: [{key: password, path: creds/db-password, mode: 0400}]}
    - configMap: {name: app}
    - downwardAPI: {items: [{path: meta/labels, fieldRef: {fieldPath: metadata.labels}}, {path: meta/cpu-request, resourceFieldRef: {containerName: c, resource: requests.cpu, divisor: 1m}}]}
    - serviceAccountToken: {path: token/jwt, audience: demo-audience, expirationSeconds: 3600}
'''
k('apply', '-f', '-', input=pod('p1', src)); running('p1')
print('  容器里 /etc/all 下的所有文件(find):' + ex('p1', 'cd /etc/all; find -L . -type f -not -path "./..*" | sort').replace('\n', '  '))
print('  ls -la /etc/all:'); [print('    ' + l) for l in ex('p1', 'ls -la /etc/all').splitlines()]
print(f'  各文件内容:db-password={ex("p1", "cat /etc/all/creds/db-password")!r};mode={ex("p1", "cat /etc/all/mode")!r};labels={ex("p1", "cat /etc/all/meta/labels")!r};cpu-request={ex("p1", "cat /etc/all/meta/cpu-request")!r}')
print(f'  权限:db-password {ex("p1", "stat -L -c %a /etc/all/creds/db-password")}(items 里写的 mode 0400);mode(没写 mode){ex("p1", "stat -L -c %a /etc/all/mode")}(volume 的 defaultMode 0644)')
c = jwt_claims(ex('p1', 'cat /etc/all/token/jwt')); print(f'  token/jwt 的声明:aud={c["aud"]};exp-iat={c["exp"] - c["iat"]} 秒;sub={c["sub"]}')
print(f'  关键:Secret 的 user 键没出现在目录里(因为用了 items,只挂了 password):{"user" not in ex("p1", "find /etc/all -name user")}')

print('== 二:不同来源写到同一个路径——Pod 被拒绝创建')
src2 = '''    - secret: {name: db, items: [{key: password, path: same}]}
    - configMap: {name: app, items: [{key: mode, path: same}]}
'''
rc, o = k('apply', '-f', '-', input=pod('p2', src2)); print(f'  创建:退出码 {rc};{" ".join(o.split(chr(10))[:2])[:200]}')
src3 = '''    - secret: {name: db}
    - configMap: {name: app}
'''
k('apply', '-f', '-', input=pod('p3', src3)); running('p3')
print(f'  整个 Secret + 整个 ConfigMap(键名不同)合并:{ex("p3", "ls /etc/all | grep -v ^\\\\.").split()}')
k('create', 'configmap', 'app2', '-n', NS, '--from-literal=password=from-configmap')
src4 = '''    - secret: {name: db}
    - configMap: {name: app2}
'''
rc, o = k('apply', '-f', '-', input=pod('p4', src4)); print(f'  整个 Secret 和整个 ConfigMap 里恰好有同名键 password:退出码 {rc};{o.strip()[:200]}')
if rc == 0:
    running('p4'); print(f'    运行起来之后 /etc/all/password 的内容:{ex("p4", "cat /etc/all/password")!r}(ConfigMap 在列表里排在 Secret 之后)')
    src4b = '    - configMap: {name: app2}\n    - secret: {name: db}\n'
    k('apply', '-f', '-', input=pod('p4b', src4b)); running('p4b'); print(f'    把两个来源的顺序对调(ConfigMap 在前、Secret 在后):/etc/all/password={ex("p4b", "cat /etc/all/password")!r}')
k('delete', 'pod', 'p2', 'p3', 'p4', 'p4b', '-n', NS, '--ignore-not-found', '--wait=true', timeout=60)

print('== 三:来源不存在——Pod 卡在 ContainerCreating;optional 让它继续')
src5 = '''    - secret: {name: later}
    - configMap: {name: app}
'''
k('apply', '-f', '-', input=pod('p5', src5)); time.sleep(8)
p = kj('get', 'pod', 'p5', '-n', NS); print(f'  Secret later 不存在:phase={p["status"]["phase"]};容器 waiting.reason={(p["status"].get("containerStatuses") or [{}])[0].get("state", {}).get("waiting", {}).get("reason")}')
ev = [e['reason'] + ': ' + e['message'][:130] for e in kj('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=p5')['items'] if e['reason'] in ('FailedMount',)]
print(f'    事件:{ev[-1:]}')
t0 = time.time(); k('create', 'secret', 'generic', 'later', '-n', NS, '--from-literal=k=v'); v, dt = until(lambda: kj('get', 'pod', 'p5', '-n', NS)['status'].get('containerStatuses', [{}])[0].get('state', {}).get('running'), 90, 0.5)
print(f'  创建 Secret later 之后 {dt:.1f} 秒容器启动(kubelet 重试挂载有间隔)')
src6 = '''    - secret: {name: nobody, optional: true}
    - configMap: {name: app}
'''
k('apply', '-f', '-', input=pod('p6', src6)); t0 = time.time(); v, dt = running('p6')
print(f'  optional: true 的 Secret nobody 不存在:{dt:.1f} 秒后 Running;/etc/all 里有:{ex("p6", "ls /etc/all | grep -v ^\\\\.").split()}(只有 ConfigMap 的键)')
k('create', 'secret', 'generic', 'nobody', '-n', NS, '--from-literal=hi=there'); v, dt = until(lambda: 'hi' in ex('p6', 'ls /etc/all'), 120, 1)
print(f'  之后创建 Secret nobody:{"%.0f 秒后" % dt if v else "120 秒内没有"} /etc/all/hi 出现(optional 的来源后来出现也会补进来)')
src7 = '''    - secret: {name: db, items: [{key: nokey, path: x}]}
'''
k('apply', '-f', '-', input=pod('p7', src7)); time.sleep(8)
p = kj('get', 'pod', 'p7', '-n', NS); ev = [e['message'][:150] for e in kj('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=p7')['items'] if e['reason'] == 'FailedMount']
print(f'  items 里引用不存在的键 nokey:容器 {(p["status"].get("containerStatuses") or [{}])[0].get("state", {}).get("waiting", {}).get("reason")};事件:{ev[-1:]}')
k('delete', 'pod', '--all', '-n', NS, '--wait=true', timeout=60)

print('== 四:serviceAccountToken 来源的限制')
for exp_ in (100, 600, 3600):
    s_ = f'    - serviceAccountToken: {{path: t, audience: a, expirationSeconds: {exp_}}}\n'
    rc, o = k('apply', '-f', '-', input=pod(f'e{exp_}', s_)); print(f'  expirationSeconds={exp_}:退出码 {rc};{" ".join(o.split(chr(10))[:2])[:260]}')
s_ = '    - serviceAccountToken: {path: t}\n'
k('apply', '-f', '-', input=pod('ed', s_)); running('ed'); c = jwt_claims(ex('ed', 'cat /etc/all/t')); print(f'  不写 audience 和 expirationSeconds:aud={c["aud"]};exp-iat={c["exp"] - c["iat"]} 秒(默认值 3600)')
k('delete', 'pod', '--all', '-n', NS, '--wait=true', timeout=60)
