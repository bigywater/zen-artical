import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import psutil, datetime, statistics
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
tee('v92'); reset()
GO = pathlib.Path(__file__).resolve().parent.parent / 'vtmp' / 'v92load' / 'load'
print('Sidecar 的开销。全部在本机回环上(没有容器和 iptables,见第 83 篇),Envoy 1.39.3 用 --concurrency 1,后端是 nginx(静态返回 "ok\\n" 或 100 KB 文件),压测客户端是自己写的 Go 程序(net/http,可调并发、是否 keep-alive,记录每个请求的延迟)。四种路径:A 客户端直连后端;B 客户端 → 一个 Envoy → 后端;C 客户端 → Envoy → Envoy → 后端(两个 sidecar,明文);D 同 C,但两个 Envoy 之间用 mTLS(ECDSA P-256 证书,要求客户端证书)。每个数字取 3 轮的中位数(各路径交替跑),看(一)单个请求的延迟代价;(二)并发下的吞吐和 Envoy 的 CPU;(三)每次新建连接;(四)100 KB 的响应;(五)Envoy 的内存和配置规模的关系')
# ---- 证书 ----
def mkca():
    k_ = ec.generate_private_key(ec.SECP256R1()); n = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'ca')]); now = datetime.datetime.now(datetime.timezone.utc)
    c = (x509.CertificateBuilder().subject_name(n).issuer_name(n).public_key(k_.public_key()).serial_number(1).not_valid_before(now - datetime.timedelta(minutes=5)).not_valid_after(now + datetime.timedelta(days=1))
         .add_extension(x509.BasicConstraints(ca=True, path_length=0), True).add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), True).sign(k_, hashes.SHA256()))
    return k_, c
CAK, CAC = mkca(); LK = ec.generate_private_key(ec.SECP256R1()); now = datetime.datetime.now(datetime.timezone.utc)
LC = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'sidecar')])).issuer_name(CAC.subject).public_key(LK.public_key()).serial_number(2)
      .not_valid_before(now - datetime.timedelta(minutes=1)).not_valid_after(now + datetime.timedelta(hours=2)).add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
      .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]), False).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), False).sign(CAK, hashes.SHA256()))
CA_PEM = CAC.public_bytes(serialization.Encoding.PEM).decode(); L_PEM = LC.public_bytes(serialization.Encoding.PEM).decode(); LK_PEM = LK.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
CTX_COMMON = f'''common_tls_context:
            tls_certificates:
            - certificate_chain: {{inline_string: {json.dumps(L_PEM)}}}
              private_key: {{inline_string: {json.dumps(LK_PEM)}}}
            validation_context: {{trusted_ca: {{inline_string: {json.dumps(CA_PEM)}}}}}'''
def cfg(up_port, listen_tls=False, up_tls=False, n_extra=0):
    ts_down = f'''
      transport_socket:
        name: envoy.transport_sockets.tls
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.DownstreamTlsContext
          require_client_certificate: true
          {CTX_COMMON}''' if listen_tls else ''
    ts_up = f'''
    transport_socket:
      name: envoy.transport_sockets.tls
      typed_config:
        "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext
        sni: localhost
        {CTX_COMMON.replace(chr(10) + "          ", chr(10) + "        ")}''' if up_tls else ''
    routes = ''.join(f'\n              - match: {{prefix: "/svc{i}"}}\n                route: {{cluster: c{i}}}' for i in range(n_extra))
    extra = ''.join(f'''
  - name: c{i}
    type: STATIC
    connect_timeout: 1s
    load_assignment:
      cluster_name: c{i}
      endpoints:
      - lb_endpoints:
        - endpoint: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {up_port}}}}}}}''' for i in range(n_extra))
    return f'''static_resources:
  listeners:
  - name: l
    address: {{socket_address: {{address: 127.0.0.1, port_value: {{port}}}}}}
    filter_chains:
    - {ts_down.strip() if ts_down else ''}
      filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress
          route_config:
            virtual_hosts:
            - name: all
              domains: ["*"]
              routes:{routes}
              - match: {{prefix: "/"}}
                route: {{cluster: up}}
          http_filters:
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
  clusters:
  - name: up
    type: STATIC
    connect_timeout: 1s{ts_up}
    load_assignment:
      cluster_name: up
      endpoints:
      - lb_endpoints:
        - endpoint: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {up_port}}}}}}}{extra}
'''.replace('    - \n      filters:', '    - filters:')
NG = Nginx('v92n', 'server { listen {port}; location / { return 200 "ok\\n"; } location /big { root {d}; } }').start(); (NG.d / 'big').write_bytes(b'x' * 102400)
ES = Envoy('v92s', cfg(NG.port)).start()
E2 = Envoy('v92e2', cfg(NG.port)).start(); E1 = Envoy('v92e1', cfg(E2.port)).start()
E2T = Envoy('v92e2t', cfg(NG.port, listen_tls=True)).start(); E1T = Envoy('v92e1t', cfg(E2T.port, up_tls=True)).start()
PATHS = {'A 直连': (NG.port, []), 'B 一个 Envoy': (ES.port, [ES]), 'C 两个 Envoy(明文)': (E1.port, [E1, E2]), 'D 两个 Envoy(mTLS)': (E1T.port, [E1T, E2T])}
def procs(nodes): return [psutil.Process(n.p.pid) for n in nodes]
def cpu(ps): return sum(p.cpu_times().user + p.cpu_times().system for p in ps)
def load(path, c, n, ka=True, warm=1000, url_path='/'):
    port, nodes = PATHS[path]; ps = procs(nodes); c0 = cpu(ps)
    r = subprocess.run([str(GO), '-url', f'http://127.0.0.1:{port}{url_path}', '-c', str(c), '-n', str(n), f'-ka={"true" if ka else "false"}', '-warm', str(warm)], capture_output=True, text=True, timeout=600)
    j = json.loads(r.stdout); j['cpu_us'] = (cpu(ps) - c0) / (n + warm) * 1e6 if nodes else 0; return j
def rounds(c, n, ka=True, warm=1000, url_path='/', k=3, gap=0):
    res = {p: [] for p in PATHS}
    for _ in range(k):
        for p in PATHS:
            res[p].append(load(p, c, n, ka, warm, url_path)); time.sleep(gap)
    out = {}
    for p, l in res.items():
        l.sort(key=lambda x: x['mean']); m = l[len(l) // 2]; out[p] = (m, min(x['mean'] for x in l), max(x['mean'] for x in l), sum(x['errs'] for x in l))
    return out
def show(out, cols):
    base = out['A 直连'][0]['mean']; rows = []
    for p, (m, lo, hi, errs) in out.items():
        rows.append([p] + [f(m) for _, f in cols] + [f'{lo:.0f}~{hi:.0f}', errs])
    table([['路径'] + [c for c, _ in cols] + ['3 轮平均延迟范围(µs)', '失败']] + [list(map(str, r)) for r in rows])
    return base

# ============ 一 ============
print('== 一:单个请求要多花多少时间。并发 1、keep-alive、每轮 20000 个请求(先预热 2000 个),延迟单位微秒(µs),3 轮取中位数那一轮')
out1 = rounds(1, 20000, True, 2000)
base = show(out1, [('平均 µs', lambda m: f'{m["mean"]:.0f}'), ('p50 µs', lambda m: f'{m["p50"]:.0f}'), ('p90 µs', lambda m: f'{m["p90"]:.0f}'), ('p99 µs', lambda m: f'{m["p99"]:.0f}'), ('请求/秒(并发 1)', lambda m: f'{m["rps"]:.0f}')])
a = out1['A 直连'][0]; b = out1['B 一个 Envoy'][0]; c_ = out1['C 两个 Envoy(明文)'][0]; d = out1['D 两个 Envoy(mTLS)'][0]
print(f'  相对直连多出的平均延迟:一个 Envoy +{b["mean"] - a["mean"]:.0f} µs,两个 Envoy(明文)+{c_["mean"] - a["mean"]:.0f} µs,两个 Envoy(mTLS)+{d["mean"] - a["mean"]:.0f} µs;p99 分别 +{b["p99"] - a["p99"]:.0f} / +{c_["p99"] - a["p99"]:.0f} / +{d["p99"] - a["p99"]:.0f} µs。D 与 C 只差几微秒;我的解释是 mTLS 握手只在建连时发生、已经建好的连接上只多了加解密,这个解释没有单独验证')

# ============ 二 ============
print('== 二:并发下的吞吐和 CPU。并发 32、keep-alive、每轮 60000 个请求(预热 3000 个)。「Envoy CPU」是这条路径上所有 Envoy 进程消耗的 CPU 时间(用户态加内核态)除以请求数,单位微秒/请求;Envoy 只开了 1 个工作线程,所以吞吐的上限受它限制')
out2 = rounds(32, 60000, True, 3000)
show(out2, [('请求/秒', lambda m: f'{m["rps"]:.0f}'), ('p50 µs', lambda m: f'{m["p50"]:.0f}'), ('p99 µs', lambda m: f'{m["p99"]:.0f}'), ('Envoy CPU µs/请求', lambda m: f'{m["cpu_us"]:.0f}')])
print('  压测程序、nginx、Envoy 在同一台机器上抢 CPU,直连(A)的吞吐很可能受压测程序自己限制,不是 nginx 的极限;表里 CPU 一列是 Envoy 自己的,不含 nginx 和压测程序')

# ============ 三 ============
print('== 三:每次请求新建连接(不 keep-alive)。并发 1,每轮 3000 个请求(预热 200 个),轮与轮之间等 5 s 避免临时端口耗尽。客户端到第一跳每次都建连;Envoy 到上游的连接是复用的(HTTP/1.1 连接池)')
out3 = rounds(1, 3000, False, 200, k=3, gap=5)
show(out3, [('平均 µs', lambda m: f'{m["mean"]:.0f}'), ('p50 µs', lambda m: f'{m["p50"]:.0f}'), ('p99 µs', lambda m: f'{m["p99"]:.0f}')])
a = out3['A 直连'][0]; b = out3['B 一个 Envoy'][0]; c_ = out3['C 两个 Envoy(明文)'][0]; d = out3['D 两个 Envoy(mTLS)'][0]
print(f'  相对直连多出的平均延迟:一个 Envoy +{b["mean"] - a["mean"]:.0f} µs,两个 Envoy +{c_["mean"] - a["mean"]:.0f} µs,两个 Envoy(mTLS)+{d["mean"] - a["mean"]:.0f} µs')

# ============ 四 ============
print('== 四:100 KB 的响应。并发 1、keep-alive,每轮 5000 个请求(预热 500 个),请求 /big(nginx 静态文件 102400 字节)')
out4 = rounds(1, 5000, True, 500, url_path='/big')
show(out4, [('平均 µs', lambda m: f'{m["mean"]:.0f}'), ('p50 µs', lambda m: f'{m["p50"]:.0f}'), ('p99 µs', lambda m: f'{m["p99"]:.0f}'), ('响应吞吐 MB/s', lambda m: f'{m["rps"] * 102400 / 1e6:.0f}')])
a = out4['A 直连'][0]; c_ = out4['C 两个 Envoy(明文)'][0]; d = out4['D 两个 Envoy(mTLS)'][0]
print(f'  响应变大之后,两个 Envoy(明文)比直连多出 {c_["mean"] - a["mean"]:.0f} µs,mTLS 比直连多出 {d["mean"] - a["mean"]:.0f} µs;我的解释是每多一跳就多拷贝一次整个响应体、mTLS 还要多加解密一次,没有单独验证')

# ============ 五 ============
print('== 五:内存。Envoy 的常驻内存(RSS)和配置里的集群数量的关系:每个配置有 N 个集群(各一个端点)和对应的 N 条路由;启动后空闲 2 s 读 RSS,并记录从启动到端口可连接的时间。再看上面第二节压测之后 B/C/D 路径上 Envoy 的 RSS')
rows = []
for nclu in (1, 100, 1000, 5000):
    e = Envoy(f'v92m{nclu}', cfg(NG.port, n_extra=nclu)); t = time.perf_counter(); e.start(); st = time.perf_counter() - t; time.sleep(2)
    rss = psutil.Process(e.p.pid).memory_info().rss / 1e6; rows.append((nclu, f'{st:.2f}', f'{rss:.0f}')); e.stop()
base_rss = float(rows[0][2]); last = rows[-1]
table([['配置里的集群数', '启动到可连接(s)', '空闲 RSS(MB)']] + [list(map(str, r)) for r in rows])
print(f'  按 1 个集群和 5000 个集群之间的差估算,每个集群(含一条路由)大约占 {(float(last[2]) - base_rss) / (int(last[0]) - 1) * 1000:.0f} KB;这是静态配置的数字,真实的网格里 Envoy 还要为每个集群保存端点、统计项,内存比这个大')
print('  压测之后各 Envoy 的 RSS:' + ', '.join(f'{name} {psutil.Process(n.p.pid).memory_info().rss / 1e6:.0f} MB' for name, n in (('B', ES), ('C 第一跳', E1), ('C 第二跳', E2), ('D 第一跳', E1T), ('D 第二跳', E2T))))
for n in (ES, E1, E2, E1T, E2T, NG): n.stop()
print('说明(哪些是测到的,哪些没有测)\n  每次运行的数字有明显波动:开发中的另一次运行里,并发 1 的平均延迟是 39 / 117 / 207 / 213 µs,新建连接时 D 比 C 慢,内存一节 1000 个集群的 RSS 是 119 MB(这次是 78 MB),5000 个集群是 250 MB(这次是 262 MB),所以微秒级和几十 MB 级的差别不能当精确值;全部在本机回环上,没有容器网络、iptables 重定向(第 83 篇)和跨主机的网络,Envoy 与后端之间的往返比真实部署小得多,绝对数字不能直接套用;每个数字是 3 轮里的中位数那一轮;Envoy 只开了 1 个工作线程;mTLS 的两个 Envoy 之间没有配置 SAN 校验;没有测:HTTP/2 与 gRPC、带 Lua / 限流 / 访问日志等过滤器的 Envoy(第 85 篇测过过滤器链的开销)、开启 tracing 与指标采集、Envoy 与应用同在一个 Pod 时的 CPU 争抢、Istio 的 Envoy 镜像和它默认配置的内存')
print('ERRORS', dict(ERRORS))
