import sys, os, re, struct, collections, ipaddress, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w33'); reset()
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
_t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); _t.connect((gw, 9)); ME = _t.getsockname()[0]; _t.close()
TY = {0x11: '成员查询', 0x12: 'IGMPv1 报告', 0x16: 'IGMPv2 报告', 0x17: 'IGMPv2 离开', 0x22: 'IGMPv3 报告'}
def mreq(g): return socket.inet_aton(g) + socket.inet_aton(ME)
def cs(b):
    if len(b) % 2: b += b'\0'
    s = sum(struct.unpack('>%dH' % (len(b) // 2), b))
    while s >> 16: s = (s & 0xffff) + (s >> 16)
    return ~s & 0xffff
def igmps(path):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf)
            if e.type != 0x0800: continue
            ip = bytes(e.data)
            if ip[9] != 2: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; m = ip[ihl:tl_]
            out.append(dict(ts=ts, src=socket.inet_ntoa(ip[12:16]), dst=socket.inet_ntoa(ip[16:20]), ttl=ip[8], ihl=ihl, msg=m, type=m[0], mac=':'.join('%02x' % b for b in e.dst), mine=socket.inet_ntoa(ip[12:16]) == ME))
    return out
def cnt():
    o = sysout('netstat', '-s', '-p', 'igmp'); d = {}
    for k_, pat in (('recv', r'(\d+) messages received\n'), ('q', r'(\d+) V1/V2 membership queries'), ('rep_rx', r'(\d+) membership reports received\n'), ('sent', r'(\d+) membership reports sent')):
        m = re.search(pat, o); d[k_] = int(m.group(1)) if m else None
    return d

print('== 一:本机的 IGMP 设置(sysctl)和 netstat -s -p igmp 的累计计数')
print('  ' + '\n  '.join(l for l in sysout('sysctl', 'net.inet.igmp').splitlines() if l.strip() and 'debug' not in l and 'kludge' not in l))
c0 = cnt(); print(f'  netstat -s -p igmp 累计:收到 IGMP 报文 {c0["recv"]} 个,其中 V1/V2 成员查询 {c0["q"]} 个,成员报告 {c0["rep_rx"]} 个(大多是别的设备发的),本机发出的成员报告 {c0["sent"]} 个')
print('  default_version = 3:本机默认说 IGMPv3;但收到 V1/V2 查询时会按对方的版本降级回应(见第三节抓到的报告类型)')

print('== 二:加入组再离开,看线上的 IGMP 报文:报告重发几次、间隔多久,离开时发什么,逐字节解码并验证校验和')
G = '239.255.42.99'; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
with Cap('igmp', iface='en0', write=True) as c:
    t0 = time.time(); s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq(G)); time.sleep(8)
    t1 = time.time(); s.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq(G)); time.sleep(4)
for tag, lo, hi in (('加入', t0, t1), ('离开', t1, t1 + 5)):
    L = [m for m in igmps(c.pcap) if m['mine'] and lo - 0.05 <= m['ts'] <= hi]
    print(f'  {tag}后本机发出 IGMP 报文 {len(L)} 个(只算与本节操作相关的、源地址是本机的)')
    for m in L:
        mm = m['msg']; ok = cs(mm) == 0
        grp = socket.inet_ntoa(mm[4:8]) if m['type'] in (0x11, 0x12, 0x16, 0x17) else None
        extra = f',组地址 {"= " + G if grp == G else grp}' if grp else ''
        if m['type'] == 0x22:
            nrec = struct.unpack('>H', mm[6:8])[0]; rt = mm[8]; ag = socket.inet_ntoa(mm[12:16])
            extra = f',记录数 {nrec},第一条记录类型 {rt}({ {1: "MODE_IS_INCLUDE", 2: "MODE_IS_EXCLUDE", 3: "TO_INCLUDE", 4: "TO_EXCLUDE", 5: "ALLOW", 6: "BLOCK"}.get(rt, "?") }),组 {"= " + G if ag == G else ag}'
        print(f'    +{(m["ts"] - lo) * 1000:7.0f} ms  {TY.get(m["type"], hex(m["type"]))}(0x{m["type"]:02x}),IP 目的 {m["dst"]},以太网目的 {m["mac"]},TTL {m["ttl"]},IP 头 {m["ihl"]} 字节,IGMP 部分 {len(mm)} 字节{extra},校验和{"正确" if ok else "不正确"}')
print('  IGMPv2 报文固定 8 字节:类型 1 + 最大响应时间 1(单位 0.1 秒)+ 校验和 2 + 组地址 4;校验和是对这 8 字节做的互联网校验和(第 17 篇)')

print('== 三:被动听 180 秒:局域网里有没有 IGMP 查询者、多久查询一次、最大响应时间;本机(已加入两个组)怎么回应;别的设备的报告只统计个数')
G1 = '239.255.42.101'; G2 = '239.255.42.102'
r1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
r1.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq(G1)); r2.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq(G2))
ca = cnt(); tstart = time.time()
with Cap('igmp', iface='en0', write=True) as c:
    time.sleep(180)
cb = cnt(); L = igmps(c.pcap)
typ = collections.Counter(m['type'] for m in L)
qs = [m for m in L if m['type'] == 0x11]
print(f'  180 秒共抓到 {len(L)} 个 IGMP 报文:' + ';'.join(f'{TY.get(k_, hex(k_))} {v}' for k_, v in typ.most_common()))
print(f'  本机发出 {sum(1 for m in L if m["mine"])} 个,别的设备发出 {sum(1 for m in L if not m["mine"])} 个(只统计个数)')
if qs:
    qk = collections.Counter((m['dst'], len(m['msg'])) for m in qs); mr = collections.Counter(m['msg'][1] for m in qs)
    print(f'  成员查询 {len(qs)} 个:目的地址/IGMP 长度 {dict(qk)}(224.0.0.1 = 所有主机;长度 8 = IGMPv1/v2 查询,≥12 = IGMPv3 查询),最大响应时间字段取值 {dict(mr)}(单位 0.1 秒),TTL {sorted({m["ttl"] for m in qs})},查询者{"是默认网关" if all(m["src"] == gw for m in qs) else "不全是默认网关"}')
    iv = [round(qs[i + 1]['ts'] - qs[i]['ts'], 1) for i in range(len(qs) - 1)]
    print(f'  相邻查询的间隔(秒):{iv}' + (f';中位 {statistics.median(iv)} 秒' if iv else ''))
    lat = []
    for q in qs:
        for m in L:
            if m['mine'] and m['type'] in (0x16, 0x22) and 0 <= m['ts'] - q['ts'] <= 15: lat.append((m['ts'] - q['ts']) * 1000)
    print(f'  每次查询之后 15 秒内本机发出的报告 {len(lat)} 个,与查询的延迟(毫秒):{sorted(round(x) for x in lat)}——查询里的最大响应时间是 {qs[0]["msg"][1] / 10:.1f} 秒,本机在 0 到最大响应时间之间随机选一个时间回应' if lat else '  查询之后 15 秒内本机没有发报告')
    mine_types = collections.Counter(m['type'] for m in L if m['mine'])
    print(f'  本机发出的报告类型:' + ';'.join(f'{TY.get(k_, hex(k_))} {v}' for k_, v in mine_types.items()))
else: print('  180 秒里没有抓到任何成员查询——这个网段上可能没有 IGMP 查询者,或者间隔比 180 秒长')
print(f'  netstat 累计的变化(180 秒):收到 IGMP 报文 +{cb["recv"] - ca["recv"]},V1/V2 成员查询 +{cb["q"] - ca["q"]},成员报告 +{cb["rep_rx"] - ca["rep_rx"]},本机发出的成员报告 +{cb["sent"] - ca["sent"]}')

print('== 四:别的设备发的 IGMP 报告长什么样(同一段抓包,只统计,不写设备地址):按组地址、报告者数量、TTL、校验和统计')
reps = [m for m in L if not m['mine'] and m['type'] == 0x16]
bygrp = collections.Counter(socket.inet_ntoa(m['msg'][4:8]) for m in reps)
KNOWN = {'224.0.0.251': 'mDNS', '224.0.0.252': 'LLMNR', '239.255.255.250': 'SSDP', '224.0.0.22': 'IGMPv3 报告', '224.0.0.1': '所有主机'}
print(f'  {len(reps)} 个 IGMPv2 报告来自 {len({m["src"] for m in reps})} 个不同的源地址,涉及 {len(bygrp)} 个不同的组;TTL 取值 {sorted({m["ttl"] for m in reps})};校验和正确的 {sum(1 for m in reps if cs(m["msg"]) == 0)} / {len(reps)};IP 头长度取值 {sorted({m["ihl"] for m in reps})} 字节(24 = 带 Router Alert 选项);最大响应时间字段(报告里恒为 0)取值 {sorted({m["msg"][1] for m in reps})}')
print('  按组统计:' + ';'.join(f'{g}{"(" + KNOWN[g] + ")" if g in KNOWN else ""} {n}' for g, n in bygrp.most_common(8)) + (f';其余 {len(bygrp) - 8} 个组' if len(bygrp) > 8 else ''))
dm = collections.Counter(m['dst'] == socket.inet_ntoa(m['msg'][4:8]) for m in reps)
print(f'  IGMPv2 报告的 IP 目的地址就是被报告的那个组({dm.get(True, 0)} / {len(reps)} 个符合);所以同一个组里的其它成员也能收到它——这就是“报告抑制”的基础:听到别人已经报告了同一个组,自己就不再发')
