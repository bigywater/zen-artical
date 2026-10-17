import sys, os, re, struct, zlib, random, timeit, threading, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import numpy as np
tee('w17'); reset()
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
PUB = '104.20.23.154'
_t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); _t.connect((gw, 9)); ME = _t.getsockname()[0]; _t.close()

def fold(s):
    while s >> 16: s = (s & 0xffff) + (s >> 16)
    return s
def words(b):
    if len(b) % 2: b += b'\0'
    return struct.unpack('>%dH' % (len(b) // 2), b)
def cs(b): return ~fold(sum(words(b))) & 0xffff
def l4sum(raw):
    ihl = (raw[0] & 15) * 4; tl = struct.unpack('>H', raw[2:4])[0]; seg = raw[ihl:tl]
    ps = raw[12:20] + bytes([0, raw[9]]) + struct.pack('>H', len(seg))
    return cs(ps + seg), seg

print('== 一:IPv4 头校验和手算:构造一个头(文档地址 192.0.2.1 → 198.51.100.7,TTL 64,协议 UDP,总长 60),逐个 16 位字相加、折回进位、取反;再把方法用在真实抓到的包上')
hdr = bytearray(struct.pack('>BBHHHBBH4s4s', 0x45, 0, 60, 0x1c46, 0x4000, 64, 17, 0, socket.inet_aton('192.0.2.1'), socket.inet_aton('198.51.100.7')))
ws = words(bytes(hdr)); tot = sum(ws)
print('  头部 10 个 16 位字(校验和字段先填 0): ' + ' '.join(f'{w:04x}' for w in ws))
print(f'  直接相加 = 0x{tot:x}(超过 16 位);把高位的进位加回低位:0x{tot:x} → 0x{(tot & 0xffff) + (tot >> 16):x};取反得校验和 0x{cs(bytes(hdr)):04x}')
hdr[10:12] = struct.pack('>H', cs(bytes(hdr)))
print(f'  填回去以后,接收方把整个头再加一遍:折回后的和 = 0x{fold(sum(words(bytes(hdr)))):04x},取反 = 0x{cs(bytes(hdr)):04x}(全 1 取反得 0,表示校验通过)')
# 真实包
with Cap(f'ip and (host {PUB} or host 1.1.1.1 or host {gw})', iface='en0', write=True) as c:
    for _ in range(3): subprocess.run(['curl', '-s', '--noproxy', '*', '-o', '/dev/null', 'http://example.com/'], capture_output=True)
    for i in range(5):
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.settimeout(2)
        u.sendto(struct.pack('>HHHHHH', 0x1000 + i, 0x100, 1, 0, 0, 0) + b'\x07example\x03com\x00\x00\x01\x00\x01', ('1.1.1.1', 53))
        try: u.recvfrom(2000)
        except Exception: pass
    sysout('ping', '-c', '5', gw)
pk = [(ts, ip.raw) for ts, ip in read_pcap(c.pcap)]
stat = {}
def bump(k, ok):
    a = stat.setdefault(k, [0, 0]); a[0] += ok; a[1] += 1
for ts, r in pk:
    ihl = (r[0] & 15) * 4; d = '本机发出' if r[12:16] == socket.inet_aton(ME) else '收到'
    bump((d, 'IP 头'), cs(r[:ihl]) == 0)
    if r[9] in (6, 17): bump((d, 'TCP' if r[9] == 6 else 'UDP'), l4sum(r)[0] == 0)
    elif r[9] == 1:
        tl_ = struct.unpack('>H', r[2:4])[0]; bump((d, 'ICMP'), cs(r[ihl:tl_]) == 0)
print(f'  真实抓包(en0)共 {len(pk)} 个 IP 包,用同一种方法检验:')
for (d, k), (ok, n) in sorted(stat.items()): print(f'    {d} 的 {k:<4}: {ok}/{n} 校验通过')

print('== 二:TCP / UDP 校验和多了一个“伪头部”(源地址、目的地址、协议、L4 长度),覆盖 IP 地址;手算一个 UDP 数据报,再看 lo0 与 en0 的差别')
src, dst = socket.inet_aton('192.0.2.1'), socket.inet_aton('198.51.100.7')
payload = b'hello, checksum'
udp = struct.pack('>HHHH', 40000, 9, 8 + len(payload), 0) + payload
ps = src + dst + bytes([0, 17]) + struct.pack('>H', len(udp))
print('  伪头部 12 字节: ' + ps.hex(' ', 2) + f'(源 192.0.2.1、目的 198.51.100.7、0、协议 17、UDP 长度 {len(udp)})')
print(f'  伪头部各字之和 0x{sum(words(ps)):x};UDP 头 + 载荷各字之和 0x{sum(words(udp)):x};合计折回后 0x{fold(sum(words(ps + udp))):04x},取反得 UDP 校验和 0x{cs(ps + udp):04x}')
print('  为什么要伪头部:让校验和也能发现“包被送到了错误的主机”——只有 UDP / TCP 头和载荷的话,地址被改错了也查不出来')
# lo0 对比
r = socket.socket(socket.AF_INET, socket.SOCK_STREAM); r.bind(('127.0.0.1', 0)); r.listen(); pt = r.getsockname()[1]
def srv():
    cn, _ = r.accept(); n = 0
    while True:
        d = cn.recv(65536)
        if not d: break
        n += len(d)
    cn.close()
th = threading.Thread(target=srv, daemon=True); th.start()
ur = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); ur.bind(('127.0.0.1', 0)); ur.settimeout(1)
with Cap(f'(tcp port {pt}) or (udp port {ur.getsockname()[1]})', iface='lo0', write=True) as c:
    k = socket.create_connection(('127.0.0.1', pt)); k.sendall(b'z' * 200000); k.close(); th.join(3)
    ux = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for _ in range(5): ux.sendto(b'lo0-udp-test' * 10, ur.getsockname())
    time.sleep(0.5)
st = {}
for ts, ip in read_pcap(c.pcap):
    r_ = ip.raw; ihl = (r_[0] & 15) * 4; proto = 'TCP' if r_[9] == 6 else 'UDP'
    a = st.setdefault(proto, dict(n=0, iphdr_ok=0, iphdr_zero=0, l4_ok=0, l4_zero=0)); a['n'] += 1
    a['iphdr_ok'] += cs(r_[:ihl]) == 0; a['iphdr_zero'] += struct.unpack('>H', r_[10:12])[0] == 0
    a['l4_ok'] += l4sum(r_)[0] == 0
    off = ihl + (16 if proto == 'TCP' else 6); a['l4_zero'] += struct.unpack('>H', r_[off:off + 2])[0] == 0
for proto, a in st.items(): print(f'  lo0 上抓到 {a["n"]} 个 {proto} 包:IP 头校验和正确 {a["iphdr_ok"]} 个(字段为 0 的 {a["iphdr_zero"]} 个);{proto} 校验和正确 {a["l4_ok"]} 个(字段为 0 的 {a["l4_zero"]} 个)')
print('  所以 lo0 上抓到的“错误校验和”不是传输错误:本机内的包校验和被卸载 / 省略了(en0 上抓到的同样检验全部通过,见第一节)')

print('== 三:校验和的盲区:相加是可交换的,所以 16 位字的顺序被调换查不出来;对比 CRC-32')
a = bytes.fromhex('1122334455667788'); b = bytes.fromhex('3344112255667788')    # 前两个字调换
c1 = bytes.fromhex('1234abcd0000'); c2 = bytes.fromhex('1235abcc0000')           # 一个字 +1,另一个字 −1
print(f'  数据 A = {a.hex()}:校验和 0x{cs(a):04x},CRC-32 0x{zlib.crc32(a):08x}')
print(f'  数据 B = {b.hex()}(前两个 16 位字 1122 / 3344 对调):校验和 0x{cs(b):04x},CRC-32 0x{zlib.crc32(b):08x}')
print(f'  校验和相同: {cs(a) == cs(b)};CRC-32 相同: {zlib.crc32(a) == zlib.crc32(b)}')
print(f'  数据 C = {c1.hex()} 和 D = {c2.hex()}(一个字 +1,另一个 −1):校验和 0x{cs(c1):04x} / 0x{cs(c2):04x},相同: {cs(c1) == cs(c2)};CRC-32 相同: {zlib.crc32(c1) == zlib.crc32(c2)}')
# 模拟:真实抓到的一个大 TCP 段上翻转比特
seg = None
with Cap(f'host {PUB} and tcp src port 80', iface='en0', write=True) as c:
    subprocess.run(['curl', '-s', '--noproxy', '*', '-o', '/dev/null', 'http://example.com/'], capture_output=True)
big = max((ip.raw for ts, ip in read_pcap(c.pcap)), key=len)
ihl = (big[0] & 15) * 4; seg = big[ihl:struct.unpack('>H', big[2:4])[0]]
base = np.frombuffer(seg + (b'\0' if len(seg) % 2 else b''), dtype='>u2').astype(np.int64)
def fcs(w):
    s = int(w.sum())
    while s >> 16: s = (s & 0xffff) + (s >> 16)
    return s
ref = fcs(base); nbits = len(seg) * 8
single = 0
for i in range(nbits):
    w = base.copy(); byte = i // 8; w[byte // 2] ^= (0x80 >> (i % 8)) << (8 if byte % 2 == 0 else 0)
    single += fcs(w) != ref
rng = random.Random(1); N = 20000; undetected = crc_un = 0
crc0 = zlib.crc32(seg)
for _ in range(N):
    i, j = rng.sample(range(nbits), 2)
    w = base.copy()
    for t in (i, j):
        byte = t // 8; w[byte // 2] ^= (0x80 >> (t % 8)) << (8 if byte % 2 == 0 else 0)
    undetected += fcs(w) == ref
    bb = bytearray(seg)
    for t in (i, j): bb[t // 8] ^= 0x80 >> (t % 8)
    crc_un += zlib.crc32(bytes(bb)) == crc0
print(f'  用真实抓到的一个 {len(seg)} 字节的 TCP 段做翻转比特实验(模拟,不是网络上的实测):')
print(f'    翻转任意 1 个比特(共 {nbits} 种):校验和能发现 {single} 种(全部发现:{single == nbits})')
print(f'    随机翻转 2 个比特({N} 次):校验和没发现 {undetected} 次({undetected / N * 100:.3f}%);CRC-32 没发现 {crc_un} 次')
print('    校验和漏掉的 2 比特翻转:两个比特在各自 16 位字里位置相同、一个 0→1 一个 1→0,变化互相抵消')

print('== 四:增量更新(RFC 1624):路由器每转发一次要把 TTL 减 1,不需要重新加整个头;NAT 改地址和端口也一样。用真实抓到的包验证公式 HC\' = ~(~HC + ~m + m\')')
def upd(hc, old, new):
    s = (~hc & 0xffff) + (~old & 0xffff) + new
    return ~fold(s) & 0xffff
ok_ttl = n_ttl = 0
for ts, r in pk:
    ihl = (r[0] & 15) * 4; h = bytearray(r[:ihl]); 
    if cs(bytes(h)) != 0: continue
    hc = struct.unpack('>H', h[10:12])[0]; old = (h[8] << 8) | h[9]; h[8] -= 1; new = (h[8] << 8) | h[9]
    n_ttl += 1
    h2 = bytearray(h); h2[10:12] = b'\0\0'
    ok_ttl += upd(hc, old, new) == cs(bytes(h2))
print(f'  把 {n_ttl} 个真实抓到的包的 TTL 减 1:增量公式算出的新校验和与整头重算的相同 {ok_ttl} 个')
tcp = [r for ts, r in pk if r[9] == 6 and l4sum(r)[0] == 0 and r[12:16] == socket.inet_aton(ME)]
ok_nat = 0
newsrc = socket.inet_aton('203.0.113.9'); newsp = 61234
for r in tcp:
    ihl = (r[0] & 15) * 4; tl_ = struct.unpack('>H', r[2:4])[0]
    old_ip = r[12:16]; sp = struct.unpack('>H', r[ihl:ihl + 2])[0]; hc = struct.unpack('>H', r[ihl + 16:ihl + 18])[0]
    for o, n in ((struct.unpack('>H', old_ip[0:2])[0], struct.unpack('>H', newsrc[0:2])[0]), (struct.unpack('>H', old_ip[2:4])[0], struct.unpack('>H', newsrc[2:4])[0]), (sp, newsp)): hc = upd(hc, o, n)
    r2 = bytearray(r); r2[12:16] = newsrc; r2[ihl:ihl + 2] = struct.pack('>H', newsp)
    r2[ihl + 16:ihl + 18] = b'\0\0'
    ok_nat += hc == l4sum(bytes(r2))[0]
print(f'  NAT 式改写:把本机发出的 {len(tcp)} 个 TCP 包的源地址改成 203.0.113.9、源端口改成 {newsp}(3 个 16 位字),增量更新的 TCP 校验和与整段重算的相同 {ok_nat} 个')
h20 = bytes(hdr)
t_full = timeit.timeit(lambda: cs(h20), number=200000) / 200000 * 1e6
t_inc = timeit.timeit(lambda: upd(0x1234, 0x4001, 0x3f01), number=200000) / 200000 * 1e6
t_big = timeit.timeit(lambda: cs(seg), number=2000) / 2000 * 1e6
print(f'  Python 里的耗时(只看相对大小):整个 20 字节头重算 {t_full:.2f} µs,增量更新一个字 {t_inc:.2f} µs;对 {len(seg)} 字节的 TCP 段整段重算 {t_big:.1f} µs(增量更新则与段长无关)')

print('== 五:UDP 校验和的特例:IPv4 的 UDP 校验和字段为 0 表示“没有校验和”,所以算出来恰好是 0 的要改发 0xffff。构造一个算出来是 0 的数据报,抓包看线上发出的值')
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind((ME, 0)); s.connect((gw, 9)); sp = s.getsockname()[1]
body = b'zero-checksum-demo!!'            # 20 字节(偶数),末尾再补一个 16 位字使整体校验和恰好为 0
def calc(pl):
    udp = struct.pack('>HHHH', sp, 9, 8 + len(pl), 0) + pl
    ps = socket.inet_aton(ME) + socket.inet_aton(gw) + bytes([0, 17]) + struct.pack('>H', len(udp))
    return cs(ps + udp), fold(sum(words(ps + udp)))
f0 = calc(body + b'\0\0')[1]
last = (0xffff - f0) & 0xffff
pl = body + struct.pack('>H', last)
cc, folded = calc(pl)
print(f'  先让末尾的 16 位字为 0,各字之和折回后是 0x{f0:04x};把末尾字设成 0xffff − 0x{f0:04x} = 0x{last:04x},现在载荷 {len(pl)} 字节,各字之和折回后 0x{folded:04x},按公式算出的校验和 = 0x{cc:04x}')
with Cap(f'ip and host {gw} and udp port 9', iface='en0', write=True) as c:
    s.send(pl); time.sleep(0.4)
wire = [ip.raw for ts, ip in read_pcap(c.pcap)]
ihl = (wire[0][0] & 15) * 4
print(f'  线上抓到 {len(wire)} 个包:UDP 校验和字段 = 0x{struct.unpack(">H", wire[0][ihl + 6:ihl + 8])[0]:04x};按接收方的检验方法(含伪头部全部相加)结果:{"通过" if l4sum(wire[0])[0] == 0 else "不通过"}')
print('  0 和 0xffff 在反码里都表示“零”,所以把 0 换成 0xffff 不改变校验;字段 0 留给“发送方没算校验和”')
