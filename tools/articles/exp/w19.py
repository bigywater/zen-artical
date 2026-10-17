import sys, os, re, struct, ipaddress, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dns.resolver
tee('w19'); reset()
PUB = '104.20.23.154'
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
_t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); _t.connect((gw, 9)); ME = _t.getsockname()[0]; _t.close()
rs = dns.resolver.Resolver(configure=False); rs.nameservers = ['1.1.1.1']; rs.lifetime = 4
def res(n): return rs.resolve(n, 'A')[0].address
SERV = [('服务器 1', res('stun.cloudflare.com'), 3478), ('服务器 2', res('global.stun.twilio.com'), 3478), ('服务器 3', res('stun.miwifi.com'), 3478)]
MAGIC = 0x2112A442
def parse(d):
    i = 20
    while i + 4 <= len(d):
        t, l = struct.unpack('>HH', d[i:i + 4]); v = d[i + 4:i + 4 + l]
        if t == 0x0020: return socket.inet_ntoa(bytes(a ^ b for a, b in zip(v[4:8], struct.pack('>I', MAGIC)))), struct.unpack('>H', v[2:4])[0] ^ (MAGIC >> 16)
        if t == 0x0001: return socket.inet_ntoa(v[4:8]), struct.unpack('>H', v[2:4])[0]
        i += 4 + ((l + 3) // 4 * 4)
def stun_udp(sock, addr, timeout=2):
    sock.settimeout(timeout); sock.sendto(struct.pack('>HHI', 1, 0, MAGIC) + os.urandom(12), addr)
    try: d, _ = sock.recvfrom(2000)
    except Exception: return None
    return parse(d)
def stun_tcp(sock, timeout=3):
    sock.settimeout(timeout); sock.send(struct.pack('>HHI', 1, 0, MAGIC) + os.urandom(12))
    try: d = sock.recv(2000)
    except Exception: return None
    return parse(d)
def cls(ip):
    a = ipaddress.ip_address(ip)
    if a in ipaddress.ip_network('100.64.0.0/10'): return '运营商级 NAT 地址段 100.64/10'
    return '私有地址' if a.is_private else '公网地址'

print('== 一:STUN 绑定请求:向公网 STUN 服务器发 UDP,服务器把它看到的源地址和端口回给你。对比本机套接字的地址(私有)和服务器看到的(NAT 之后)。公网 IP 是本机出口的地址,不写出来,只比较')
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('0.0.0.0', 0)); lp = s.getsockname()[1]
maps = []
for nm, ip, p in SERV:
    m = stun_udp(s, (ip, p)); maps.append((nm, m))
ok = [m for nm, m in maps if m]
print(f'  本机套接字:地址是{cls(ME)}(本机局域网地址),本地端口 {lp}')
for nm, m in maps: print(f'  {nm}看到的:' + (f'地址是{cls(m[0])},端口 {m[1]}' if m else '没有回应'))
ips = {m[0] for m in ok}; ports = {m[1] for m in ok}
print(f'  {len(ok)} 个服务器有回应:它们看到的公网地址互相{"相同" if len(ips) == 1 else "不同"}(不同的值 {len(ips)} 个),端口{"相同" if len(ports) == 1 else "不同"}(不同的值 {len(ports)} 个);服务器看到的公网地址与本机地址{"相同(没有 NAT)" if ME in ips else "不同"}')
print(f'  同一个本地套接字发往 {len(ok)} 个不同的目的地,映射到同一个外部地址和端口:{len(set(ok)) == 1}——这叫“与目的无关的映射”(endpoint-independent mapping)')
print(f'  服务器看到的端口 {sorted(ports)} 与本地端口 {lp}{"相同" if ports == {lp} else "不同"}:NAT 没有改端口(端口保留)' if len(ports) == 1 else '')

print('== 二:端口保留是不是总成立:用 40 个不同本地端口的 UDP 套接字(随机端口 + 几个固定端口)各发一次,比较外部看到的端口;再看 TCP')
same = diff = fail = 0; changed = []
socks = []
fixed = [5000, 5060, 9000, 12345, 40000, 4500]
for fp in fixed + [0] * 34:
    t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: t.bind(('0.0.0.0', fp))
    except OSError: t.bind(('0.0.0.0', 0))
    m = stun_udp(t, (SERV[0][1], SERV[0][2]), 2)
    if not m: fail += 1
    elif m[1] == t.getsockname()[1]: same += 1
    else: diff += 1; changed.append((t.getsockname()[1], m[1]))
    socks.append(t)
print(f'  UDP:{same + diff + fail} 个套接字,外部端口与本地端口相同 {same} 个、不同 {diff} 个、没有回应 {fail} 个' + (f';不同的:{changed[:5]}' if changed else ''))
tcpres = []
for nm, ip, p in SERV:
    try:
        k = socket.socket(); k.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); k.bind(('0.0.0.0', 0)); lp2 = k.getsockname()[1]; k.settimeout(3); k.connect((ip, p))
        m = stun_tcp(k); k.close()
        tcpres.append((nm, lp2, m))
    except Exception as e: tcpres.append((nm, None, None))
for nm, lp2, m in tcpres:
    if m: print(f'  TCP {nm}:本地端口 {lp2},外部看到 {m[1]}({"相同" if m[1] == lp2 else "不同"}),地址是{cls(m[0])}')
    else: print(f'  TCP {nm}:没有拿到 STUN 回应(服务器可能不支持 TCP STUN)')

print('== 三:能不能用 traceroute 看出 NAT 在哪一跳:UDP 探测从固定本地端口发出,TTL 1~16;每一跳回的超时报文里引用了它收到的原包头,看里面的源地址和源端口')
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.bind(('0.0.0.0', 0)); up = u.getsockname()[1]
plan = [(ttl, 33700 + ttl * 3 + k_) for ttl in range(1, 17) for k_ in range(3)]
with Cap('icmp[icmptype]==11 or (udp and dst portrange 33700-33800)', iface='en0', write=True) as c:
    for ttl, port_ in plan:
        u.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl); u.sendto(b'n' * 12, (PUB, port_)); time.sleep(0.3)
    time.sleep(2)
quote = {}
for ts, ip in read_pcap(c.pcap):
    r_ = ip.raw; ihl = (r_[0] & 15) * 4
    if r_[9] == 1 and r_[ihl] == 11:
        q = r_[ihl + 8:]
        if len(q) >= 28:
            qi = (q[0] & 15) * 4; quote[struct.unpack('>H', q[qi + 2:qi + 4])[0]] = (socket.inet_ntoa(q[12:16]), struct.unpack('>H', q[qi:qi + 2])[0], socket.inet_ntoa(r_[12:16]))
firstpub = None
for ttl in range(1, 17):
    got = [quote[p] for t_, p in plan if t_ == ttl and p in quote]
    if not got: print(f'  TTL={ttl}:3 个探测都没有回应'); continue
    kinds = sorted({('本机局域网地址' if g[0] == ME else cls(g[0])) for g in got}); sp_same = all(g[1] == up for g in got)
    print(f'  TTL={ttl}:{len(got)}/3 个回应;该跳收到的包源地址是 {"、".join(kinds)};源端口{"与本机发出的相同" if sp_same else "与本机发出的不同"}')
    if firstpub is None and any(g[0] != ME for g in got): firstpub = ttl
resp = [ttl for ttl in range(1, 17) if any(p in quote for t_, p in plan if t_ == ttl)]
lanhops = [ttl for ttl in resp if any(quote.get(p, (None,))[0] == ME for t_, p in plan if t_ == ttl)]
print(f'  16 个 TTL 里 {len(resp)} 个有回应(第 {resp} 跳);其中引用的源地址是本机局域网地址的有 {len(lanhops)} 个,不是的有 {len(resp) - len(lanhops)} 个;引用的源端口与本机发出的相同的有 {sum(1 for ttl in resp if all(quote[p][1] == up for t_, p in plan if t_ == ttl and p in quote))} 个')
print('  第一节明明显示服务器看到的是改写之后的公网地址,但路径上远处的路由器回的差错里引用的却仍是本机局域网地址。我的解释是:NAT 设备在把差错报文送回内网时,把内嵌的原包头也翻译回了内网地址(NAT 处理 ICMP 差错时需要这样做,否则内网主机认不出这是自己的包)——这个解释没有直接验证。结论:用这种方法看不出 NAT 位于哪一跳')
print('== 四:NAPT 表的纸面模型(模拟,不是实测):3 台内网主机、5 个连接,公网地址 203.0.113.1;演示端口分配、冲突处理、回程翻译、未请求的入站包被丢、校验和增量更新')
def fold(s):
    while s >> 16: s = (s & 0xffff) + (s >> 16)
    return s
def upd(hc, old, new): return ~fold((~hc & 0xffff) + (~old & 0xffff) + new) & 0xffff
class Nat:
    def __init__(self, pub): self.pub = pub; self.out = {}; self.back = {}; self.next = 40000
    def outbound(self, proto, src, sport, dst, dport):
        k = (proto, src, sport, dst, dport)
        if k in self.out: return self.out[k]
        ext = sport if (proto, sport) not in self.back else None
        if ext is None:
            ext = self.next; self.next += 1
        self.out[k] = (self.pub, ext); self.back[(proto, ext)] = (src, sport, dst, dport); return self.out[k]
    def inbound(self, proto, dst_port, from_ip, from_port):
        e = self.back.get((proto, dst_port))
        if e and e[2] == from_ip and e[3] == from_port: return e[0], e[1]
        return None
nat = Nat('203.0.113.1')
flows = [('udp', '10.0.0.2', 5000, '198.51.100.7', 53), ('udp', '10.0.0.3', 5000, '198.51.100.7', 53), ('tcp', '10.0.0.2', 52111, '198.51.100.9', 443), ('tcp', '10.0.0.4', 52111, '198.51.100.9', 443), ('udp', '10.0.0.2', 5000, '198.51.100.8', 123)]
print('    内网连接                                    → 公网映射')
for f in flows:
    m = nat.outbound(*f); print(f'    {f[0]} {f[1]}:{f[2]} → {f[3]}:{f[4]:<4}  →  {m[0]}:{m[1]}')
print(f'  NAT 表里 {len(nat.out)} 条记录;两台主机都用源端口 5000 的 UDP:第一台映射到外部端口 {nat.out[flows[0]][1]}(保留),第二台因为 {nat.out[flows[0]][1]} 已被占用而换成 {nat.out[flows[1]][1]}')
r1 = nat.inbound('udp', nat.out[flows[0]][1], '198.51.100.7', 53); r2 = nat.inbound('udp', nat.out[flows[0]][1], '198.51.100.99', 53); r3 = nat.inbound('udp', 41234, '198.51.100.7', 53)
print(f'  回程翻译:来自 198.51.100.7:53 发往 {nat.out[flows[0]][1]} 的包 → {r1};来自没联系过的 198.51.100.99:53 的包 → {r2}(丢弃);发往没有记录的端口 41234 → {r3}(丢弃)')
# 校验和增量更新
hdr = struct.pack('>BBHHHBBH4s4s', 0x45, 0, 60, 1, 0x4000, 64, 17, 0, socket.inet_aton('10.0.0.2'), socket.inet_aton('198.51.100.7'))
def cs16(b):
    s = sum(struct.unpack('>%dH' % (len(b) // 2), b)); return ~fold(s) & 0xffff
hc = cs16(hdr); hdr = hdr[:10] + struct.pack('>H', hc) + hdr[12:]
old = struct.unpack('>2H', socket.inet_aton('10.0.0.2')); new = struct.unpack('>2H', socket.inet_aton('203.0.113.1'))
h2 = hc
for o_, n_ in zip(old, new): h2 = upd(h2, o_, n_)
newhdr = hdr[:10] + b'\0\0' + socket.inet_aton('203.0.113.1') + hdr[16:]
print(f'  改写源地址 10.0.0.2 → 203.0.113.1 以后的 IP 头校验和:增量更新 0x{h2:04x},整头重算 0x{cs16(newhdr):04x},{"一致" if h2 == cs16(newhdr) else "不一致"}(TCP / UDP 的校验和还要同样更新,因为伪头部含地址)')
