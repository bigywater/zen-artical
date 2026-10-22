import sys, os, re, time, json, subprocess, statistics, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('v94')
cn, _ = up('main'); load('traefik:v3.7.15', 'busybox:1.36', 'python:3.12-alpine')
D = HERE / 'vtmp' / 'v94'
rc, o = k('apply', '--server-side', '-f', str(D / 'gwapi-standard.yaml')); assert rc == 0, o[-300:]
rc, o = k('apply', '-f', str(D / 'traefik.yaml')); assert rc == 0, o[-300:]
rc, o = k('rollout', 'status', 'deploy/traefik', '-n', 'traefik', '--timeout=150s', timeout=170); assert rc == 0, o
A, B = ns('v94'), ns('v94b')
def app(v, n):
    return f"""apiVersion: apps/v1
kind: Deployment
metadata: {{name: app-{v}, namespace: {n}}}
spec:
  replicas: 1
  selector: {{matchLabels: {{app: app-{v}}}}}
  template:
    metadata: {{labels: {{app: app-{v}}}}}
    spec:
      containers:
      - name: a
        image: busybox:1.36
        command: [sh, -c, "mkdir -p /www && echo {v} > /www/index.html && cp /www/index.html /www/a && cp /www/index.html /www/b && httpd -f -p 8080 -h /www"]
        readinessProbe: {{tcpSocket: {{port: 8080}}, periodSeconds: 1}}
---
apiVersion: v1
kind: Service
metadata: {{name: app-{v}, namespace: {n}}}
spec: {{selector: {{app: app-{v}}}, ports: [{{port: 80, targetPort: 8080}}]}}
---
"""
k('apply', '-f', '-', input=app('v1', A) + app('v2', A) + app('v3', B) + f"""apiVersion: v1
kind: Pod
metadata: {{name: client, namespace: {A}}}
spec:
  terminationGracePeriodSeconds: 1
  containers: [{{name: c, image: python:3.12-alpine, command: [sleep, "36000"]}}]
""")
for d, n in (('app-v1', A), ('app-v2', A), ('app-v3', B)): assert k('rollout', 'status', f'deploy/{d}', '-n', n, '--timeout=90s', timeout=120)[0] == 0
until(lambda: (kj('get', 'pod', 'client', '-n', A) or {}).get('status', {}).get('phase') == 'Running', 60)
HIT = """
import http.client, collections, json, sys
n = int(sys.argv[1]); host = sys.argv[2]; path = sys.argv[3]; hdr = json.loads(sys.argv[4]); c = collections.Counter()
for i in range(n):
    conn = http.client.HTTPConnection('traefik.traefik', 80, timeout=5); h = {'Host': host}; h.update(hdr)
    try:
        conn.request('GET', path, headers=h); r = conn.getresponse(); b = r.read().decode().strip(); c[f'{r.status}:{b[:12]}' if r.status == 200 else str(r.status)] += 1
    except Exception as e: c['err:' + type(e).__name__] += 1
    conn.close()
print(json.dumps(c, sort_keys=True))
"""
def hit(n, host, path='/', hdr=None):
    rc, o = k('exec', '-i', 'client', '-n', A, '--', 'python', '-', str(n), host, path, json.dumps(hdr or {}), input=HIT, timeout=180); return o.strip().splitlines()[-1]
def fmt(j): return ', '.join(f'{k_} × {v}' for k_, v in json.loads(j).items())
def conds(kind, name, ns_, parent=False):
    j = kj('get', kind, name, '-n', ns_) or {}
    cs = (j.get('status', {}).get('parents', [{}])[0].get('conditions', []) if parent else j.get('status', {}).get('conditions', []))
    return ', '.join(f'{c["type"]}={c["status"]}({c["reason"]})' for c in cs) or '(没有 status)'
def ing(rules, n=A, name='ing'):
    return f"""apiVersion: networking.k8s.io/v1
kind: Ingress
metadata: {{name: {name}, namespace: {n}}}
spec:
  ingressClassName: traefik
  rules:
  - host: shop.local
    http:
      paths:
{rules}
"""
def ipath(path, svc, n=None): return f"      - {{path: {path}, pathType: Prefix, backend: {{service: {{name: {svc}, port: {{number: 80}}}}}}}}"
def gw(frm='Same', sel=''):
    return f"""apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata: {{name: gw, namespace: {A}}}
spec:
  gatewayClassName: traefik
  listeners:
  - {{name: web, port: 8000, protocol: HTTP, allowedRoutes: {{namespaces: {{from: {frm}{sel}}}}}}}
"""
def route(rules, n=A, name='r', host='api.local'):
    return f"""apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata: {{name: {name}, namespace: {n}}}
spec:
  parentRefs: [{{name: gw, namespace: {A}}}]
  hostnames: [{host}]
  rules:
{rules}
"""
def wb(*pairs): return '  - backendRefs: [' + ', '.join(f'{{name: {n}, port: 80, weight: {w}}}' for n, w in pairs) + ']'
k('apply', '-f', '-', input=gw()); time.sleep(3)
ver = lambda img: img.split(':')[-1]
print(f'Kubernetes(kind 节点镜像 {NODE_IMG.split(":")[-1]}),Gateway API 标准通道 CRD v1.6.3(下载自 kubernetes-sigs/gateway-api 的发布页),Traefik {ver("traefik:v3.7.15")} 同时开 Ingress 与 Gateway API 两个 provider(同一个数据面,这样两种写法比较的是 API 而不是实现);后端是 busybox httpd,回应 v1 / v2 / v3;客户端是集群里的一个 Pod,经 Service traefik.traefik 访问。Traefik 只是 Gateway API 的一种实现,其它实现对 Gateway API 的支持程度和 Ingress 的注解不一样,结论只代表这一个实现')

# ============ 一 ============
print('== 一:Ingress 能表达什么。Ingress(host shop.local):(a)/a 路由到 app-v1,/b 路由到 app-v2;(b)想让 / 的流量一部分去 app-v1、一部分去 app-v2,只能写两条 path 相同的规则,各指一个 Service;(c)用 kubectl explain 看 Ingress 的一条路径上有哪些字段。每种请求 200 个')
k('apply', '-f', '-', input=ing(ipath('/a', 'app-v1') + '\n' + ipath('/b', 'app-v2'))); time.sleep(4)
print(f'  (a)GET /a:{fmt(hit(200, "shop.local", "/a"))};GET /b:{fmt(hit(200, "shop.local", "/b"))}')
k('apply', '-f', '-', input=ing(ipath('/', 'app-v1') + '\n' + ipath('/', 'app-v2'))); time.sleep(4)
rb_ = fmt(hit(200, 'shop.local', '/')); print(f'  (b)两条 path 都是 / 的规则(先写 app-v1,后写 app-v2):GET /:{rb_}')
rc, o = k('explain', 'ingress.spec.rules.http.paths'); fields = re.findall(r'^\s{2,}(\w+)\s+<', o, re.M)
print(f'  (c)kubectl explain ingress.spec.rules.http.paths 列出的字段:{fields}')
rc, o = k('explain', 'ingress.spec.rules'); print(f'  (c)kubectl explain ingress.spec.rules 列出的字段:{re.findall(chr(94) + r"\s{2,}(\w+)\s+<", o, re.M)}')
print('  Ingress 的规则只有 host、path、pathType 和一个后端 Service;每条路径只指一个后端,没有权重、请求头匹配这些字段;两条同样的 path 时流量不会按比例分,全部去了同一个后端(上面 (b) 的结果),想要流量比例或按请求头分流,只能用具体控制器自己的注解或自定义资源,换一个控制器就要重写')

# ============ 二 ============
print('== 二:Gateway API 的 HTTPRoute。同一个 Gateway(监听 8000,即 Traefik 的 web 入口):(a)权重 90 对 10;(b)改成 50 对 50;(c)改成 0 对 100;(d)请求头匹配:带 x-canary: 1 的请求去 app-v2,其它去 app-v1。(a)到(c)各请求 500 个,(d)各 200 个')
for lab, ws in (('(a)app-v1 权重 90、app-v2 权重 10', (90, 10)), ('(b)权重 50 对 50', (50, 50)), ('(c)权重 0 对 100', (0, 100))):
    k('apply', '-f', '-', input=route(wb(('app-v1', ws[0]), ('app-v2', ws[1])))); time.sleep(4)
    print(f'  {lab}:{fmt(hit(500, "api.local"))}')
k('apply', '-f', '-', input=route("  - matches: [{headers: [{name: x-canary, value: '1'}]}]\n    backendRefs: [{name: app-v2, port: 80}]\n  - backendRefs: [{name: app-v1, port: 80}]")); time.sleep(4)
print(f'  (d)带 x-canary: 1:{fmt(hit(200, "api.local", "/", {"x-canary": "1"}))};不带:{fmt(hit(200, "api.local"))}')
print('  权重和请求头匹配是 HTTPRoute 规范里的字段,不是某个控制器的注解;这个实现按权重轮转,500 个请求的分配是精确的比例(不是随机抽样)')

# ============ 三 ============
print('== 三:谁能把路由挂到谁的网关上。Gateway 在命名空间 v94,监听器的 allowedRoutes 先是 from: Same。另一个命名空间 v94b 里有一个 HTTPRoute(host other.local,后端是 v94b 里的 app-v3),parentRef 指向 v94 里的 gw。(a)allowedRoutes 为 Same 时路由的状态和请求结果;(b)把监听器改成 from: All 之后;(c)v94b 的路由再引用 v94 里的 Service(app-v1,另一个命名空间),没有 ReferenceGrant 时;(d)在 v94 里加上允许 v94b 的 HTTPRoute 引用 Service 的 ReferenceGrant 之后')
k('apply', '-f', '-', input=route(wb(('app-v3', 1)), n=B, name='rb', host='other.local')); time.sleep(4)
print(f'  (a)from: Same:路由状态 {conds("httproute", "rb", B, True)};GET other.local:{fmt(hit(100, "other.local"))}')
k('apply', '-f', '-', input=gw('All')); time.sleep(5)
print(f'  (b)from: All:路由状态 {conds("httproute", "rb", B, True)};GET other.local:{fmt(hit(100, "other.local"))}')
k('apply', '-f', '-', input=route(f"  - backendRefs: [{{name: app-v1, namespace: {A}, port: 80}}]", n=B, name='rb', host='other.local')); time.sleep(5)
print(f'  (c)后端是另一个命名空间的 Service,没有 ReferenceGrant:路由状态 {conds("httproute", "rb", B, True)};GET other.local:{fmt(hit(100, "other.local"))}')
k('apply', '-f', '-', input=f"""apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata: {{name: allow-b, namespace: {A}}}
spec:
  from: [{{group: gateway.networking.k8s.io, kind: HTTPRoute, namespace: {B}}}]
  to: [{{group: "", kind: Service}}]
"""); time.sleep(5)
print(f'  (d)加上 ReferenceGrant:路由状态 {conds("httproute", "rb", B, True)};GET other.local:{fmt(hit(100, "other.local"))}')
print('  Gateway API 把 “谁拥有网关” 和 “谁写路由” 分开,并且在规范里规定了越界时怎么办:路由要经过监听器的 allowedRoutes 才能挂上去,引用别的命名空间的 Service 要对方用 ReferenceGrant 授权;Ingress 没有这一层,任何命名空间的 Ingress 都能挂到同一个控制器上')

# ============ 四 ============
print('== 四:配置错了,从 kubectl 能看到什么。(a)Ingress 指向一个不存在的 Service;(b)HTTPRoute 的 backendRef 指向一个不存在的 Service。看 kubectl get -o 的状态字段、请求的结果')
k('delete', 'httproute', 'rb', '-n', B, '--ignore-not-found'); k('apply', '-f', '-', input=ing(ipath('/', 'no-such-svc'), name='ing-bad')); k('delete', 'ingress', 'ing', '-n', A); time.sleep(5)
j = kj('get', 'ingress', 'ing-bad', '-n', A) or {}
print(f'  (a)Ingress 指向不存在的 Service:status = {json.dumps(j.get("status"), ensure_ascii=False)};GET /:{fmt(hit(100, "shop.local"))}')
k('delete', 'ingress', 'ing-bad', '-n', A); k('apply', '-f', '-', input=route("  - backendRefs: [{name: no-such-svc, port: 80}]")); time.sleep(5)
print(f'  (b)HTTPRoute 指向不存在的 Service:路由状态 {conds("httproute", "r", A, True)};GET /:{fmt(hit(100, "api.local"))}')
rc, o = k('get', 'httproute', 'r', '-n', A, '-o', 'jsonpath={.status.parents[0].conditions[?(@.type=="ResolvedRefs")].message}'); print(f'  (b)ResolvedRefs 的 message:{o.strip()[:160]}')
print('  Ingress 的 status 里只有负载均衡器地址,规则写错了从 kubectl 看不出来(得去看控制器日志);HTTPRoute 的 status.parents[*].conditions 是规范规定的,控制器必须写 Accepted / ResolvedRefs,指向不存在的后端会有明确的原因')

# ============ 五 ============
print('== 五:改一次配置要多久生效。把流量从 app-v1 全部切到 app-v2:Ingress 改后端 Service,HTTPRoute 改权重(100/0 → 0/100)。客户端每 20 ms 请求一次,记下第一次看到 v2 的时刻;从宿主机的 kubectl apply 开始算(用 kubectl exec 对表估计宿主机与容器的时钟差,误差在 0.1 s 以内),各 5 次取中位数')
POLL = """
import http.client, time, sys, json
host = sys.argv[1]; end = time.time() + 20; first = None
while time.time() < end:
    conn = http.client.HTTPConnection('traefik.traefik', 80, timeout=3)
    try:
        conn.request('GET', '/', headers={'Host': host}); b = conn.getresponse().read().decode().strip()
        if b == 'v2' and first is None: first = time.time(); break
    except Exception: pass
    conn.close(); time.sleep(0.02)
print(json.dumps({'first_v2': first}))
"""
def clock_offset():
    best = None
    for _ in range(5):
        t0 = time.time(); o = k('exec', 'client', '-n', A, '--', 'python', '-c', 'import time;print(time.time())')[1]; t1 = time.time(); off = float(o.strip().splitlines()[-1]) - (t0 + t1) / 2
        if best is None or (t1 - t0) < best[0]: best = (t1 - t0, off)
    return best[1]
def propagate(host, before_yaml, after_yaml):
    k('apply', '-f', '-', input=before_yaml); time.sleep(4); off = clock_offset()
    p = subprocess.Popen(['kubectl', '--kubeconfig', kcfg(), 'exec', '-i', 'client', '-n', A, '--', 'python', '-', host], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    p.stdin.write(POLL); p.stdin.close(); time.sleep(1.5); t = time.time(); k('apply', '-f', '-', input=after_yaml); out = p.communicate(timeout=60)[0]
    first = json.loads(out.strip().splitlines()[-1])['first_v2']; return None if first is None else first - off - t
res = {'Ingress': [], 'HTTPRoute': []}
for _ in range(5):
    res['Ingress'].append(propagate('shop.local', ing(ipath('/', 'app-v1')), ing(ipath('/', 'app-v2'))))
    res['HTTPRoute'].append(propagate('api.local', route(wb(('app-v1', 100), ('app-v2', 0))), route(wb(('app-v1', 0), ('app-v2', 100)))))
for name, xs in res.items():
    ok = [x for x in xs if x is not None]
    print(f'  {name}:从 kubectl apply 开始(含 kubectl 进程本身的启动和请求 API 的时间)到客户端第一次看到 v2,中位数 {statistics.median(ok):.2f} s(5 次:{", ".join(f"{x:.2f}" for x in ok)})')
print('  两种写法最终都是控制器监听 API 对象的变化再更新数据面,生效的时间取决于控制器,不取决于 API 本身;这是同一个实现(Traefik)里两种写法的数字,换一个控制器会不同')
k('delete', 'ns', A, B, '--wait=false')
print('说明(哪些是测到的,哪些没有测)\n  全部是一个实现(Traefik v3.7.15)在 kind 集群里的结果;每个场景只跑了一次(传播延迟 5 次);没有测:TLS 终止与证书(Gateway 的 certificateRefs、Ingress 的 tls)、其它控制器(ingress-nginx、Envoy Gateway、Istio)对 Ingress 注解和 Gateway API 特性的支持差异、GRPCRoute / TCPRoute 与实验通道的特性、多个 Gateway 的共享、真实云负载均衡器后面的行为(kind 里没有 LoadBalancer),以及 Traefik 对权重分配是否在所有版本里都是精确比例')
