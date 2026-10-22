import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import ssl, datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec
tee('v34'); reset()
print('TLS 终止:nginx 1.31.6 在网关上终止 client 的 TLS,再用明文或重新加密连接上游。证书由我用 cryptography 库自己签:根 CA(ECDSA P-256)→ 中间 CA(ECDSA P-256)→ 叶子证书(RSA 2048 / RSA 4096 / ECDSA P-256 三种,SAN 为 localhost 和 127.0.0.1)。client 是 Python 的 ssl 模块,信任的只有这个根 CA')
D = TT / 'v34'; D.mkdir(exist_ok=True)
now = datetime.datetime.now(datetime.timezone.utc)
def name(cn): return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
def mk_cert(subj, key, issuer_name, issuer_key, ca, san=None, path_len=None):
    b = x509.CertificateBuilder().subject_name(name(subj)).issuer_name(issuer_name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1)).not_valid_after(now + datetime.timedelta(days=30))
    b = b.add_extension(x509.BasicConstraints(ca=ca, path_length=path_len), critical=True)
    b = b.add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
    b = b.add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()), critical=False)
    b = b.add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=not ca, data_encipherment=False, key_agreement=False, key_cert_sign=ca, crl_sign=ca, encipher_only=False, decipher_only=False), critical=True)
    if san: b = b.add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'), x509.IPAddress(__import__('ipaddress').ip_address('127.0.0.1'))]), critical=False)
    return b.sign(issuer_key, hashes.SHA256())
def pem(c): return c.public_bytes(serialization.Encoding.PEM)
def kpem(k): return k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
root_k = ec.generate_private_key(ec.SECP256R1()); root = mk_cert('Lab Root CA', root_k, name('Lab Root CA'), root_k, True, path_len=1)
int_k = ec.generate_private_key(ec.SECP256R1()); inter = mk_cert('Lab Intermediate CA', int_k, root.subject, root_k, True, path_len=0)
(D / 'root.pem').write_bytes(pem(root))
leaves = {}
for lname, key in (('rsa2048', rsa.generate_private_key(65537, 2048)), ('rsa4096', rsa.generate_private_key(65537, 4096)), ('ec256', ec.generate_private_key(ec.SECP256R1()))):
    c = mk_cert('localhost', key, inter.subject, int_k, False, san=True)
    (D / f'{lname}.key').write_bytes(kpem(key)); (D / f'{lname}.leaf.pem').write_bytes(pem(c)); (D / f'{lname}.full.pem').write_bytes(pem(c) + pem(inter)); leaves[lname] = c
B = Svc(lambda h: h.reply(200, b'hello'))
def tls_conf(cert, key, extra='', loc='proxy_pass http://u;'):
    return f'upstream u {{ server 127.0.0.1:{B.port}; }} server {{ listen {{port}} ssl; ssl_certificate {D}/{cert}; ssl_certificate_key {D}/{key}; {extra} location / {{ {loc} }} }}'
def client_ctx(verify=True):
    ctx = ssl.create_default_context(cafile=str(D / 'root.pem'))
    if not verify: ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    return ctx
def handshake(port, ctx, session=None, want_session=False):
    t0 = time.perf_counter(); s = socket.create_connection(('127.0.0.1', port))
    c = ctx.wrap_socket(s, server_hostname='localhost', session=session); dt = time.perf_counter() - t0; sess = None
    if want_session:       # TLS 1.3 的会话票据在握手之后才由服务端发来,要先收发一次数据才能取到
        c.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n'); c.recv(4096); sess = c.session
    r = (dt, c.session_reused, c.version(), sess); c.close(); return r

# ============ 一 ============
print('== 一:证书链要配全。nginx 的 ssl_certificate 只放叶子证书,或放“叶子 + 中间 CA”(fullchain)。client 只信任根 CA。看握手能否通过,以及服务端在握手里发出的证书消息有多大(用 openssl s_client -showcerts 数出 nginx 发了几张证书)')
rows = []
for name_, cert in (('只有叶子证书', 'ec256.leaf.pem'), ('叶子 + 中间 CA(fullchain)', 'ec256.full.pem')):
    ng = Nginx('v34a', tls_conf(cert, 'ec256.key')).start()
    try: r = handshake(ng.port, client_ctx()); res = '握手成功,校验通过'
    except ssl.SSLCertVerificationError as e: res = '校验失败:' + e.verify_message
    sc = sh(f'echo | openssl s_client -connect 127.0.0.1:{ng.port} -servername localhost -showcerts 2>/dev/null | grep -c "BEGIN CERTIFICATE"')
    rows.append((name_, res, f'{sc} 张'))
    ng.stop()
table(rows, ['ssl_certificate', 'client(只信根 CA)的结果', 'nginx 发出的证书数'])
print('  叶子证书不是根 CA 直接签的,client 需要中间 CA 才能一路验证到自己信任的根;服务端不发中间证书,有的 client 会自己去下载(AIA),这里的 Python 不会,所以失败。根 CA 一般不需要发,client 本来就有')

# ============ 二 ============
print('== 二:握手耗时。每种配置做 200 次全新的 TCP 连接 + TLS 握手(不复用会话),取 TCP+TLS 总耗时的中位数。变量:叶子证书的密钥类型(RSA 2048 / RSA 4096 / ECDSA P-256)、TLS 版本(1.2 / 1.3)。另外对比有无会话复用:ssl_session_cache shared:SSL:1m(服务端缓存)时,client 带着上一次的会话票据重连')
rows = []
for lname in ('ec256', 'rsa2048', 'rsa4096'):
    for ver in ('TLSv1.2', 'TLSv1.3'):
        ng = Nginx('v34b', tls_conf(f'{lname}.full.pem', f'{lname}.key', f'ssl_protocols {ver};')).start(); ctx = client_ctx()
        lat = [handshake(ng.port, ctx)[0] for _ in range(200)]; v = handshake(ng.port, ctx)[2]; ng.stop()
        rows.append((lname, ver, v, f'{statistics.median(lat) * 1000:.2f} ms', f'{pct(lat, 99) * 1000:.2f} ms'))
table(rows, ['叶子证书', '服务端允许的版本', '实际协商', '握手耗时中位数(TCP + TLS)', 'p99'])
rows = []
for name_, extra in (('无会话缓存(ssl_session_cache off)', 'ssl_session_cache off; ssl_session_tickets off;'), ('shared 会话缓存 + session tickets 默认', 'ssl_session_cache shared:SSL:1m;')):
    ng = Nginx('v34c', tls_conf('rsa2048.full.pem', 'rsa2048.key', extra)).start(); ctx = client_ctx(); first = handshake(ng.port, ctx, want_session=True); full = []; res = []; sess = first[3]
    for _ in range(100):
        r = handshake(ng.port, ctx, session=sess); res.append((r[0], r[1]))
    ng.stop(); rr = [t for t, reused in res if reused]; nr = [t for t, reused in res if not reused]
    rows.append((name_, f'{sum(1 for t, u in res if u)} / 100', f'{statistics.median(rr) * 1000:.2f} ms' if rr else '-', f'{statistics.median(nr) * 1000:.2f} ms' if nr else '-'))
table(rows, ['配置(TLS 1.3 默认,RSA 2048)', '带着上次的会话重连,被复用的次数', '复用的握手中位数', '没复用的握手中位数'])

# ============ 三 ============
print('== 三:到上游是明文还是重新加密。上游(后端)有一个 HTTPS 版本(Python ssl,证书是中间 CA 签的 RSA 2048)。比较 nginx 的 proxy_pass http://(明文)/ proxy_pass https:// 默认(nginx 1.31.6 默认复用到上游的连接,TLS 握手只做一次)/ 强制每个请求新建连接(Connection: close)的 https 与 http / https:// + upstream keepalive / https:// + proxy_ssl_verify on(校验上游证书)。client 到 nginx 用 HTTP(为了单独看到上游一段的开销)。500 个顺序请求')
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def do_GET(self): self.send_response(200); self.send_header('Content-Length', '5'); self.end_headers(); self.wfile.write(b'hello')
class SS_(ThreadingHTTPServer): daemon_threads = True
def tls_backend(cert, key):
    p = free_port(); srv = SS_(('127.0.0.1', p), H); ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(str(D / cert), str(D / key)); srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv, p
TB, tp = tls_backend('rsa2048.full.pem', 'rsa2048.key'); BADB, badp = tls_backend('ec256.leaf.pem', 'ec256.key')
def up_conf(scheme, port, extra='', up_extra=''):
    return f'upstream u {{ server 127.0.0.1:{port}; {up_extra} }} server {{ listen {{port}}; location / {{ proxy_pass {scheme}://u; {extra} }} }}'
rows = []
for name_, scheme, port, extra, upx in (('proxy_pass http://(明文)', 'http', B.port, '', ''), ('proxy_pass https://,默认', 'https', tp, '', ''), ('https:// + Connection: close(每个请求新建 TLS 连接)', 'https', tp, 'proxy_set_header Connection close; proxy_ssl_session_reuse off;', ''), ('https:// + Connection: close + 会话复用', 'https', tp, 'proxy_set_header Connection close; proxy_ssl_session_reuse on;', ''), ('proxy_pass http:// + Connection: close(明文也每次新建连接)', 'http', B.port, 'proxy_set_header Connection close;', ''), ('proxy_pass https:// + upstream keepalive 16', 'https', tp, '', 'keepalive 16;'), ('https:// + proxy_ssl_verify on(信任根 CA)', 'https', tp, f'proxy_ssl_verify on; proxy_ssl_trusted_certificate {D}/root.pem; proxy_ssl_name localhost; proxy_ssl_server_name on;', 'keepalive 16;')):
    ng = Nginx('v34d', up_conf(scheme, port, extra, upx)).start(); lat = []; cnt = collections.Counter()
    for _ in range(500):
        st, b, dt = rpc(ng.port, '/', 5.0); lat.append(dt); cnt[st] += 1
    ng.stop(); rows.append((name_, f'{pct(lat, 50) * 1000:.2f} ms', f'{pct(lat, 99) * 1000:.2f} ms', dict(cnt)))
table(rows, ['到上游的方式', '延迟中位数', 'p99', '状态码'])
print('  上游证书的校验:默认的 proxy_ssl_verify 是 off,nginx 不检查上游证书是否可信、名字是否对得上;下面让上游用一张叶子证书(没有发中间 CA),分别在 verify off / on 下请求')
rows = []
for name_, extra in (('proxy_ssl_verify off(默认)', ''), ('proxy_ssl_verify on', f'proxy_ssl_verify on; proxy_ssl_trusted_certificate {D}/root.pem; proxy_ssl_name localhost; proxy_ssl_server_name on;')):
    ng = Nginx('v34e', up_conf('https', badp, extra)).start(); st, b, dt = rpc(ng.port, '/', 5.0); err = [l for l in (ng.d / 'err.log').read_text().splitlines() if '[error]' in l]; ng.stop()
    rows.append((name_, st, (err[0].split('] ', 1)[1][:130] if err else '(没有错误)')))
table(rows, ['配置', '状态码', 'error.log'])
TB.shutdown(); BADB.shutdown()
