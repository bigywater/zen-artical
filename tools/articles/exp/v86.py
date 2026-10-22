import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import re
tee('v86'); reset()
print('Envoy 的异常检测、熔断、重试与超时。Envoy 1.39.3(--concurrency 1)+ 本机的 Python 后端(每个后端可以设定失败率和延迟,并统计到达的请求数)。(一)重试策略:谁来重试、重试到哪个主机、放大多少请求;(二)per_try_timeout 对慢主机的作用;(三)熔断器(连接数、等待队列)溢出时的表现;(四)异常点检测(连续 5xx 就摘除)和 panic 模式')
class BE:
    def __init__(self, name, fail=0.0, delay=0.0):
        self.name, self.fail, self.delay, self.arrived = name, fail, delay, 0; self.rnd = random.Random(hash(name) & 0xffff)
        def app(h):
            self.arrived += 1
            if self.delay: time.sleep(self.delay)
            if self.rnd.random() < self.fail: h.reply(503 if self.fail < 1 else 500, b'err')
            else: h.reply(200, name.encode())
        self.svc = Svc(app, name); self.port = self.svc.port
    def stop(self): self.svc.stop()
def mkcfg(ports, cluster_extra='', route_extra='', admin=0):
    eps = ''.join(f'\n        - endpoint: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {p}}}}}}}' for p in ports)
    return f'''admin: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {admin}}}}}}}
static_resources:
  listeners:
  - name: l
    address: {{socket_address: {{address: 127.0.0.1, port_value: {{port}}}}}}
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress
          http_filters:
          - name: envoy.filters.http.router
            typed_config: {{"@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router}}
          route_config:
            virtual_hosts:
            - name: v
              domains: ["*"]
              routes:
              - match: {{prefix: "/"}}
                route:
                  cluster: back
                  {route_extra}
  clusters:
  - name: back
    type: STATIC
    connect_timeout: 1s
    lb_policy: ROUND_ROBIN
    {cluster_extra}
    load_assignment:
      cluster_name: back
      endpoints:
      - lb_endpoints:{eps}
'''
def stats(admin, flt):
    s, d, _ = rpc(admin, f'/stats?filter={flt}', 3.0); out = {}
    for line in d.decode().splitlines():
        k, _, v = line.partition(': ')
        try: out[k] = int(v)
        except ValueError: pass
    return out
def run_env(ports, cluster_extra='', route_extra=''):
    admin = free_port(); e = Envoy('v86e', mkcfg(ports, cluster_extra, route_extra, admin)).start(); time.sleep(0.5); return e, admin

# ============ 一 ============
print('== 一:重试策略。两个后端:good(总是 200)和 bad(50% 返回 503),Envoy 轮询。路由重试策略 retry_on: 5xx。三种:(a)不重试;(b)num_retries: 1 且 retry_host_predicate: previous_hosts(重试时避开已经试过的主机);(c)num_retries: 1 且没有主机谓词(重试可能再选到同一个主机)。每种 2000 个请求(200 个/秒,开环)。统计客户端看到的成功率、后端实际收到的请求总数相对客户端请求数的比例,以及 Envoy 的重试统计')
rows = []
for name, route in (('(a)不重试', ''), ('(b)重试 1 次,避开已试过的主机', 'retry_policy: {retry_on: "5xx", num_retries: 1, retry_host_predicate: [{name: envoy.retry_host_predicates.previous_hosts, typed_config: {"@type": type.googleapis.com/envoy.extensions.retry.host.previous_hosts.v3.PreviousHostsPredicate}}], host_selection_retry_max_attempts: 5}'), ('(c)重试 1 次,不避开', 'retry_policy: {retry_on: "5xx", num_retries: 1}')):
    good, bad = BE('good'), BE('bad', fail=0.5); e, admin = run_env([good.port, bad.port], route_extra=route)
    res = openloop(lambda i: rpc(e.port, '/', 3.0, keepalive=False)[0], 200, 10, workers=100); c = collections.Counter(x for _, x in res); st = stats(admin, 'upstream_rq_retry')
    rows.append((name, f'{c.get(200, 0) / len(res):.1%}', f'{(good.arrived + bad.arrived) / len(res):.2f}', st.get('cluster.back.upstream_rq_retry', 0), st.get('cluster.back.upstream_rq_retry_success', 0), bad.arrived)); e.stop(); good.stop(); bad.stop()
table(rows, ['策略', '客户端看到的成功率', '后端收到的请求数 ÷ 客户端请求数', 'Envoy 记录的重试次数', '重试成功次数', 'bad 收到的请求数'])
print('  重试把一半请求的失败(轮询到 bad 并且 bad 这次失败,约 25%)变成成功,代价是后端多收到请求;重试时避开已经试过的主机,重试几乎都落在 good 上;不避开时重试仍有机会选到 bad 并再次失败,成功率低一些')

# ============ 二 ============
print('== 二:per_try_timeout。两个后端:fast(5 ms)和 slow(每个请求 1 s)。路由总超时 2 s。(a)不设 per_try_timeout、不重试;(b)per_try_timeout: 0.2s,retry_on: 5xx(每次尝试超时会变成 504),num_retries: 1,避开已试过的主机。200 个请求(20 个/秒,10 s,开环),统计延迟分布、成功率,以及 slow 后端实际收到的请求数(被超时取消的请求,后端还是收到了)')
rows = []
for name, route in (('(a)只有总超时 2 s', 'timeout: 2s'), ('(b)per_try_timeout 0.2 s + 重试 1 次', 'timeout: 2s\n                  retry_policy: {retry_on: "5xx", num_retries: 1, per_try_timeout: 0.2s, retry_host_predicate: [{name: envoy.retry_host_predicates.previous_hosts, typed_config: {"@type": type.googleapis.com/envoy.extensions.retry.host.previous_hosts.v3.PreviousHostsPredicate}}], host_selection_retry_max_attempts: 5}')):
    fast, slow = BE('fast'), BE('slow', delay=1.0); e, admin = run_env([fast.port, slow.port], route_extra=route)
    res = openloop(lambda i: (lambda r: (r[0], r[2]))(rpc(e.port, '/', 5.0, keepalive=False)), 20, 10, workers=200); lat = [r[1] * 1000 for _, r in res]; ok = sum(1 for _, r in res if r[0] == 200)
    rows.append((name, f'{ok / len(res):.0%}', f'{pct(lat, 25):.0f}', f'{pct(lat, 50):.0f}', f'{pct(lat, 75):.0f}', f'{pct(lat, 99):.0f}', f'{sum(1 for x in lat if x > 150) / len(lat):.0%}', slow.arrived)); e.stop(); fast.stop(); slow.stop()
table(rows, ['配置', '成功率', '延迟 p25(ms)', 'p50(ms)', 'p75(ms)', 'p99(ms)', '延迟超过 150 ms 的请求比例', 'slow 后端收到的请求数'])
print('  没有 per_try_timeout 时,轮询落到 slow 的请求要等满 1 s;设了 per_try_timeout 之后,第一次尝试 0.2 s 超时就换到 fast 重试,这些请求的延迟变成 0.2 s 多一点,所以 p99 从约 1 s 降到 0.2 s 多;代价是要等满 per_try_timeout 的请求仍然比较多,slow 后端收到的请求数也比 (a) 多——重试本身会让 Envoy 的轮询游标多走几步,我的猜测是这让更多请求第一次落到 slow 上(这个猜测没有另外验证,每次运行具体数字略有不同);超时只是 Envoy 不再等,slow 后端并没有因此少收请求')

# ============ 三 ============
print('== 三:熔断器(circuit_breakers)。一个后端,每个请求 300 ms。上游走 HTTP/1.1(一条连接同时只能处理一个请求)。(a)阈值很宽(默认 1024);(b)max_connections: 2、max_pending_requests: 2。20 个请求同时发出(20 个线程同时开始)。统计状态码、被溢出的请求带不带 x-envoy-overloaded 头,以及 Envoy 的溢出计数')
rows = []
for name, cb in (('(a)默认阈值', ''), ('(b)max_connections 2、max_pending_requests 2', 'circuit_breakers: {thresholds: [{max_connections: 2, max_pending_requests: 2, max_requests: 1000, max_retries: 3}]}')):
    be = BE('b', delay=0.3); e, admin = run_env([be.port], cluster_extra=cb); bar = threading.Barrier(20); out = []; lk = threading.Lock()
    def one(i):
        bar.wait(); t = time.perf_counter(); c = http.client.HTTPConnection('127.0.0.1', e.port, timeout=10); c.request('GET', '/'); r = c.getresponse(); r.read(); h = dict(r.getheaders()); c.close()
        with lk: out.append((r.status, h.get('x-envoy-overloaded'), time.perf_counter() - t))
    ths = [threading.Thread(target=one, args=(i,)) for i in range(20)]
    for t in ths: t.start()
    for t in ths: t.join()
    cs = collections.Counter(s for s, _, _ in out); ov = sum(1 for s, o, _ in out if o); st = stats(admin, 'overflow')
    rows.append((name, cs.get(200, 0), cs.get(503, 0), ov, max(t for _, _, t in out) * 1000, st.get('cluster.back.upstream_rq_pending_overflow', 0), st.get('cluster.back.upstream_cx_overflow', 0), be.arrived)); e.stop(); be.stop()
table([(a, b, c, d, f'{e_:.0f}', f, g, h) for a, b, c, d, e_, f, g, h in rows], ['配置', '200', '503', '带 x-envoy-overloaded 头的', '最慢的请求耗时(ms)', 'upstream_rq_pending_overflow', 'upstream_cx_overflow', '后端实际收到的请求数'])
print('  上游是 HTTP/1.1 时一个连接同时只处理一个请求,超过 max_connections 的请求进入等待队列,等待队列也满了就立即被拒绝(503,响应头带 x-envoy-overloaded);熔断的作用是在上游已经跟不上时快速失败,而不是把更多请求堆在上游前面')

# ============ 四 ============
print('== 四:异常点检测与 panic 模式。三个后端 h1、h2 正常,h3 总是返回 500;10 个请求/秒,运行 24 s。(a)outlier_detection:consecutive_5xx: 3,interval: 1s,base_ejection_time: 6s,max_ejection_percent: 50;看 h3 收到请求的比例随时间的变化(按每 3 秒统计,被摘除前 / 摘除后 / 摘除时间到之后)。(b)h2 和 h3 都总是返回 500、h1 正常,max_ejection_percent: 100:异常点检测会把两个坏主机都摘掉,健康主机只剩 1/3,低于 healthy_panic_threshold 默认的 50%,看流量是不是又会回到坏主机上')
def outlier(mp): return f'outlier_detection: {{consecutive_5xx: 3, interval: 1s, base_ejection_time: 6s, max_ejection_percent: {mp}, enforcing_consecutive_5xx: 100}}'
def timeline(bads, mp, label):
    hs = [BE('h1')] + [BE(f'h{i + 2}', fail=1.0) for i in range(2)]
    bad_idx = [i for i in range(3) if i in bads]
    for i, h in enumerate(hs): h.fail = 1.0 if i in bads else 0.0
    e, admin = run_env([h.port for h in hs], cluster_extra=outlier(mp)); t0 = time.perf_counter(); log = []
    def one(i): s, d, dt = rpc(e.port, '/', 3.0, keepalive=False); return (s, d.decode()[:3] if s == 200 else '5xx')
    res = openloop(one, 10, 24, workers=50)
    st = stats(admin, 'outlier_detection'); st.update(stats(admin, 'lb_healthy_panic')); e.stop()
    for h in hs: h.stop()
    buckets = collections.defaultdict(lambda: collections.Counter())
    for ts, (s, who) in res: buckets[int(ts // 3)][s] += 1
    return buckets, st, len(res)
for label, bads, mp in (('(a)h3 坏,max_ejection_percent 50', [2], 50), ('(b)h2、h3 都坏,max_ejection_percent 100', [1, 2], 100)):
    b, st, n = timeline(bads, mp, label); rows = []
    for k in sorted(b): c = b[k]; tot = sum(c.values()); rows.append((f'{k * 3}~{k * 3 + 3} s', tot, c.get(200, 0), c.get(500, 0), f'{c.get(500, 0) / tot:.0%}' if tot else '-'))
    print(f'  {label}:')
    table(rows, ['时间段', '请求数', '200', '500', '500 的比例'])
    print(f'    Envoy 的异常点检测统计:ejections_enforced_total = {st.get("cluster.back.outlier_detection.ejections_enforced_total", 0)},ejections_active(结束时)= {st.get("cluster.back.outlier_detection.ejections_active", 0)},ejections_consecutive_5xx = {st.get("cluster.back.outlier_detection.ejections_consecutive_5xx", 0)};lb_healthy_panic(进入 panic 模式后被选主机的请求数)= {st.get("cluster.back.lb_healthy_panic", 0)}')
print('  (a)刚开始 h3 收到约三分之一的请求并且全部失败,连续 3 次 5xx 之后 h3 被摘除,失败消失;6 s 的摘除时间到了之后 h3 被放回来,又收到请求、失败,再被摘除;这一次摘除之后要到约 18 s 才再有失败,比 6 s 的 base_ejection_time 长得多(摘除时间随摘除次数增加是我对文档的了解,表里的先后是实测)。(b)两个坏主机被摘除之后只剩 1 个健康主机,健康比例低于默认的 panic 阈值,按 lb_healthy_panic 的计数看 Envoy 进入了 panic 模式——忽略摘除状态,把请求分给所有主机,坏主机重新收到流量,失败的比例和没有异常点检测时差不多(约三分之二)')
print('ERRORS', dict(ERRORS))
