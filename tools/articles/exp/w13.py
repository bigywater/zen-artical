import sys, os, re, ipaddress, struct; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w13'); reset()
TARGET = '104.20.23.154'      # example.com 的一个公网地址

def cls(a):
    """只给地址分类,不写出别人的地址"""
    if a == '*': return '无应答'
    ip = ipaddress.ip_address(a)
    if str(ip).startswith('192.168.'): return '本机局域网网关' 
    if ip.is_private: return '私有地址'
    return '公网地址'

def parse_tr(txt):
    """-n 输出 → {跳数: [(地址或*, rtt或None), ...]};同一跳的续行(换了地址)并入同一跳"""
    hops = {}; n = None
    for l in txt.splitlines():
        m = re.match(r'^\s*(\d+)\s+(.*)$', l)
        if m and not l.startswith('traceroute') and re.match(r'^\s*\d+ ', l) and not re.match(r'^\s{3,}', l): n = int(m.group(1)); rest = m.group(2)
        elif n is not None and re.match(r'^\s+\d+\.\d+\.\d+\.\d+', l): rest = l.strip()
        else: continue
        hops.setdefault(n, []); cur = None; toks = rest.split(); i = 0
        while i < len(toks):
            t = toks[i]
            if t == '*': hops[n].append(('*', None)); i += 1
            elif re.match(r'^\d+\.\d+\.\d+\.\d+$', t): cur = t; i += 1
            elif re.match(r'^[\d.]+$', t) and i + 1 < len(toks) and toks[i + 1] == 'ms': hops[n].append((cur, float(t))); i += 2
            else: i += 1
    return hops

def trace(target, q=1, m=30, w=1):
    return parse_tr(sysout('traceroute', '-n', '-q', str(q), '-m', str(m), '-w', str(w), target, timeout=200))

print('== 一:TTL 的默认值和作用:系统默认 TTL;套接字上读 / 改 IP_TTL;TTL=1 的包能走多远(ping 的 -m 选项设置 TTL)')
print('  ' + sysout('sysctl', 'net.inet.ip.ttl').strip())
for kind, typ in (('TCP', socket.SOCK_STREAM), ('UDP', socket.SOCK_DGRAM)):
    s = socket.socket(socket.AF_INET, typ); a = s.getsockopt(socket.IPPROTO_IP, socket.IP_TTL)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, 7); b = s.getsockopt(socket.IPPROTO_IP, socket.IP_TTL); s.close()
    print(f'  {kind} 套接字 getsockopt(IP_TTL) 默认 = {a};setsockopt 设成 7 以后读回 = {b}')
r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('127.0.0.1', 0)); r.settimeout(2)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, 1)
with Cap('udp port %d' % r.getsockname()[1], iface='lo0', write=True) as c:
    s.sendto(b'ttl1', r.getsockname()); data, _ = r.recvfrom(100)
pk = read_pcap(c.pcap)
print(f'  给本机(127.0.0.1)发 TTL=1 的 UDP 包:对方收到 {data!r};抓到的包 TTL = {pk[0][1].ttl}——不经过路由器,TTL 不会被减')
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
for ttl in (1, 2, 3):
    o = sysout('ping', '-c', '1', '-m', str(ttl), '-t', '3', TARGET)
    ex = re.search(r'bytes from ([\d.]+): Time to live exceeded', o)
    print(f'  ping -m {ttl} 到公网地址:' + (f'第 {ttl} 跳的路由器回了 “Time to live exceeded”(它是{cls(ex.group(1))})' if ex else '没有收到 Time to live exceeded'))
o = sysout('ping', '-c', '1', '-m', '1', '-t', '3', gw)
print('  ping -m 1 到默认网关(它就是目的地,不需要再转发):' + ('收到应答' if '1 packets received' in o or '1 received' in o else '没有应答'))

print('== 二:系统 traceroute 到一个公网地址,逐跳的结果(每跳 3 个探测;别人的路由器地址不写出来,只写类别和 RTT)')
tr3 = trace(TARGET, q=3, m=30, w=1)
last = max(tr3)
for n in sorted(tr3):
    its = tr3[n]; got = [r for a, r in its if a != '*']
    kinds = sorted({cls(a) for a, _ in its if a != '*'}); nad = len({a for a, _ in its if a != '*'})
    if got: print(f'  第 {n:>2} 跳  {len(got)}/3 个应答  来自 {nad} 个不同地址  RTT {" / ".join(f"{x:.1f}" for x in got)} ms  ({"、".join(kinds)})')
    else: print(f'  第 {n:>2} 跳  0/3 个应答  (* * *)')
reach = [n for n in tr3 if any(a == TARGET for a, _ in tr3[n])]
silent = [n for n in sorted(tr3) if all(a == '*' for a, _ in tr3[n])]
multi = [n for n in sorted(tr3) if len({a for a, _ in tr3[n] if a != '*'}) > 1]
print(f'  目的地在第 {min(reach) if reach else "(没有应答)"} 跳应答;全部无应答的跳:{silent}(共 {len(silent)} 个);同一跳的 3 个探测来自不止一个地址的跳有 {len(multi)} 个({multi});最大 RTT {max(r for n in tr3 for a, r in tr3[n] if r):.1f} ms')

print('== 三:抓包看 traceroute 的探测:每个 UDP 探测包的 TTL 和目的端口,以及路由器回的 ICMP 里引用的原始包')
def icmp_info(raw):
    ihl = (raw[0] & 15) * 4; src = socket.inet_ntoa(raw[12:16]); t, code = raw[ihl], raw[ihl + 1]
    q = raw[ihl + 8:]; qihl = (q[0] & 15) * 4
    return dict(src=src, ttl=raw[8], type=t, code=code, qttl=q[8], qdst=socket.inet_ntoa(q[16:20]), qdport=struct.unpack('>H', q[qihl + 2:qihl + 4])[0], qsport=struct.unpack('>H', q[qihl:qihl + 2])[0])
flt = f'(icmp[icmptype]==11 or icmp[icmptype]==3) or (udp and dst host {TARGET})'
with Cap(flt, iface='en0', write=True) as c:
    sysout('traceroute', '-n', '-q', '1', '-m', '20', '-w', '1', TARGET, timeout=60)
sent = []; rep = []
for ts, ip in read_pcap(c.pcap):
    raw = ip.raw
    if raw[9] == 17 and socket.inet_ntoa(raw[16:20]) == TARGET:
        ihl = (raw[0] & 15) * 4; sp, dp, ul = struct.unpack('>HHH', raw[ihl:ihl + 6])
        sent.append(dict(ts=ts, ttl=raw[8], dport=dp, sport=sp, iplen=struct.unpack('>H', raw[2:4])[0], ulen=ul))
    elif raw[9] == 1:
        try:
            d = icmp_info(raw)
            if d['qdst'] == TARGET: d['ts'] = ts; rep.append(d)
        except Exception: pass
byport = {d['qdport']: d for d in rep}
print(f'  抓到 {len(sent)} 个 UDP 探测包、{len(rep)} 个 ICMP 回复(类型 11 = Time Exceeded,类型 3 = Destination Unreachable)')
print('    序号  发出的 TTL  目的端口  IP 总长  UDP 长度  →  回复 ICMP 类型/代码  引用原包里的 TTL  引用的目的端口  回复包自己的 TTL  RTT')
for i, p in enumerate(sent):
    d = byport.get(p['dport'])
    if d: print(f'    {i + 1:>3}   {p["ttl"]:>6}      {p["dport"]}   {p["iplen"]:>5}   {p["ulen"]:>6}      {d["type"]:>2}/{d["code"]}                {d["qttl"]:>3}               {d["qdport"]}          {d["ttl"]:>3}       {(d["ts"] - p["ts"]) * 1000:6.1f} ms')
    else: print(f'    {i + 1:>3}   {p["ttl"]:>6}      {p["dport"]}   {p["iplen"]:>5}   {p["ulen"]:>6}      无回复')
ports = [p['dport'] for p in sent]
print(f'  目的端口从 {ports[0]} 开始,每个探测加 1(到 {ports[-1]});源端口都是同一个:{len({p["sport"] for p in sent}) == 1};所有探测 IP 总长都是 {sorted({p["iplen"] for p in sent})[0]} 字节(UDP 长度 {sorted({p["ulen"] for p in sent})[0]},载荷 {sorted({p["ulen"] for p in sent})[0] - 8} 字节)')
tm = [d for d in rep if d['type'] == 11]; un = [d for d in rep if d['type'] == 3]
print(f'  Time Exceeded {len(tm)} 个:引用原包里的 TTL 全是 {sorted({d["qttl"] for d in tm})}(被引用的是路由器丢弃它时手里的那份包头);Destination Unreachable {len(un)} 个:代码 {sorted({d["code"] for d in un})}(3 = 端口不可达),来自目的地本身:{all(d["src"] == TARGET for d in un)}')
print(f'  回复包自己的 TTL 取值: {sorted({d["ttl"] for d in rep})}——前三跳依次是 64、63、62(同一类设备,每多一跳回程少 1),后面几跳是 252、248、246……(接近 255,是另一类设备)')

print('== 四:自己实现 traceroute:UDP 套接字设 IP_TTL=1..N 发探测,从抓包里读 ICMP 回复(没有原始套接字权限);然后和系统 traceroute 逐跳对比,再对无应答的跳重复探测')
def probes(target, ttls, base_port, gap=0.04, wait=3.0):
    flt = f'(icmp[icmptype]==11 or icmp[icmptype]==3) or (udp and dst host {target})'
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    with Cap(flt, iface='en0', write=True) as c:
        for i, ttl in enumerate(ttls):
            s.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl); s.sendto(b'w13-traceroute', (target, base_port + i)); time.sleep(gap)
        time.sleep(wait)
    s.close()
    tx = {}; rx = {}
    for ts, ip in read_pcap(c.pcap):
        raw = ip.raw
        if raw[9] == 17 and socket.inet_ntoa(raw[16:20]) == target:
            ihl = (raw[0] & 15) * 4; dp = struct.unpack('>H', raw[ihl + 2:ihl + 4])[0]; tx[dp] = (ts, raw[8])
        elif raw[9] == 1:
            try:
                d = icmp_info(raw)
                if d['qdst'] == target: rx[d['qdport']] = (ts, d)
            except Exception: pass
    res = []
    for i, ttl in enumerate(ttls):
        dp = base_port + i
        if dp in rx and dp in tx: res.append((ttl, rx[dp][1]['src'], (rx[dp][0] - tx[dp][0]) * 1000, rx[dp][1]['type']))
        else: res.append((ttl, '*', None, None))
    return res, len(tx)
tr1 = trace(TARGET, q=1, m=30, w=1)
sweeps = {}
for base, gap in ((33435, 0.04), (33435, 0.25), (33435, 1.0), (34500, 0.25)):
    res, ntx = probes(TARGET, list(range(1, 21)), base, gap=gap)
    sweeps[(base, gap)] = res
    got = [r for r in res if r[1] != '*']
    print(f'  目的端口从 {base} 起、间隔 {int(gap * 1000)} ms 发 TTL=1~20 共 {len(res)} 个探测(抓包确认发出 {ntx} 个):收到 ICMP 回复 {len(got)} 个;其中来自目的地本身的有 {sum(1 for r in got if r[1] == TARGET)} 个')
best = max(sweeps, key=lambda g: sum(1 for r in sweeps[g] if r[1] != '*'))
mine = sweeps[best]
same = diff = onlyme = onlysys = 0
for ttl, a, rtt, t in mine:
    sysa = [x for x, _ in tr1.get(ttl, []) if x != '*']
    if a != '*' and sysa: same += (a == sysa[0]); diff += (a != sysa[0])
    elif a != '*': onlyme += 1
    elif sysa: onlysys += 1
print(f'  取回复最多的一轮(端口 {best[0]} 起、间隔 {int(best[1] * 1000)} ms)和系统 traceroute(-q 1)逐跳对比:两边都有应答的跳里地址相同 {same} 个、不同 {diff} 个;只有我的有应答 {onlyme} 个、只有系统的有应答 {onlysys} 个')
fin = [ttl for ttl, a, rtt, t in mine if a == TARGET]
silent_mine = [ttl for ttl, a, rtt, t in mine if a == '*' and ttl < (min(fin) if fin else 99)][:4]
tot = {}
for ttl in silent_mine:
    r, _ = probes(TARGET, [ttl] * 8, 33435, gap=1.0, wait=2.0)
    tot[ttl] = sum(1 for x in r if x[1] != '*')
print(f'  那一轮里无应答的中间跳(取前 4 个):{silent_mine}。对每个再间隔 1 s 发 8 个探测:' + ';'.join(f'TTL={k} 收到 {v}/8' for k, v in tot.items()) + '——“*” 只表示这次没收到回复,不一定是路由器不存在;不回的原因这里没有验证')

print('== 五:不用 traceroute 也能估跳数:收到的包的 TTL 靠近哪个常见初始值(32 / 64 / 128 / 255),和 traceroute 实测、能连通的最小 TTL 对比')
cands = [('104.20.23.154', 80), ('172.66.147.243', 80), ('1.1.1.1', 80), ('8.8.8.8', 443), ('223.5.5.5', 443)]
alive = []
with Cap('tcp and (tcp[tcpflags] & (tcp-syn|tcp-ack)) = (tcp-syn|tcp-ack)', iface='en0', write=True) as c:
    for ip, port in cands:
        try:
            s = socket.create_connection((ip, port), timeout=3); s.close(); alive.append((ip, port))
        except Exception: pass
        time.sleep(0.3)
synack = {}
for ts, ip in read_pcap(c.pcap):
    raw = ip.raw
    if raw[9] == 6: synack.setdefault(socket.inet_ntoa(raw[12:16]), raw[8])
print(f'  试了 {len(cands)} 个公网目的地,TCP 能连通 {len(alive)} 个')
rows = []
for ip, port in alive:
    ttl = synack.get(ip)
    if ttl is None: continue
    init = min(x for x in (32, 64, 128, 255) if x >= ttl); est = init - ttl + 1
    t1 = trace(ip, q=1, m=30, w=1); hit = [n for n in t1 if any(a == ip for a, _ in t1[n])]
    rows.append((ip, ttl, init, est, min(hit) if hit else None))
print('    目的地     SYN-ACK 的 TTL  推测初始值  按 TTL 估的跳数(初始值−TTL+1)  traceroute 实测到达的跳数')
for k, (ip, ttl, init, est, real) in enumerate(rows, 1):
    print(f'    目的地{k}        {ttl:>3}            {init:>3}                 {est:>2}                       {real if real else "未到达"}')
print(f'  估计与实测相同的有 {sum(1 for r in rows if r[3] == r[4])} / {len(rows)} 个;差值(估计−实测):{[r[3] - r[4] if r[4] else None for r in rows]}')
# 最小可连通 TTL
for ip, ttl, init, est, real in rows[:2]:
    ok = None; errs = {}
    for n in range(1, (real or est) + 4):
        s = socket.socket(); s.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, n); s.settimeout(1.2)
        e = s.connect_ex((ip, 80 if ip != '8.8.8.8' else 443)); s.close()
        errs[n] = e
        if e == 0: ok = n; break
    k = rows.index((ip, ttl, init, est, real)) + 1
    fails = {n: e for n, e in errs.items() if e != 0}
    cnt = {}
    for n, e in fails.items(): cnt.setdefault(e, []).append(n)
    print(f'  给目的地 {k} 的 TCP 连接设 IP_TTL=n 再 connect(超时 1.2 s):n={ok} 是第一次成功的;n 更小时都失败,错误码分布 ' + ';'.join(f'{os.strerror(e)}({e}): n={v}' for e, v in cnt.items()) + f';traceroute 说该目的地在第 {real} 跳')
