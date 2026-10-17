import sys, os, re, struct, threading, statistics, errno, ssl, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
tee('w94'); reset()
UTC = datetime.UTC
def mkkey(): return ec.generate_private_key(ec.SECP256R1())
def mkcert(cn, issuer_cert=None, issuer_key=None, key=None, ca=False, days=30, start=None, san=None, eku=None):
    key = key or mkkey(); name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)]); start = start or (datetime.datetime.now(UTC) - datetime.timedelta(days=1))
    b = x509.CertificateBuilder().subject_name(name).issuer_name(issuer_cert.subject if issuer_cert else name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(start).not_valid_after(start + datetime.timedelta(days=days))
    b = b.add_extension(x509.BasicConstraints(ca=ca, path_length=None), True).add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
    if issuer_cert is not None: b = b.add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()), False)
    else: b = b.add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), False)
    b = b.add_extension(x509.KeyUsage(digital_signature=not ca, content_commitment=False, key_encipherment=False, data_encipherment=False, key_agreement=False, key_cert_sign=ca, crl_sign=ca, encipher_only=False, decipher_only=False), True)
    if san: b = b.add_extension(x509.SubjectAlternativeName(san), False)
    if eku: b = b.add_extension(x509.ExtendedKeyUsage([eku]), False)
    c = b.sign(issuer_key or key, hashes.SHA256()); return c, key
def save(c, k, base):
    cp, kp = str(WT / (base + '.crt')), str(WT / (base + '.key')); open(cp, 'wb').write(c.public_bytes(serialization.Encoding.PEM)); open(kp, 'wb').write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())); return cp, kp
ca, cak = mkcert('w94 Test CA', ca=True, days=365); other, otherk = mkcert('w94 Other CA', ca=True, days=365)
srv, srvk = mkcert('localhost', ca, cak, san=[x509.DNSName('localhost')], eku=ExtendedKeyUsageOID.SERVER_AUTH)
good, goodk = mkcert('alice@w94', ca, cak, eku=ExtendedKeyUsageOID.CLIENT_AUTH)
bad, badk = mkcert('mallory@w94', other, otherk, eku=ExtendedKeyUsageOID.CLIENT_AUTH)
old, oldk = mkcert('bob-expired@w94', ca, cak, eku=ExtendedKeyUsageOID.CLIENT_AUTH, days=2, start=datetime.datetime.now(UTC) - datetime.timedelta(days=10))
p_ca = save(ca, cak, 'w94_ca')[0]; p_srv = save(srv, srvk, 'w94_srv'); p_good = save(good, goodk, 'w94_good'); p_bad = save(bad, badk, 'w94_bad'); p_old = save(old, oldk, 'w94_old')
log = []
def run_server(mode, port, v12=False, stop=None):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(*p_srv); ctx.load_verify_locations(p_ca); ctx.verify_mode = {'required': ssl.CERT_REQUIRED, 'optional': ssl.CERT_OPTIONAL, 'none': ssl.CERT_NONE}[mode]
    if v12: ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(32); ls.settimeout(0.3)
    def h(c):
        try:
            c.settimeout(5); ss = ctx.wrap_socket(c, server_side=True); pc = ss.getpeercert(); who = dict(x[0] for x in pc['subject'])['commonName'] if pc else None
            log.append(('ok', who)); ss.recv(100); ss.sendall(b'hello ' + (who or 'anonymous').encode()); ss.close()
        except Exception as e: log.append(('fail', f'{type(e).__name__}: {str(e)[:60]}'))
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
def client(port, cert=None, v12=False):
    ctx = ssl.create_default_context(cafile=p_ca)
    if cert: ctx.load_cert_chain(*cert)
    if v12: ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    s = socket.create_connection(('127.0.0.1', port), timeout=5); t0 = time.time()
    try:
        ss = ctx.wrap_socket(s, server_hostname='localhost'); t_hs = (time.time() - t0) * 1000; ss.sendall(b'hi')
        try: r = ss.recv(100).decode(); res = f'握手 {t_hs:.1f} ms 成功,收到 {r!r}'
        except Exception as e: res = f'握手 {t_hs:.1f} ms 看起来成功,但第一次读就失败:{type(e).__name__} {str(e)[:70]}'
        ss.close(); return res
    except Exception as e: return f'握手失败({(time.time() - t0) * 1000:.1f} ms):{type(e).__name__} {str(e)[:80]}'

print('== 一:本机搭一套小 PKI:一个 CA(w94 Test CA)签发服务器证书(localhost)和客户端证书(alice);另有“另一个 CA”签发的客户端证书(mallory)和已过期的客户端证书(bob)。证书全是临时生成的,只在本机用')
print(f'  CA:{ca.subject.rfc4514_string()},CA=True;服务器证书:{srv.subject.rfc4514_string()},扩展 serverAuth,SAN localhost;客户端证书 alice:extendedKeyUsage = clientAuth,签发者 w94 Test CA')
print(f'  mallory 的证书由 "{bad.issuer.rfc4514_string()}" 签发(服务器不信任这个 CA);bob 的证书有效期 {old.not_valid_before_utc:%m-%d} ~ {old.not_valid_after_utc:%m-%d},已经过期')
print('== 二:服务器要求客户端证书(CERT_REQUIRED,只信任 w94 Test CA),五种客户端的结果')
port = lab_port(); stop = [False]; run_server('required', port, stop=stop)
cases = [('alice(有效的客户端证书)', p_good), ('不带任何客户端证书', None), ('mallory(由不被信任的 CA 签发)', p_bad), ('bob(证书已过期)', p_old)]
for nm, c in cases:
    log.clear(); r = client(port, c); time.sleep(0.2); print(f'  {nm:<28}→ 客户端:{r};服务器记录:{log[-1] if log else None}')
stop[0] = True
print('== 三:服务器“可选”客户端证书(CERT_OPTIONAL):没有证书也让进,由应用层决定怎么处理')
port = lab_port(); stop = [False]; run_server('optional', port, stop=stop)
for nm, c in (('alice', p_good), ('不带证书', None), ('mallory', p_bad)):
    log.clear(); r = client(port, c); time.sleep(0.2); print(f'  {nm:<10}→ 客户端:{r};服务器记录:{log[-1] if log else None}')
stop[0] = True
print('== 四:客户端证书在线上能不能被看到?抓 lo0 上 TLS 1.2 与 TLS 1.3 两次带客户端证书的握手,列出每个方向的握手消息类型')
HT = {1: 'ClientHello', 2: 'ServerHello', 11: 'Certificate', 12: 'ServerKeyExchange', 13: 'CertificateRequest', 14: 'ServerHelloDone', 15: 'CertificateVerify', 16: 'ClientKeyExchange', 20: 'Finished', 4: 'NewSessionTicket'}
def cap_hs(v12):
    port = lab_port(); stop = [False]; run_server('required', port, v12=v12, stop=stop)
    with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=0) as c:
        client(port, p_good, v12=v12); time.sleep(0.4)
    stop[0] = True; cs = b''; ss = b''; seen = {'c': set(), 's': set()}
    with open(c.pcap, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            ip = bytes(buf[4:]); ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]; sp, dp, seq, ack, off = struct.unpack('>HHIIB', t[:13]); hl = (off >> 4) * 4; pl = t[hl:tl_ - ihl]
            if not pl: continue
            d = 'c' if dp == port else 's'
            if seq in seen[d]: continue
            seen[d].add(seq)
            if d == 'c': cs += pl
            else: ss += pl
    def recs(b):
        out = []; i = 0
        while i + 5 <= len(b): t, v, n = b[i], struct.unpack('>H', b[i + 1:i + 3])[0], struct.unpack('>H', b[i + 3:i + 5])[0]; out.append((t, n, b[i + 5:i + 5 + n])); i += 5 + n
        return out
    def hs_types(rs):
        out = []
        for t, n, p in rs:
            if t == 22:
                i = 0
                while i + 4 <= len(p): out.append(HT.get(p[i], p[i])); i += 4 + int.from_bytes(p[i + 1:i + 4], 'big')
            elif t == 23: out.append('(加密记录 %d 字节)' % n)
            elif t == 20: out.append('ChangeCipherSpec')
        return out
    return hs_types(recs(cs)), hs_types(recs(ss)), len(cs), len(ss)
for v12, nm in ((True, 'TLS 1.2'), (False, 'TLS 1.3')):
    c_, s_, nc, ns = cap_hs(v12)
    print(f'  {nm}:客户端→服务器 {nc} 字节:{c_};服务器→客户端 {ns} 字节:{s_}')
print('  TLS 1.2 里服务器的 CertificateRequest 和客户端的 Certificate / CertificateVerify 都是明文握手消息,路径上的设备能直接读出客户端证书(包括里面的身份);TLS 1.3 把它们放进了加密记录里')
print('== 五:双向认证的代价:lo0 上 TLS 1.3,服务器要求 / 不要求客户端证书,各做 150 次握手(每次新连接),看每次握手的耗时中位数')
res = {}
for mode, cert, nm in (('none', None, '单向 TLS(不要客户端证书)'), ('required', p_good, '双向 TLS(客户端出示证书)')):
    port = lab_port(); stop = [False]; run_server(mode, port, stop=stop); ts = []
    for i in range(150):
        ctx = ssl.create_default_context(cafile=p_ca)
        if cert: ctx.load_cert_chain(*cert)
        s = socket.create_connection(('127.0.0.1', port)); t0 = time.perf_counter(); ss = ctx.wrap_socket(s, server_hostname='localhost'); ts.append((time.perf_counter() - t0) * 1000); ss.sendall(b'x'); ss.recv(100); ss.close()
    stop[0] = True; res[nm] = ts; time.sleep(0.3)
for nm, ts in res.items(): print(f'  {nm:<26}:握手耗时 中位 {statistics.median(ts):.2f} ms,p90 {sorted(ts)[int(len(ts) * 0.9)]:.2f} ms')
a, b = [statistics.median(v) for v in res.values()]
print(f'  双向认证比单向多约 {b - a:.2f} ms({(b - a) / a:.0%}):客户端要多发一个证书 + 一个 CertificateVerify 签名,服务器要多验证一条证书链和一个签名(本机 lo0 上没有网络延迟,这个差就是纯计算和消息处理)')
