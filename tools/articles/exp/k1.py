import sys, os, re, time, json, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k1')
cn, t_up = up('main')
NS = ns('k1')
k('label', 'ns', NS, 'pod-security.kubernetes.io/enforce=restricted', '--overwrite')
server = ko('config', 'view', '--minify', '-o', 'jsonpath={.clusters[0].cluster.server}')
sa_tok = ko('create', 'token', 'default', '-n', NS)   # k1 命名空间里 default 这个 ServiceAccount 的令牌,没有任何 RBAC 权限
print(f'集群:{cn}(3 节点 kind,Kubernetes {ko("version", "-o", "json").split(chr(34)+"serverVersion"+chr(34))[1].split(chr(34)+"gitVersion"+chr(34)+": "+chr(34))[1].split(chr(34))[0]}),命名空间 {NS} 带 pod-security enforce=restricted')


def call(method, path, token=None, body=None):
    cmd = ['curl', '-sk', '-X', method, '-w', '\n%{http_code}', '-H', 'Content-Type: application/json']
    if token: cmd += ['-H', f'Authorization: Bearer {token}']
    if body is not None: cmd += ['-d', json.dumps(body)]
    r = subprocess.run(cmd + [server + path], capture_output=True, text=True, timeout=30)
    txt, code = r.stdout.rsplit('\n', 1)
    try: j = json.loads(txt)
    except Exception: j = {}
    return int(code), j


def admin_token():
    # kubectl 自己用的是客户端证书;curl 里用管理员身份要换成一个有权限的 ServiceAccount 令牌
    k('create', 'sa', 'k1-admin', '-n', NS)
    k('create', 'clusterrolebinding', 'k1-admin', '--clusterrole=cluster-admin', f'--serviceaccount={NS}:k1-admin')
    return ko('create', 'token', 'k1-admin', '-n', NS)


good_pod = lambda name: {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name}, 'spec': {'containers': [{'name': 'c', 'image': 'busybox:1.36', 'command': ['sleep', '3600'], 'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}, 'runAsNonRoot': True, 'runAsUser': 1000, 'seccompProfile': {'type': 'RuntimeDefault'}}}]}}
bad_schema = lambda name: {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name}, 'spec': {'containers': [{'name': 'c', 'image': 'busybox:1.36', 'ports': [{'containerPort': 99999}]}]}}   # 端口超范围,同时不满足 restricted
psa_bad = lambda name: {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name}, 'spec': {'containers': [{'name': 'c', 'image': 'busybox:1.36', 'securityContext': {'privileged': True}}]}}
P = f'/api/v1/namespaces/{NS}/pods'
adm = admin_token()

print('== 一:同一个 POST /pods,在四个不同的关卡被拒绝(状态码和 reason 不一样)')
rows = []
def show(label, code, j):
    print(f'  [{label}] HTTP {code} reason={j.get("reason")} message={(j.get("message") or "")[:230]}')
c, j = call('POST', P, 'not-a-real-token', good_pod('t401')); show('1 令牌是假的', c, j)
c, j = call('POST', P, None, good_pod('t403a')); show('2 不带令牌(匿名)', c, j)
c, j = call('POST', P, sa_tok, bad_schema('t403b')); show('3 合法身份但没有 RBAC 权限,请求体还是错的', c, j)
c, j = call('POST', P, adm, bad_schema('t422')); show('4 有权限,请求体不合法又违反 restricted', c, j)
c, j = call('POST', P, adm, psa_bad('t403c')); show('5 有权限,请求体合法,违反 restricted', c, j)
c, j = call('POST', P, adm, good_pod('t201')); show('6 有权限,合法,满足 restricted', c, j)

print('== 二:--dry-run=server:走完认证、鉴权、准入、校验,但不写入 etcd——对比提交的和服务端回来的对象')
mini = f'apiVersion: v1\nkind: Pod\nmetadata:\n  name: k1-dry\n  namespace: {NS}\nspec:\n  containers:\n  - name: c\n    image: busybox:1.36\n    command: ["sleep","3600"]\n    securityContext: {{allowPrivilegeEscalation: false, capabilities: {{drop: [ALL]}}, runAsNonRoot: true, runAsUser: 1000, seccompProfile: {{type: RuntimeDefault}}}}\n'
def flat(o, p=''):
    out_ = {}
    if isinstance(o, dict):
        for kk, v in o.items(): out_.update(flat(v, f'{p}.{kk}' if p else kk))
    elif isinstance(o, list):
        for i, v in enumerate(o): out_.update(flat(v, f'{p}[{i}]'))
    else: out_[p] = o
    return out_
import yaml
sent = flat(yaml.safe_load(mini))
rc, o = k('create', '-f', '-', '--dry-run=server', '-o', 'json', input=mini, raw=True)
back = flat(json.loads(o))
new = {p: v for p, v in back.items() if p not in sent and not p.startswith('status')}
print(f'  提交 {len(sent)} 个字段,服务端回来 {len([p for p in back if not p.startswith("status")])} 个(不含 status);多出来的 {len(new)} 个里:')
for p in sorted(new):
    if re.search(r'tolerations|serviceAccount|priority|preemption|dnsPolicy|restartPolicy|schedulerName|terminationGrace|enableServiceLinks|imagePullPolicy|terminationMessage|volumes|volumeMounts|uid|resourceVersion|creationTimestamp|securityContext', p):
        print(f'    + {p} = {json.dumps(new[p], ensure_ascii=False)[:90]}')
rc, o = k('get', 'pod', 'k1-dry', '-n', NS)
print(f'  干跑之后 kubectl get pod k1-dry:{o.strip()}')

print('== 三:准入插件的调用——创建一个 Pod 前后各取一次 /metrics,看哪些准入控制器的计数增加了')
def adm_counts():
    txt = ko('get', '--raw', '/metrics', timeout=60)
    d = {}
    for l in txt.splitlines():
        m = re.match(r'apiserver_admission_controller_admission_duration_seconds_count\{.*name="([^"]+)",operation="([^"]+)",rejected="(\w+)",type="(\w+)"\} (\d+)', l)
        if m: d[(m.group(4), m.group(1), m.group(2), m.group(3))] = int(m.group(5))
    return d
a0 = adm_counts()
k('apply', '-n', NS, '-f', '-', input=mini.replace('k1-dry', 'k1-real').replace(f'  namespace: {NS}\n', ''))
a1 = adm_counts()
inc = {key: a1[key] - a0.get(key, 0) for key in a1 if a1[key] - a0.get(key, 0) > 0 and key[2] == 'CREATE'}
for typ in ('admit', 'validate'):
    names = sorted(key[1] for key in inc if key[0] == typ)
    print(f'  type={typ}({"变更阶段" if typ == "admit" else "校验阶段"})被调用的准入控制器({len(names)} 个):' + ', '.join(names))

print('== 四:真正创建之后才有 uid/resourceVersion,etcd 里才有 key;干跑的那个没有')
def etcd_keys(prefix):
    rc, o = k('exec', '-n', 'kube-system', f'etcd-{cn}-control-plane', '--', 'etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/server.crt', '--key=/etc/kubernetes/pki/etcd/server.key', 'get', prefix, '--prefix', '--keys-only')
    return [l for l in o.splitlines() if l.startswith('/registry')]
print(f'  etcd 里 /registry/pods/{NS}/ 下的 key:{etcd_keys(f"/registry/pods/{NS}/")}')
j_real = kj('get', 'pod', 'k1-real', '-n', NS)
print(f'  k1-real:uid={j_real["metadata"]["uid"][:8]}… resourceVersion={j_real["metadata"]["resourceVersion"]} creationTimestamp={j_real["metadata"]["creationTimestamp"]}')
j_dry = json.loads(k('create', '-f', '-', '--dry-run=server', '-o', 'json', input=mini.replace('k1-dry', 'k1-dry2'), raw=True)[1])
print(f'  干跑返回的对象:uid={j_dry["metadata"].get("uid", "(无)")[:8]} resourceVersion={j_dry["metadata"].get("resourceVersion", "(无)")} creationTimestamp={j_dry["metadata"].get("creationTimestamp", "(无)")}')
k('delete', 'clusterrolebinding', 'k1-admin', '--ignore-not-found')
rmns(NS)
