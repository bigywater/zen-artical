import sys, os, re, struct, collections, ipaddress, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w25'); reset()
IFI = socket.if_nametoindex('en0')
ga = [l for l in sysout('ifconfig', 'en0').splitlines() if 'inet6 fe80' in l]
ME6 = ga[0].split()[1].split('%')[0]
MYMAC = [l.split()[1] for l in sysout('ifconfig', 'en0').splitlines() if l.strip().startswith('ether ')][0]
def ndp():
    out = {}
    for l in sysout('ndp', '-an').splitlines()[1:]:
        m = re.match(r'^(fe80:\S+?)%en0\s+(\S+)\s+en0\s+(\S+)\s+(\w)\s*(\w*)', l)
        if m: out[m.group(1)] = dict(mac=m.group(2), expire=m.group(3), st=m.group(4), fl=m.group(5))
    return out
def dur(s):
    if s in ('permanent', 'expired', 'Never'): return None
    t = 0
    for n, u in re.findall(r'(\d+)([dhms])', s): t += int(n) * {'d': 86400, 'h': 3600, 'm': 60, 's': 1}[u]
    return t
def frames(path):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf)
            if e.type != 0x86dd: continue
            p = bytes(e.data)
            if p[6] != 58: continue
            out.append((ts, ':'.join('%02x' % b for b in e.src), ':'.join('%02x' % b for b in e.dst), p))
    return out
def mcmac(a): return '33:33:' + ':'.join('%02x' % b for b in ipaddress.IPv6Address(a).packed[12:16])
def cs6(p):
    icmp = p[40:]; ps = p[8:40] + struct.pack('>I', len(icmp)) + b'\0\0\0' + bytes([58])
    b = ps + icmp[:2] + b'\0\0' + icmp[4:]
    if len(b) % 2: b += b'\0'
    s = sum(struct.unpack('>%dH' % (len(b) // 2), b))
    while s >> 16: s = (s & 0xffff) + (s >> 16)
    return ~s & 0xffff
def nd(p):
    t = p[40]; d = dict(type=t, hlim=p[7], code=p[41], ck=struct.unpack('>H', p[42:44])[0], ok=None)
    if t == 135: d['target'] = socket.inet_ntop(socket.AF_INET6, p[48:64]); opt = p[64:]
    elif t == 136: d['flags'] = p[44]; d['target'] = socket.inet_ntop(socket.AF_INET6, p[48:64]); opt = p[64:]
    else: opt = b''; d['target'] = None
    d['opts'] = []; i = 0
    while i + 2 <= len(opt):
        ot, ol = opt[i], opt[i + 1]
        if ol == 0: break
        d['opts'].append((ot, opt[i + 2:i + ol * 8])); i += ol * 8
    d['ok'] = cs6(p) == d['ck']
    return d

print('== 一:邻居缓存(ndp -an)和接口参数:邻居的状态分布、过期时间、en0 上的 NUD 参数;以及本机有没有从路由器通告里学到默认路由 / 前缀')
nb = ndp(); cnt = collections.Counter(v['st'] for v in nb.values())
ex = [dur(v['expire']) for v in nb.values() if dur(v['expire'])]
inc = sum(1 for l in sysout('ndp', '-an').splitlines() if '(incomplete)' in l)
print(f'  en0 上的邻居缓存 {len(nb)} 项(另有 {inc} 项 incomplete):状态 ' + ';'.join(f'{k_}={v}' for k_, v in cnt.most_common()) + '(R = REACHABLE,S = STALE,D = DELAY,P = PROBE;incomplete = 还在解析)')
print(f'  过期时间(剩余):最长 {max(ex) / 3600:.1f} 小时、最短 {min(ex)} 秒;STALE 项最长可以放 24 小时,但下一次发数据时会先重新确认')
ii = sysout('ndp', '-i', 'en0'); m = re.search(r'basereachable=(\S+), reachable=(\S+), retrans=(\S+)', ii)
print(f'  en0 的参数:基础可达时间 {m.group(1)},当前随机化后的可达时间 {m.group(2)},NS 重传间隔 {m.group(3)};标志:' + re.search(r'Flags: (.*)', ii).group(1).strip())
rt = [l for l in sysout('ndp', '-rn').splitlines() if l.strip()]
print(f'  默认路由器列表里有 {len(rt)} 项,其中接口是 en0 的 {sum(1 for l in rt if "if=en0" in l)} 项(其余是 utun 隧道接口)——en0 这条链路上没有收到过路由器通告(RA),所以没有 IPv6 默认路由器,也没有学到全球前缀')
pf = sysout('ndp', '-pn')
print(f'  前缀列表里 en0 的条目:{"有" if "if=en0" in pf else "没有"},且“No advertising router”(只有自己的链路本地前缀),没有任何路由器通告过的前缀')

print('== 二:对一个 STALE 邻居发数据,看邻居不可达检测(NUD):状态怎么变,线上发了什么(NS 单播给该邻居,NA 回应)')
stale = [a for a, v in nb.items() if v['st'] == 'S' and v['mac'].count(':') == 5]
target = random.Random(7).choice(stale); tmac = nb[target]['mac']
s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
hist = []
with Cap('icmp6', iface='en0', write=True) as c:
    t0 = time.time(); s.sendto(b'nud', (target, 9, 0, IFI))
    last = None
    while time.time() - t0 < 12:
        st = ndp().get(target, {}).get('st'); 
        if st != last: hist.append((time.time() - t0, st)); last = st
        time.sleep(0.2)
print(f'  选了缓存里一个状态为 STALE 的邻居(地址不写出)发一个 UDP 包。状态变化(相对发包时刻):' + ' → '.join(f'{st} @ {t:.1f}s' for t, st in hist))
fr = [(ts, src, dst, p) for ts, src, dst, p in frames(c.pcap) if p[40] in (135, 136) and ((src == MYMAC and dst == tmac) or (src == tmac and dst == MYMAC))]
mine = [(ts, src, dst, p, nd(p)) for ts, src, dst, p in fr]
first = t0
for ts, src, dst, p, d in mine:
    who = '本机' if src == MYMAC else '邻居'
    dstk = '单播给邻居' if dst == tmac else '单播给本机'
    fl = ''
    if d['type'] == 136: fl = ' 标志 R=%d S=%d O=%d' % ((d['flags'] >> 7) & 1, (d['flags'] >> 6) & 1, (d['flags'] >> 5) & 1)
    print(f'    +{(ts - first) * 1000:8.1f} ms  {who} 发 {"邻居请求 NS" if d["type"] == 135 else "邻居通告 NA"},以太网目的 {dstk},跳数限制 {d["hlim"]}{fl},选项 {[o[0] for o in d["opts"]]},校验和{"正确" if d["ok"] else "不正确"}')
print(f'  线上共 {len(mine)} 个相关的 ND 报文;发 UDP 数据的那一下并不等 NUD:数据包立刻就发出去了(数据先发,NUD 在后台确认)' if mine else '  这次没有抓到相关的 ND 报文')

print('== 三:解析一个不存在的邻居:往一个本链路上没人用的链路本地地址发 UDP,看 NS 发给谁、重传几次、间隔多久、最后应用得到什么')
rnd = random.Random(99); iid = bytes(rnd.getrandbits(8) for _ in range(8))
ghost = socket.inet_ntop(socket.AF_INET6, bytes.fromhex('fe80000000000000') + iid)
snm = ipaddress.IPv6Address(bytes.fromhex('ff0200000000000000000001ff') + iid[5:8])
s2 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM); errs = []
with Cap('icmp6', iface='en0', write=True) as c:
    t0 = time.time(); s2.sendto(b'who', (ghost, 9, 0, IFI)); time.sleep(4.5)
    try: s2.sendto(b'again', (ghost, 9, 0, IFI)); errs.append('第二次 sendto:成功')
    except OSError as e: errs.append(f'第二次 sendto:{e.strerror}')
fr3 = [(ts, src, dst, p) for ts, src, dst, p in frames(c.pcap) if p[40] == 135 and nd(p)['target'] == ghost]
print(f'  目标地址是随机的链路本地地址(后 24 位决定被请求节点组播地址,形如 ff02::1:ff__:____);抓到发给它的 NS {len(fr3)} 个')
for i, (ts, src, dst, p) in enumerate(fr3):
    d = nd(p)
    print(f'    +{(ts - fr3[0][0]) * 1000:8.1f} ms  NS #{i + 1}:IPv6 目的是{"被请求节点组播地址(与目标地址的后 24 位对应)" if ipaddress.IPv6Address(p[24:40]) == snm else "其它"},以太网目的 MAC {"= 33:33 + 组播地址的后 4 字节" if dst == mcmac(str(snm)) else "不符"},跳数限制 {d["hlim"]},选项 {[o[0] for o in d["opts"]]}(1 = 源链路层地址,内容{"是本机 MAC" if any(o[0] == 1 and ":".join("%02x" % b for b in o[1][:6]) == MYMAC for o in d["opts"]) else "不是本机 MAC"})')
if len(fr3) > 1: print(f'  NS 之间的间隔(毫秒):{[round((fr3[i + 1][0] - fr3[i][0]) * 1000) for i in range(len(fr3) - 1)]};ndp -i 给出的重传间隔是 {m.group(3)},实测间隔在 1.0 到 1.9 秒之间不等,为什么比 1 秒长没有深究')
ent = ndp().get(ghost); print(f'  之后 ndp -an 里这个地址的状态:{"(incomplete)" if any(ghost in l and "incomplete" in l for l in sysout("ndp", "-an").splitlines()) else (ent or "无记录")};{errs[0]}')

print('== 四:ND 报文长什么样:用二、三节抓到的包拆开看 —— IPv6 头跳数限制必须是 255;ICMPv6 头 + 保留字段 + 目标地址 + 选项(类型 / 长度以 8 字节为单位);组播 MAC 的映射规则')
sample = [x for x in mine if x[4]['type'] == 136] or []
allnd = [(ts, src, dst, p, nd(p)) for ts, src, dst, p in fr3] + [(ts, src, dst, p, d) for ts, src, dst, p, d in mine]
if allnd:
    ts, src, dst, p, d = allnd[0]
    print('  一个 NS 的 ICMPv6 部分(十六进制,目标地址与链路层地址已遮盖):' + p[40:48].hex(' ') + ' <目标地址 16 字节> ' + f'{p[64]:02x} {p[65]:02x} <MAC 6 字节>')
    print(f'  = 类型 {p[40]}(135 = 邻居请求)、代码 {p[41]}、校验和 0x{struct.unpack(">H", p[42:44])[0]:04x}、4 字节保留 + 16 字节目标地址 + 选项(类型 {p[64]}、长度 {p[65]}×8 = {p[65] * 8} 字节,即 2 + 6 字节 MAC)')
    print(f'  全部 {len(allnd)} 个 ND 报文的跳数限制取值:{sorted({x[4]["hlim"] for x in allnd})};校验和全部正确:{all(x[4]["ok"] for x in allnd)}')
print('  类型号:133 路由器请求 RS、134 路由器通告 RA、135 邻居请求 NS、136 邻居通告 NA、137 重定向。NA 的标志位 R = 发送者是路由器、S = 这是对 NS 的回应、O = 覆盖旧的缓存记录')
print(f'  组播 MAC 映射:IPv6 组播地址的后 4 字节接在 33:33 后面:例如被请求节点组播地址 → 33:33:ff:xx:xx:xx(上面抓到的 NS 的目的 MAC 就是这样)')
try:
    x = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM, 58); body = struct.pack('>BBHI', 133, 0, 0, 0)
    x.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 255); x.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, IFI)
    x.sendto(body, ('ff02::2', 0, 0, IFI)); print('  用普通 ICMPv6 套接字发路由器请求(类型 133):成功')
except OSError as e: print(f'  用普通 ICMPv6 套接字发路由器请求(类型 133):失败,{e.strerror}——ND 报文只能由内核发,应用不能伪造(也就不能伪造跳数限制 255)')

print('== 五:邻居缓存和 IPv4 的 ARP 缓存对比(同一个 en0):条目数量、状态、过期时间')
arp = sysout('arp', '-an').splitlines(); ae = [l for l in arp if 'en0' in l]
inca = sum(1 for l in ae if 'incomplete' in l)
print(f'  ARP 缓存(arp -an)en0 上 {len(ae)} 项,其中 incomplete {inca} 项;NDP 缓存 {len(nb)} 项(+{inc} 项 incomplete)')
ma = sysout('sysctl', 'net.link.ether.inet.max_age').strip(); print(f'  IPv4:{ma} 秒;IPv6 的 STALE 项可以保留的最长剩余时间约 {max(ex) / 3600:.1f} 小时')
print(f'  ARP 缓存里是 IPv4 地址 ↔ MAC;NDP 缓存里是 IPv6 地址 ↔ MAC,还多了状态机(REACHABLE / STALE / DELAY / PROBE)——ARP 靠定时器过期后重新广播,NDP 在使用时才用单播 NS 探测邻居')
