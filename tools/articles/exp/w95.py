import sys, os, re, struct, threading, statistics, errno, ssl, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
tee('w95'); reset()
key = ec.generate_private_key(ec.SECP256R1()); nm = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
cert = x509.CertificateBuilder().subject_name(nm).issuer_name(nm).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=2)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), False).sign(key, hashes.SHA256())
CF, KF = str(WT / 'w95_c.pem'), str(WT / 'w95_k.pem'); open(CF, 'wb').write(cert.public_bytes(serialization.Encoding.PEM)); open(KF, 'wb').write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
def server(port, stop, v12=False, ciphers=None):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(CF, KF)
    if v12: ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    if ciphers: ctx.set_ciphers(ciphers)
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(8); ls.settimeout(0.3)
    def h(c):
        try:
            ss = ctx.wrap_socket(c, server_side=True); ss.settimeout(5)
            while True:
                d = ss.recv(1 << 20)
                if not d: break
        except Exception: pass
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
def app_records(path, port):
    cs = b''; seen = set()
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            ip = bytes(buf[4:]); ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]; sp, dp, seq, ack, off = struct.unpack('>HHIIB', t[:13]); hl = (off >> 4) * 4; pl = t[hl:tl_ - ihl]
            if not pl or dp != port or seq in seen: continue
            seen.add(seq); cs += pl
    out = []; i = 0
    while i + 5 <= len(cs): t, v, n = cs[i], struct.unpack('>H', cs[i + 1:i + 3])[0], struct.unpack('>H', cs[i + 3:i + 5])[0]; out.append((t, n)); i += 5 + n
    return out
def probe(sizes, v12=False, ciphers=None, gap=0.15):
    port = lab_port(); stop = [False]; server(port, stop, v12, ciphers)
    cctx = ssl.create_default_context(); cctx.check_hostname = False; cctx.verify_mode = ssl.CERT_NONE
    if v12: cctx.maximum_version = ssl.TLSVersion.TLSv1_2
    if ciphers: cctx.set_ciphers(ciphers)
    with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=0) as c:
        s = socket.create_connection(('127.0.0.1', port)); s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1); ss = cctx.wrap_socket(s, server_hostname='localhost'); ver = (ss.version(), ss.cipher()[0]); time.sleep(0.3)
        mark = len(app_records(c.pcap, port)) if False else None
        for n in sizes: ss.sendall(b'x' * n); time.sleep(gap)
        ss.close(); time.sleep(0.4)
    stop[0] = True; recs = app_records(c.pcap, port)
    return ver, [r for r in recs if r[0] == 23]

print('== 一:一次 write 变成一条什么样的记录?本机 TLS 服务器,客户端依次 sendall 1、10、100、1000、10000 字节(间隔 150 ms,TCP_NODELAY,每次一条记录),抓 lo0 看每条应用数据记录的长度。TLS 1.3(AES-256-GCM)与 TLS 1.2(AES-GCM)对比')
sizes = [1, 10, 100, 1000, 10000]
for v12, nm_ in ((False, 'TLS 1.3'), (True, 'TLS 1.2')):
    ver, recs = probe(sizes, v12=v12); body = [n for t, n in recs]
    tail = body[-len(sizes):]
    print(f'  {nm_}(协商 {ver[0]},{ver[1]}):最后 {len(sizes)} 条应用数据记录的长度(记录体,不含 5 字节记录头)= {tail}')
    print('    每条的开销(记录体 − 明文 + 5 字节记录头):' + ', '.join(f'{n} → {t - n + 5}' for n, t in zip(sizes, tail)))
print('  TLS 1.3:记录体 = 明文 + 1 字节真实内容类型 + 16 字节认证标签 → 开销 22 字节(含 5 字节头);TLS 1.2 GCM:记录体 = 8 字节显式 nonce + 密文 + 16 字节标签 → 开销 29 字节。最外层的“记录类型”在 TLS 1.3 里一律写成 23(ApplicationData),真实类型藏在密文里')
print('  记录长度明文可见:1 → 10 → 100 → 1000 → 10000 的明文长度,在线上对应的记录长度严格单调且差值恰好等于明文差——路径上的观察者能看出每条消息有多长')

print('== 二:大块数据怎么切记录:一次 sendall 100000 字节(TLS 1.3),看被切成多少条记录、每条多长')
ver, recs = probe([100000], v12=False); body = [n for t, n in recs]
big = body[-8:]
print(f'  一次写 100000 字节,最后出现的记录体长度:{big}')
full = [n for n in body if n >= 16000]
print(f'  其中 {len(full)} 条是满的记录(体 {max(full) if full else None} 字节 = 16384 明文 + 1 类型字节 + 16 标签 = {16384 + 17});剩下的是尾部较短的记录;总共 {sum(n for n in body[-len(big):])} 字节密文承载 100000 字节明文')
if full:
    print(f'  TLS 记录明文最大 2^14 = 16384 字节;100000 ÷ 16384 = {100000 / 16384:.2f} → 需要 {-(-100000 // 16384)} 条记录;额外开销 {-(-100000 // 16384)} × 22 = {-(-100000 // 16384) * 22} 字节({-(-100000 // 16384) * 22 / 100000:.2%})')

print('== 三:许多小写入 vs 一次大写入:同样 4000 字节,分成 40 次 100 字节写(TCP_NODELAY,每次一条记录)与一次写 4000 字节,线上的记录数和总字节')
for label, szs in (('40 次 × 100 字节', [100] * 40), ('1 次 × 4000 字节', [4000])):
    ver, recs = probe(szs, gap=0.0); app = [n for t, n in recs]; mine = app[-len(szs):] if len(app) >= len(szs) else app
    print(f'  {label}:线上应用数据记录 {len(mine)} 条(最后这批),合计记录体 {sum(mine)} 字节,加上记录头 {sum(mine) + 5 * len(mine)} 字节;明文 {sum(szs)} 字节;开销 {sum(mine) + 5 * len(mine) - sum(szs)} 字节({(sum(mine) + 5 * len(mine) - sum(szs)) / sum(szs):.1%})')
print('  每条记录固定多 22 字节的头 + 标签,所以小消息越碎、开销占比越高;应用要合并小写入(或依赖 TCP 层之上的缓冲)')
