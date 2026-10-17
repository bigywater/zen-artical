"""在集群里跑一个真实的 webhook 服务(python:3.12-alpine + 标准库 http.server + TLS),给准入 / CRD 转换实验用。
pki() 用宿主机的 openssl 生成 CA 和服务端证书(SAN = <svc>.<ns>.svc);deploy() 创建 Secret / ConfigMap / Deployment / Service。
服务按 URL 路径决定行为,每个请求打一行 JSON 日志(kubectl logs 能看到)。"""
import base64, json, os, subprocess, textwrap, time, shutil, pathlib
from kl import *

SERVER = r'''
import json, ssl, sys, time, base64, os, urllib.parse, signal
signal.signal(signal.SIGTERM, lambda *a: os._exit(0))
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
def log(**kw):
    kw['t'] = round(time.time(), 3); print(json.dumps(kw, ensure_ascii=False), flush=True)
def esc(s): return s.replace('~', '~0').replace('/', '~1')
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query); path = u.path
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if body.get('kind') == 'ConversionReview':
            return self.convert(body, path)
        r = body['request']; obj = r.get('object') or {}; md = obj.get('metadata', {}) or {}
        ann = md.get('annotations') or {}
        resp = {'uid': r['uid'], 'allowed': True}
        info = dict(path=path, op=r['operation'], dry=r.get('dryRun', False), kind=r['kind']['kind'], name=r.get('name') or md.get('name'), order=ann.get('order'), user=r['userInfo'].get('username'))
        if path.startswith('/slow'): time.sleep(4)
        if path.startswith('/mutate/'):
            tag = path.split('/')[2]
            cur = ann.get('order')
            val = (cur + ',' + tag) if cur else tag
            if 'annotations' not in md: patch = [{'op': 'add', 'path': '/metadata/annotations', 'value': {'order': val}}]
            else: patch = [{'op': 'add', 'path': '/metadata/annotations/order', 'value': val}]
            resp['patch'] = base64.b64encode(json.dumps(patch).encode()).decode(); resp['patchType'] = 'JSONPatch'
        elif path.startswith('/validate'):
            if (md.get('labels') or {}).get('deny') == 'true':
                resp['allowed'] = False; resp['status'] = {'code': 403, 'message': 'validate webhook 拒绝:对象带有 deny=true 标签(它看到的 order 注解是 %r)' % ann.get('order')}
        info['allowed'] = resp['allowed']; log(**info)
        out = json.dumps({'apiVersion': 'admission.k8s.io/v1', 'kind': 'AdmissionReview', 'response': resp}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(out))); self.end_headers(); self.wfile.write(out)
    def convert(self, body, path):
        req = body['request']; want = req['desiredAPIVersion']; res = []
        for o in req['objects']:
            o = json.loads(json.dumps(o)); have = o['apiVersion']; spec = o.get('spec', {})
            if have != want:
                if have.endswith('/v1beta1') and want.endswith('/v1'):
                    if 'replicas' in spec: spec['size'] = spec.pop('replicas')
                elif have.endswith('/v1') and want.endswith('/v1beta1'):
                    if 'size' in spec: spec['replicas'] = spec.pop('size')
                o['apiVersion'] = want
            res.append(o)
        log(path=path, op='CONVERT', frm=sorted({x['apiVersion'] for x in req['objects']}), to=want, n=len(res))
        out = json.dumps({'apiVersion': 'apiextensions.k8s.io/v1', 'kind': 'ConversionReview', 'response': {'uid': req['uid'], 'convertedObjects': res, 'result': {'status': 'Success'}}}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(out))); self.end_headers(); self.wfile.write(out)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain('/tls/tls.crt', '/tls/tls.key')
srv = ThreadingHTTPServer(('0.0.0.0', 8443), H); srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
log(started=True); srv.serve_forever()
'''


def pki(name, ns):
    """返回 (ca_pem_bytes, crt_pem_bytes, key_pem_bytes);SAN 包含 <name>.<ns>.svc。"""
    d = KT / f'pki-{name}'; shutil.rmtree(d, ignore_errors=True); d.mkdir()
    cnf = f'[req]\ndistinguished_name=dn\nprompt=no\n[dn]\nCN={name}.{ns}.svc\n[v3]\nsubjectAltName=DNS:{name}.{ns}.svc,DNS:{name}.{ns}.svc.cluster.local\nextendedKeyUsage=serverAuth\n'
    (d / 'o.cnf').write_text(cnf)
    run = lambda *a: subprocess.run(['openssl', *a], cwd=d, capture_output=True, check=True)
    run('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key', '-out', 'ca.crt', '-days', '30', '-subj', '/CN=kx-webhook-ca')
    run('req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'tls.key', '-out', 'tls.csr', '-config', 'o.cnf')
    run('x509', '-req', '-in', 'tls.csr', '-CA', 'ca.crt', '-CAkey', 'ca.key', '-CAcreateserial', '-out', 'tls.crt', '-days', '30', '-extfile', 'o.cnf', '-extensions', 'v3')
    r = (d / 'ca.crt').read_bytes(), (d / 'tls.crt').read_bytes(), (d / 'tls.key').read_bytes()
    shutil.rmtree(d, ignore_errors=True)
    return r


def deploy(name, ns, c=None):
    """在 ns 里部署名为 name 的 webhook 服务(Service 443→8443),返回 base64 的 caBundle。"""
    ca, crt, key = pki(name, ns)
    b64 = lambda b: base64.b64encode(b).decode()
    y = f'''
apiVersion: v1
kind: Secret
metadata: {{name: {name}-tls}}
type: kubernetes.io/tls
data: {{tls.crt: {b64(crt)}, tls.key: {b64(key)}}}
---
apiVersion: v1
kind: ConfigMap
metadata: {{name: {name}-code}}
data:
  server.py: |
{textwrap.indent(SERVER, "    ")}
---
apiVersion: apps/v1
kind: Deployment
metadata: {{name: {name}}}
spec:
  replicas: 1
  selector: {{matchLabels: {{app: {name}}}}}
  template:
    metadata: {{labels: {{app: {name}}}}}
    spec:
      terminationGracePeriodSeconds: 1
      containers:
      - name: s
        image: python:3.12-alpine
        imagePullPolicy: IfNotPresent
        command: ["python", "-u", "/code/server.py"]
        ports: [{{containerPort: 8443}}]
        volumeMounts: [{{name: tls, mountPath: /tls}}, {{name: code, mountPath: /code}}]
        readinessProbe: {{tcpSocket: {{port: 8443}}, periodSeconds: 1}}
      volumes:
      - {{name: tls, secret: {{secretName: {name}-tls}}}}
      - {{name: code, configMap: {{name: {name}-code}}}}
---
apiVersion: v1
kind: Service
metadata: {{name: {name}}}
spec:
  selector: {{app: {name}}}
  ports: [{{port: 443, targetPort: 8443}}]
'''
    rc, o = apply(y, ns=ns, c=c)
    assert rc == 0, o
    rc, o = k('rollout', 'status', f'deploy/{name}', '-n', ns, '--timeout=120s', c=c, timeout=130)
    assert rc == 0, o
    return b64(ca)


def hook_logs(name, ns, since=None, c=None):
    """返回 webhook 服务日志里的 JSON 行(解析后的 dict 列表)。"""
    rc, o = k('logs', f'deploy/{name}', '-n', ns, c=c, raw=True)
    r = []
    for l in o.splitlines():
        try: r.append(json.loads(l))
        except Exception: pass
    return [x for x in r if 'started' not in x]


def scale(name, ns, n, c=None):
    """缩放并等到 Pod 数真的等于 n(旧 Pod 完全消失,新 Pod 就绪)。"""
    k('scale', f'deploy/{name}', '-n', ns, f'--replicas={n}', c=c)
    def ok():
        ps = kj('get', 'pods', '-n', ns, '-l', f'app={name}', c=c)['items']
        return len(ps) == n and all(any(x['type'] == 'Ready' and x['status'] == 'True' for x in p['status'].get('conditions', [])) for p in ps)
    v, dt = until(ok, 90)
    assert v or n == 0 and not kj('get', 'pods', '-n', ns, '-l', f'app={name}', c=c)['items'], 'scale 超时'
