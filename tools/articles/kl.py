"""Kubernetes 实验辅助:kind(Docker Desktop 里的真实集群,节点镜像 kindest/node:v1.37.0)+ kubectl。
- 集群名一律以 kx 开头(Docker 系列的 purge() 只清理 bwlab*,互不影响);kubeconfig 放在 ktmp/,
  每条 kubectl 都显式带 --kubeconfig,绝不碰 ~/.kube 和用户自己的集群
- Docker 守护进程和集群节点都拉不到镜像仓库:镜像用 img() 经 dpull.py 在宿主机下载再 kind load 进节点
- 端口:不映射任何宿主机端口;访问都走 kubectl(apiserver 的随机回环端口)或 docker exec 进节点
- 绝不碰 5432/3306/6379/8181/9101/9333"""
import os, sys, subprocess, shutil, pathlib, textwrap, time, json, re, socket, statistics
HERE = pathlib.Path(__file__).parent
KT = HERE / 'ktmp'; KT.mkdir(exist_ok=True)
for k_ in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
    os.environ.pop(k_, None)
sys.path.insert(0, str(HERE))
from rl import tee, save
NODE_IMG = 'kindest/node:v1.37.0'
os.environ['KUBECACHEDIR'] = str(KT / 'kcache')   # kubectl 的发现缓存放在实验目录里,不写用户的 ~/.kube
C = 'kx-main'   # 当前默认集群


def tidy(t):
    t = re.sub(r'\x1b\[[0-9;]*m', '', t).replace(str(KT), '<ktmp>').replace(str(HERE), '<实验目录>')
    return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).strip('\n')


def sh(*args, timeout=120, input=None, env=None, raw=False, cwd=None):
    e = dict(os.environ); e.update(env or {})
    try:
        r = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=timeout, input=input, env=e, cwd=cwd)
        o = r.stdout + r.stderr
        return r.returncode, (o if raw else tidy(o))
    except subprocess.TimeoutExpired as ex:
        o = (ex.stdout.decode() if isinstance(ex.stdout, bytes) else (ex.stdout or '')) + '\n(超时)'
        return -9, tidy(o)


def kcfg(c=None):
    return str(KT / f'{c or C}.kubeconfig')


def k(*args, c=None, timeout=60, input=None, raw=False, env=None):
    """kubectl,返回 (退出码, 合并输出)。"""
    return sh('kubectl', '--kubeconfig', kcfg(c), *args, timeout=timeout, input=input, raw=raw, env=env)


def ko(*args, c=None, timeout=60, input=None):
    """kubectl,只要 stdout(去掉末尾空白)。失败返回空串。"""
    r = subprocess.run(['kubectl', '--kubeconfig', kcfg(c), *map(str, args)], capture_output=True, text=True, timeout=timeout, input=input)
    return r.stdout.strip()


def kj(*args, c=None, timeout=60):
    """kubectl ... -o json,返回解析后的对象;失败返回 None。"""
    r = subprocess.run(['kubectl', '--kubeconfig', kcfg(c), *map(str, args), '-o', 'json'], capture_output=True, text=True, timeout=timeout)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def apply(yaml, ns=None, c=None, args=()):
    a = ['apply', '-f', '-', *args] + (['-n', ns] if ns else [])
    return k(*a, c=c, input=textwrap.dedent(yaml).lstrip('\n'))


def nx(node, cmd, timeout=60, raw=False):
    """在 kind 节点容器里执行 shell 命令。node 可以是完整容器名或 control-plane / worker / worker2 的简称。"""
    full = node if node.startswith('kx-') else f'{C}-{node}'
    return sh('docker', 'exec', full, 'sh', '-c', cmd, timeout=timeout, raw=raw)


def until(fn, timeout=60, step=0.5):
    """轮询 fn() 直到返回真值,返回 (值, 耗时秒);超时返回 (None, 耗时)。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            v = fn()
        except Exception:
            v = None
        if v:
            return v, time.time() - t0
        time.sleep(step)
    return None, time.time() - t0


def ms(t0):
    return (time.time() - t0) * 1000


def med(xs):
    xs = sorted(xs); return xs[len(xs) // 2]


# ---------- 镜像 ----------
def have(ref):
    return subprocess.run(['docker', 'image', 'inspect', ref], capture_output=True).returncode == 0


def img(*refs):
    for ref in refs:
        if not have(ref):
            r = subprocess.run([sys.executable, str(HERE / 'dpull.py'), ref], capture_output=True, text=True, timeout=1800)
            assert have(ref), (ref, r.stdout[-300:], r.stderr[-300:])


def load(*refs, c=None):
    """确保镜像在宿主机 Docker 里,再 kind load 进集群所有节点(已经在的跳过)。"""
    img(*refs)
    for ref in refs:
        rc, o = sh('kind', 'load', 'docker-image', ref, '--name', c or C, timeout=300)
        assert rc == 0, (ref, o)


# ---------- 集群 ----------
def clusters():
    r = subprocess.run(['kind', 'get', 'clusters'], capture_output=True, text=True)
    return [x for x in r.stdout.split() if x.startswith('kx')]


def config(workers=2, cp_patches='', extra_cp='', kubelet_patch='', nodes_extra='', feature_gates='', runtime_config=''):
    """生成 kind 配置。cp_patches 是 kubeadm ClusterConfiguration 补丁(YAML 片段);workers=0 就是单节点。"""
    s = 'kind: Cluster\napiVersion: kind.x-k8s.io/v1alpha4\n'
    if feature_gates: s += 'featureGates:\n' + textwrap.indent(textwrap.dedent(feature_gates).strip('\n'), '  ') + '\n'
    if runtime_config: s += 'runtimeConfig:\n' + textwrap.indent(textwrap.dedent(runtime_config).strip('\n'), '  ') + '\n'
    patches = []
    if cp_patches: patches.append(textwrap.dedent(cp_patches).strip('\n'))
    if kubelet_patch: patches.append(textwrap.dedent(kubelet_patch).strip('\n'))
    if patches:
        s += 'kubeadmConfigPatches:\n' + ''.join('- |\n' + textwrap.indent(p, '  ') + '\n' for p in patches)
    s += 'nodes:\n- role: control-plane\n' + (textwrap.indent(textwrap.dedent(extra_cp).strip('\n'), '  ') + '\n' if extra_cp else '')
    s += ''.join('- role: worker\n' for _ in range(workers)) + nodes_extra
    return s


def up(name='main', cfg=None, workers=2, timeout=420):
    """创建(或复用)集群 kx-<name>,返回 (名字, 创建耗时秒或 0)。创建后把 C 指向它。"""
    global C
    cn = 'kx-' + name
    C = cn
    if cn in clusters():
        sh('kind', 'export', 'kubeconfig', '--name', cn, '--kubeconfig', kcfg(cn))
        return cn, 0.0
    cf = KT / f'{cn}.yaml'; cf.write_text(cfg or config(workers=workers))
    t0 = time.time()
    rc, o = sh('kind', 'create', 'cluster', '--name', cn, '--image', NODE_IMG, '--config', cf, '--kubeconfig', kcfg(cn), '--wait', '180s', timeout=timeout)
    assert rc == 0, o[-1500:]
    return cn, time.time() - t0


def down(name='main'):
    cn = 'kx-' + name
    sh('kind', 'delete', 'cluster', '--name', cn, '--kubeconfig', kcfg(cn), timeout=180)
    for f in (KT / f'{cn}.kubeconfig', KT / f'{cn}.yaml'):
        f.unlink(missing_ok=True)


def down_all():
    for cn in clusters(): down(cn[3:])


def ns(name, labels=None):
    k('delete', 'ns', name, '--ignore-not-found', '--wait=true', timeout=180)
    rc, o = k('create', 'ns', name)
    if labels: k('label', 'ns', name, *[f'{a}={b}' for a, b in labels.items()], '--overwrite')
    return name


def rmns(name):
    k('delete', 'ns', name, '--ignore-not-found', '--wait=false')


def pod_ready(name, namespace, c=None):
    p = kj('get', 'pod', name, '-n', namespace, c=c)
    return bool(p) and any(x['type'] == 'Ready' and x['status'] == 'True' for x in p['status'].get('conditions', []))


def wait_ready(name, namespace, timeout=90):
    v, dt = until(lambda: pod_ready(name, namespace), timeout)
    return bool(v), dt


def table(rows):
    """kubectl get 风格的对齐输出(rows 是 list[list[str]])。"""
    w = [max(len(str(r[i])) for r in rows) for i in range(len(rows[0]))]
    return '\n'.join('   '.join(str(c).ljust(w[i]) for i, c in enumerate(r)).rstrip() for r in rows)


def cleanup_stale():
    """清掉上次残留的 kx-* 以外的东西:这里只处理集群,实验自己的 namespace 在 ns() 里重建。"""
    pass


if __name__ == '__main__':
    print(clusters())


# ---------- watch 辅助 ----------
def watch_events(path, ops=None, secs=3, c=None, lead=1.0):
    """在后台起一个 kubectl get --raw <path>&watch=true&timeoutSeconds=secs,期间执行 ops(),返回解析后的事件列表
    [(type, name, resourceVersion, 原始事件 dict)]。服务端到点关闭流。"""
    sep = '&' if '?' in path else '?'
    p = subprocess.Popen(['kubectl', '--kubeconfig', kcfg(c), 'get', '--raw', f'{path}{sep}watch=true&timeoutSeconds={secs}'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(lead)
    if ops: ops()
    try: out_, _ = p.communicate(timeout=secs + 30)
    except subprocess.TimeoutExpired:
        p.kill(); out_, _ = p.communicate()
    ev = []
    for l in out_.splitlines():
        try: e = json.loads(l)
        except Exception: ev.append(('RAW', l[:200], '', {})); continue
        o = e.get('object', {}); md = o.get('metadata', {})
        ev.append((e['type'], md.get('name') or o.get('reason', ''), md.get('resourceVersion', ''), e))
    return ev


def fmt_ev(ev):
    return ' | '.join(f'{t} {n} rv={r}' if t != 'ERROR' else f'ERROR code={e["object"].get("code")} {e["object"].get("message", "")[:120]}' for t, n, r, e in ev)


def burst(n, ns_, name='burst', workers=8):
    """用 n 次 kubectl patch 制造 n 个写入(8 个线程并发),返回耗时。"""
    import concurrent.futures as cf
    t0 = time.time()
    def one(i):
        subprocess.run(['kubectl', '--kubeconfig', kcfg(), 'patch', 'cm', name, '-n', ns_, '--type=merge', '-p', json.dumps({'data': {'i': str(i)}})], capture_output=True)
    with cf.ThreadPoolExecutor(workers) as ex: list(ex.map(one, range(n)))
    return time.time() - t0


class WatchBg:
    """后台持续读一个 watch 流,每个事件记下到达的时间(距 start 的秒数)。用法:w = WatchBg(path, secs); ...; w.wait(); w.events"""
    def __init__(self, path, secs=60, c=None):
        import threading
        sep = '&' if '?' in path else '?'
        self.t0 = time.time(); self.events = []
        self.p = subprocess.Popen(['kubectl', '--kubeconfig', kcfg(c), 'get', '--raw', f'{path}{sep}watch=true&timeoutSeconds={secs}'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        def rd():
            for l in self.p.stdout:
                try: e = json.loads(l)
                except Exception: continue
                o = e.get('object', {}); md = o.get('metadata', {})
                self.events.append((round(time.time() - self.t0, 1), e['type'], md.get('name', ''), md.get('resourceVersion', ''), e))
        self.th = threading.Thread(target=rd, daemon=True); self.th.start()
    def wait(self, extra=30):
        try: self.p.wait(timeout=extra + 200)
        except subprocess.TimeoutExpired: self.p.kill()
        self.th.join(5)


# ---------- ServiceAccount 令牌 / API 直连辅助 ----------
import base64 as _b64, ssl as _ssl, http.client as _hc, urllib.parse as _up


def jwt_claims(tok):
    p = tok.split('.')[1]; p += '=' * (-len(p) % 4)
    return json.loads(_b64.urlsafe_b64decode(p))


def api(method, path, token=None, body=None, c=None, timeout=30):
    """用 Bearer 令牌(或不带)直接请求 apiserver,返回 (状态码, 解析后的 JSON 或原文)。"""
    u = _up.urlparse(ko('config', 'view', '--minify', '-o', 'jsonpath={.clusters[0].cluster.server}', c=c))
    cn = _hc.HTTPSConnection(u.hostname, u.port, context=_ssl._create_unverified_context(), timeout=timeout)
    h = {'Content-Type': 'application/json'}
    if token: h['Authorization'] = 'Bearer ' + token
    cn.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
    r = cn.getresponse(); raw = r.read().decode(); cn.close()
    try: return r.status, json.loads(raw)
    except Exception: return r.status, raw


def whoami(token, c=None):
    st, j = api('POST', '/apis/authentication.k8s.io/v1/selfsubjectreviews', token, {'apiVersion': 'authentication.k8s.io/v1', 'kind': 'SelfSubjectReview'}, c=c)
    if isinstance(j, dict) and isinstance(j.get('status'), dict): return st, j['status'].get('userInfo')
    return st, (j.get('message') if isinstance(j, dict) else j)


# ---------- cgroup 辅助(kind 节点:cgroup v2,systemd 驱动,kubelet 根在 /kubelet) ----------
CG_ROOT = '/sys/fs/cgroup/kubelet.slice/kubelet-kubepods.slice'


def pod_cgroup(pod_obj):
    """返回 (节点名, 该 Pod 在节点里的 cgroup 绝对路径)。"""
    uid = pod_obj['metadata']['uid'].replace('-', '_'); q = pod_obj['status'].get('qosClass', '').lower()
    node = pod_obj['spec']['nodeName']
    if q == 'guaranteed': p = f'{CG_ROOT}/kubelet-kubepods-pod{uid}.slice'
    else: p = f'{CG_ROOT}/kubelet-kubepods-{q}.slice/kubelet-kubepods-{q}-pod{uid}.slice'
    return node, p


def container_cgroup(pod_obj, cname=None, init=False):
    """返回 (节点名, 容器的 cgroup 路径, 容器 ID)。"""
    node, pcg = pod_cgroup(pod_obj)
    cs = (pod_obj['status'].get('initContainerStatuses' if init else 'containerStatuses') or [])
    c = next(x for x in cs if cname is None or x['name'] == cname)
    cid = c['containerID'].split('//')[1]
    return node, f'{pcg}/cri-containerd-{cid}.scope', cid


def cgread(node, path, f):
    rc, o = nx(node, f'cat {path}/{f}', raw=True); return o.strip()


def wait_nodes_ready(timeout=180):
    """等所有节点 Ready(kind create 只等控制面,worker 可能还在 NotReady)。"""
    def ok():
        ns_ = kj('get', 'nodes')['items']
        return ns_ and all(any(c['type'] == 'Ready' and c['status'] == 'True' for c in n['status']['conditions']) for n in ns_)
    v, dt = until(ok, timeout, 1); assert v, '节点没有全部 Ready'
    time.sleep(3)
    return dt


MS_IMAGE = 'registry.k8s.io/metrics-server/metrics-server:v0.7.2'
MS_YAML = '''apiVersion: v1
kind: ServiceAccount
metadata: {name: metrics-server, namespace: kube-system}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: system:aggregated-metrics-reader, labels: {rbac.authorization.k8s.io/aggregate-to-view: "true", rbac.authorization.k8s.io/aggregate-to-edit: "true", rbac.authorization.k8s.io/aggregate-to-admin: "true"}}
rules: [{apiGroups: [metrics.k8s.io], resources: [pods, nodes], verbs: [get, list, watch]}]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: system:metrics-server}
rules:
- {apiGroups: [""], resources: [nodes/metrics], verbs: [get]}
- {apiGroups: [""], resources: [pods, nodes], verbs: [get, list, watch]}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: metrics-server-auth-reader, namespace: kube-system}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: Role, name: extension-apiserver-authentication-reader}
subjects: [{kind: ServiceAccount, name: metrics-server, namespace: kube-system}]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {name: metrics-server:system:auth-delegator}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: system:auth-delegator}
subjects: [{kind: ServiceAccount, name: metrics-server, namespace: kube-system}]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {name: system:metrics-server}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: system:metrics-server}
subjects: [{kind: ServiceAccount, name: metrics-server, namespace: kube-system}]
---
apiVersion: v1
kind: Service
metadata: {name: metrics-server, namespace: kube-system}
spec: {selector: {k8s-app: metrics-server}, ports: [{name: https, port: 443, targetPort: https}]}
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: metrics-server, namespace: kube-system}
spec:
  selector: {matchLabels: {k8s-app: metrics-server}}
  template:
    metadata: {labels: {k8s-app: metrics-server}}
    spec:
      serviceAccountName: metrics-server
      containers:
      - name: metrics-server
        image: registry.k8s.io/metrics-server/metrics-server:v0.7.2
        imagePullPolicy: IfNotPresent
        args: [--cert-dir=/tmp, --secure-port=10250, --kubelet-preferred-address-types=InternalIP, --kubelet-use-node-status-port, --metric-resolution=15s, --kubelet-request-timeout=5s, --kubelet-insecure-tls]
        ports: [{name: https, containerPort: 10250}]
        readinessProbe: {httpGet: {path: /readyz, port: https, scheme: HTTPS}, periodSeconds: 5}
        resources: {requests: {cpu: 50m, memory: 64Mi}}
        securityContext: {readOnlyRootFilesystem: true, runAsNonRoot: true, runAsUser: 1000, allowPrivilegeEscalation: false}
        volumeMounts: [{name: tmp, mountPath: /tmp}]
      volumes: [{name: tmp, emptyDir: {}}]
---
apiVersion: apiregistration.k8s.io/v1
kind: APIService
metadata: {name: v1beta1.metrics.k8s.io}
spec: {service: {name: metrics-server, namespace: kube-system}, group: metrics.k8s.io, version: v1beta1, insecureSkipTLSVerify: true, groupPriorityMinimum: 100, versionPriority: 100}
'''


def install_metrics_server(c=None, timeout=180):
    """装 metrics-server(v0.7.2,--kubelet-insecure-tls,采集周期 15 秒),等 metrics API 可用并且 kubectl top node 有数据。"""
    load(MS_IMAGE, c=c)
    rc, o = k('apply', '-f', '-', input=MS_YAML, c=c); assert rc == 0, o
    def ok():
        rc, o = k('top', 'nodes', c=c); return rc == 0 and 'cpu' in o.lower() and '<unknown>' not in o
    v, dt = until(ok, timeout, 3); assert v, 'metrics API 一直没有数据'
    return dt
