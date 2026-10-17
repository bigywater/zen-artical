import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k95')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36'); load('nginx:1.27-alpine')
NS = ns('k95')
W = 'kx-main-worker'
def pod(name, image, policy=None, node=W):
    pp = f'\n    imagePullPolicy: {policy}' if policy else ''
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  nodeName: {node}\n  terminationGracePeriodSeconds: 0\n  containers:\n  - name: c\n    image: {image}{pp}\n    command: [sleep, "3600"]\n'
def state(name, t=25):
    until(lambda: (kj('get', 'pod', name, '-n', NS)['status'].get('containerStatuses') or [{}])[0].get('state'), t, 0.5)
    c = (kj('get', 'pod', name, '-n', NS)['status'].get('containerStatuses') or [{}])[0]; st = c.get('state', {}); kind = next(iter(st), '?')
    return kind, (st.get(kind) or {}).get('reason'), c
def pol(image): 
    rc, o = k('apply', '-f', '-', '--dry-run=server', '-o', 'jsonpath={.spec.containers[0].imagePullPolicy}', input=pod('probe', image)); return o.strip()
def events(name): return [e['reason'] + ': ' + e['message'][:150] for e in kj('get', 'events', '-n', NS, '--field-selector', f'involvedObject.name={name}')['items'] if e['reason'] in ('Pulling', 'Pulled', 'Failed', 'BackOff', 'ErrImageNeverPull', 'Started', 'Created')]
print(f'集群 {cn};imagePullPolicy 决定 kubelet 创建容器前要不要去仓库拉镜像:Always / IfNotPresent / Never。节点(kind)上已经有 busybox:1.36 和 nginx:1.27-alpine,但没有办法访问外网仓库')

print('== 一:不写 imagePullPolicy 时,默认值由镜像引用决定')
for img in ('busybox', 'busybox:latest', 'busybox:1.36', 'busybox@sha256:' + 'a' * 64, 'registry.example.com/team/app'):
    print(f'  image: {img[:40]:<42}→ imagePullPolicy={pol(img)}')
print('  规则:没写 tag 或 tag 是 latest → Always;指定了别的 tag 或 digest → IfNotPresent(由 API Server 的准入补上)')

REG = 'localhost:5999'
sh('docker', 'tag', 'busybox:1.36', f'{REG}/app:1.0'); load(f'{REG}/app:1.0')
print('== 二:镜像在本地,但仓库连不上——Always 失败,IfNotPresent 和 Never 能跑')
k('apply', '-f', '-', input=pod('ifnp-present', f'{REG}/app:1.0', 'IfNotPresent') + '---\n' + pod('never-present', f'{REG}/app:1.0', 'Never') + '---\n' + pod('always-present', f'{REG}/app:1.0', 'Always'))
def settle(n, t=40):
    until(lambda: (lambda c: c.get('state', {}).get('running') or (c.get('state', {}).get('waiting') or {}).get('reason') in ('ImagePullBackOff', 'ErrImageNeverPull', 'ErrImagePull'))((kj('get', 'pod', n, '-n', NS)['status'].get('containerStatuses') or [{}])[0]), t, 1)
for n in ('ifnp-present', 'never-present', 'always-present'):
    settle(n); kind, reason, c = state(n, 3); st = c.get('state', {}).get(kind, {}) or {}
    print(f'  {n}({REG}/app:1.0 本地已有):容器状态 {kind}{"/" + reason if reason else ""};{(st.get("message") or "")[:150]!r}')
print(f'    always-present 的事件:{events("always-present")[:4]}')
t0 = time.time()
k('apply', '-f', '-', input=pod('docker-always', 'busybox:1.36', 'Always')); time.sleep(60)
kind, reason, c = state('docker-always', 3); print(f'  对照:busybox:1.36(docker.io 的镜像,节点上有,但访问 docker.io 的连接不通也不拒绝)+ Always,过了 60 秒:容器状态 {kind}/{reason},事件 {events("docker-always")[:2]}(连接既不通也不被拒绝,要等超时才报错:DeadlineExceeded)')

print('== 三:本地没有的镜像')
k('apply', '-f', '-', input=pod('ifnp-missing', f'{REG}/missing:1.0', 'IfNotPresent') + '---\n' + pod('never-missing', f'{REG}/missing:1.0', 'Never'))
for n, d in (('ifnp-missing', 'IfNotPresent + 本地没有'), ('never-missing', 'Never + 本地没有')):
    settle(n); kind, reason, c = state(n, 3); st = c.get('state', {}).get(kind, {}) or {}; print(f'  {n}({d}):容器状态 {kind}/{reason};message={(st.get("message") or "")[:200]!r}')
print(f'  对照:never-missing 的事件里{"没有" if not [e for e in events("never-missing") if "Pulling" in e] else "有"} Pulling(Never 不会尝试拉取);ifnp-missing 的事件:{events("ifnp-missing")[:3]}')

print('== 四:同一个 tag 可能对应不同的镜像——IfNotPresent 只看 tag 在不在')
k('delete', 'pod', '--all', '-n', NS, '--wait=true', timeout=60)
sh('docker', 'tag', 'busybox:1.36', 'demo:v1'); load('demo:v1')
k('apply', '-f', '-', input=pod('first', 'demo:v1', 'IfNotPresent')); k('wait', '--for=condition=Ready', 'pod/first', '-n', NS, '--timeout=60s')
id1 = kj('get', 'pod', 'first', '-n', NS)['status']['containerStatuses'][0]['imageID']
print(f'  节点上 demo:v1 原本是 busybox:第一个 Pod first 的 imageID={id1[-24:]}')
rc, o = nx(W, 'ctr -n k8s.io images tag --force docker.io/library/nginx:1.27-alpine docker.io/library/demo:v1'); print(f'  在节点上把 demo:v1 这个 tag 改指向 nginx 镜像:{o.strip() or "完成"}')
k('apply', '-f', '-', input=pod('second', 'demo:v1', 'IfNotPresent')); k('wait', '--for=condition=Ready', 'pod/second', '-n', NS, '--timeout=60s')
id2 = kj('get', 'pod', 'second', '-n', NS)['status']['containerStatuses'][0]['imageID']
print(f'  第二个 Pod second 同样写 demo:v1 + IfNotPresent:imageID={id2[-24:]}(不同:{id1 != id2})——没有拉取事件:{[e for e in events("second") if "Pulling" in e] or "无 Pulling"}')
rc, o = k('exec', 'first', '-n', NS, '--', 'sh', '-c', 'busybox | head -1 | cut -c1-30'); rc2, o2 = k('exec', 'second', '-n', NS, '--', 'sh', '-c', 'nginx -v 2>&1'); print(f'  first 里是 {o.strip()};second 里是 {o2.strip()}——同一个 tag,同一个节点,两个 Pod 跑的是不同的镜像')
print('  这就是为什么生产环境推荐固定 digest 或不可变 tag,而不是依赖 latest + Always 去“刷新”')
nx(W, 'ctr -n k8s.io images rm docker.io/library/demo:v1 >/dev/null 2>&1; crictl rmi docker.io/library/demo:v1 >/dev/null 2>&1; true')
k('delete', 'ns', NS, '--wait=false')
