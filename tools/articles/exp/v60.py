import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v60'); reset()
print('预热:新实例的权重逐渐提高。新启动的实例往往很慢(JIT、缓存、连接池都是冷的),一加入就按满额权重接流量,会让一部分请求变慢甚至失败。用 Envoy 1.39.3 的 slow start(round_robin_lb_config.slow_start_config)演示权重怎么随时间升高,新实例通过文件型 EDS 在运行中加入;后端是本进程里的 Python 服务:3 个一直是热的(每个请求 5 ms),新实例在它启动后的前 8 s 每个请求 120 ms(模拟冷启动),之后 5 ms。再用我写的客户端侧线性预热权重(Dubbo 风格的公式,不是 Dubbo)对照')
COLD_S, COLD_MS, WARM_MS = 8.0, 120, 5
class Cold:
    """冷启动的后端:启动后 COLD_S 秒内每个请求 COLD_MS 毫秒,之后 WARM_MS 毫秒。"""
    def __init__(self, port=None):
        self.t0 = time.time()
        def app(h):
            if h.path.startswith('/hc'): h.reply(200, b'ok'); return
            time.sleep((COLD_MS if time.time() - self.t0 < COLD_S else WARM_MS) / 1000); h.reply(200, b'new')
        self.svc = Svc(app, 'new', port=port); self.port = self.svc.port
    def stop(self): self.svc.stop()
def warm_backend(name):
    def app(h):
        if h.path.startswith('/hc'): h.reply(200, b'ok'); return
        time.sleep(WARM_MS / 1000); h.reply(200, name.encode())
    return Svc(app, name)
def eds_yaml(ports):
    return 'version_info: "%s"\nresources:\n- "@type": type.googleapis.com/envoy.config.endpoint.v3.ClusterLoadAssignment\n  cluster_name: web\n  endpoints:\n  - lb_endpoints:\n' % time.time() + ''.join(f'    - endpoint: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {p}}}}}}}\n' for p in ports)
class Lab:
    def __init__(self, tag, window=None, aggr=1.0, hc=False):
        self.warm = [warm_backend(f'w{i}') for i in range(3)]; self.new = None; self.d = txl.tdir(tag + 'eds'); self.eds = self.d / 'eds.yaml'; self.admin = free_port()
        self.write([b.port for b in self.warm])
        ss = f'''
    round_robin_lb_config:
      slow_start_config:
        slow_start_window: {window}s
        aggression: {{default_value: {aggr}, runtime_key: aggr}}
        min_weight_percent: {{value: 10}}''' if window else ''
        hcs = '''
    health_checks:
    - {timeout: 0.5s, interval: 0.5s, no_traffic_interval: 0.5s, unhealthy_threshold: 2, healthy_threshold: 1, http_health_check: {path: /hc}}''' if hc else ''
        y = f'''node: {{id: n1, cluster: c1}}
admin: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {self.admin}}}}}}}
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
                route: {{cluster: web}}
  clusters:
  - name: web
    type: EDS
    connect_timeout: 1s
    lb_policy: ROUND_ROBIN{ss}{hcs}
    eds_cluster_config:
      eds_config:
        resource_api_version: V3
        path_config_source: {{path: {self.eds}}}
'''
        self.env = Envoy(tag, y).start(); time.sleep(1.5)
    def write(self, ports):
        t = self.d / 'eds.tmp'; t.write_text(eds_yaml(ports)); os.replace(t, self.eds)
    def add_new(self):
        self.new = Cold(); self.write([b.port for b in self.warm] + [self.new.port]); return self.new
    def stop(self):
        self.env.stop()
        for b in self.warm: b.stop()
        if self.new: self.new.stop()
def load(port_fn, rate=100, dur=22):
    def one(i):
        port = port_fn(); s, d, dt = rpc(port, '/x', 5.0, keepalive=False); return (s, d.decode() if s == 200 else '', dt)
    return sorted(openloop(one, rate, dur, workers=150))
def analyze(res, t_add, span=16):
    sel = [(ts, r) for ts, r in res if t_add <= ts < t_add + span]; ok = [(ts, r) for ts, r in sel if r[0] == 200]
    lat = [r[2] * 1000 for ts, r in ok]; sh = []
    for k in range(span):
        w = [r for ts, r in ok if t_add + k <= ts < t_add + k + 1]; sh.append(sum(1 for r in w if r[1] == 'new') / max(1, len(w)))
    return dict(n=len(sel), errs=len(sel) - len(ok), new=sum(1 for ts, r in ok if r[1] == 'new'), slow=sum(1 for x in lat if x > 50), p50=pct(lat, 50), p99=pct(lat, 99), share=sh)

# ============ 一 ============
print('== 一:新实例加入之后流量怎么爬升。3 个热实例已经在服务,第 3 s 把第 4 个(冷启动)实例通过 EDS 加进集群。100 个/秒的开环负载跑 22 s。三种配置:(a)没有 slow start;(b)slow_start_window 10 s、aggression 1.0、min_weight_percent 10;(c)slow_start_window 20 s。统计新实例加入之后 16 s 内落在新实例的请求比例(每秒一格)')
cfgs = [('(a)没有 slow start', dict()), ('(b)window 10 s', dict(window=10)), ('(c)window 20 s', dict(window=20))]
AN = {}
for name, kw in cfgs:
    lab = Lab('v60a' + name[1], **kw); info = {}
    def adder():
        time.sleep(3.0); info['t'] = time.perf_counter(); lab.add_new()
    T0 = time.perf_counter(); threading.Thread(target=adder, daemon=True).start()
    res = load(lambda: lab.env.port); AN[name] = analyze(res, info['t'] - T0); lab.stop()
secs = [0, 2, 4, 6, 8, 10, 12, 15]
table([(n, *[f'{AN[n]["share"][k] * 100:.0f}%' for k in secs]) for n, _ in cfgs], ['配置'] + [f'加入后第 {k} 秒' for k in secs])
print('  每个格子是那一秒里落在新实例的请求占比;没有 slow start 时新实例一加入就接近 1/4(4 个实例轮询);有 slow start 时从很低的比例按窗口爬升,窗口走完后回到 1/4')

# ============ 二 ============
print('== 二:冷启动的代价。同一组实验里,新实例在启动后的前 8 s 每个请求要 120 ms,之后 5 ms,另外 3 个热实例一直是 5 ms。统计新实例加入之后 16 s 内的所有请求:总数、落在新实例上的数量、慢请求(>50 ms)的数量、延迟 p50 和 p99')
table([(n, AN[n]['n'], AN[n]['new'], AN[n]['slow'], f'{AN[n]["p50"]:.1f}', f'{AN[n]["p99"]:.1f}', AN[n]['errs']) for n, _ in cfgs], ['配置', '加入后 16 s 的请求数', '落在新实例上', '慢请求(>50 ms)', '延迟 p50(ms)', '延迟 p99(ms)', '失败'])
print('  慢请求几乎都是落在冷实例上的请求;slow start 减少的是冷的那 8 s 里落在新实例上的请求数。预热窗口比冷启动时间长得多时,冷实例接到的请求更少,但新实例也要更久才能分担满额的流量')

# ============ 三 ============
print('== 三:客户端侧的线性预热权重(我写的,Dubbo 文档里描述的做法:权重 = max(1, min(满额, 运行时间 ÷ 预热时间 × 满额)),满额 100)。客户端直接按权重随机选后端,不经过 Envoy。预热时间 10 s 和 20 s,其余同第一、二节')
def client_side(window):
    warm = [warm_backend(f'w{i}') for i in range(3)]; st = {}; rnd = random.Random(7)
    def adder():
        time.sleep(3.0); st['t'] = time.perf_counter(); st['new'] = Cold()
    T0 = time.perf_counter(); threading.Thread(target=adder, daemon=True).start()
    def pick():
        new = st.get('new')
        if new is None: return rnd.choice(warm).port
        up = time.time() - new.t0; wnew = max(1, min(100, int(up / window * 100))); r = rnd.random() * (300 + wnew)
        return new.port if r >= 300 else warm[int(r // 100)].port
    res = load(pick); a = analyze(res, st['t'] - T0)
    for b in warm: b.stop()
    st['new'].stop(); return a
rows = []
for window in (10, 20):
    a = client_side(window); AN[f'client{window}'] = a
rows = [(f'客户端线性预热 {w} s', AN[f'client{w}']['n'], AN[f'client{w}']['new'], AN[f'client{w}']['slow'], f'{AN[f"client{w}"]["p50"]:.1f}', f'{AN[f"client{w}"]["p99"]:.1f}', *[f'{AN[f"client{w}"]["share"][k] * 100:.0f}%' for k in (0, 4, 8, 12, 15)]) for w in (10, 20)]
table(rows, ['配置', '请求数', '落在新实例上', '慢请求(>50 ms)', 'p50(ms)', 'p99(ms)', '第 0 秒', '第 4 秒', '第 8 秒', '第 12 秒', '第 15 秒'])
print('  线性预热从权重 1 起步,所以起初几乎不分流量;Envoy 的 slow start 用 min_weight_percent 做下限,起步比例更高')

# ============ 四 ============
print('== 四:实例重启(或健康检查反复)之后是否重新预热。cluster 开主动健康检查(0.5 s)。新实例已经加入并热了之后:第 6 s 停掉它,第 10 s 在同一个端口重新启动(又是冷的,前 8 s 每个请求 120 ms),看它重新被检查通过之后落在它上面的流量比例。(a)没有 slow start;(b)slow_start_window 10 s。负载 100 个/秒,共 40 s')
rows = []
for name, kw in (('(a)没有 slow start', dict()), ('(b)window 10 s', dict(window=10))):
    lab = Lab('v60d' + name[1], hc=True, **kw); lab.add_new(); time.sleep(12.0)       # 先让它热起来(8 s 冷期已过),并走完预热窗口
    st = {}
    def restarter():
        time.sleep(6.0); port = lab.new.port; lab.new.stop(); time.sleep(4.0); st['t'] = time.perf_counter(); lab.new = Cold(port=port)
    T0 = time.perf_counter(); threading.Thread(target=restarter, daemon=True).start()
    res = load(lambda: lab.env.port, 100, 30); a = analyze(res, st['t'] - T0, 16); lab.stop()
    AN['re' + name[1]] = a
secs2 = [0, 2, 4, 6, 8, 10, 12, 15]
table([(n, *[f'{AN["re" + n[1]]["share"][k] * 100:.0f}%' for k in secs2]) for n in ('(a)没有 slow start', '(b)window 10 s')], ['配置'] + [f'重启后第 {k} 秒' for k in secs2])
table([(n, AN['re' + n[1]]['n'], AN['re' + n[1]]['new'], AN['re' + n[1]]['errs'], AN['re' + n[1]]['slow'], f'{AN["re" + n[1]]["p99"]:.1f}') for n in ('(a)没有 slow start', '(b)window 10 s')], ['配置', '重启后 16 s 的请求数', '落在重启的实例上', '失败', '慢请求(>50 ms)', 'p99(ms)'])
print('  “重启后第 0 秒”从新进程开始监听同一个端口的时刻算起;健康检查把它重新标成健康很快(上表第 0 秒一格里没有 slow start 的已经接近满额),所以重启之后是否重新预热,看的是 slow start 是否对“重新变健康的实例”再次生效')
print('ERRORS', dict(ERRORS))
