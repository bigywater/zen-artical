import sys, os, re, struct, collections, ipaddress, subprocess, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt, dns.message, dns.rdatatype, dns.rdataclass, dns.name
tee('w35'); reset()
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
_t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); _t.connect((gw, 9)); ME = _t.getsockname()[0]; _t.close()
HOST = sysout('scutil', '--get', 'LocalHostName').strip()
ST = re.compile(r'^_[a-z0-9-]+\._(tcp|udp)\.local\.?$', re.I)
def parse(w):
    try: return dns.message.from_wire(w, ignore_trailing=True)
    except Exception: return None

print('== 一:mDNS 的地址与端口:224.0.0.251:5353(IPv4)/ ff02::fb(IPv6),TTL 255;在 en0 上被动听 60 秒,统计 mDNS 流量(别的设备的内容只统计个数,具体名字不写出)')
with Cap('udp port 5353', iface='en0', write=True) as c:
    time.sleep(60)
fr = []; ttl = collections.Counter(); dstk = collections.Counter(); srcs = set(); qr = collections.Counter(); qt = collections.Counter(); qu = qtot = 0; sts = collections.Counter(); lens = []; named = 0; fam = collections.Counter(); known = qmsgs = tc = 0; ttlh = collections.Counter(); cflush = 0; nans = 0; adds = collections.Counter()
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(buf)
        if e.type == 0x0800: ip = bytes(e.data); ihl = (ip[0] & 15) * 4; payload = ip[ihl + 8:]; src = socket.inet_ntoa(ip[12:16]); dst = socket.inet_ntoa(ip[16:20]); t = ip[8]; fam['IPv4'] += 1
        elif e.type == 0x86dd: ip = bytes(e.data); payload = ip[48:]; src = ip[8:24]; dst = socket.inet_ntop(socket.AF_INET6, ip[24:40]); t = ip[7]; fam['IPv6'] += 1
        else: continue
        srcs.add(src); ttl[t] += 1; dstk[dst if dst in ('224.0.0.251', 'ff02::fb') else '单播'] += 1; lens.append(len(buf))
        m = parse(payload)
        if not m: continue
        isresp = bool(m.flags & 0x8000); qr['应答' if isresp else '查询'] += 1
        if m.flags & 0x0200: tc += 1
        if not isresp:
            qmsgs += 1
            if m.answer: known += 1
        else:
            for rrs in m.answer:
                nans += 1; ttlh['0(告别)' if rrs.ttl == 0 else ('≤10' if rrs.ttl <= 10 else ('120' if rrs.ttl == 120 else ('4500' if rrs.ttl == 4500 else '其它')))] += 1
                if rrs.rdclass & 0x8000: cflush += 1
        for q in m.question:
            qtot += 1; qt[dns.rdatatype.to_text(q.rdtype)] += 1
            if q.rdclass & 0x8000: qu += 1
            nm = q.name.to_text()
            if ST.match(nm) or nm.startswith('_services._dns-sd._udp'): sts[nm.rstrip('.')] += 1
            else: named += 1
n = sum(fam.values())
print(f'  60 秒共 {n} 个 mDNS 包({dict(fam)}),{len(srcs)} 个不同的源地址;{n / 60:.1f} 包/秒;包长 中位 {statistics.median(lens):.0f} / 最大 {max(lens)} 字节')
print(f'  IP 目的:{dict(dstk)};TTL / 跳数限制取值:{dict(ttl)}——mDNS 要求 255,接收方据此确认包没有经过路由器')
print(f'  DNS 报文类型:{dict(qr)};问题总数 {qtot},类型分布 {dict(qt)};带 QU 位(请求单播应答)的问题 {qu} 个')
print(f'  问题名字里,服务类型名(形如 _xxx._tcp.local)出现 {sum(sts.values())} 次,最多的:' + ';'.join(f'{k_} {v}' for k_, v in sts.most_common(6)) + f';指向具体设备 / 服务实例的名字 {named} 次(名字不写出)')

print('== 二:自己发一个 mDNS 查询:问“_services._dns-sd._udp.local”的 PTR(列出局域网里所有服务类型)。用随机源端口发(这叫传统单播查询),有人用单播直接回给我;统计应答来源与内容')
q = dns.message.make_query('_services._dns-sd._udp.local', 'PTR'); q.id = 0; w = q.to_wire()
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255); s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ME)); s.settimeout(0.3)
t0 = time.time(); s.sendto(w, ('224.0.0.251', 5353)); got = []
while time.time() - t0 < 4:
    try: d, a = s.recvfrom(9000); got.append((time.time() - t0, a, d))
    except socket.timeout: pass
print(f'  查询共 {len(w)} 字节(DNS 头 12 + 名字 {len(w) - 12 - 4} + 类型 / 类 4);源端口是随机的 {s.getsockname()[1]}(不是 5353),所以应答是单播的')
types = collections.Counter(); ttls = set(); fl = collections.Counter(); first = None
for dt, a, d in got:
    m = parse(d)
    if not m: continue
    fl[f'ID={m.id} QR={(m.flags >> 15) & 1} AA={(m.flags >> 10) & 1}'] += 1
    for rr in m.answer:
        ttls.add(rr.ttl)
        if rr.rdtype == dns.rdatatype.PTR:
            for it in rr: types[it.target.to_text().rstrip('.')] += 1
    if first is None: first = dt
print(f'  4 秒内收到 {len(got)} 个应答,来自 {len({a[0] for _, a, _ in got})} 个不同的源地址;第一个应答在 {first * 1000:.0f} ms 后到达;最后一个在 {max(dt for dt, _, _ in got) * 1000:.0f} ms' if got else '  没有收到应答')
print(f'  应答头:{dict(fl)}(传统单播应答里 ID 回显了查询的 ID = 0,AA = 1 表示权威);记录 TTL 取值 {sorted(ttls)}(传统单播应答的 TTL 不超过 10 秒)')
print(f'  发现的服务类型 {len(types)} 种,被多少个应答提到:' + ';'.join(f'{k_} ×{v}' for k_, v in types.most_common(8)))

print('== 三:Bonjour 发现的完整链条:PTR(有哪些实例)→ SRV + TXT(实例在哪台主机、哪个端口)→ A / AAAA(那台主机的地址),用 _airplay._tcp 这个服务类型,每一步计时(实例名、主机名、地址、TXT 内容都不写出)')
def ask(name, rts, wait=1.5, qu=False):
    q = dns.message.make_query(name, rts[0]); q.id = 0
    for rt in rts[1:]: q.question.append(dns.rrset.from_text(name, 0, 'IN', rt))
    s_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s_.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255); s_.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ME)); s_.settimeout(0.2)
    w_ = q.to_wire(); t0 = time.time(); s_.sendto(w_, ('224.0.0.251', 5353)); out = []
    while time.time() - t0 < wait:
        try: d, a = s_.recvfrom(9000); m = parse(d); out.append((time.time() - t0, a, m, len(d)))
        except socket.timeout: pass
    return len(w_), out
import dns.rrset
ql, resp = ask('_airplay._tcp.local', ['PTR'], 2.0)
inst = []; addl = collections.Counter()
for dt, a, m, ln in resp:
    if not m: continue
    for rr in m.answer:
        if rr.rdtype == dns.rdatatype.PTR:
            for it in rr: inst.append(it.target)
    for rr in m.additional: addl[dns.rdatatype.to_text(rr.rdtype)] += 1
inst = list(dict.fromkeys(inst))
print(f'  第 1 步 PTR 问 _airplay._tcp.local:查询 {ql} 字节,2 秒内 {len(resp)} 个应答({len({a[0] for _, a, _, _ in resp})} 个设备),发现 {len(inst)} 个不同的服务实例;第一个应答 {resp[0][0] * 1000:.0f} ms 后到达;应答里附带的“附加记录”(提前帮你答了后面几步)类型分布 {dict(addl)}' if resp else '  第 1 步没有应答')
for k_, name in enumerate(inst[:2]):
    ql2, r2 = ask(name.to_text(), ['SRV', 'TXT'], 1.0)
    srv = txt = None; hostn = None; port = None
    for dt, a, m, ln in r2:
        if not m: continue
        for rr in list(m.answer) + list(m.additional):
            if rr.rdtype == dns.rdatatype.SRV and srv is None: srv = (dt, rr[0].priority, rr[0].weight, rr[0].port); hostn = rr[0].target; port = rr[0].port
            if rr.rdtype == dns.rdatatype.TXT and txt is None: txt = (dt, sum(len(x) for x in rr[0].strings), len(rr[0].strings))
    print(f'  实例 {k_ + 1}  第 2 步 SRV + TXT:查询 {ql2} 字节(一个报文里问 2 个问题);' + (f'SRV 在 {srv[0] * 1000:.0f} ms 后到达,优先级 {srv[1]}、权重 {srv[2]}、端口 {srv[3]};' if srv else '没有 SRV;') + (f'TXT 在 {txt[0] * 1000:.0f} ms 后到达,{txt[2]} 个键值对共 {txt[1]} 字节' if txt else '没有 TXT'))
    if hostn is not None:
        ql3, r3 = ask(hostn.to_text(), ['A', 'AAAA'], 1.0)
        got4 = got6 = 0; t_ = None
        for dt, a, m, ln in r3:
            if not m: continue
            for rr in list(m.answer) + list(m.additional):
                if rr.rdtype == dns.rdatatype.A: got4 += len(rr); t_ = t_ or dt
                if rr.rdtype == dns.rdatatype.AAAA: got6 += len(rr); t_ = t_ or dt
        print(f'          第 3 步 A + AAAA 问那台主机:{"第一个地址在 " + format(t_ * 1000, ".0f") + " ms 后到达" if t_ else "没有应答"};IPv4 地址 {got4} 个、IPv6 地址 {got6} 个')
print('  三步合起来就是 Bonjour 的“浏览 → 解析 → 地址”:先知道有哪些实例(PTR),再知道实例的主机和端口(SRV)与参数(TXT),最后拿到主机的地址(A / AAAA);每一步都是一次组播查询')

print('== 四:系统解析器怎么处理 .local:getaddrinfo 解析自己的 .local 名字、一个不存在的 .local 名字,看耗时(.local 走 mDNS,不走 DNS 服务器)')
def gai(name):
    t0 = time.time()
    try: r = socket.getaddrinfo(name, 80, socket.AF_UNSPEC, socket.SOCK_STREAM); res = f'{len(r)} 个地址'
    except Exception as e: res = f'失败:{type(e).__name__}: {getattr(e, "args", [""])[-1]}'
    return time.time() - t0, res
for nm, name in (('本机的 .local 名字', f'{HOST}.local'), ('本机的 .local 名字(第二次)', f'{HOST}.local'), ('不存在的 .local 名字', 'no-such-host-w35.local'), ('不存在的 .local 名字(第二次)', 'no-such-host-w35.local'), ('不存在的普通名字(对照,走 DNS)', 'no-such-host-w35.example.invalid')):
    dt, res = gai(name); print(f'  {nm}:{dt * 1000:.0f} ms,{res}')

print('== 五:报文细节统计(同一段 60 秒被动抓包):已知答案抑制、TC 位、记录 TTL、cache-flush 位')
print(f'  查询报文 {qmsgs} 个,其中带“已知答案”(查询里已经带了应答记录,告诉对方“这些我有了,不用再答”)的 {known} 个;TC(截断)位置位的报文 {tc} 个')
print(f'  应答报文里共 {nans} 条应答记录,TTL 分布:' + ';'.join(f'{k_} × {v}' for k_, v in ttlh.most_common()) + f';cache-flush 位置位的记录 {cflush} 条')
print('  已知答案抑制让多个设备都在问同一个服务时,不会让所有人重复回答已经缓存的内容;TTL 为 0 的记录是“告别包”,通知别人立刻删掉缓存;cache-flush 位表示这条记录是该名字下唯一的一组,可以替换旧缓存')
