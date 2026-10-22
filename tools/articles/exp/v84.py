import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import xdsl as ADS
tee('v84'); reset()
print('Envoy 的 xDS:LDS、RDS、CDS、EDS。Envoy 1.39.3 作为数据平面,控制平面是我用 Python(grpcio + xds-protos)写的最小 ADS 服务(只实现 State-of-the-World 的 StreamAggregatedResources,约 70 行),资源用与 Envoy YAML 同构的 JSON 构造。看(一)Envoy 启动后向控制平面请求资源的顺序;(二)控制平面推一个 Envoy 不接受的配置(NACK)后的行为;(三)推送一次更新到流量真正切换的延迟,以及新集群没有端点时的窗口;(四)控制平面断开之后数据平面的表现')
def backend(name):
    return Svc(lambda h: h.reply(200, name.encode()), name)
A, B = backend('A'), backend('B')
LP = free_port(); XP = free_port(); AP = free_port()
def listener(route='r0', filters=None, port=None):
    return {'name': 'l0', 'address': {'socket_address': {'address': '127.0.0.1', 'port_value': port or LP}}, 'filter_chains': [{'filters': [{'name': 'envoy.filters.network.http_connection_manager', 'typed_config': {'@type': 'type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager', 'stat_prefix': 'ing', 'rds': {'route_config_name': route, 'config_source': {'ads': {}, 'resource_api_version': 'V3'}}, 'http_filters': filters or [{'name': 'envoy.filters.http.router', 'typed_config': {'@type': 'type.googleapis.com/envoy.extensions.filters.http.router.v3.Router'}}]}}]}]}
def route(name, cluster): return {'name': name, 'virtual_hosts': [{'name': 'v', 'domains': ['*'], 'routes': [{'match': {'prefix': '/'}, 'route': {'cluster': cluster}}]}]}
def cluster(name): return {'name': name, 'type': 'EDS', 'connect_timeout': '1s', 'lb_policy': 'ROUND_ROBIN', 'eds_cluster_config': {'eds_config': {'ads': {}, 'resource_api_version': 'V3'}}}
def eds(name, ports): return {'cluster_name': name, 'endpoints': [{'lb_endpoints': [{'endpoint': {'address': {'socket_address': {'address': '127.0.0.1', 'port_value': p}}}} for p in ports]}]}
ads = ADS.Ads()
ads.set(ADS.LDS, {'l0': listener()}); ads.set(ADS.RDS, {'r0': route('r0', 'c_a')}); ads.set(ADS.CDS, {'c_a': cluster('c_a')}); ads.set(ADS.EDS, {'c_a': eds('c_a', [A.port])})
ads.serve(AP)
ADMIN = free_port()
boot = f"""node: {{id: n1, cluster: c1}}
admin: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {ADMIN}}}}}}}
dynamic_resources:
  ads_config: {{api_type: GRPC, transport_api_version: V3, grpc_services: [{{envoy_grpc: {{cluster_name: xds}}}}]}}
  cds_config: {{ads: {{}}, resource_api_version: V3}}
  lds_config: {{ads: {{}}, resource_api_version: V3}}
static_resources:
  clusters:
  - name: xds
    type: STATIC
    connect_timeout: 1s
    typed_extension_protocol_options:
      envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
        "@type": type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
        explicit_http_config: {{http2_protocol_options: {{}}}}
    load_assignment:
      cluster_name: xds
      endpoints:
      - lb_endpoints:
        - endpoint: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {AP}}}}}}}
"""
env = Envoy('v84', boot, port=XP)
env.p = subprocess.Popen(['envoy', '-c', str(env.d / 'envoy.yaml'), '--concurrency', '1', '--disable-hot-restart', '-l', 'warning', '--base-id', str(random.randrange(1, 10**6))], stdout=open(env.d / 'out.log', 'w'), stderr=subprocess.STDOUT); txl._nodes.append(env)
def probe(timeout=1.0):
    s, d, dt = rpc(LP, '/', timeout, keepalive=False); return (d.decode() if s == 200 else f'HTTP {s}'), dt
t_start = time.time(); ok = False
while time.time() - t_start < 20:
    r, _ = probe(0.5)
    if r == 'A': ok = True; break
    time.sleep(0.05)
t_ready = time.time() - t_start
assert ok, env.d / 'out.log'
ERRORS.clear()          # 上面等监听器就绪时的连接被拒绝不算实验里的错误

# ============ 一 ============
print('== 一:启动时 Envoy 向控制平面要了什么、什么顺序。Envoy 起来之后通过一条 ADS 流依次请求;表里是控制平面收到和发出的消息(t 是控制平面的时钟,从 ADS 服务器创建算起;“请求”是 Envoy 发来的 DiscoveryRequest,“发出”是控制平面的 DiscoveryResponse)。控制平面里预先放好了 1 个监听器 l0、1 条路由配置 r0、1 个集群 c_a、c_a 的 1 个端点')
rows = []
for e in ads.log[:20]:
    if e['kind'] in ('request', 'send'): rows.append((f'{e["t"]:.2f}', '请求' if e['kind'] == 'request' else '发出', e['type'], e['version'], ','.join(e['names']) or '(空)', e['nonce']))
    elif e['kind'] == 'stream_open': rows.append((f'{e["t"]:.2f}', '流打开', '', '', '', ''))
table(rows, ['t(s)', '方向', '类型', 'version_info', '资源名', 'nonce'])
print(f'  Envoy 起来到第一个请求能成功用了 {t_ready:.2f} s。表里各资源类型第一次被请求的先后是 CDS、EDS、LDS、RDS:最先是 CDS(不带资源名,订阅全部集群);收到 CDS 之后请求其中集群的 EDS(带上集群名 c_a);再请求 LDS(订阅全部监听器);收到 LDS 之后请求监听器引用的 RDS(带上路由配置名 r0)。先集群、后监听器、最后路由,避免监听器已经开始接流量而它引用的集群还没准备好(这个顺序的理由是我对 xDS 文档的了解,表里的先后是实测)。每个资源类型收到之后 Envoy 回一条带着刚收到的 version_info 和 nonce 的请求,就是 ACK')

# ============ 二 ============
print('== 二:NACK。控制平面推一个 Envoy 不接受的监听器(http_filters 里用了一个不存在的过滤器名)。看 Envoy 回给控制平面的消息(version_info、error_detail),以及这时数据平面的流量;再推一个有效的更新,看 Envoy 的 ACK')
n0 = len(ads.log); ads.set(ADS.LDS, {'l0': listener(filters=[{'name': 'envoy.filters.http.nonexistent', 'typed_config': {'@type': 'type.googleapis.com/envoy.extensions.filters.http.router.v3.Router'}}, {'name': 'envoy.filters.http.router', 'typed_config': {'@type': 'type.googleapis.com/envoy.extensions.filters.http.router.v3.Router'}}])}); time.sleep(1.5)
resp_during = [probe()[0] for _ in range(10)]
ads.set(ADS.LDS, {'l0': listener()}); time.sleep(1.5); resp_after = [probe()[0] for _ in range(5)]
rows = []
for e in ads.log[n0:]:
    if e['type' if 'type' in e else 'kind'] == 'LDS' or e['kind'] == 'nack':
        if e.get('type') == 'LDS': rows.append((f'{e["t"]:.2f}', {'send': '发出', 'request': '请求', 'nack': 'NACK'}.get(e['kind'], e['kind']), e['version'], (e.get('error') or ','.join(e.get('names', []))) or '(空)'))
table(rows, ['t(s)', '方向', 'version_info', '内容 / error_detail'])
print(f'  推送坏配置期间(NACK 之后)通过 Envoy 的 10 个请求:{collections.Counter(resp_during)};推送有效更新之后的 5 个请求:{collections.Counter(resp_after)}。坏配置被 NACK(error_detail 里写着原因),version_info 仍然是上一个被接受的版本,Envoy 继续用旧监听器,流量不受影响;控制平面推了有效版本之后 Envoy 回 ACK(version_info 变成新版本)')

# ============ 三 ============
print('== 三:一次推送到流量切换的延迟。(a)EDS 更新:c_a 的端点从 [A] 换成 [B],测控制平面调用 set 到客户端第一次收到 B 的响应;(b)RDS 更新:路由 r0 从 c_a 改到 c_b(c_b 的 EDS 已经提前推好),同样测到第一次收到 B;各 15 次,客户端每 2 ms 发一个请求。(c)新集群没有端点的窗口:同时推 CDS(新集群 c_c)和 RDS(路由改到 c_c),但 c_c 的 EDS 故意延迟 1.0 s 再推,看这期间的请求结果')
def first_switch(target, pre_fn, timeout=5.0):
    t0 = time.perf_counter(); pre_fn()
    while time.perf_counter() - t0 < timeout:
        r, _ = probe(1.0)
        if r == target: return (time.perf_counter() - t0) * 1000
        time.sleep(0.002)
    return float('nan')
ads.set(ADS.CDS, {'c_a': cluster('c_a'), 'c_b': cluster('c_b')}); ads.set(ADS.EDS, {'c_a': eds('c_a', [A.port]), 'c_b': eds('c_b', [B.port])}); time.sleep(1.0)
lat_eds = []
for i in range(15):
    lat_eds.append(first_switch('B', lambda: ads.set(ADS.EDS, {'c_a': eds('c_a', [B.port]), 'c_b': eds('c_b', [B.port])})))
    first_switch('A', lambda: ads.set(ADS.EDS, {'c_a': eds('c_a', [A.port]), 'c_b': eds('c_b', [B.port])}))
lat_rds = []
for i in range(15):
    lat_rds.append(first_switch('B', lambda: ads.set(ADS.RDS, {'r0': route('r0', 'c_b')})))
    first_switch('A', lambda: ads.set(ADS.RDS, {'r0': route('r0', 'c_a')}))
ads.set(ADS.CDS, {'c_a': cluster('c_a'), 'c_b': cluster('c_b'), 'c_c': cluster('c_c')}); time.sleep(0.5)
t0 = time.perf_counter(); ads.set(ADS.RDS, {'r0': route('r0', 'c_c')}); timeline = []; pushed = [False]
def late_eds(): time.sleep(1.0); pushed[0] = time.perf_counter(); ads.set(ADS.EDS, {'c_a': eds('c_a', [A.port]), 'c_b': eds('c_b', [B.port]), 'c_c': eds('c_c', [B.port])})
th = threading.Thread(target=late_eds); th.start()
while time.perf_counter() - t0 < 2.5:
    r, _ = probe(1.0); timeline.append(((time.perf_counter() - t0) * 1000, r)); time.sleep(0.01)
th.join(); first_ok = next((t for t, r in timeline if r == 'B'), None); codes = collections.Counter(r for t, r in timeline if t < 1000)
table([('(a)EDS 更新', f'{statistics.median(lat_eds):.1f}', f'{min(lat_eds):.1f}', f'{max(lat_eds):.1f}'), ('(b)RDS 更新(换路由)', f'{statistics.median(lat_rds):.1f}', f'{min(lat_rds):.1f}', f'{max(lat_rds):.1f}')], ['更新类型', '到流量切换 中位数(ms)', '最小(ms)', '最大(ms)'])
print(f'  (c)新集群没有端点:路由改到 c_c 之后的前 1 s(EDS 还没推)里的请求结果 {dict(codes)};EDS 在第 {(pushed[0] - t0) * 1000:.0f} ms 推出,第一次收到 B 的响应在 {first_ok:.0f} ms。路由指向了一个还没有端点的集群,在端点到位之前请求得不到成功的响应')

# ============ 四 ============
print('== 四:控制平面断开。关掉控制平面(gRPC 服务器停掉),让数据平面独自运行 6 s,期间每 50 ms 发一个请求;再在原来的端口重启控制平面(资源不变),看 Envoy 多久重新连上、重新发了哪些请求,以及重新连上之后推送更新(把 c_a 的端点换成 B)能不能生效')
log_n = len(ads.log); ads.stop(); t_down = time.time(); res = []; t0 = time.perf_counter()
while time.perf_counter() - t0 < 6.0: res.append(probe(0.5)[0]); time.sleep(0.05)
ads2 = ADS.Ads(); ads2.res = ads.res; ads2.ver = ads.ver; ads2.serve(AP); t_up = time.time(); time.sleep(0.01)
t0 = time.perf_counter(); reconn = None
while time.perf_counter() - t0 < 40.0:
    if any(e['kind'] == 'stream_open' for e in ads2.log): reconn = time.time() - t_up; break
    time.sleep(0.1)
time.sleep(1.5); reqs = [(e['type'], e['version'], ','.join(e['names']) or '(空)') for e in ads2.log if e['kind'] == 'request']
ads2.set(ADS.EDS, {'c_a': eds('c_a', [B.port]), 'c_b': eds('c_b', [B.port]), 'c_c': eds('c_c', [B.port])}); ads2.set(ADS.RDS, {'r0': route('r0', 'c_a')}); time.sleep(1.0)
after = [probe()[0] for _ in range(5)]
print(f'  控制平面停了 6 s 期间的 {len(res)} 个请求:{collections.Counter(res)}(流量不受控制平面断开的影响,Envoy 继续用最后一份配置);控制平面重启之后 Envoy 重新建立 ADS 流用了 {reconn:.1f} s' if reconn is not None else '  控制平面重启之后 40 s 内 Envoy 没有重新连上')
print(f'  重新连上之后 Envoy 重新发来的请求:{reqs[:8]};重连后推送更新(c_a 的端点换成 B)之后的 5 个请求:{collections.Counter(after)}')
print('  数据平面与控制平面解耦:控制平面不可用时已经下发的配置照常工作,只是无法更新;Envoy 在控制平面恢复之后 {reconn:.1f} s 重新连上(更长时间的断开下重连间隔会不会变长,我没有测),重连后重新订阅并拿到当前版本'.replace('{reconn:.1f}', f'{reconn:.1f}') if reconn is not None else '')
ads2.stop(); env.stop(); A.stop(); B.stop()
print('ERRORS', dict(ERRORS))
