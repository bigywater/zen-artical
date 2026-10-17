import sys, os, re, struct, threading, statistics, errno, ssl; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w90'); reset()
HOST = 'example.com'; IP = '104.20.23.154'
CS = {0x1301: 'TLS_AES_128_GCM_SHA256', 0x1302: 'TLS_AES_256_GCM_SHA384', 0x1303: 'TLS_CHACHA20_POLY1305_SHA256', 0xc02b: 'ECDHE_ECDSA_AES128_GCM', 0xc02f: 'ECDHE_RSA_AES128_GCM', 0xc02c: 'ECDHE_ECDSA_AES256_GCM', 0xc030: 'ECDHE_RSA_AES256_GCM', 0xcca9: 'ECDHE_ECDSA_CHACHA20', 0xcca8: 'ECDHE_RSA_CHACHA20', 0x00ff: 'EMPTY_RENEGOTIATION_INFO'}
GR = {0x001d: 'x25519', 0x0017: 'secp256r1', 0x0018: 'secp384r1', 0x0019: 'secp521r1', 0x001e: 'x448', 0x0100: 'ffdhe2048', 0x0101: 'ffdhe3072', 0x11ec: 'X25519MLKEM768', 0x6399: 'X25519Kyber768Draft00'}
EXT = {0: 'server_name', 5: 'status_request', 10: 'supported_groups', 11: 'ec_point_formats', 13: 'signature_algorithms', 16: 'ALPN', 18: 'signed_certificate_timestamp', 23: 'extended_master_secret', 35: 'session_ticket', 43: 'supported_versions', 45: 'psk_key_exchange_modes', 51: 'key_share', 21: 'padding', 22: 'encrypt_then_mac', 65281: 'renegotiation_info', 28: 'record_size_limit'}
def streams(path, port=443):
    cs = b''; ss = b''; seen = {'c': set(), 's': set()}; ev = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf)
            if e.type != 0x0800 or not isinstance(e.data.data, dpkt.tcp.TCP): continue
            ip = e.data; t = ip.data
            if not t.data: continue
            d = 'c' if t.dport == port else 's'
            if t.seq in seen[d]: continue
            seen[d].add(t.seq)
            if d == 'c': cs += bytes(t.data)
            else: ss += bytes(t.data)
            ev.append((ts, d, len(t.data)))
    return cs, ss, ev
def records(b):
    out = []; i = 0
    while i + 5 <= len(b):
        t, v, n = b[i], struct.unpack('>H', b[i + 1:i + 3])[0], struct.unpack('>H', b[i + 3:i + 5])[0]; out.append((t, v, n, b[i + 5:i + 5 + n])); i += 5 + n
    return out
RT = {20: 'ChangeCipherSpec', 21: 'Alert', 22: 'Handshake', 23: 'ApplicationData'}
def parse_ch(p):
    i = 4; ver = struct.unpack('>H', p[i:i + 2])[0]; i += 34; sl = p[i]; i += 1 + sl; cl = struct.unpack('>H', p[i:i + 2])[0]; i += 2
    suites = [struct.unpack('>H', p[i + j:i + j + 2])[0] for j in range(0, cl, 2)]; i += cl; i += 1 + p[i]
    el = struct.unpack('>H', p[i:i + 2])[0]; i += 2; end = i + el; exts = []
    while i < end:
        t, l = struct.unpack('>HH', p[i:i + 4]); exts.append((t, p[i + 4:i + 4 + l])); i += 4 + l
    return ver, sl, suites, exts
def ext_detail(t, d):
    if t == 0: return d[5:5 + struct.unpack('>H', d[3:5])[0]].decode()
    if t == 43: return [hex(struct.unpack('>H', d[1 + j:3 + j])[0]) for j in range(0, d[0], 2)]
    if t == 10: return [GR.get(struct.unpack('>H', d[2 + j:4 + j])[0], hex(struct.unpack('>H', d[2 + j:4 + j])[0])) for j in range(0, struct.unpack('>H', d[:2])[0], 2)]
    if t == 51:
        l = struct.unpack('>H', d[:2])[0]; i = 2; r = []
        while i < 2 + l: g, n = struct.unpack('>HH', d[i:i + 4]); r.append(f'{GR.get(g, hex(g))}({n} 字节公钥)'); i += 4 + n
        return r
    if t == 16:
        r = []; i = 2
        while i < len(d): r.append(d[i + 1:i + 1 + d[i]].decode()); i += 1 + d[i]
        return r
    if t == 13: return f'{struct.unpack(">H", d[:2])[0] // 2} 种签名算法'
    if t == 45: return [d[1 + j] for j in range(d[0])]
    return f'{len(d)} 字节'
def one(ctx_mod=None, label=''):
    ctx = ssl.create_default_context(); ctx.set_alpn_protocols(['h2', 'http/1.1'])
    if ctx_mod: ctx_mod(ctx)
    with Cap(f'tcp port 443 and host {IP}', iface='en0', write=True, snaplen=0) as c:
        t0 = time.time(); s = socket.create_connection((IP, 443), timeout=8); t1 = time.time(); ss = ctx.wrap_socket(s, server_hostname=HOST); t2 = time.time()
        info = (ss.version(), ss.cipher(), ss.selected_alpn_protocol()); ss.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'); ss.recv(100); ss.close(); time.sleep(0.4)
    return c.pcap, (t1 - t0) * 1000, (t2 - t1) * 1000, info

print('== 一:ClientHello:客户端的第一个包,明文。看它提供了什么:版本、密码套件、扩展(SNI、支持的组、key_share 里的公钥、ALPN……)')
pcap, tcp_ms, tls_ms, info = one()
cs, ss_, ev = streams(pcap); crec = records(cs); srec = records(ss_)
ch = crec[0][3]; ver, sl, suites, exts = parse_ch(ch)
print(f'  这次连接协商的结果(Python ssl 告诉的):{info[0]},{info[1][0]},ALPN {info[2]};TCP 握手 {tcp_ms:.0f} ms,TLS 握手 {tls_ms:.0f} ms')
print(f'  第一条记录:类型 {RT[crec[0][0]]},记录层版本 0x{crec[0][1]:04x}(旧版本号,为兼容中间设备),长度 {crec[0][2]} 字节;握手消息类型 {ch[0]}(1 = ClientHello),长度 {int.from_bytes(ch[1:4], "big")} 字节')
print(f'  ClientHello 里的版本字段 0x{ver:04x}(= TLS 1.2,同样为兼容;真正的版本在 supported_versions 扩展里);session_id 长度 {sl}(TLS 1.3 的兼容模式下是 32 字节随机数)')
print(f'  提供的密码套件({len(suites)} 个):{[CS.get(x, hex(x)) for x in suites]}')
print(f'  扩展({len(exts)} 个):' + ', '.join(EXT.get(t, str(t)) for t, d in exts))
for t, d in exts:
    if t in (0, 43, 10, 51, 16, 13, 45): print(f'    {EXT[t]:<18} {ext_detail(t, d)}')

print('== 二:服务器的回应:ServerHello(明文,选择了套件和密钥交换组),随后一切都是加密的')
sh_rec = srec[0]; sh = sh_rec[3]; i = 4 + 2 + 32; sl2 = sh[i]; i += 1 + sl2; cipher = struct.unpack('>H', sh[i:i + 2])[0]; i += 3
el = struct.unpack('>H', sh[i:i + 2])[0]; i += 2; ex2 = []
while i < len(sh):
    t, l = struct.unpack('>HH', sh[i:i + 4]); ex2.append((t, sh[i + 4:i + 4 + l])); i += 4 + l
print(f'  ServerHello 记录 {sh_rec[2]} 字节:选了密码套件 {CS.get(cipher, hex(cipher))};扩展 ' + ', '.join(EXT.get(t, str(t)) for t, d in ex2))
for t, d in ex2:
    if t == 43: print(f'    supported_versions 选定 0x{struct.unpack(">H", d)[0]:04x}(0x0304 = TLS 1.3)')
    if t == 51: g = struct.unpack('>H', d[:2])[0]; n = struct.unpack('>H', d[2:4])[0]; print(f'    key_share 选定的组 {GR.get(g, hex(g))},服务器的公钥 {n} 字节(客户端用自己的私钥 + 这个公钥算出共享密钥)')
print('  服务器→客户端 的全部 TLS 记录(顺序、类型、长度):')
for t, v, n, p in srec[:8]: print(f'    {RT.get(t, t):<18} 版本 0x{v:04x}  长度 {n:>5}' + ('  ← 从这里起是加密的(外层伪装成 ApplicationData,真实类型藏在密文里)' if t == 23 and (v == 0x0303) and False else ''))
print(f'  客户端→服务器 的全部 TLS 记录:' + '; '.join(f'{RT.get(t, t)} {n} 字节' for t, v, n, p in crec[:8]))
enc = [r for r in srec if r[0] == 23]
print(f'  服务器的 ServerHello 之后:{sum(1 for r in srec if r[0] == 20)} 个 ChangeCipherSpec(兼容用,内容是 1 个字节的 01)、{len(enc)} 个加密记录,合计 {sum(r[2] for r in enc)} 字节——里面是 EncryptedExtensions、Certificate、CertificateVerify、Finished(以及之后的应用数据)')

print('== 三:一个往返:从包的时间线看 TLS 1.3 握手用了几个往返')
t0 = ev[0][0]
print('    相对时间(ms)  方向  载荷字节')
for ts, d, n in ev[:12]: print(f'    {(ts - t0) * 1000:10.1f}   {"C→S" if d == "c" else "S→C"}   {n:>6}')
first_c = [e for e in ev if e[1] == 'c'][0]; first_s = [e for e in ev if e[1] == 's'][0]
cfin = next((e for e in ev if e[1] == 'c' and e[0] > first_s[0]), None)
print(f'  ClientHello(+{(first_c[0] - t0) * 1000:.0f} ms)→ 服务器回 ServerHello 等(+{(first_s[0] - t0) * 1000:.0f} ms)= 1 个往返 {(first_s[0] - first_c[0]) * 1000:.0f} ms;' + (f'客户端随后发出 Finished(+{(cfin[0] - t0) * 1000:.0f} ms),这时客户端已经可以同时发应用数据' if cfin else ''))
print(f'  Python 量到的 TLS 握手总计 {tls_ms:.0f} ms ≈ 1 个往返({(first_s[0] - first_c[0]) * 1000:.0f} ms)加上本机计算');
print('== 四:对比 TLS 1.2:同一个服务器,把客户端最高版本限制成 TLS 1.2,看握手几个往返、耗时多少(各 4 次对比)')
def lim12(ctx): ctx.maximum_version = ssl.TLSVersion.TLSv1_2
t13 = []; t12 = []
for i in range(4):
    p, a, b_, inf = one(); t13.append(b_)
    p, a, b_, inf12 = one(lim12); t12.append(b_)
print(f'  TLS 1.3 握手耗时(ms):{[round(x) for x in t13]},中位 {statistics.median(t13):.0f}')
print(f'  TLS 1.2 握手耗时(ms):{[round(x) for x in t12]},中位 {statistics.median(t12):.0f};协商结果 {inf12[0]},{inf12[1][0]}')
cs2, ss2, ev2 = streams(p); c2 = records(cs2); s2 = records(ss2)
print(f'  TLS 1.2 握手里服务器→客户端的记录:' + '; '.join(f'{RT.get(t, t)} {n} 字节' for t, v, n, pl in s2[:6]) + '(这里 Certificate 是明文的,可以直接被路径上的设备读到)')
hs = [(pl[0], n) for t, v, n, pl in s2 if t == 22]
HT = {2: 'ServerHello', 11: 'Certificate', 12: 'ServerKeyExchange', 14: 'ServerHelloDone', 4: 'NewSessionTicket', 20: 'Finished'}
print(f'  TLS 1.2 服务器发出的握手消息类型:{[HT.get(x[0], x[0]) for x in hs]}')
