import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v59'); reset()
print('多机房:就近路由与跨机房容灾。把两个机房模拟成同一台机器上的两组后端(dc1 四个、dc2 四个;“跨机房”的代价用 dc2 后端额外的响应延迟来模拟,不是真的网络),看 Envoy 1.39.3 的优先级(priority)故障转移——dc1 为优先级 0、dc2 为优先级 1,overprovisioning factor 决定什么时候开始把流量溢出到 dc2;对照 nginx 1.31.6 的 backup 服务器')
def backend(name, delay=0.0):
    def app(h):
        if h.path.startswith('/hc'): h.reply(200, b'ok'); return
        if delay: time.sleep(delay)
        h.reply(200, name.encode())
    return Svc(app, name)
def envoy_yaml(p0, p1, factor=140, hc=True, outlier=False, one_priority=False, admin=0, idle=True):
    def eps(ports, prio, zone):
        return f'''
      - priority: {prio}
        locality: {{zone: {zone}}}
        lb_endpoints:''' + ''.join(f'''
        - endpoint: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {p}}}}}}}''' for p in ports)
    if one_priority: ends = f'''
      - locality: {{zone: all}}
        lb_endpoints:''' + ''.join(f'''
        - endpoint: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {p}}}}}}}''' for p in list(p0) + list(p1))
    else: ends = eps(p0, 0, 'dc1') + (eps(p1, 1, 'dc2') if p1 else '')
    hcs = '''
    health_checks:
    - {timeout: 0.5s, interval: 0.5s, ''' + ('no_traffic_interval: 0.5s, ' if idle else '') + '''unhealthy_threshold: 2, healthy_threshold: 1, http_health_check: {path: /hc}}''' if hc else ''
    od = '''
    outlier_detection: {consecutive_5xx: 3, consecutive_gateway_failure: 3, consecutive_local_origin_failure: 3, split_external_local_origin_errors: true, interval: 0.5s, base_ejection_time: 60s, max_ejection_percent: 100}''' if outlier else ''
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
                route: {{cluster: web}}
  clusters:
  - name: web
    type: STATIC
    connect_timeout: 1s{hcs}{od}
    load_assignment:
      cluster_name: web
      policy: {{overprovisioning_factor: {factor}}}
      endpoints:{ends}
'''
class Lab:
    def __init__(self, tag, factor=140, hc=True, outlier=False, one_priority=False, d0=0.0, d1=0.0, idle=True):
        self.b0 = [backend(f'p0-{i}', d0) for i in range(4)]; self.b1 = [backend(f'p1-{i}', d1) for i in range(4)]; self.admin = free_port()
        self.env = Envoy(tag, envoy_yaml([b.port for b in self.b0], [b.port for b in self.b1], factor, hc, outlier, one_priority, self.admin, idle)).start()
    def health(self):
        s, d, _ = rpc(self.admin, '/clusters', 3.0); out = {}
        for line in d.decode().splitlines():
            if line.startswith('web::127.0.0.1:') and '::health_flags::' in line:
                out[int(line.split('::')[1].split(':')[1])] = line.split('::health_flags::')[1].strip()
        return out
    def wait_healthy(self, ports_ok, timeout=15.0):
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < timeout:
            h = self.health()
            if all(h.get(p) == 'healthy' for p in ports_ok) and all(h.get(p) != 'healthy' for p in h if p not in ports_ok): return time.perf_counter() - t0
            time.sleep(0.1)
        return None
    def stop(self):
        self.env.stop()
        for b in self.b0 + self.b1:
            try: b.stop()
            except Exception: pass
def share(lab, n=1500):
    c = collections.Counter(); 
    for _ in range(n):
        s, d, dt = rpc(lab.env.port, '/x', 5.0); c[d.decode()[:2] if s == 200 else f'err{s}'] += 1
    return c

# ============ 一 ============
print('== 一:优先级与 overprovisioning factor。dc1(优先级 0)四个后端、dc2(优先级 1)四个后端,Envoy 做主动健康检查(0.5 s 一次,连续 2 次失败算不健康)。依次把 dc1 的后端一个个停掉(0、1、2、3、4 个),每次等 Envoy 把它们标成不健康后,顺序发 1500 个请求,统计落在 dc1、dc2 的比例。overprovisioning factor 分别用默认的 140 和 100(1.0 倍)')
rows = []; envoy_k2 = None
for factor in (140, 100):
    lab = Lab(f'v59a{factor}', factor=factor); assert lab.wait_healthy([b.port for b in lab.b0 + lab.b1]) is not None
    for k in range(5):
        if k:
            lab.b0[k - 1].stop(); ok = lab.wait_healthy([b.port for b in lab.b0[k:] + lab.b1])
        c = share(lab); tot = sum(c.values()); rows.append((factor, k, f'{(4 - k) * 25}%', f'{c["p0"] / tot:.1%}', f'{c["p1"] / tot:.1%}', sum(v for kk, v in c.items() if kk.startswith('err'))))
        if factor == 140 and k == 2: envoy_k2 = (c['p0'] / tot, c['p1'] / tot)
    lab.stop()
table(rows, ['overprovisioning factor', 'dc1 停掉的后端数', 'dc1 健康比例', '落在 dc1 的请求', '落在 dc2 的请求', '错误数'])
print('  dc1 的健康比例乘以 factor/100(封顶 100%)就是留在 dc1 的比例,剩下的溢出到 dc2:factor 140 时 dc1 还有 75% 健康仍然全部留在 dc1,降到 50% 才开始溢出;factor 100 时只要少了一个后端就开始溢出')

# ============ 二 ============
print('== 二:dc1 整体挂掉的切换。dc1 的四个后端同时停掉,看 Envoy 多久把流量切到 dc2、期间有多少请求失败。以 100 个/秒的开环负载跑 8 s,在第 2.5 s 同时停掉 dc1 的四个后端。三种配置:(a)主动健康检查(0.5 s,2 次失败);(b)没有主动检查,只有被动的异常点检测(连续 3 次本地来源失败就摘除,检测间隔 0.5 s);(c)两者都没有')
rows = []
for name, kw in (('(a)主动健康检查', dict(hc=True)), ('(b)只有被动异常点检测', dict(hc=False, outlier=True)), ('(c)两者都没有', dict(hc=False))):
    lab = Lab('v59b' + name[1], **kw); time.sleep(1.5)
    killed = {}
    def killer():
        time.sleep(2.5); killed['t'] = time.perf_counter()
        for b in lab.b0: b.stop()
    T0 = time.perf_counter(); threading.Thread(target=killer, daemon=True).start()
    def one(i):
        s, d, dt = rpc(lab.env.port, '/x', 3.0, keepalive=False); return (s, d.decode()[:2] if s == 200 else '')
    res = openloop(one, 100, 8, workers=100); tk = killed['t'] - T0
    res.sort(); errs = [(ts, r) for ts, r in res if r[0] != 200]; p1 = [ts for ts, r in res if r[0] == 200 and r[1] == 'p1' and ts > tk]
    after_ok = [ts for ts, r in res if r[0] == 200 and ts > tk]
    rows.append((name, len(res), len(errs), f'{min(t for t, _ in errs) - tk:.2f}~{max(t for t, _ in errs) - tk:.2f}' if errs else '-', f'{p1[0] - tk:.2f}' if p1 else '没有切过去'))
    lab.stop()
table(rows, ['配置', '请求总数', '失败的请求数', '失败的请求相对停机时刻的范围(s)', '停机后第一个由 dc2 成功响应的请求(s)'])
print('  主动健康检查把 dc1 摘掉要等连续两次检查失败;被动检测靠真实请求失败来发现,摘除后同样切到 dc2;两者都没有时,Envoy 一直认为 dc1 健康,所有请求失败')
lab = Lab('v59bi', idle=False); lab.wait_healthy([b.port for b in lab.b0 + lab.b1]); time.sleep(1.0)
for r_ in range(20): rpc(lab.env.port, '/x', 3.0)
lab.b0[0].stop(); t0 = time.perf_counter(); t_det = None
while time.perf_counter() - t0 < 90:
    if lab.health().get(lab.b0[0].port) != 'healthy': t_det = time.perf_counter() - t0; break
    time.sleep(0.2)
print(f'  另一个观察:健康检查 interval 设 0.5 s,但 no_traffic_interval 保持默认值,先发了 20 个请求再停掉一个 dc1 的后端,Envoy 把它标成不健康用了 {t_det:.1f} s(最多等 90 s;配置里写 no_traffic_interval: 0.5s 之后,前面的实验里是 1 s 左右)' if t_det else '  另一个观察:健康检查 interval 设 0.5 s,但 no_traffic_interval 保持默认值,停掉一个 dc1 的后端,90 s 内 Envoy 没有把它标成不健康')
lab.stop()

# ============ 三 ============
print('== 三:就近的好处。dc1 的后端响应延迟 2 ms,dc2 的后端 40 ms(模拟跨机房的往返)。(a)dc1 优先(优先级 0 / 1);(b)八个后端放在同一优先级里轮询(不区分机房)。顺序发 1000 个请求,看延迟分布')
rows = []
for name, kw in (('(a)dc1 优先', dict()), ('(b)不区分机房轮询', dict(one_priority=True))):
    lab = Lab('v59c' + name[1], d0=0.002, d1=0.040, **kw); lab.wait_healthy([b.port for b in lab.b0 + lab.b1])
    lat = []; c = collections.Counter()
    for _ in range(1000):
        s, d, dt = rpc(lab.env.port, '/x', 5.0); lat.append(dt * 1000); c[d.decode()[:2] if s == 200 else 'err'] += 1
    rows.append((name, f'{pct(lat, 50):.1f}', f'{pct(lat, 99):.1f}', f'{c["p0"] / 10:.1f}% / {c["p1"] / 10:.1f}%')); lab.stop()
table(rows, ['配置', '延迟 p50(ms)', '延迟 p99(ms)', '落在 dc1 / dc2 的请求'])

# ============ 四 ============
print('== 四:nginx 的 backup 与 Envoy 的优先级在部分故障时的区别。nginx upstream 里 dc1 的四个后端是普通 server,dc2 的四个是 backup(默认的被动健康检查:max_fails=1,fail_timeout=10s)。(a)停掉 dc1 的两个后端,先发 50 个请求让 nginx 发现,再发 1500 个请求统计落点;(b)再停掉 dc1 剩下的两个,统计之后的 1500 个请求。Envoy 一栏用第一节里 factor 140、dc1 停掉两个后端的数字')
bs0 = [backend(f'p0-{i}') for i in range(4)]; bs1 = [backend(f'p1-{i}') for i in range(4)]
srvs = ''.join(f'    server 127.0.0.1:{b.port} max_fails=1 fail_timeout=10s;\n' for b in bs0) + ''.join(f'    server 127.0.0.1:{b.port} backup;\n' for b in bs1)
ng = Nginx('v59d', f'upstream u {{\n{srvs}}}\nserver {{ listen {{port}}; location / {{ proxy_pass http://u; }} }}').start()
def share_ng(n=1500):
    c = collections.Counter()
    for _ in range(n):
        s, d, dt = rpc(ng.port, '/x', 5.0); c[d.decode() if s == 200 else f'err{s}'] += 1
    return c
bs0[0].stop(); bs0[1].stop(); share_ng(50); c = share_ng(); tot = sum(c.values())
rows = [('nginx(a)dc1 停掉两个', f'{sum(v for k, v in c.items() if k.startswith("p0")) / tot:.1%}', f'{sum(v for k, v in c.items() if k.startswith("p1")) / tot:.1%}', sum(v for k, v in c.items() if k.startswith('err')), ' '.join(f'{k}:{v}' for k, v in sorted(c.items())))]
rows.append(('Envoy(factor 140)dc1 停掉两个', f'{envoy_k2[0]:.1%}', f'{envoy_k2[1]:.1%}', 0, '(见第一节)'))
bs0[2].stop(); bs0[3].stop(); share_ng(50); c = share_ng(); tot = sum(c.values())
rows.append(('nginx(b)dc1 全停', f'{sum(v for k, v in c.items() if k.startswith("p0")) / tot:.1%}', f'{sum(v for k, v in c.items() if k.startswith("p1")) / tot:.1%}', sum(v for k, v in c.items() if k.startswith('err')), ' '.join(f'{k}:{v}' for k, v in sorted(c.items()))))
table(rows, ['场景', '落在 dc1', '落在 dc2', '错误数', '各后端的请求数'])
print('  nginx 的 backup 只在所有普通 server 都不可用时才接流量:dc1 还剩一半时,剩下的两个后端承担全部流量;Envoy 的优先级按健康比例逐步溢出')
ng.stop()
for b in bs0 + bs1:
    try: b.stop()
    except Exception: pass
print('ERRORS', dict(ERRORS))
