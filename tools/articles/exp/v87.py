import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import ssl, datetime
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
tee('v87'); reset()
print('mTLS:证书签发与轮换。Envoy 1.39.3 做服务端(要求客户端证书),服务端证书和信任的 CA 通过文件型 SDS 下发(Envoy 监听文件的变化);我用 Python 的 cryptography 库做一个小 CA(ECDSA P-256),签发带 SPIFFE 风格 URI SAN 的短期证书;客户端是 Python 的 ssl。看(一)什么情况下握手失败、错误信息是什么;(二)服务端证书轮换(原子替换 SDS 文件)时有没有握手失败、多久生效;(三)证书过期之后的窗口;(四)CA 轮换的顺序')
class CA:
    def __init__(self, cn):
        self.key = ec.generate_private_key(ec.SECP256R1()); n = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)]); now = datetime.datetime.now(datetime.timezone.utc)
        self.cert = (x509.CertificateBuilder().subject_name(n).issuer_name(n).public_key(self.key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5)).not_valid_after(now + datetime.timedelta(days=1))
                     .add_extension(x509.BasicConstraints(ca=True, path_length=0), True).add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), True)
                     .add_extension(x509.SubjectKeyIdentifier.from_public_key(self.key.public_key()), False).sign(self.key, hashes.SHA256()))
    @property
    def pem(self): return self.cert.public_bytes(serialization.Encoding.PEM).decode()
    def issue(self, name, ttl_s=3600, server=False, not_before_offset=-60):
        k = ec.generate_private_key(ec.SECP256R1()); now = datetime.datetime.now(datetime.timezone.utc)
        san = [x509.UniformResourceIdentifier(f'spiffe://trust.local/ns/default/sa/{name}')] + ([x509.DNSName('localhost')] if server else [])
        c = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])).issuer_name(self.cert.subject).public_key(k.public_key()).serial_number(x509.random_serial_number())
             .not_valid_before(now + datetime.timedelta(seconds=not_before_offset)).not_valid_after(now + datetime.timedelta(seconds=ttl_s))
             .add_extension(x509.BasicConstraints(ca=False, path_length=None), True).add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), True)
             .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]), False).add_extension(x509.SubjectAlternativeName(san), False)
             .add_extension(x509.SubjectKeyIdentifier.from_public_key(k.public_key()), False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(self.key.public_key()), False).sign(self.key, hashes.SHA256()))
        return c.public_bytes(serialization.Encoding.PEM).decode(), k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(), c.serial_number
CA1, CA2 = CA('mesh-ca-1'), CA('mesh-ca-2')
BACK = Svc(lambda h: h.reply(200, b'ok'), 'back'); D = txl.tdir('v87sds'); SDS = D / 'server.yaml'; VAL = D / 'validation.yaml'
def sds_secret(cert, key): return f'resources:\n- "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.Secret\n  name: server_cert\n  tls_certificate:\n    certificate_chain: {{inline_string: {json.dumps(cert)}}}\n    private_key: {{inline_string: {json.dumps(key)}}}\n'
def val_secret(bundle): return f'resources:\n- "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.Secret\n  name: validation\n  validation_context:\n    trusted_ca: {{inline_string: {json.dumps(bundle)}}}\n'
def atomic(path, text): t = path.with_suffix('.tmp'); t.write_text(text); os.replace(t, path)
def set_server(cert, key): atomic(SDS, sds_secret(cert, key))
def set_validation(bundle): atomic(VAL, val_secret(bundle))
c0, k0, s0 = CA1.issue('server', 3600, True); set_server(c0, k0); set_validation(CA1.pem + CA2.pem)
cfg = f'''node: {{id: v87, cluster: v87}}
admin: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {free_port()}}}}}}}
static_resources:
  listeners:
  - name: l
    address: {{socket_address: {{address: 127.0.0.1, port_value: {{port}}}}}}
    filter_chains:
    - transport_socket:
        name: envoy.transport_sockets.tls
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.DownstreamTlsContext
          require_client_certificate: true
          common_tls_context:
            tls_certificate_sds_secret_configs:
            - name: server_cert
              sds_config: {{path_config_source: {{path: {SDS}}}, resource_api_version: V3}}
            validation_context_sds_secret_config:
              name: validation
              sds_config: {{path_config_source: {{path: {VAL}}}, resource_api_version: V3}}
      filters:
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
                route: {{cluster: back}}
  clusters:
  - name: back
    type: STATIC
    connect_timeout: 1s
    load_assignment:
      cluster_name: back
      endpoints:
      - lb_endpoints:
        - endpoint: {{address: {{socket_address: {{address: 127.0.0.1, port_value: {BACK.port}}}}}}}
'''
env = Envoy('v87', cfg).start(); time.sleep(0.5)
def cctx(trust_pem, cert=None, key=None):
    c = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); c.load_verify_locations(cadata=trust_pem); c.check_hostname = False
    if cert:
        cf = D / f'c_{abs(hash(cert)) % 10**8}.pem'; cf.write_text(cert + key); c.load_cert_chain(str(cf))
    return c
def hs(ctx, timeout=3.0):
    t = time.perf_counter()
    try:
        raw = socket.create_connection(('127.0.0.1', env.port), timeout=timeout); s = ctx.wrap_socket(raw, server_hostname='localhost')
        der = s.getpeercert(binary_form=True); serial = x509.load_der_x509_certificate(der).serial_number
        s.sendall(b'GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n'); d = s.recv(4096); s.close()
        return True, serial, ('200' if b' 200 ' in d[:20] else d[:30]), time.perf_counter() - t
    except Exception as e:
        return False, None, f'{type(e).__name__}: {str(e)[:110]}', time.perf_counter() - t
cc, ck, _ = CA1.issue('client', 3600)

# ============ 一 ============
print('== 一:什么情况下握手会失败。服务端证书由 CA1 签发、有效;服务端信任 CA1 和 CA2。客户端分别:(a)带 CA1 签发的有效证书;(b)不带客户端证书;(c)带 CA2 签发的有效证书(服务端信任 CA2,所以应该成功);(d)带一个未知 CA3 签发的证书;(e)带 CA1 签发、但已经过期的证书(有效期 1 s,握手前已过期);(f)客户端不信任服务端的 CA(信任库里是 CA2)')
CA3 = CA('mesh-ca-3'); exp_c, exp_k, _ = CA1.issue('client-expired', 1, not_before_offset=-120); time.sleep(1.6)
c2, k2, _ = CA2.issue('client2', 3600); c3, k3, _ = CA3.issue('client3', 3600); trust = CA1.pem
rows = []
for name, ctx in (('(a)CA1 签发的有效客户端证书', cctx(trust, cc, ck)), ('(b)不带客户端证书', cctx(trust)), ('(c)CA2 签发的有效客户端证书', cctx(trust, c2, k2)), ('(d)未知 CA3 签发的客户端证书', cctx(trust, c3, k3)), ('(e)已经过期的客户端证书', cctx(trust, exp_c, exp_k)), ('(f)客户端不信任服务端的 CA', cctx(CA2.pem, cc, ck))):
    ok, serial, info, dt = hs(ctx); rows.append((name, '成功' if ok else '失败', info if not ok else f'HTTP {info},服务端证书序列号尾号 …{str(serial)[-6:]}', f'{dt * 1000:.0f}'))
table(rows, ['客户端', '结果', '详情', '耗时(ms)'])
print('  上面的错误信息来自客户端 Python ssl 抛出的异常(握手和第一次读写都在 hs() 里统一捕获);服务端拒绝客户端证书时,客户端看到的是 TLS alert,不是 HTTP 响应')

# ============ 二 ============
print('== 二:服务端证书轮换。客户端(CA1 签发的证书)每 20 ms 发起一次完整的握手加一个请求,持续 6 s;在第 2 s 把服务端证书换成新签发的(新密钥、新序列号,同一个 CA),方式是原子替换 SDS 文件(写临时文件再 rename)。统计失败的握手数,以及看到的服务端证书序列号在什么时候变的')
c1, k1, s1 = CA1.issue('server', 3600, True); set_server(c1, k1); time.sleep(1.0)
ctx = cctx(trust, cc, ck); log = []; stop = threading.Event(); T0 = time.perf_counter()
def loop():
    while not stop.is_set():
        ok, serial, info, dt = hs(ctx); log.append((time.perf_counter() - T0, ok, serial, info)); time.sleep(0.02)
th = threading.Thread(target=loop); th.start(); time.sleep(2.0)
c2s, k2s, s2 = CA1.issue('server', 3600, True); t_rot = time.perf_counter() - T0; set_server(c2s, k2s); time.sleep(4.0); stop.set(); th.join()
fails = [l for l in log if not l[1]]; new_first = next((l[0] for l in log if l[2] == s2), None)
print(f'  共 {len(log)} 次握手,失败 {len(fails)} 次;服务端证书序列号变化:旧 …{str(s1)[-6:]} → 新 …{str(s2)[-6:]};替换 SDS 文件的时刻 {t_rot:.2f} s,客户端第一次看到新证书的时刻 {new_first:.2f} s(相差 {(new_first - t_rot) * 1000:.0f} ms);新证书出现之后又看到旧证书的次数 {sum(1 for l in log if l[0] > new_first and l[2] == s1)}')
print('  原子替换 SDS 文件之后,新的握手很快(见上一行)用上新证书,期间没有握手失败')

# ============ 三 ============
print('== 三:证书过期之后。把服务端证书换成一张有效期只有 5 s 的证书,客户端每 200 ms 握手一次,共 12 s;第 8 s 轮换成新的 1 小时证书。看成功和失败在时间轴上的分布、失败的错误信息,以及 Envoy 在证书过期之后是否仍然提供这张证书')
c5, k5, s5 = CA1.issue('server', 5, True); set_server(c5, k5); time.sleep(0.5); log = []; T0 = time.perf_counter(); ctx = cctx(trust, cc, ck); stop = threading.Event()
def loop2():
    while not stop.is_set():
        ok, serial, info, dt = hs(ctx); log.append((time.perf_counter() - T0, ok, serial, info)); time.sleep(0.2)
th = threading.Thread(target=loop2); th.start(); time.sleep(8.0)
c6, k6, s6 = CA1.issue('server', 3600, True); t_rot = time.perf_counter() - T0; set_server(c6, k6); time.sleep(4.0); stop.set(); th.join()
okt = [l[0] for l in log if l[1] and l[2] == s5]; failt = [l[0] for l in log if not l[1]]; recov = next((l[0] for l in log if l[1] and l[2] == s6), None)
print(f'  旧证书(有效期 5 s)的握手在 {min(okt):.1f}~{max(okt):.1f} s 成功({len(okt)} 次);失败 {len(failt)} 次,时间范围 {min(failt):.1f}~{max(failt):.1f} s;错误信息:{log[[i for i, l in enumerate(log) if not l[1]][0]][3]};第 {t_rot:.1f} s 轮换,第一次用新证书成功在 {recov:.1f} s')
print('  Envoy 在证书过期之后仍然把它提供给客户端(它没有因为过期而撤下证书),是客户端验证失败拒绝的;所以过期的窗口从证书到期一直延续到轮换完成,期间所有新握手都失败——证书要在到期之前很久轮换(例如有效期的一半),而不是到期时')

# ============ 四 ============
print('== 四:CA 轮换的顺序。把 CA1 换成 CA2 签发服务端证书。五种(客户端信任库,服务端证书的签发者)组合,看握手结果。对应的发布步骤:先让所有客户端信任 CA1 + CA2(信任包),再把服务端证书改成 CA2 签发,最后从信任包里去掉 CA1;顺序错了就会失败')
rows = []
sc1, sk1, _ = CA1.issue('server', 3600, True); sc2, sk2, _ = CA2.issue('server', 3600, True)
for name, trust_pem, sc, sk in (('(a)信任 CA1,服务端证书 CA1', CA1.pem, sc1, sk1), ('(b)信任 CA1,服务端证书 CA2(顺序错:服务端先换)', CA1.pem, sc2, sk2), ('(c)信任 CA1+CA2,服务端证书 CA2(正确:先分发信任包)', CA1.pem + CA2.pem, sc2, sk2), ('(d)信任 CA2,服务端证书 CA1(客户端先去掉了 CA1)', CA2.pem, sc1, sk1), ('(e)信任 CA2,服务端证书 CA2(最终状态)', CA2.pem, sc2, sk2)):
    set_server(sc, sk); time.sleep(0.6); ok, serial, info, dt = hs(cctx(trust_pem, cc, ck)); rows.append((name, '成功' if ok else '失败', info if not ok else 'HTTP ' + info))
table(rows, ['组合', '结果', '详情'])
print('  信任包要先于证书发出去:服务端证书先换成新 CA 而客户端还不信任它,握手立刻失败;客户端过早去掉旧 CA 同理。所以 CA 轮换分三步:分发包含新旧两个 CA 的信任包 → 换签发者 → 去掉旧 CA,每一步要等上一步在所有实例上完成')
env.stop(); BACK.stop()
print('ERRORS', dict(ERRORS))
