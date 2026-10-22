import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import http.client, urllib.request
tee('v88'); reset()
print('流量镜像(shadow / mirror)。Envoy 1.39.3,路由里的 request_mirror_policies,本机的 Python 后端:prod 总是回 200 "prod",shadow 的行为按实验改变。(一)镜像到底发了什么(请求数、Host 头、请求体),客户端拿到谁的响应;(二)shadow 变慢、返回 500、整个挂掉时客户端受不受影响;(三)runtime_fraction 控制镜像比例;(四)shadow 的并发被熔断器限住之后会怎样;(五)镜像的写请求在 shadow 里是真的执行了')
class Shadow:
    def __init__(self, delay=0.0, code=200):
        self.delay, self.code, self.hosts, self.bodies, self.writes = delay, code, collections.Counter(), [], 0
        def app(h):
            n = int(h.headers.get('Content-Length') or 0); body = h.rfile.read(n) if n else b''
            with self.svc.lock:
                self.hosts[h.headers.get('Host')] += 1
                if body: self.bodies.append(len(body))
                if h.command == 'POST': self.writes += 1
            if self.delay: time.sleep(self.delay)
            h.reply(self.code, b'shadow')
        self.svc = Svc(app, 'shadow'); self.port = self.svc.port
    @property
    def arrived(self): return self.svc.arrived
    def stop(self): self.svc.stop()
PROD = Svc(lambda h: (h.rfile.read(int(h.headers.get('Content-Length') or 0)), h.reply(200, b'prod'))[1], 'prod')
def conf(sh_port, frac=100, suffix=True, breaker=None, admin=None):
    routes = f'''              - match: {{prefix: "/"}}
                route:
                  cluster: prod
                  request_mirror_policies:
                  - cluster: shadow
                    runtime_fraction: {{default_value: {{numerator: {frac}, denominator: HUNDRED}}}}
                    {"" if suffix else "disable_shadow_host_suffix_append: true"}'''
    y = envoy_http_conf(routes, {'prod': [PROD.port], 'shadow': [sh_port]})
    if breaker: y = y.replace('  - name: shadow\n    type: STATIC\n    connect_timeout: 1s', f'  - name: shadow\n    type: STATIC\n    connect_timeout: 1s\n    circuit_breakers: {{thresholds: [{{max_connections: {breaker}, max_pending_requests: {breaker}}}]}}')
    return f'admin: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {admin}}}}}}}\n' + y
def stat(admin, name):
    t = urllib.request.urlopen(f'http://127.0.0.1:{admin}/stats?filter={name}', timeout=3).read().decode()
    for l in t.splitlines():
        k, _, v = l.partition(': ')
        if k == name: return int(v)
    return 0
def run(n, rate, path='/'):
    def one(i):
        s, d, dt = rpc(E.port, path, 5.0, keepalive=False); return (s, d, dt)
    r = openloop(one, rate, n / rate, workers=300)
    return [x for _, x in r]
def summ(res):
    ok = [x for x in res if x[0] == 200]; lat = [x[2] * 1000 for x in res]
    return len(res), len(ok) / len(res) * 100, pct(lat, 50), pct(lat, 99), collections.Counter(x[1] for x in res if x[0] == 200)

# ============ 一 ============
print('== 一:镜像发了什么。路由把请求发给 prod,同时镜像一份给 shadow(100%)。发 200 个 GET(100 个/秒)。看客户端拿到谁的响应、shadow 收到几个请求、shadow 看到的 Host 头;再对比 disable_shadow_host_suffix_append: true')
rows = []
for name, suffix in (('默认', True), ('disable_shadow_host_suffix_append: true', False)):
    sh = Shadow(); admin = free_port(); E = Envoy('v88a', conf(sh.port, 100, suffix, admin=admin)).start(); time.sleep(0.5)
    res = run(200, 100); time.sleep(0.5); n, ok, p50, p99, bodies = summ(res)
    rows.append((name, f'{n}', dict(bodies).__repr__().replace("b'", "").replace("'", ""), sh.arrived, ', '.join(f'{h}×{c}' for h, c in sh.hosts.most_common(1))))
    E.stop(); sh.stop()
table(rows, ['配置', '客户端请求数', '客户端拿到的响应体', 'shadow 收到', 'shadow 看到的 Host(出现次数)'])
print('  客户端永远只拿到 prod 的响应,shadow 的响应被 Envoy 丢弃;shadow 收到的请求和 prod 一样多;默认情况下 Envoy 会在 Host 的主机名后面追加 "-shadow"(上表是 127.0.0.1-shadow:端口,后缀加在端口之前),这样 shadow 能区分镜像流量;关掉之后 Host 和 prod 看到的完全相同')

# ============ 二 ============
print('== 二:shadow 出问题时客户端受不受影响。每种 400 个 GET(100 个/秒),镜像 100%。对照组:不镜像(没有 request_mirror_policies)。shadow 状态:正常 / 每个请求慢 1 s / 返回 500 / 整个进程已经停了(连接被拒绝)')
rows = []
for name, mk in (('不镜像(对照)', 'none'), ('shadow 正常', Shadow()), ('shadow 每个请求 1 s', Shadow(1.0)), ('shadow 返回 500', Shadow(0, 500)), ('shadow 已停止', 'dead')):
    admin = free_port()
    if mk == 'none':
        E = Envoy('v88b', f'admin: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {admin}}}}}}}\n' + envoy_http_conf('              - match: {prefix: "/"}\n                route: {cluster: prod}', {'prod': [PROD.port]})).start(); sh = None
    else:
        if mk == 'dead': sh = Shadow(); p = sh.port; sh.stop()
        else: sh = mk; p = sh.port
        E = Envoy('v88b', conf(p, 100, True, admin=admin)).start()
    time.sleep(0.5); res = run(400, 100); time.sleep(1.5); n, ok, p50, p99, _ = summ(res)
    mirrored = '-' if mk == 'none' else stat(admin, 'cluster.shadow.upstream_rq_total'); sh_arr = '-' if sh is None or mk == 'dead' else sh.arrived
    rows.append((name, n, f'{ok:.1f}%', f'{p50:.1f}', f'{p99:.1f}', mirrored, sh_arr))
    E.stop()
    if sh and mk != 'dead': sh.stop()
table(rows, ['场景', '请求数', '客户端成功率', '延迟 p50 (ms)', '延迟 p99 (ms)', 'Envoy 发往 shadow 的请求(upstream_rq_total)', 'shadow 收到'])
print('  镜像是 “发出去就不管”(fire-and-forget):shadow 慢、报错、或者整个挂掉,客户端的成功率和延迟都和不镜像时在同一个量级,看不出区别')

# ============ 三 ============
print('== 三:runtime_fraction 控制镜像比例。每种 1000 个 GET(200 个/秒),default_value 的 numerator 分别是 0 / 10 / 50 / 100(denominator HUNDRED)')
rows = []
for frac in (0, 10, 50, 100):
    sh = Shadow(); admin = free_port(); E = Envoy('v88c', conf(sh.port, frac, True, admin=admin)).start(); time.sleep(0.5)
    res = run(1000, 200); time.sleep(0.8); n, ok, p50, p99, _ = summ(res)
    rows.append((f'{frac}%', n, sh.arrived, f'{sh.arrived / n * 100:.1f}%')); E.stop(); sh.stop()
table(rows, ['numerator', '客户端请求数', 'shadow 收到', '占比'])
print('  镜像比例是按请求随机抽的,实际比例围绕设定值上下波动')

# ============ 四 ============
print('== 四:shadow 变慢 + 熔断器。shadow 每个请求 2 s,300 个/秒的 GET 持续 4 s(共 1200 个)。两种配置:(a)shadow 集群默认熔断阈值(300 个/秒 × 2 s ≈ 600 个并发,低于默认的 1024 个连接);(b)shadow 集群 max_connections 5 / max_pending_requests 5。看客户端和 shadow 的情况,以及 Envoy 的 upstream_rq_pending_overflow / upstream_cx_overflow(统计 shadow 集群)')
rows = []
for name, br in (('(a)默认熔断阈值', None), ('(b)max_connections 5, max_pending_requests 5', 5)):
    sh = Shadow(2.0); admin = free_port(); E = Envoy('v88d', conf(sh.port, 100, True, breaker=br, admin=admin)).start(); time.sleep(0.5)
    res = run(1200, 300); n, ok, p50, p99, _ = summ(res); time.sleep(0.5)
    rows.append((name, n, f'{ok:.1f}%', f'{p50:.1f}', f'{p99:.1f}', stat(admin, 'cluster.shadow.upstream_rq_total'), stat(admin, 'cluster.shadow.upstream_rq_pending_overflow'), stat(admin, 'cluster.shadow.upstream_cx_overflow'), sh.arrived))
    E.stop(); sh.stop()
table(rows, ['配置', '请求数', '客户端成功率', 'p50 (ms)', 'p99 (ms)', '发往 shadow 的请求', 'pending_overflow', 'cx_overflow', 'shadow 实际收到'])
print('  shadow 的并发被熔断器限住时,超出的镜像请求直接丢掉(这次 1200 个里只有 15 个到了 shadow,其余 1185 个是 pending_overflow),客户端不受影响;代价是 shadow 只看到一部分流量,采样会失真(别以为 shadow 看到的是全量)')

# ============ 五 ============
print('== 五:镜像的写请求在 shadow 里真的执行了。客户端发 100 个 POST /pay(每个带 64 字节请求体),镜像 100%。shadow 把每个 POST 当作一次 “写”(计数),prod 也计数')
sh = Shadow(); admin = free_port(); prod_posts = [0]; pb = [0]
PROD2 = Svc(lambda h: (prod_posts.__setitem__(0, prod_posts[0] + 1), h.rfile.read(int(h.headers.get('Content-Length') or 0)), h.reply(200, b'paid'))[2], 'prod2')
y = conf(sh.port, 100, True, admin=admin).replace(f'port_value: {PROD.port}', f'port_value: {PROD2.port}'); E = Envoy('v88e', y).start(); time.sleep(0.5)
def post(i):
    c = http.client.HTTPConnection('127.0.0.1', E.port, timeout=5); c.request('POST', '/pay', body=b'x' * 64, headers={'Content-Type': 'application/octet-stream'}); r = c.getresponse(); b = r.read(); c.close(); return r.status, b
r = openloop(lambda i: post(i), 50, 2.0, workers=50); res = [x for _, x in r]; time.sleep(0.8)
print(f'  客户端 POST {len(res)} 个,响应 {collections.Counter((s, b) for s, b in res)};prod 执行的写 {prod_posts[0]} 次,shadow 执行的写 {sh.writes} 次;shadow 收到的请求体长度 {sorted(set(sh.bodies))} 字节(共 {len(sh.bodies)} 个)')
print('  镜像连请求体一起发,shadow 如果是真实的服务并且连着真实的下游(数据库、消息队列、支付渠道),这些写会再执行一遍;shadow 必须指向隔离的数据和下游,或者只镜像读请求')
E.stop(); sh.stop(); PROD2.stop(); PROD.stop()
print('ERRORS', dict(ERRORS))
