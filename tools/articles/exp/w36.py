import sys, os, re, struct, collections, ipaddress, statistics, itertools; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt, dns.resolver
tee('w36'); reset()
rs = dns.resolver.Resolver(configure=False); rs.nameservers = ['1.1.1.1']; rs.lifetime = 4
def res(n): return rs.resolve(n, 'A')[0].address
MAGIC = 0x2112A442
AN = {0x0001: 'MAPPED-ADDRESS', 0x0003: 'CHANGE-REQUEST', 0x0020: 'XOR-MAPPED-ADDRESS', 0x8022: 'SOFTWARE', 0x802b: 'RESPONSE-ORIGIN', 0x802c: 'OTHER-ADDRESS', 0x8028: 'FINGERPRINT', 0x0004: 'SOURCE-ADDRESS', 0x0005: 'CHANGED-ADDRESS'}
def attrs(d):
    i = 20; out = []
    while i + 4 <= len(d):
        t, l = struct.unpack('>HH', d[i:i + 4]); out.append((t, d[i + 4:i + 4 + l])); i += 4 + ((l + 3) // 4 * 4)
    return out
def req(change=0):
    a = b''
    if change: a = struct.pack('>HHI', 0x0003, 4, change)
    return struct.pack('>HHI', 1, len(a), MAGIC) + os.urandom(12) + a
def xaddr(v):
    return socket.inet_ntoa(bytes(x ^ y for x, y in zip(v[4:8], struct.pack('>I', MAGIC)))), struct.unpack('>H', v[2:4])[0] ^ (MAGIC >> 16)
def plain(v): return socket.inet_ntoa(v[4:8]), struct.unpack('>H', v[2:4])[0]
def ask(sock, dst, change=0, timeout=1.5):
    sock.settimeout(timeout); r = req(change); sock.sendto(r, dst)
    t0 = time.time()
    try: d, a = sock.recvfrom(2000)
    except socket.timeout: return None
    A = dict(attrs(d))
    return dict(rtt=(time.time() - t0) * 1000, src=a, raw=d, req=r, attrs=attrs(d), xor=xaddr(A[0x0020]) if 0x0020 in A else None, other=plain(A[0x802c]) if 0x802c in A else None, origin=plain(A[0x802b]) if 0x802b in A else None)
def cls(ip_):
    a = ipaddress.ip_address(ip_); return '私有' if a.is_private else '公网'
SERV = [('服务器 1', res('stun.cloudflare.com'), 3478), ('服务器 2', res('global.stun.twilio.com'), 3478), ('服务器 3', res('stun.miwifi.com'), 3478), ('服务器 4', res('stun.sipgate.net'), 3478)]

print('== 一:STUN 报文:请求只有 20 字节的头(类型 + 长度 + magic cookie 0x2112A442 + 96 位事务编号),应答里带属性;抓包看真实的字节,并验证 XOR-MAPPED-ADDRESS 的异或规则')
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('0.0.0.0', 0)); lp = s.getsockname()[1]
with Cap(f'udp port {lp}', iface='en0', write=True) as c:
    r1 = ask(s, (SERV[1][1], 3478)); r3 = ask(s, (SERV[2][1], 3478)); time.sleep(0.3)
print(f'  请求(20 字节):{r1["req"].hex(" ", 4)}')
print(f'    = 类型 0x{r1["req"][0] << 8 | r1["req"][1]:04x}(Binding Request)、长度 {struct.unpack(">H", r1["req"][2:4])[0]}、magic cookie 0x{struct.unpack(">I", r1["req"][4:8])[0]:08x}、事务编号 12 字节(随机)')
for nm, r in (('服务器 2', r1), ('服务器 3', r3)):
    d = r['raw']; print(f'  {nm}的应答 {len(d)} 字节:类型 0x{struct.unpack(">H", d[:2])[0]:04x}(Binding Success Response)、长度 {struct.unpack(">H", d[2:4])[0]}、事务编号与请求{"相同" if d[8:20] == r["req"][8:20] else "不同"};属性:' + ';'.join(f'{AN.get(t, hex(t))}({len(v)} 字节)' for t, v in r['attrs']))
t, v = [(t, v) for t, v in r1['attrs'] if t == 0x0020][0]
print(f'  XOR-MAPPED-ADDRESS 的值 {len(v)} 字节:保留 1 + 地址族 {v[1]}(1 = IPv4)+ 端口 2 字节 + 地址 4 字节;线上的端口字段 0x{struct.unpack(">H", v[2:4])[0]:04x},与 0x{MAGIC >> 16:04x}(cookie 的高 16 位)异或得 {struct.unpack(">H", v[2:4])[0] ^ (MAGIC >> 16)},我的本地端口是 {lp},{"相同" if struct.unpack(">H", v[2:4])[0] ^ (MAGIC >> 16) == lp else "不同"}(NAT 没改端口);地址 4 个字节与 cookie 异或还原(公网地址不写出)')
if r1['xor'] and any(t == 0x0001 for t, _ in r1['attrs']):
    mp = plain(dict(r1['attrs'])[0x0001]); print(f'  同一个应答里还有旧式的 MAPPED-ADDRESS(不异或):与 XOR 还原的地址 / 端口{"一致" if mp == r1["xor"] else "不一致"}——旧版 STUN 直接写明文地址,会被某些改写载荷里 IP 地址的 NAT/ALG 破坏,异或就是为了避开它们')
pk = [(ts, bytes(dpkt.ethernet.Ethernet(b).data)) for ts, b in dpkt.pcap.Reader(open(c.pcap, 'rb'))]
print(f'  抓包:{len(pk)} 个 IP 包,请求 IP 总长 {struct.unpack(">H", pk[0][1][2:4])[0]} 字节(20 IP + 8 UDP + 20 STUN),两个应答的 IP 总长 {sorted({struct.unpack(">H", p[2:4])[0] for _, p in pk[1:]})} 字节;往返 RTT:服务器 2 {r1["rtt"]:.0f} ms、服务器 3 {r3["rtt"]:.0f} ms')

print('== 二:映射行为(RFC 5780):同一个本地套接字发往服务器的 4 个“目的”(主 IP:主端口、主 IP:另一个端口、另一个 IP:主端口、另一个 IP:另一个端口),看 NAT 给的外部地址 / 端口是否变化。能做这个测试的服务器要通告 OTHER-ADDRESS')
def mapping_test(name, ip_, p):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('0.0.0.0', 0)); lp_ = s.getsockname()[1]
    a = ask(s, (ip_, p))
    if not a or not a['other']: print(f'  {name}:不通告 OTHER-ADDRESS,没法做 RFC 5780 的映射测试'); return None
    oi, op = a['other']; res_ = [('主 IP:主端口', a['xor'])]
    for nm, dst in (('主 IP:另一个端口', (ip_, op)), ('另一个 IP:主端口', (oi, p)), ('另一个 IP:另一个端口', (oi, op))):
        b = ask(s, dst); res_.append((nm, b['xor'] if b else None))
    ports = [x[1][1] if x[1] else None for x in res_]; ips = {x[1][0] for x in res_ if x[1]}
    beh = '与目的无关的映射(EIM)' if len(set(ports)) == 1 and len(ips) == 1 and None not in ports else '依赖目的的映射(地址或端口相关)'
    print(f'  {name}(本地端口 {lp_}):' + ';'.join(f'{k_} → 外部端口 {v[1] if v else "无应答"}' for k_, v in res_) + f';公网地址是否一致:{len(ips) == 1};结论:{beh}')
    return beh
for nm, ip_, p in SERV: mapping_test(nm, ip_, p)

print('== 三:过滤行为(RFC 5780):先向服务器发一个请求(给服务器开个洞),再让服务器用“另一个 IP 和端口”(CHANGE-REQUEST 0x06)或“同 IP 另一个端口”(0x02)回应,看能不能收到')
def filter_test(name, ip_, p):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('0.0.0.0', 0))
    a = ask(s, (ip_, p))
    if not a or not a['other']: print(f'  {name}:不通告 OTHER-ADDRESS,没法做过滤测试'); return
    r1_ = ask(s, (ip_, p), change=0x06, timeout=2.0)
    r2_ = ask(s, (ip_, p), change=0x02, timeout=2.0)
    f1 = f'收到(应答来自 {"另一个 IP" if r1_ and r1_["src"][0] != ip_ else "同 IP"}:{"另一个端口" if r1_ and r1_["src"][1] != p else "同端口"})' if r1_ else '没收到'
    f2 = f'收到(应答来自 {"另一个 IP" if r2_ and r2_["src"][0] != ip_ else "同 IP"}:{"另一个端口" if r2_ and r2_["src"][1] != p else "同端口"})' if r2_ else '没收到'
    beh = '与目的无关的过滤(全锥)' if r1_ else ('地址受限过滤' if r2_ else '两种都没收到——既可能是 NAT 的过滤,也可能是服务器根本没实现 CHANGE-REQUEST,这里无法区分')
    print(f'  {name}:CHANGE-REQUEST 换 IP 和端口 → {f1};只换端口 → {f2};结论:{beh}')
for nm, ip_, p in SERV: filter_test(nm, ip_, p)
print('  本机的 NAT:映射行为测出来是与目的无关(第二节);过滤行为没有测出来——公共 STUN 服务器大多不再实现 CHANGE-REQUEST(RFC 5780 已把这套测试标成可选),所以两种都没收到不能说明是端口受限。若收到了换 IP 的应答才能确定是全锥')

print('== 四:STUN 自己的可靠性:跑在 UDP 上,客户端按 RFC 5389 重传:初始 RTO 500 ms,每次翻倍,最多发 7 次,总等待约 39.5 秒(计算);下面对各服务器各发 8 个请求量 RTT')
rto = 0.5; t_ = 0; sched = []
for i in range(7):
    sched.append(round(t_, 1)); t_ += rto; rto = rto * 2 if i < 5 else rto
print(f'  重传时刻(计算,秒):{sched};第 7 次发出后再等 16 × 500 ms = 8 秒才放弃,总共 {sched[-1] + 8:.1f} 秒')
for nm, ip_, p in SERV:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); rt = []
    for _ in range(8):
        a = ask(s, (ip_, p), timeout=1.0)
        if a: rt.append(a['rtt'])
        time.sleep(0.2)
    print(f'  {nm}:8 个请求收到 {len(rt)} 个应答' + (f',RTT 最小 {min(rt):.0f} / 中位 {statistics.median(rt):.0f} / 最大 {max(rt):.0f} ms' if rt else ''))

print('== 五:UDP 打洞的原理(模拟,不是实测):两个内网主机 A、B 各在一个 NAT 后面,都先向公网的会合服务器 S 发 UDP,S 把各自观察到的外部地址告诉对方,然后两边同时向对方的外部地址发包。四种 NAT(锥形三种 + 对称)两两组合,能不能打通')
class Nat:
    def __init__(self, pub, mapping, filt):
        self.pub = pub; self.mapping = mapping; self.filt = filt; self.next = 40000; self.maps = {}; self.sent = collections.defaultdict(set)
    def out(self, internal, dst):
        key = (internal,) if self.mapping == 'eim' else ((internal, dst[0]) if self.mapping == 'adm' else (internal, dst))
        if key not in self.maps: self.maps[key] = self.next; self.next += 1
        ep = self.maps[key]; self.sent[ep].add(dst); return (self.pub, ep)
    def inbound(self, ext_port, src):
        if ext_port not in self.sent: return False
        s_ = self.sent[ext_port]
        if self.filt == 'eif': return True
        if self.filt == 'adf': return any(x[0] == src[0] for x in s_)
        return src in s_
TYPES = [('全锥', 'eim', 'eif'), ('地址受限', 'eim', 'adf'), ('端口受限', 'eim', 'apdf'), ('对称', 'apdm', 'apdf')]
S = ('203.0.113.100', 3478)
def punch(ta, tb):
    A = Nat('198.51.100.1', ta[1], ta[2]); B = Nat('198.51.100.2', tb[1], tb[2])
    aep = A.out('A:5000', S); bep = B.out('B:5000', S)          # 会合服务器看到的外部地址
    a_to = bep; b_to = aep; got_a = got_b = False
    for rnd in range(3):
        src_a = A.out('A:5000', a_to); src_b = B.out('B:5000', b_to)       # 两边同时发
        if b_to == aep or True:
            if B.inbound(a_to[1], src_a) and a_to[0] == B.pub: got_b = True; b_to = src_a        # B 收到后把对方的实际源地址当作新目的
            if A.inbound(b_to[1], src_b) and b_to[0] == A.pub: got_a = True; a_to = src_b
    src_a = A.out('A:5000', a_to); src_b = B.out('B:5000', b_to)
    if B.inbound(a_to[1], src_a) and a_to[0] == B.pub: got_b = True
    if A.inbound(b_to[1], src_b) and b_to[0] == A.pub: got_a = True
    return got_a and got_b
names = [t[0] for t in TYPES]
print('    A \\\\ B      ' + ''.join(f'{n:<10}' for n in names))
ok = 0
for ta in TYPES:
    row = []
    for tb in TYPES:
        r_ = punch(ta, tb); ok += r_; row.append('通' if r_ else '不通')
    print(f'    {ta[0]:<10}' + ''.join(f'{x:<10}' for x in row))
print(f'  16 种组合里 {ok} 种能打通;打不通的是“对称 + 端口受限”和“对称 + 对称”(对称 NAT 给每个目的分配不同的外部端口,对方按 S 看到的端口去发,过滤规则不认)。这类情况只能走中继服务器(TURN)')
