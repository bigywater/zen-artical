import sys, os, re, time, json, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('v89')
cn, _ = up('main'); load('python:3.12-alpine')
NS = ns('v89')
APP = r'''
import os, sys, time, signal, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
VER = os.environ['VERSION']; MODE = os.environ.get('MODE', 'exit'); START = float(os.environ.get('START_DELAY', '0'))
draining = False; active = 0; last_active = time.time(); lock = threading.Lock()
def term(sig, frm):
    global draining
    if MODE == 'exit': os._exit(0)
    draining = True
    def fin():
        while True:
            time.sleep(0.5)
            with lock:
                if active == 0 and time.time() - last_active >= 1.0: break
        os._exit(0)
    threading.Thread(target=fin, daemon=True).start()
signal.signal(signal.SIGTERM, term)
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def do_GET(self):
        global active, last_active
        with lock: active += 1
        try:
            if self.path.startswith('/slow'): time.sleep(1.5)
            body = VER.encode(); self.send_response(200); self.send_header('Content-Length', str(len(body)))
            if draining: self.send_header('Connection', 'close'); self.close_connection = True
            self.end_headers(); self.wfile.write(body)
        finally:
            with lock: active -= 1; last_active = time.time()
time.sleep(START)
srv = ThreadingHTTPServer(('0.0.0.0', 8080), H); srv.daemon_threads = True
srv.serve_forever()
'''
CLIENT = r'''
import os, sys, time, json, threading, http.client, socket
HOST = 'app'; KA = os.environ.get('KEEPALIVE') == '1'; RATE = 100; W = 50
res = []; lock = threading.Lock()
def worker(wid):
    conn = None; nxt = time.time() + wid * 0.01; n = 0; iv = W / RATE
    while not os.path.exists('/tmp/stop'):
        now = time.time()
        if now < nxt: time.sleep(nxt - now)
        nxt = max(nxt + iv, time.time()); n += 1; slow = (n % 20 == 0); t = time.time()
        try:
            if conn is None or not KA: conn = http.client.HTTPConnection(HOST, 80, timeout=5)
            conn.request('GET', '/slow' if slow else '/'); r = conn.getresponse(); v = r.read().decode(); out = ('ok', v) if r.status == 200 else ('http%d' % r.status, '')
            if not KA: conn.close()
        except ConnectionRefusedError: out = ('refused', ''); conn = None
        except (ConnectionResetError, BrokenPipeError): out = ('reset', ''); conn = None
        except http.client.RemoteDisconnected: out = ('disconnected', ''); conn = None
        except (socket.timeout, TimeoutError): out = ('timeout', ''); conn = None
        except Exception as e: out = ('other:' + type(e).__name__, ''); conn = None
        with lock: res.append((t, out[0], out[1], slow))
ths = [threading.Thread(target=worker, args=(i,)) for i in range(W)]
for t in ths: t.start()
for t in ths: t.join()
print('RESULT ' + json.dumps(res))
'''
k('create', 'configmap', 'code', '-n', NS, '--from-literal=app.py=' + APP, '--from-literal=client.py=' + CLIENT)
def dep(readiness, prestop, mode, start=3):
    rp = '''
        readinessProbe: {httpGet: {path: /, port: 8080}, periodSeconds: 1, failureThreshold: 1}''' if readiness else ''
    ps = f'''
        lifecycle: {{preStop: {{exec: {{command: [sleep, "{prestop}"]}}}}}}''' if prestop else ''
    return f'''apiVersion: apps/v1
kind: Deployment
metadata: {{name: app, namespace: {NS}}}
spec:
  replicas: 3
  strategy: {{type: RollingUpdate, rollingUpdate: {{maxSurge: 1, maxUnavailable: 0}}}}
  selector: {{matchLabels: {{app: app}}}}
  template:
    metadata: {{labels: {{app: app}}}}
    spec:
      terminationGracePeriodSeconds: 30
      volumes: [{{name: code, configMap: {{name: code}}}}]
      containers:
      - name: app
        image: python:3.12-alpine
        command: [python, /code/app.py]
        env: [{{name: VERSION, value: v1}}, {{name: MODE, value: {mode}}}, {{name: START_DELAY, value: "{start}"}}]
        ports: [{{containerPort: 8080}}]
        volumeMounts: [{{name: code, mountPath: /code}}]{rp}{ps}
---
apiVersion: v1
kind: Service
metadata: {{name: app, namespace: {NS}}}
spec: {{selector: {{app: app}}, ports: [{{port: 80, targetPort: 8080}}]}}
'''
def client_yaml(ka):
    return f'''apiVersion: v1
kind: Pod
metadata: {{name: client, namespace: {NS}}}
spec:
  restartPolicy: Never
  terminationGracePeriodSeconds: 1
  volumes: [{{name: code, configMap: {{name: code}}}}]
  containers:
  - name: c
    image: python:3.12-alpine
    command: [python, /code/client.py]
    env: [{{name: KEEPALIVE, value: "{'1' if ka else '0'}"}}]
    volumeMounts: [{{name: code, mountPath: /code}}]
'''
def scenario(readiness, prestop, mode, ka=False):
    k('delete', 'deployment', 'app', '-n', NS, '--ignore-not-found', '--wait=true', timeout=120); k('delete', 'pod', 'client', '-n', NS, '--ignore-not-found', '--wait=true', timeout=60)
    k('apply', '-f', '-', input=dep(readiness, prestop, mode))
    rc, o = k('rollout', 'status', 'deployment/app', '-n', NS, '--timeout=120s', timeout=140); assert rc == 0, o
    time.sleep(6)   # 没有 readinessProbe 时,Pod 一启动就算 Ready,应用还要 3 s 才监听;等它真的起来再开始测
    k('apply', '-f', '-', input=client_yaml(ka)); until(lambda: (kj('get', 'pod', 'client', '-n', NS) or {}).get('status', {}).get('phase') == 'Running', 60); time.sleep(5)
    t0 = time.time(); k('set', 'env', 'deployment/app', 'VERSION=v2', '-n', NS)
    rc, o = k('rollout', 'status', 'deployment/app', '-n', NS, '--timeout=180s', timeout=200); assert rc == 0, o
    dur = time.time() - t0; time.sleep(8); k('exec', 'client', '-n', NS, '--', 'touch', '/tmp/stop'); until(lambda: (kj('get', 'pod', 'client', '-n', NS) or {}).get('status', {}).get('phase') in ('Succeeded', 'Failed'), 40)
    out = ko('logs', 'client', '-n', NS, timeout=60); line = [l for l in out.splitlines() if l.startswith('RESULT ')][-1]
    return json.loads(line[7:]), dur
def analyse(res, dur):
    n = len(res); err = [r for r in res if r[1] != 'ok']; kinds = collections.Counter(r[1] for r in err); slow_err = sum(1 for r in err if r[3])
    oks = sorted(r[0] for r in res if r[1] == 'ok'); gap = max(b - a for a, b in zip(oks, oks[1:]))
    v2 = [r[0] for r in res if r[2] == 'v2']; v1 = [r[0] for r in res if r[2] == 'v1']
    win = (max(r[0] for r in err) - min(r[0] for r in err)) if err else 0
    t0 = min(r[0] for r in res)
    return dict(n=n, err=len(err), kinds=kinds, win=win, dur=dur, slow_err=slow_err, gap=gap, v1_last=max(v1) - t0, v2_first=min(v2) - t0, nslow=sum(1 for r in res if r[3]))
import collections
CASES = [('一', '没有 readinessProbe、没有 preStop、应用收到 SIGTERM 立刻退出', (False, 0, 'exit')), ('二', '加上 readinessProbe', (True, 0, 'exit')), ('三', 'readinessProbe + preStop sleep 5', (True, 5, 'exit')),
         ('四', 'readinessProbe + 应用优雅退出(SIGTERM 后继续服务,空闲 1 s 才退出),没有 preStop', (True, 0, 'drain')), ('五', 'readinessProbe + preStop sleep 5 + 应用优雅退出', (True, 5, 'drain'))]
print(f'集群 {cn};应用是 python:3.12-alpine 里的小 HTTP 服务,启动要 3 s(才开始监听);Deployment 3 副本,RollingUpdate maxSurge 1 maxUnavailable 0,terminationGracePeriodSeconds 30;客户端是集群里的一个 Pod,经 Service 以约 100 个请求/秒访问(50 个线程各约 2 个请求/秒,线程被超时卡住时不补发;每 20 个请求有一个 /slow,服务端睡 1.5 s 再回),每次请求新建连接,超时 5 s;滚动发布 = kubectl set env VERSION=v1→v2;时间的基准是客户端第一次收到 v2 响应的时刻(客户端自己的时钟,避开宿主机和节点的时钟差)')
R = {}
for key, title, args in CASES:
    print(f'== {key}:{title}')
    res, dur = scenario(*args); a = analyse(res, dur); R[key] = a
    print(f'  客户端请求 {a["n"]} 个,失败 {a["err"]} 个({a["err"] / a["n"] * 100:.2f}%),其中 /slow 请求失败 {a["slow_err"]} 个;失败类型 {dict(a["kinds"])};' + (f'第一个到最后一个失败相隔 {a["win"]:.1f} s' if a['err'] else '没有失败') + f';最长一段没有任何成功响应的间隔 {a["gap"]:.2f} s;客户端第一次收到 v2 在 {a["v2_first"]:.1f} s,最后一次收到 v1 在 {a["v1_last"]:.1f} s(从客户端开始算);kubectl rollout 耗时 {a["dur"]:.0f} s')
print('== 六:长连接(keep-alive)的客户端。同样的滚动发布,客户端复用连接(连接断了不自动重试,直接算一次失败),对比 preStop sleep 5 + 应用立刻退出 与 preStop sleep 5 + 应用优雅退出(优雅退出期间响应带 Connection: close)')
for key, title, args in (('六甲', 'keep-alive、readinessProbe + preStop sleep 5、应用立刻退出', (True, 5, 'exit', True)), ('六乙', 'keep-alive、readinessProbe + preStop sleep 5 + 应用优雅退出', (True, 5, 'drain', True))):
    res, dur = scenario(*args); a = analyse(res, dur); R[key] = a
    print(f'  {title}:请求 {a["n"]} 个,失败 {a["err"]} 个({a["err"] / a["n"] * 100:.2f}%),其中 /slow 失败 {a["slow_err"]} 个;失败类型 {dict(a["kinds"])};' + (f'第一个到最后一个失败相隔 {a["win"]:.1f} s' if a['err'] else '没有失败') + f';最长无成功响应的间隔 {a["gap"]:.2f} s')
print('说明(哪些是测到的,哪些是推测)\n  每种配置只跑了一次,没有重复,失败数每次运行会不一样(开发中的一次运行里,第一种配置失败 129 个,第二种读日志时客户端还没结束);「最长一段没有成功响应的间隔」在没有任何失败的几种配置里也有大约 1 s,我没有查清原因(可能是客户端自己的停顿),所以只有第一种配置里的 2 s 多的间隔能说明问题;timeout 失败的原因是推测(旧 Pod 已经删掉,往它的 IP 发的连接没有任何回应),没有抓包验证;第二种配置里 reset 的数量与 /slow 失败的数量相同,我认为是正在处理的慢请求被进程退出打断,没有逐条核对;应用的「优雅退出」是我手写的(SIGTERM 后继续服务到空闲 1 s),不代表框架自带的行为')
k('delete', 'ns', NS, '--wait=false')
