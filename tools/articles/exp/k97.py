import sys, os, re, time, json, base64, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k97')
cn, _ = up('main'); wait_nodes_ready()
load('python:3.12-alpine'); load('busybox:1.36')
NS = ns('k97'); NS2 = ns('k97b')
W = 'kx-main-worker'
nx(W, 'mkdir -p "/etc/containerd/certs.d/localhost:5000" && printf "server = \\"http://localhost:5000\\"\\n[host.\\"http://localhost:5000\\"]\\n  capabilities = [\\"pull\\", \\"resolve\\"]\\n" > "/etc/containerd/certs.d/localhost:5000/hosts.toml"')
SERVER = r'''
import json, time, base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
GOOD = 'Basic ' + base64.b64encode(b'puller:s3cret').decode()
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self): self.h()
    def do_HEAD(self): self.h()
    def h(self):
        a = self.headers.get('Authorization')
        print(json.dumps({'t': round(time.time(), 2), 'm': self.command, 'p': self.path, 'auth': a}), flush=True)
        if a != GOOD:
            b = b'{"errors":[{"code":"UNAUTHORIZED","message":"authentication required"}]}'
            self.send_response(401); self.send_header('WWW-Authenticate', 'Basic realm="fake-registry"'); self.send_header('Content-Length', str(len(b))); self.send_header('Content-Type', 'application/json'); self.end_headers()
            if self.command != 'HEAD': self.wfile.write(b)
            return
        b = b'{"errors":[{"code":"MANIFEST_UNKNOWN","message":"manifest unknown"}]}'
        self.send_response(404); self.send_header('Content-Length', str(len(b))); self.send_header('Content-Type', 'application/json'); self.end_headers()
        if self.command != 'HEAD': self.wfile.write(b)
ThreadingHTTPServer(('0.0.0.0', 5000), H).serve_forever()
'''
k('apply', '-f', '-', input=f'''apiVersion: v1
kind: ConfigMap
metadata: {{name: fakereg, namespace: {NS}}}
data: {{server.py: {json.dumps(SERVER)}}}
---
apiVersion: v1
kind: Pod
metadata: {{name: fakereg, namespace: {NS}}}
spec:
  nodeName: {W}
  hostNetwork: true
  terminationGracePeriodSeconds: 0
  containers:
  - {{name: s, image: python:3.12-alpine, imagePullPolicy: IfNotPresent, command: [python, -u, /code/server.py], volumeMounts: [{{name: code, mountPath: /code}}]}}
  volumes: [{{name: code, configMap: {{name: fakereg}}}}]
''')
k('wait', '--for=condition=Ready', 'pod/fakereg', '-n', NS, '--timeout=60s'); time.sleep(2)
def pod(name, image, ns_=NS, secrets=None):
    ps = ''.join(f'  imagePullSecrets:\n  - name: {s}\n' for s in (secrets or []))
    return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {ns_}}}\nspec:\n  nodeName: {W}\n  terminationGracePeriodSeconds: 0\n{ps}  containers: [{{name: c, image: "{image}", command: [sleep, "3600"]}}]\n'
def cstate(n, ns_=NS):
    c = (kj('get', 'pod', n, '-n', ns_)['status'].get('containerStatuses') or [{}])[0]; st = c.get('state', {}); kind = next(iter(st), '?'); return kind, (st.get(kind) or {}).get('reason'), (st.get(kind) or {}).get('message') or ''
def reqs(): return [json.loads(l) for l in k('logs', 'fakereg', '-n', NS, raw=True)[1].splitlines() if l.startswith('{')]
def settle(n, ns_=NS, t=60): until(lambda: cstate(n, ns_)[1] in ('ErrImagePull', 'ImagePullBackOff'), t, 1)
def msg(n, ns_=NS): return re.sub(r'.*failed to resolve reference "[^"]*": ', '', cstate(n, ns_)[2])[:200]
print(f'集群 {cn};私有仓库需要认证:kubelet 把 Pod 的 imagePullSecrets 里的凭证交给容器运行时去拉镜像。假仓库在 worker 的 localhost:5000,要求 Basic 认证 puller:s3cret(认证通过后对不存在的镜像返回 404,以此区分“凭证被接受”)')

print('== 一:dockerconfigjson Secret 的内容')
k('create', 'secret', 'docker-registry', 'regcred', '-n', NS, '--docker-server=localhost:5000', '--docker-username=puller', '--docker-password=s3cret', '--docker-email=a@b.c')
sc = kj('get', 'secret', 'regcred', '-n', NS); dj = json.loads(base64.b64decode(sc['data']['.dockerconfigjson']))
print(f'  type={sc["type"]};data 的键={list(sc["data"].keys())}')
a = dj['auths']['localhost:5000']; print(f'  解码后的 .dockerconfigjson:auths 的键={list(dj["auths"].keys())};里面 {sorted(a.keys())};auth 字段 = base64("用户名:密码") = {a["auth"]} → {base64.b64decode(a["auth"]).decode()}')

print('== 二:没有 secret vs 有 secret,仓库看到的请求头')
k('apply', '-f', '-', input=pod('nosecret', 'localhost:5000/team/app:1.0') + '---\n' + pod('withsecret', 'localhost:5000/team/app:1.0', secrets=['regcred']))
settle('nosecret'); settle('withsecret'); time.sleep(3)
R = reqs(); mine = [r for r in R if '/team/app/' in r['p']]
no_auth = [r for r in mine if not r['auth']]; has_auth = [r for r in mine if r['auth']]
print(f'  仓库收到 {len(mine)} 个对 team/app 的请求:其中 {len(no_auth)} 个没有 Authorization 头(不带凭证的探测),{len(has_auth)} 个带 Authorization:{sorted({base64.b64decode(r["auth"].split()[1]).decode() for r in has_auth})}')
print(f'  nosecret Pod:{cstate("nosecret")[1]};{msg("nosecret")}')
print(f'  withsecret Pod:{cstate("withsecret")[1]};{msg("withsecret")}(认证通过了,失败原因变成“镜像不存在”)')
print(f'  Pod spec 里:withsecret.spec.imagePullSecrets={kj("get", "pod", "withsecret", "-n", NS)["spec"].get("imagePullSecrets")}')

print('== 三:通过 ServiceAccount 自动带上 secret')
k('patch', 'sa', 'default', '-n', NS, '-p', '{"imagePullSecrets":[{"name":"regcred"}]}')
k('apply', '-f', '-', input=pod('viasa', 'localhost:5000/team/app:2.0'))
p = kj('get', 'pod', 'viasa', '-n', NS); print(f'  给 default ServiceAccount 加上 imagePullSecrets: [regcred] 后,新建的 Pod viasa 没写 imagePullSecrets,spec.imagePullSecrets={p["spec"].get("imagePullSecrets")}(ServiceAccount 准入补进去的)')
settle('viasa'); print(f'    viasa:{cstate("viasa")[1]};{msg("viasa")}')

print('== 四:secret 的作用域与 server 地址')
k('create', 'secret', 'docker-registry', 'wrongserver', '-n', NS, '--docker-server=registry.other.com', '--docker-username=puller', '--docker-password=s3cret')
k('apply', '-f', '-', input=pod('wrongsrv', 'localhost:5000/team/app:3.0', secrets=['wrongserver'])); settle('wrongsrv'); print(f'  secret 的 auths 键是 registry.other.com,镜像在 localhost:5000:{cstate("wrongsrv")[1]};{msg("wrongsrv")}(仓库地址不匹配,凭证不会发给它)')
k('create', 'secret', 'docker-registry', 'wrongpass', '-n', NS, '--docker-server=localhost:5000', '--docker-username=puller', '--docker-password=bad')
k('apply', '-f', '-', input=pod('wrongpw', 'localhost:5000/team/app:4.0', secrets=['wrongpass'])); settle('wrongpw'); print(f'  地址对但密码错:{cstate("wrongpw")[1]};{msg("wrongpw")}')
k('apply', '-f', '-', input=pod('otherns', 'localhost:5000/team/app:5.0', ns_=NS2, secrets=['regcred']))
time.sleep(5); p = kj('get', 'pod', 'otherns', '-n', NS2); print(f'  命名空间 {NS2} 里的 Pod 引用 {NS} 里的 secret regcred(imagePullSecrets 只能引用同命名空间的):创建是否成功:{bool(p)};容器状态 {cstate("otherns", NS2)[:2]}')
settle('otherns', NS2, 20); print(f'    {msg("otherns", NS2)}')
rc, o = k('get', 'events', '-n', NS2, '--field-selector', 'involvedObject.name=otherns'); print(f'    事件:{[re.sub(chr(32) + "+", " ", l)[:150] for l in o.strip().splitlines()[1:4]]}')
k('delete', 'ns', NS, NS2, '--wait=false')
