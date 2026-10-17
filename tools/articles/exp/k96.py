import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k96')
cn, _ = up('main'); wait_nodes_ready()
load('python:3.12-alpine'); load('busybox:1.36')
nx('kx-main-worker', 'mkdir -p "/etc/containerd/certs.d/localhost:5000" && printf "server = \\"http://localhost:5000\\"\\n[host.\\"http://localhost:5000\\"]\\n  capabilities = [\\"pull\\", \\"resolve\\"]\\n" > "/etc/containerd/certs.d/localhost:5000/hosts.toml"')
NS = ns('k96')
W = 'kx-main-worker'
SERVER = r'''
import json, time, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self): self.h()
    def do_HEAD(self): self.h()
    def h(self):
        print(json.dumps({'t': round(time.time(), 2), 'm': self.command, 'p': self.path}), flush=True)
        if self.path.rstrip('/') == '/v2': return self.send(200, {})
        if '/private/' in self.path: return self.send(401, {'errors': [{'code': 'UNAUTHORIZED', 'message': 'authentication required'}]})
        return self.send(404, {'errors': [{'code': 'MANIFEST_UNKNOWN', 'message': 'manifest unknown'}]})
    def send(self, code, body):
        b = json.dumps(body).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Docker-Distribution-API-Version', 'registry/2.0'); self.send_header('Content-Length', str(len(b))); self.end_headers()
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
def pod(name, image): return f'apiVersion: v1\nkind: Pod\nmetadata: {{name: {name}, namespace: {NS}}}\nspec:\n  nodeName: {W}\n  terminationGracePeriodSeconds: 0\n  containers: [{{name: c, image: "{image}", command: [sleep, "3600"]}}]\n'
def cstate(n):
    c = (kj('get', 'pod', n, '-n', NS)['status'].get('containerStatuses') or [{}])[0]; st = c.get('state', {}); kind = next(iter(st), '?'); return kind, (st.get(kind) or {}).get('reason'), (st.get(kind) or {}).get('message') or ''
print(f'集群 {cn};ImagePullBackOff 是“拉取失败后,kubelet 退避等待再试”的状态,真正的原因要看事件里 ErrImagePull 的 message。为了得到可重复的失败原因,在 worker 上用 hostNetwork Pod 跑了一个假的镜像仓库(localhost:5000):/v2/ 返回 200,名字里有 private 的返回 401,其余的 manifest 返回 404')

print('== 一:几种常见原因,message 各不相同')
cases = [('refused', 'localhost:5999/nolocal:1.0', '仓库地址没有服务(连接被拒绝)'), ('notfound', 'localhost:5000/missing:1.0', '仓库在线,镜像或 tag 不存在(404)'), ('private', 'localhost:5000/private/app:1.0', '需要认证(401)'), ('nohost', 'nonexistent.invalid/app:1.0', '域名解析失败'), ('badname', 'busybox:1.36:extra', '镜像名格式不对')]
k('apply', '-f', '-', input='---\n'.join(pod(n, im) for n, im, _ in cases))
for n, im, d in cases:
    until(lambda: cstate(n)[1] in ('ErrImagePull', 'ImagePullBackOff', 'InvalidImageName'), 90, 1)
    kind, reason, msg = cstate(n); m = re.sub(r'failed to pull and unpack image "[^"]*": ', '', msg)
    print(f'  {n:<9}{im:<34}→ {reason};原因:{d}')
    print(f'      message:{m[:230]}')

print('== 二:ErrImagePull → ImagePullBackOff 的退避节奏')
reqs = lambda: [json.loads(l) for l in k('logs', 'fakereg', '-n', NS, raw=True)[1].splitlines() if l.startswith('{')]
k('delete', 'pod', 'refused', 'notfound', 'private', 'nohost', 'badname', '-n', NS, '--wait=true', timeout=60)
k('delete', 'pod', 'fakereg', '-n', NS, '--wait=true', timeout=60)
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: fakereg, namespace: {NS}}}\nspec:\n  nodeName: {W}\n  hostNetwork: true\n  terminationGracePeriodSeconds: 0\n  containers:\n  - {{name: s, image: python:3.12-alpine, imagePullPolicy: IfNotPresent, command: [python, -u, /code/server.py], volumeMounts: [{{name: code, mountPath: /code}}]}}\n  volumes: [{{name: code, configMap: {{name: fakereg}}}}]\n')
k('wait', '--for=condition=Ready', 'pod/fakereg', '-n', NS, '--timeout=60s'); time.sleep(2)
k('apply', '-f', '-', input=pod('backoff', 'localhost:5000/missing:2.0')); t0 = time.time(); seen = []; last = None
while time.time() - t0 < 330:
    st = cstate('backoff')[1]
    if st != last: seen.append((round(time.time() - t0), st)); last = st
    time.sleep(1)
att = [t for t, r in seen if r == 'ErrImagePull']
print(f'  Pod 创建后 330 秒内,容器状态变化(相对秒, reason):{seen}')
print(f'  每次出现 ErrImagePull(= 一次新的拉取尝试失败)的时刻:{att};相邻尝试的间隔(秒):{[b - a for a, b in zip(att, att[1:])]}')
print(f'  假仓库日志里 missing/manifests/2.0 的请求共 {len([r for r in reqs() if "missing/manifests/2.0" in r["p"]])} 条')
ev = [e for e in kj('get', 'events', '-n', NS, '--field-selector', 'involvedObject.name=backoff')['items']]
print(f'  事件(去重后):{sorted({(e["reason"], e.get("count", 1)) for e in ev})}')
k('delete', 'ns', NS, '--wait=false')
