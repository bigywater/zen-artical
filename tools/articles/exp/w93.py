import sys, os, re, struct, threading, statistics, errno, ssl, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w93'); reset()
HOST = 'example.com'; IP = '104.20.23.154'
EXT = {0: 'server_name', 10: 'supported_groups', 11: 'ec_point_formats', 13: 'signature_algorithms', 16: 'ALPN', 22: 'encrypt_then_mac', 23: 'extended_master_secret', 35: 'session_ticket', 41: 'pre_shared_key', 43: 'supported_versions', 45: 'psk_key_exchange_modes', 51: 'key_share', 65281: 'renegotiation_info', 21: 'padding'}
def streams(path, port=443):
    cs = b''; ss = b''; seen = {'c': set(), 's': set()}
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf)
            if e.type != 0x0800 or not isinstance(e.data.data, dpkt.tcp.TCP): continue
            t = e.data.data
            if not t.data: continue
            d = 'c' if t.dport == port else 's'
            if t.seq in seen[d]: continue
            seen[d].add(t.seq)
            if d == 'c': cs += bytes(t.data)
            else: ss += bytes(t.data)
    return cs, ss
def records(b):
    out = []; i = 0
    while i + 5 <= len(b):
        t, v, n = b[i], struct.unpack('>H', b[i + 1:i + 3])[0], struct.unpack('>H', b[i + 3:i + 5])[0]; out.append((t, v, n, b[i + 5:i + 5 + n])); i += 5 + n
    return out
def ch_exts(p):
    i = 4 + 34; sl = p[i]; i += 1 + sl; cl = struct.unpack('>H', p[i:i + 2])[0]; i += 2 + cl; i += 1 + p[i]
    el = struct.unpack('>H', p[i:i + 2])[0]; i += 2; end = i + el; ex = []
    while i < end: t, l = struct.unpack('>HH', p[i:i + 4]); ex.append((t, l)); i += 4 + l
    return ex
def sh_exts(p):
    i = 4 + 2 + 32; sl = p[i]; i += 1 + sl + 3; el = struct.unpack('>H', p[i:i + 2])[0]; i += 2; ex = []
    while i < len(p): t, l = struct.unpack('>HH', p[i:i + 4]); ex.append((t, l)); i += 4 + l
    return ex
CTX = {}
def conn(session=None, v12=False):
    if v12 not in CTX:
        c_ = ssl.create_default_context(); c_.set_alpn_protocols(['http/1.1'])
        if v12: c_.maximum_version = ssl.TLSVersion.TLSv1_2
        CTX[v12] = c_
    ctx = CTX[v12]
    s = socket.create_connection((IP, 443), timeout=8); t0 = time.time(); ss = ctx.wrap_socket(s, server_hostname=HOST, session=session); dt = (time.time() - t0) * 1000
    return ss, dt
def finish(ss):
    ss.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'); ss.settimeout(5)
    try:
        while ss.recv(65536): pass
    except Exception: pass
    sess = ss.session; ss.close(); return sess

print('== 一:TLS 1.3 的会话恢复:第一次完整握手,收到服务器在握手后发来的 session ticket;第二次带着 ticket 恢复(PSK)。各 5 对,看握手耗时、是否恢复、以及线上服务器→客户端的字节数')
full = []; res = []; rb = []
for i in range(5):
    with Cap(f'tcp port 443 and host {IP}', iface='en0', write=True, snaplen=0) as c1:
        ss, dt = conn(); sess = finish(ss); time.sleep(0.3)
    cs1, ss1 = streams(c1.pcap)
    with Cap(f'tcp port 443 and host {IP}', iface='en0', write=True, snaplen=0) as c2:
        ss2, dt2 = conn(session=sess); reused = ss2.session_reused; finish(ss2); time.sleep(0.3)
    cs2, ss2_ = streams(c2.pcap)
    full.append((dt, len(ss1), len(cs1), ss.session_reused if False else None)); res.append((dt2, len(ss2_), len(cs2), reused))
    if i == 0: first = (c1.pcap, c2.pcap, sess)
print(f'  完整握手:耗时(ms){[round(x[0]) for x in full]},中位 {statistics.median(x[0] for x in full):.0f};服务器→客户端 {statistics.median(x[1] for x in full):.0f} 字节,客户端→服务器 {statistics.median(x[2] for x in full):.0f} 字节(中位,包含收发各一次 HTTP 请求和响应)')
print(f'  恢复握手:耗时(ms){[round(x[0]) for x in res]},中位 {statistics.median(x[0] for x in res):.0f};session_reused = {[x[3] for x in res]};服务器→客户端 {statistics.median(x[1] for x in res):.0f} 字节,客户端→服务器 {statistics.median(x[2] for x in res):.0f} 字节(中位)')
print(f'  session 对象:{type(first[2]).__name__},has_ticket = {first[2].has_ticket},ticket 生存期提示 {first[2].timeout} 秒({first[2].timeout / 3600:.1f} 小时)')

print('== 二:恢复的握手在线上长什么样:对比第一对里的 ClientHello 和 ServerHello 的扩展列表')
r1c = records(streams(first[0])[0]); r1s = records(streams(first[0])[1]); r2c = records(streams(first[1])[0]); r2s = records(streams(first[1])[1])
e1 = ch_exts(r1c[0][3]); e2 = ch_exts(r2c[0][3])
print(f'  完整握手的 ClientHello {r1c[0][2]} 字节,扩展:{[EXT.get(t, t) for t, l in e1]}')
print(f'  恢复握手的 ClientHello {r2c[0][2]} 字节,扩展:{[EXT.get(t, t) for t, l in e2]}')
psk = [l for t, l in e2 if t == 41]
print(f'  恢复的 ClientHello 多了 pre_shared_key 扩展({psk[0] if psk else None} 字节:里面是 ticket 本身 + 一个 binder,用来证明客户端知道密钥),并且它必须是最后一个扩展')
s1 = sh_exts(r1s[0][3]); s2 = sh_exts(r2s[0][3])
print(f'  完整握手的 ServerHello 扩展:{[EXT.get(t, t) for t, l in s1]};恢复握手的 ServerHello 扩展:{[EXT.get(t, t) for t, l in s2]}(pre_shared_key 表示服务器接受了恢复)')
print(f'  服务器在 ServerHello 之后发的加密记录:完整握手 {[n for t, v, n, p in r1s[1:] if t == 23]},恢复握手 {[n for t, v, n, p in r2s[1:] if t == 23]}——恢复时不再发证书(完整握手的那个 3000+ 字节记录),只剩 Finished 之类的小记录')

print('== 三:TLS 1.2 的会话恢复(session ticket):TLS 1.2 完整握手要 2 个往返,恢复后只要 1 个。限定 TLS 1.2,各 5 对')
f12 = []; r12 = []; reus = []
for i in range(5):
    ss, dt = conn(v12=True); sess = finish(ss); f12.append(dt)
    ss2, dt2 = conn(session=sess, v12=True); reus.append(ss2.session_reused); r12.append(dt2); finish(ss2)
print(f'  TLS 1.2 完整握手:{[round(x) for x in f12]},中位 {statistics.median(f12):.0f} ms;恢复握手:{[round(x) for x in r12]},中位 {statistics.median(r12):.0f} ms;session_reused = {reus}')
print(f'  对比 TLS 1.3:完整 {statistics.median(x[0] for x in full):.0f} ms,恢复 {statistics.median(x[0] for x in res):.0f} ms——TLS 1.3 的完整握手本来就只要 1 个往返,恢复省的是证书和计算,不省往返')

print('== 四:ticket 能用几次?同一个 session 对象连续恢复 4 次')
ss, dt = conn(); sess = finish(ss); outs = []
for i in range(4):
    ss2, dt2 = conn(session=sess); outs.append((ss2.session_reused, round(dt2))); finish(ss2)
print(f'  连续 4 次用同一个 ticket:(是否恢复, 握手 ms) = {outs}')
print('  TLS 1.3 规范建议 ticket 只用一次(防重放和跨连接关联),服务器可以拒绝重复使用;这里看到服务器是否接受重复使用')

print('== 五:0-RTT(早期数据):恢复握手时可以在第一个包里就带上应用数据,省掉整个握手往返,代价是可被重放。用 openssl s_client 对 example.com 实测')
def run(args, inp=b'', t=20):
    try: p = subprocess.run(args, input=inp, capture_output=True, timeout=t); return p.stdout.decode(errors='replace') + p.stderr.decode(errors='replace')
    except subprocess.TimeoutExpired as e: return (e.stdout or b'').decode(errors='replace') + (e.stderr or b'').decode(errors='replace')
REQ = b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'
sp = str(WT / 'w93_sess.pem'); er = str(WT / 'w93_early.txt'); open(er, 'wb').write(REQ)
o1 = run(['openssl', 's_client', '-connect', f'{IP}:443', '-servername', HOST, '-tls1_3', '-sess_out', sp, '-ign_eof'], REQ)
print('  第一次连接(openssl):' + '; '.join(l.strip() for l in o1.splitlines() if re.search(r'Protocol  :|ticket lifetime hint|Max Early Data', l))[:300])
o2 = run(['openssl', 's_client', '-connect', f'{IP}:443', '-servername', HOST, '-tls1_3', '-sess_in', sp, '-early_data', er, '-ign_eof'], REQ)
print('  第二次(带 ticket 并要求发 early data):' + '; '.join(l.strip() for l in o2.splitlines() if re.search(r'Reused|Early data|early', l)))
print(f'  服务器收到了 {len(re.findall("ticket lifetime hint", o1)) // 2} 个 NewSessionTicket(openssl 在输出里打印了每个 ticket 的信息);Max Early Data 为 0 表示服务器没有允许 0-RTT——这个站点关闭了 0-RTT')
