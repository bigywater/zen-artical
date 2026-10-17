import sys, os, re, struct, collections, ipaddress, hashlib, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w26'); reset()
def sc(k_): return sysout('sysctl', '-n', k_).strip()

print('== 一:本机和 SLAAC / 邻居发现有关的内核参数(sysctl),以及各接口的链路本地地址是怎么生成的(是不是由 MAC 推出的 EUI-64)')
for k_ in ('net.inet6.ip6.accept_rtadv', 'net.inet6.ip6.auto_linklocal', 'net.inet6.ip6.use_tempaddr', 'net.inet6.ip6.temppltime', 'net.inet6.ip6.tempvltime', 'net.inet6.ip6.dad_count', 'net.inet6.icmp6.nd6_optimistic_dad', 'net.inet6.ip6.auto_flowlabel', 'net.inet6.icmp6.nd6_delay', 'net.inet6.icmp6.nd6_mmaxtries', 'net.inet6.icmp6.nd6_umaxtries'):
    print(f'  {k_} = {sc(k_)}')
print(f'  临时地址:首选寿命 {int(sc("net.inet6.ip6.temppltime")) // 3600} 小时、有效寿命 {int(sc("net.inet6.ip6.tempvltime")) // 86400} 天(use_tempaddr = {sc("net.inet6.ip6.use_tempaddr")},1 表示启用隐私扩展);nd6_delay = {sc("net.inet6.icmp6.nd6_delay")} 秒,就是上一篇看到的 DELAY 阶段长度;auto_flowlabel = {sc("net.inet6.ip6.auto_flowlabel")},就是第 23 篇里内核自动填流标签的开关')
def eui64(macs):
    b = bytearray(int(x, 16) for x in macs.split(':')); b[0] ^= 2
    return bytes(b[:3]) + b'\xff\xfe' + bytes(b[3:])
o = sysout('ifconfig'); cur = None; cases = []; macs = {}
for l in o.splitlines():
    m = re.match(r'^(\w+): flags=', l)
    if m: cur = m.group(1); continue
    m = re.match(r'^\s+ether (\S+)', l)
    if m and cur: macs[cur] = m.group(1)
    m = re.match(r'^\s+inet6 (fe80\S+?)%\w+ prefixlen', l)
    if m and cur: cases.append((cur, m.group(1), l))
res = []
for ifn, a, l in cases:
    iid = ipaddress.IPv6Address(a).packed[8:]
    if ifn in macs: res.append((ifn, '有 MAC', iid == eui64(macs[ifn]), 'secured' in l))
    else: res.append((ifn, '无 MAC(隧道)', None, 'secured' in l))
for ifn, hasmac, eq, secured in res:
    print(f'    {ifn:<7}{hasmac:<14}' + (f'接口标识符{"= MAC 推出的 EUI-64" if eq else "不是 EUI-64"}' if eq is not None else '接口标识符无法与 MAC 比较') + ('(地址标志 secured)' if secured else ''))
print(f'  有 MAC 的接口 {sum(1 for r in res if r[2] is not None)} 个,其中链路本地地址是 EUI-64 的 {sum(1 for r in res if r[2])} 个')

print('== 二:SLAAC 地址怎么拼(计算,不是抓来的):假设路由器通告了前缀 2001:db8:1:2::/64,同一台机器的三种接口标识符——EUI-64、稳定不透明(RFC 7217 风格)、临时(RFC 8981 风格)')
mac = '00:11:22:33:44:55'; prefix = ipaddress.IPv6Network('2001:db8:1:2::/64')
e = eui64(mac)
print('  (示例 MAC 用 00:11:22:33:44:55,不是本机的 MAC)')
print(f'  1. EUI-64:接口标识符 = MAC 中间插 ff:fe 并翻转第 7 位 → {":".join(e[i:i + 2].hex() for i in range(0, 8, 2))}(由 MAC 决定,在任何网络里都一样)')
def stable(prefix, ifname, secret=b'host-secret', dad=0):
    h = hashlib.sha256(prefix.network_address.packed[:8] + ifname.encode() + secret + bytes([dad])).digest(); return h[:8]
s1 = stable(prefix, 'en0'); s2 = stable(ipaddress.IPv6Network('2001:db8:9:9::/64'), 'en0'); s1b = stable(prefix, 'en0')
print(f'  2. 稳定不透明:接口标识符 = 哈希(前缀, 接口名, 本机秘密值, DAD 计数)的前 64 位 → {":".join(s1[i:i + 2].hex() for i in range(0, 8, 2))};同一前缀每次算出相同:{s1 == s1b};换一个前缀(2001:db8:9:9::/64)得到 {":".join(s2[i:i + 2].hex() for i in range(0, 8, 2))},不同:{s1 != s2}')
rng = random.Random(1); temps = [bytes(rng.getrandbits(8) for _ in range(8)) for _ in range(3)]
print('  3. 临时地址:每个首选寿命周期重新随机生成:' + ';'.join(':'.join(t[i:i + 2].hex() for i in range(0, 8, 2)) for t in temps))
mk = lambda iid: ipaddress.IPv6Address(prefix.network_address.packed[:8] + iid)
print(f'  拼出来的地址:EUI-64 {mk(e)}、稳定 {mk(s1)}、临时 {mk(temps[0])}')
print('  EUI-64 的缺点:同一个设备走到任何网络,后 64 位都不变,可以被跟踪;稳定不透明地址在一个网络内不变、换网络就变;临时地址对外连接用,定期更换')
e_other = lambda p: ipaddress.IPv6Address(p.network_address.packed[:8] + e)
print(f'  同一台机器在两个网络(前缀 2001:db8:1:2::/64 与 2001:db8:9:9::/64)里:EUI-64 地址后 64 位{"相同" if e_other(prefix).packed[8:] == e_other(ipaddress.IPv6Network("2001:db8:9:9::/64")).packed[8:] else "不同"},稳定地址后 64 位{"相同" if s1 == s2 else "不同"}')

print('== 三:被动听 120 秒的 ND 流量(en0):路由器请求 RS、路由器通告 RA、邻居请求 NS、邻居通告 NA、DAD 探测(NS 的源地址是 ::)各有多少个——只统计个数')
with Cap('icmp6', iface='en0', write=True) as c:
    time.sleep(120)
cnt = collections.Counter(); dad = 0; ns_snm = ns_uni = 0
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        e_ = dpkt.ethernet.Ethernet(buf)
        if e_.type != 0x86dd: continue
        p = bytes(e_.data)
        if p[6] != 58: continue
        t = p[40]; cnt[t] += 1
        if t == 135:
            if p[8:24] == b'\0' * 16: dad += 1
            elif p[24:27] == bytes.fromhex('ff0200'): ns_snm += 1
            else: ns_uni += 1
NAMES = {128: '回显请求', 129: '回显应答', 130: 'MLD 查询', 131: 'MLDv1 报告', 133: 'RS 路由器请求', 134: 'RA 路由器通告', 135: 'NS 邻居请求', 136: 'NA 邻居通告', 137: '重定向', 143: 'MLDv2 报告'}
print(f'  120 秒共抓到 {sum(cnt.values())} 个 ICMPv6 报文:' + ';'.join(f'{NAMES.get(k_, k_)} {v}' for k_, v in sorted(cnt.items())))
print(f'  其中 NS 里:源地址是 ::(DAD 探测,有设备在检查自己要用的地址有没有人占用){dad} 个;目的是被请求节点组播的 {ns_snm} 个;单播的(NUD 探测){ns_uni} 个')
print(f'  RA 路由器通告 {cnt.get(134, 0)} 个——{"这条链路上有路由器在发通告" if cnt.get(134, 0) else "120 秒内没有任何路由器通告(RA 的发送间隔通常是几分钟,但本机的 ndp -rn 也显示 en0 上没有路由器,见上一篇)"}')

print('== 四:没有 IPv6 路由器时应用看到什么:getaddrinfo 是否还返回 IPv6 地址(AI_ADDRCONFIG),去往全球 IPv6 地址的路由,以及 connect 的错误')
import dns.resolver
rs = dns.resolver.Resolver(configure=False); rs.nameservers = ['1.1.1.1']; rs.lifetime = 4
aaaa = [a.address for a in rs.resolve('example.com', 'AAAA')]; a4 = [a.address for a in rs.resolve('example.com', 'A')]
print(f'  经 DNS 查 example.com:A 记录 {len(a4)} 个、AAAA 记录 {len(aaaa)} 个(DNS 里有 IPv6 地址)')
gi = lambda flags: socket.getaddrinfo('example.com', 80, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, flags)
for nm, fl in (('默认', 0), ('AI_ADDRCONFIG', socket.AI_ADDRCONFIG)):
    try: r = gi(fl); fam = collections.Counter('IPv6' if x[0] == socket.AF_INET6 else 'IPv4' for x in r); print(f'  getaddrinfo(example.com, 80) 使用 {nm}:返回 {len(r)} 项:{dict(fam)};第一项是 {"IPv6" if r[0][0] == socket.AF_INET6 else "IPv4"}')
    except Exception as e: print(f'  getaddrinfo 使用 {nm}:失败 {e}')
r6 = sysout('route', '-n', 'get', '-inet6', aaaa[0])
rl = {k_.strip(): v.strip() for k_, v in (l.split(':', 1) for l in r6.splitlines() if ':' in l)}
print(f'  route get -inet6 到 example.com 的一个 IPv6 地址:{priv(r6.strip().splitlines()[0]) if r6.strip() else "无输出"};' + (f'接口 {rl.get("interface", "?")},标志 {rl.get("flags", "?")}' if rl else ''))
s = socket.socket(socket.AF_INET6); s.settimeout(3); t0 = time.time()
try: s.connect((aaaa[0], 80)); print('  connect 成功')
except Exception as ex: print(f'  connect 到该 IPv6 地址:{type(ex).__name__}: {getattr(ex, "strerror", ex)},用时 {(time.time() - t0) * 1000:.1f} ms——没有 IPv6 路由,内核立刻失败,不用等超时')
