import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k94')
cn, _ = up('main'); wait_nodes_ready()
load('busybox:1.36')
NS = ns('k94')
C = 'kx-main-control-plane'
MAN = '/etc/kubernetes/manifests/kube-apiserver.yaml'
def cr(c): return nx(C, c)[1].strip()
def short(o, n=1, w=300): return [re.sub(r'\s+', ' ', l)[:w] for l in o.strip().splitlines() if l.strip()][:n]
def svc(name, np_=None): return f'apiVersion: v1\nkind: Service\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  type: NodePort\n  selector: {{app: x}}\n  ports: [{{port: 80{", nodePort: %d" % np_ if np_ else ""}}}]\n'
def pod(name): return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  terminationGracePeriodSeconds: 0\n  containers: [{{name: c, image: busybox:1.36, imagePullPolicy: IfNotPresent, command: [sleep, "3600"]}}]\n'
def anon():
    rc, o = sh('curl', '-sk', '-m', '5', '-o', '/dev/null', '-w', '%{http_code}', kj_server() + '/api/v1/namespaces/default/pods', raw=True); return o.strip()
server = ko('config', 'view', '--minify', '-o', 'jsonpath={.clusters[0].cluster.server}')
def kj_server(): return server
def flags():
    return json.loads(cr(f"python3 - <<'EOF'\nimport yaml,json\nEOF\n") or '[]') if False else None
def get_flags():
    p = kj('get', 'pod', f'kube-apiserver-{C}', '-n', 'kube-system'); return p['spec']['containers'][0]['command'][1:]
print(f'集群 {cn};kube-apiserver 的启动参数写在 {MAN}(静态 Pod),改文件 kubelet 就会重启它。本文挑几个参数,改前改后各测一遍')

print('== 一:kubeadm 生成的参数,按作用分类')
fl_ = get_flags(); groups = {'认证/鉴权': ['--authorization-mode', '--client-ca-file', '--enable-bootstrap-token-auth', '--requestheader-client-ca-file', '--service-account-issuer', '--service-account-key-file', '--service-account-signing-key-file'],
 '准入': ['--enable-admission-plugins'], '网络范围': ['--service-cluster-ip-range', '--secure-port', '--advertise-address'], 'etcd 与 kubelet': ['--etcd-servers', '--etcd-cafile', '--kubelet-client-certificate', '--kubelet-preferred-address-types'], 'TLS 服务证书': ['--tls-cert-file', '--tls-private-key-file']}
print(f'  共 {len(fl_)} 个参数;按作用选几个:')
for g, names in groups.items():
    got = [x for x in fl_ if x.split('=')[0] in names]
    print(f'    {g}:' + ' '.join(re.sub(r'/etc/kubernetes/pki/', 'pki/', x) for x in got))
print(f'  没有出现的、使用默认值的重要参数:--service-node-port-range(默认 30000-32767)、--anonymous-auth(默认 true)、--max-requests-inflight(默认 400)、--etcd-compaction-interval(默认 5m)')

print('== 二:改三个参数,重启 apiserver')
orig = cr(f'cat {MAN}')
k('apply', '-f', '-', input=svc('before'))
pre_np = kj('get', 'svc', 'before', '-n', NS)['spec']['ports'][0]['nodePort']
k('apply', '-f', '-', input=pod('pre')); pre_pol = kj('get', 'pod', 'pre', '-n', NS)['spec']['containers'][0]['imagePullPolicy']
print(f'  改前:NodePort Service 分到 {pre_np};Pod 写 imagePullPolicy: IfNotPresent → 实际 {pre_pol};不带令牌访问 /api/v1/namespaces/default/pods → HTTP {anon()}(匿名请求默认被当作 system:anonymous,走到鉴权才被拒)')
new = orig
new = new.replace('    - kube-apiserver\n', '    - kube-apiserver\n    - --service-node-port-range=31000-31010\n    - --anonymous-auth=false\n', 1)
new = re.sub(r'(--enable-admission-plugins=\S+)', r'\1,AlwaysPullImages', new, count=1)
assert new != orig and 'AlwaysPullImages' in new
open(KT / 'kube-apiserver-k94.yaml', 'w').write(new); t0 = time.time()
cid0 = cr('crictl ps --name kube-apiserver -q | head -1')
sh('docker', 'cp', str(KT / 'kube-apiserver-k94.yaml'), f'{C}:/root/kube-apiserver.yaml'); nx(C, f'cp /root/kube-apiserver.yaml {MAN}')
def up_new():
    try:
        p = kj('get', 'pod', f'kube-apiserver-{C}', '-n', 'kube-system'); return any('port-range' in a for a in p['spec']['containers'][0]['command']) and cr('crictl ps --name kube-apiserver -q | head -1') != cid0 and k('get', '--raw', '/readyz')[1].strip() == 'ok'
    except Exception: return False
v, dt = until(up_new, 180, 1); print(f'  修改 {MAN} 之后 {dt:.0f} 秒,新的 apiserver 就绪(旧容器 {cid0[:8]} → 新容器 {cr("crictl ps --name kube-apiserver -q | head -1")[:8]})')
rc, o = k('apply', '-f', '-', input=svc('after')); print(f'  改后:新建 NodePort Service → 退出码 {rc}')
print(f'    nodePort={kj("get", "svc", "after", "-n", NS)["spec"]["ports"][0]["nodePort"]}(落在 31000-31010 里);原来分到的 {pre_np} 的 Service before 仍在:{kj("get", "svc", "before", "-n", NS)["spec"]["ports"][0]["nodePort"]}(已有的不动)')
rc, o = k('apply', '-f', '-', input=svc('manual', 30050)); print(f'    指定 nodePort: 30050 → 退出码 {rc};{short(o, 1, 260)}')
k('apply', '-f', '-', input=pod('post')); print(f'    Pod 写 imagePullPolicy: IfNotPresent → 实际 {kj("get", "pod", "post", "-n", NS)["spec"]["containers"][0]["imagePullPolicy"]}(AlwaysPullImages 准入把它改成了 Always);旧的 pre 仍是 {kj("get", "pod", "pre", "-n", NS)["spec"]["containers"][0]["imagePullPolicy"]}')
print(f'    不带令牌访问 /api/v1/namespaces/default/pods → HTTP {anon()}(--anonymous-auth=false 之后是 401 而不是 403)')

print('== 三:改回去')
open(KT / 'kube-apiserver-orig.yaml', 'w').write(orig); cid1 = cr('crictl ps --name kube-apiserver -q | head -1'); t0 = time.time()
sh('docker', 'cp', str(KT / 'kube-apiserver-orig.yaml'), f'{C}:/root/kube-apiserver.yaml'); nx(C, f'cp /root/kube-apiserver.yaml {MAN}')
def back_orig():
    try:
        p = kj('get', 'pod', f'kube-apiserver-{C}', '-n', 'kube-system'); return not any('port-range' in a for a in p['spec']['containers'][0]['command']) and cr('crictl ps --name kube-apiserver -q | head -1') != cid1 and k('get', '--raw', '/readyz')[1].strip() == 'ok'
    except Exception: return False
v, dt = until(back_orig, 180, 1); print(f'  恢复原来的 manifest,{dt:.0f} 秒后 apiserver 就绪;匿名访问 → HTTP {anon()};新建 NodePort Service 分到 {(lambda: (k("apply", "-f", "-", input=svc("again")), kj("get", "svc", "again", "-n", NS)["spec"]["ports"][0]["nodePort"])[1])()}')
k('delete', 'ns', NS, '--wait=false')
