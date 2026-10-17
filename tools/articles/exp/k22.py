import sys, os, re, time, json, shutil, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k22')
cn, _ = up('main')
D = KT / 'k22'; shutil.rmtree(D, ignore_errors=True); D.mkdir()
(D / 'sub').mkdir(); (D / 'sub' / 'ca.pem').write_text('-----BEGIN CERTIFICATE-----\nMIIBfake-ca-for-experiment\n-----END CERTIFICATE-----\n')
A = '''apiVersion: v1
kind: Config
current-context: ctx-a
clusters:
- name: c-shared
  cluster: {server: "https://127.0.0.1:9821", certificate-authority: sub/ca.pem}
- name: c-a
  cluster: {server: "https://127.0.0.1:9821", insecure-skip-tls-verify: true}
users:
- name: u-a
  user: {token: token-from-A}
contexts:
- name: ctx-a
  context: {cluster: c-a, user: u-a, namespace: ns-a}
- name: ctx-shared
  context: {cluster: c-shared, user: u-a}
'''
B = '''apiVersion: v1
kind: Config
current-context: ctx-b
clusters:
- name: c-shared
  cluster: {server: "https://127.0.0.1:9822", insecure-skip-tls-verify: true}
- name: c-b
  cluster: {server: "https://127.0.0.1:9822", insecure-skip-tls-verify: true}
users:
- name: u-b
  user: {token: token-from-B}
- name: u-a
  user: {token: token-from-B-for-u-a}
contexts:
- name: ctx-b
  context: {cluster: c-b, user: u-b, namespace: ns-b}
- name: ctx-shared
  context: {cluster: c-shared, user: u-b}
'''
(D / 'a.yaml').write_text(A); (D / 'b.yaml').write_text(B)
FA, FB = str(D / 'a.yaml'), str(D / 'b.yaml')

import threading, http.server
SEEN = []
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        SEEN.append((self.server.server_port, self.path, self.headers.get('Authorization')))
        p = self.path.split('?')[0]
        body = {'/api': {'kind': 'APIVersions', 'versions': ['v1']}, '/apis': {'kind': 'APIGroupList', 'apiVersion': 'v1', 'groups': []},
                '/api/v1': {'kind': 'APIResourceList', 'groupVersion': 'v1', 'resources': [{'name': 'pods', 'singularName': 'pod', 'namespaced': True, 'kind': 'Pod', 'verbs': ['get', 'list']}]}}.get(p, {'kind': 'PodList', 'apiVersion': 'v1', 'metadata': {}, 'items': []})
        b = json.dumps(body).encode(); self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
import ssl
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(D / 'fake.key'), '-out', str(D / 'fake.crt'), '-days', '1', '-subj', '/CN=localhost'], capture_output=True)
SRV = [http.server.ThreadingHTTPServer(('127.0.0.1', p), H) for p in (9821, 9822)]
for sv in SRV:
    cx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); cx.load_cert_chain(str(D / 'fake.crt'), str(D / 'fake.key')); sv.socket = cx.wrap_socket(sv.socket, server_side=True)
    threading.Thread(target=sv.serve_forever, daemon=True).start()
def real_request(*args, env=None):
    """真的跑一次 kubectl get pods,返回假 apiserver 收到的最后一个 pods 列表请求:(端口, 路径, Authorization)"""
    SEEN.clear(); e = dict(os.environ); e.pop('KUBECONFIG', None); e.update(env or {}); e['KUBECACHEDIR'] = str(D / 'cache')
    r = subprocess.run(['kubectl', *args, 'get', 'pods'], capture_output=True, text=True, env=e, cwd='/')
    hit = [x for x in SEEN if x[1].endswith('/pods') or '/pods?' in x[1]]
    return (hit[-1] if hit else None), r.returncode, tidy(r.stdout + r.stderr)

def kc(*a, kubeconfig=None, env=None):
    e = dict(os.environ); e.pop('KUBECONFIG', None)
    if env: e.update(env)
    r = subprocess.run(['kubectl', *a], capture_output=True, text=True, env=e, cwd='/'); return r.returncode, tidy(r.stdout + r.stderr)
def view(env=None, *extra, jp=None):
    rc, o = kc('config', 'view', *extra, '-o', 'json', env=env)
    return json.loads(o) if rc == 0 else None
def summary(j):
    cl = {c['name']: c['cluster'].get('server') for c in j['clusters']}; us = {u['name']: list(u['user'].values())[0] for u in j['users']}
    cx = {c['name']: (c['context']['cluster'], c['context']['user'], c['context'].get('namespace')) for c in j['contexts']}
    return j.get('current-context'), cl, us, cx
print(f'集群 {cn};用两个手写的 kubeconfig(a.yaml、b.yaml,放在实验目录)演示合并规则;每条 kubectl config view 都显式设置 KUBECONFIG,不碰 ~/.kube/config')

print('== 一:KUBECONFIG=a.yaml:b.yaml——同名的条目谁说了算')
j = view({'KUBECONFIG': f'{FA}:{FB}'})
cur, cl, us, cx = summary(j)
print(f'  current-context={cur}')
print(f'  clusters:{cl}')
print(f'  users(token 在默认视图里被遮掉,这里取自 --raw):' + str({u["name"]: list(u["user"].values())[0] for u in view({"KUBECONFIG": f"{FA}:{FB}"}, "--raw")["users"]}))
print(f'  contexts:{cx}')
print('  规则:同名的 cluster / user / context,先出现的文件胜出(a 里的 c-shared、u-a、ctx-shared 生效,b 里的被忽略);不同名的合并;current-context 取第一个设了它的文件')

print('== 二:把顺序反过来——KUBECONFIG=b.yaml:a.yaml')
j = view({'KUBECONFIG': f'{FB}:{FA}'}); cur, cl, us, cx = summary(j)
print(f'  current-context={cur}')
print(f'  clusters:{cl}')
print(f'  users:' + str({u["name"]: list(u["user"].values())[0] for u in view({"KUBECONFIG": f"{FB}:{FA}"}, "--raw")["users"]}))
print(f'  contexts:{cx}')
rc, o = kc('config', 'view', '--minify', '-o', 'jsonpath={.clusters[0].cluster.server} {.contexts[0].context.namespace}', env={'KUBECONFIG': f'{FB}:{FA}'}); print(f'  --minify(只留当前 context 用到的部分):server+namespace = {o.strip()}')
print('  文件的位置不同,最终的集群地址 / 用户凭据就不同——KUBECONFIG 里的顺序是有意义的')

print('== 三:命令行参数的优先级——真的发一次 kubectl get pods,看假 apiserver(9821 = a 的集群,9822 = b 的集群)收到了什么')
env = {'KUBECONFIG': f'{FA}:{FB}'}
def line(label, *args, env=env):
    hit, rc, o = real_request(*args, env=env)
    if hit: print(f'  {label}:请求打到端口 {hit[0]},路径 {re.sub(r"[?].*", "", hit[1])},Authorization={hit[2]}')
    else: print(f'  {label}:没有发出 pods 请求(退出码 {rc};{o.strip()[:120]})')
line('默认(a.yaml:b.yaml,当前 context=ctx-a)')
line('--context=ctx-b', '--context=ctx-b')
line('--cluster=c-b(只换集群)', '--cluster=c-b')
line('--user=u-b(只换用户)', '--user=u-b')
line('--namespace=other(只换命名空间)', '--namespace=other')
line('--cluster=c-b --user=u-b --namespace=other', '--cluster=c-b', '--user=u-b', '--namespace=other')
line('--token=cli-token(命令行直接给令牌)', '--token=cli-token')
line(f'--kubeconfig=b.yaml(环境变量里的 a.yaml:b.yaml 被整个忽略)', f'--kubeconfig={FB}')
hit, rc, o = real_request('--context=no-such', env=env); print(f'  --context=no-such:退出码 {rc};{o.strip()[:100]}')

print('== 四:路径与遮掩——相对路径相对于 kubeconfig 所在的目录;默认视图遮掉密钥')
rc, o = kc('config', 'view', '--minify', env={'KUBECONFIG': FA}); print('  默认视图里的 c-a 集群与用户(a.yaml 的 ctx-a):' + ' | '.join(l.strip() for l in o.splitlines() if 'token' in l or 'server' in l or 'insecure' in l))
rc, o = kc('config', 'view', '--context=ctx-shared', '--minify', env={'KUBECONFIG': FA}); print('  ctx-shared(CA 写的是相对路径 sub/ca.pem):' + ' | '.join(l.strip() for l in o.splitlines() if 'certificate-authority' in l or 'server' in l))
rc, o = kc('config', 'view', '--context=ctx-shared', '--minify', '--flatten', env={'KUBECONFIG': FA}); print('  --flatten 把引用的文件内容嵌进去:' + ' | '.join(l.strip()[:80] for l in o.splitlines() if 'certificate-authority' in l))
print(f'  工作目录是 /(与 kubeconfig 不在同一目录)时上面的路径仍然被正确解析:是——解析基准是 a.yaml 所在目录 {D.name}/')
(D / 'sub' / 'ca.pem').unlink()
rc, o = kc('--kubeconfig', FA, '--context=ctx-shared', 'get', 'nodes'); print(f'  删掉 sub/ca.pem 之后 kubectl get nodes:退出码 {rc};{o.strip()[:200]}')
rc, o = kc('config', 'get-contexts', env={'KUBECONFIG': kcfg()}); print('  对照:kind 给 kx-main 生成的 kubeconfig:' + o.strip().replace('\n', ' | '))
for sv in SRV: sv.shutdown()
shutil.rmtree(D, ignore_errors=True)
