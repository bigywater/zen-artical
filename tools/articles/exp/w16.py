import sys, os, re, struct, ipaddress; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w16'); reset()
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
PUB = '104.20.23.154'
IP_DONTFRAG = 28

def raws(path): return [(ts, ip.raw) for ts, ip in read_pcap(path)]
def flags(raw): return struct.unpack('>H', raw[6:8])[0] >> 13      # 3 位:保留 / DF / MF
def udp_sock(df):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if df: s.setsockopt(socket.IPPROTO_IP, IP_DONTFRAG, 1)
    return s


def rtt_lines(c): return c.lines

print('== 一:本机对 DF 的处理:UDP 设了 DF(IP_DONTFRAG)发超过 MTU 的数据报,内核当场拒绝、线上一个包都没有;不设 DF 则被分片;再看各协议默认带不带 DF,以及内核里和 PMTUD 有关的参数')
for df, size in ((True, 1472), (True, 1473), (True, 4000), (False, 1473), (False, 4000)):
    s = udp_sock(df)
    with Cap(f'dst host {gw} and (udp dst port 9 or (ip[6:2] & 0x1fff != 0))', iface='en0', write=True) as c:
        try: s.sendto(b'x' * size, (gw, 9)); res = '发送成功'
        except OSError as e: res = f'{type(e).__name__}: [Errno {e.errno}] {e.strerror}'
        time.sleep(0.5)
    pk = raws(c.pcap)
    print(f'  DF={"置位" if df else "不置位"} 载荷 {size:>4} 字节(IP 总长 {size + 28}):{res};线上抓到 {len(pk)} 个 IP 包' + (f',IP 总长 {[struct.unpack(">H", r[2:4])[0] for _, r in pk]},DF 位 {[(flags(r) >> 1) & 1 for _, r in pk]}' if pk else ''))
r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('127.0.0.1', 0)); r.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20); r.settimeout(1)
s = udp_sock(True); s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
try: s.sendto(b'x' * 20000, r.getsockname()); d, _ = r.recvfrom(65535); res = f'发送成功,对方收到 {len(d)} 字节'
except OSError as e: res = f'{type(e).__name__}: [Errno {e.errno}] {e.strerror}'
print(f'  lo0(MTU 16384)DF 置位发 20000 字节 UDP:{res}')
with Cap(f'host {PUB} or host {gw}', iface='en0', write=True) as c:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b'u' * 20, (PUB, 33435)); time.sleep(0.3)
    sysout('ping', '-c', '1', gw); sysout('ping', '-c', '1', '-D', gw)
    k = socket.create_connection((PUB, 80), timeout=4); k.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'); k.recv(100); k.close(); time.sleep(0.5)
seen = {}
for ts, r_ in raws(c.pcap):
    src = socket.inet_ntoa(r_[12:16])
    if src.startswith('192.168'):
        ihl = (r_[0] & 15) * 4
        if r_[9] == 17: key = 'UDP(本机发出)'
        elif r_[9] == 6: key = 'TCP(本机发出)'
        elif r_[9] == 1 and r_[ihl] == 8: key = 'ICMP echo 请求(ping 默认)' if 'ICMP echo 请求(ping 默认)' not in seen else 'ICMP echo 请求(ping -D)'
        else: continue
        seen.setdefault(key, set()).add((flags(r_) >> 1) & 1)
for k_, v in seen.items(): print(f'  {k_:<26}DF 位 = {sorted(v)}')
for k_ in ('net.inet.tcp.path_mtu_discovery', 'net.inet.tcp.pmtud_blackhole_detection', 'net.inet.tcp.pmtud_blackhole_mss', 'net.inet.tcp.mssdflt'):
    print('  ' + sysout('sysctl', k_).strip())
def route_mtu(dst):
    o = sysout('route', '-n', 'get', dst).splitlines()
    i = [j for j, l in enumerate(o) if 'mtu' in l][0]; h = o[i].split(); v = o[i + 1].split()
    return int(v[h.index('mtu')]), [l.split()[-1] for l in o if 'interface:' in l][0]
for nm, dst in (('默认路由', 'default'), ('127.0.0.1', '127.0.0.1'), ('公网某主机', PUB)):
    m, ifc = route_mtu(dst); print(f'  route get {nm}:接口 {ifc},MTU = {m}')
print('  TCP 默认带 DF(靠 PMTUD 调整段长);UDP 和 ping 默认不带,放不下就被分片;ping -D 加上 DF')

def icmp_replies(rs):
    out = []
    for ts, r_ in rs:
        ihl = (r_[0] & 15) * 4
        if r_[9] == 1 and r_[ihl] in (3, 11):
            q = r_[ihl + 8:]
            if len(q) >= 28: out.append(dict(ts=ts, type=r_[ihl], code=r_[ihl + 1], nhmtu=struct.unpack('>H', r_[ihl + 6:ihl + 8])[0], src=socket.inet_ntoa(r_[12:16]), ttl=r_[8], iplen=struct.unpack('>H', r_[2:4])[0], qdst=socket.inet_ntoa(q[16:20]), qlen=struct.unpack('>H', q[2:4])[0], qttl=q[8], qdport=struct.unpack('>H', q[((q[0] & 15) * 4) + 2:((q[0] & 15) * 4) + 4])[0]))
    return out

def dfprobe(plan, gap=0.6, wait=2.5):
    """plan: [(目的地, IP 总长, TTL 或 None, 目的端口)] → (抓到的发出包, ICMP 回复列表)"""
    s = udp_sock(True)
    with Cap('icmp or (udp and dst portrange 33435-34000)', iface='en0', write=True) as c:
        for d, sz, ttl, port in plan:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl or 64)
            try: s.sendto(b'p' * (sz - 28), (d, port))
            except OSError as e: print('   sendto 失败', sz, e)
            time.sleep(gap)
        time.sleep(wait)
    rs = raws(c.pcap)
    return rs, icmp_replies(rs)

print('== 二:真实公网路径上用 DF 探测:不同大小、DF=1 的 UDP 数据报发到三个公网主机的没人监听的端口,每种大小 3 个(间隔 0.6 s);收到“端口不可达”说明那个大小的包到达了目的地,收到“需要分片”(3/4)说明路上某处放不下')
dests = [('主机 A', PUB), ('主机 B', '8.8.8.8'), ('主机 C', '1.1.1.1')]
sizes = [576, 1000, 1280, 1400, 1472, 1480, 1492, 1500]
plan = []; port = 33435
for nm, d in dests:
    for sz in sizes:
        for k_ in range(3): plan.append((d, sz, None, port)); port += 1
rs, rep = dfprobe(plan, gap=0.6)
byport = {x['qdport']: x for x in rep}
print(f'  共发出 {len(plan)} 个探测;抓到的发出包 DF 位全部置位:{all((flags(r_) >> 1) & 1 for ts, r_ in rs if r_[9] == 17)}')
print('    IP 总长   ' + '          '.join(nm for nm, _ in dests) + '        (格式:端口不可达个数 + 需要分片个数 / 发出个数)')
tab = {}
pp = 33435
for nm, d in dests:
    for sz in sizes:
        n3 = n4 = 0
        for k_ in range(3):
            x = byport.get(pp); pp += 1
            if x and x['type'] == 3 and x['code'] == 3: n3 += 1
            if x and x['type'] == 3 and x['code'] == 4: n4 += 1
        tab[(nm, sz)] = (n3, n4)
for sz in sizes:
    print(f'    {sz:>5}     ' + '       '.join(f'{tab[(nm, sz)][0]}+{tab[(nm, sz)][1]}/3' for nm, _ in dests))
mt = sorted({x['nhmtu'] for x in rep if x['code'] == 4})
print(f'  收到的 3/4 报文里的“下一跳 MTU”字段:{mt};其中 IP 总长 > {mt[0] if mt else "?"} 的探测(1500)收到了 3/4,≤ {mt[0] if mt else "?"} 的收到的是端口不可达' if mt else '  没有收到 3/4')
big = [x for x in rep if x['code'] == 4]
print(f'  3/4 报文来自:{sorted({("默认网关" if x["src"] == gw else ("私有地址" if ipaddress.ip_address(x["src"]).is_private else "公网地址")) for x in big})};引用的原包总长 {sorted({x["qlen"] for x in big})},引用的原包 TTL {sorted({x["qttl"] for x in big})};回复包自己的 TTL {sorted({x["ttl"] for x in big})}')

print('== 三:找出窄链路在第几跳:DF=1 的 1500 字节 UDP 探测,TTL 从 1 加到 10,看每个 TTL 得到的是“超时”(还没到窄链路)还是“需要分片”(3/4)')
plan = [(PUB, 1500, ttl, 33500 + ttl * 3 + k_) for ttl in range(1, 11) for k_ in range(3)]
rs, rep = dfprobe(plan, gap=0.5)
byport = {x['qdport']: x for x in rep}
first4 = None
for ttl in range(1, 11):
    xs = [byport.get(33500 + ttl * 3 + k_) for k_ in range(3)]; xs = [x for x in xs if x]
    if not xs: print(f'  TTL={ttl:>2}:3 个探测都没有回应'); continue
    desc = {}
    for x in xs: desc[(x['type'], x['code'], x['nhmtu'])] = desc.get((x['type'], x['code'], x['nhmtu']), 0) + 1
    t = ';'.join(f'{"超时 11/0" if k_[0] == 11 else ("需要分片 3/4,下一跳 MTU " + str(k_[2]) if k_[1] == 4 else "端口不可达 3/3")} × {v}' for k_, v in desc.items())
    who = sorted({('默认网关' if x['src'] == gw else ('私有地址的路由器' if ipaddress.ip_address(x['src']).is_private else '公网地址的路由器')) for x in xs})
    print(f'  TTL={ttl:>2}:收到 {len(xs)}/3 个回应:{t}(来自{"、".join(who)})')
    if first4 is None and any(x['code'] == 4 for x in xs): first4 = ttl
src3 = {x['src'] for k_ in range(3) for x in [byport.get(33500 + 3 * 3 + k_)] if x}      # TTL=3 的超时由谁回
src4 = {x['src'] for ttl in range(4, 11) for k_ in range(3) for x in [byport.get(33500 + ttl * 3 + k_)] if x and x['code'] == 4}
ttl3 = {x['ttl'] for k_ in range(3) for x in [byport.get(33500 + 3 * 3 + k_)] if x}; ttl4 = {x['ttl'] for ttl in range(4, 11) for k_ in range(3) for x in [byport.get(33500 + ttl * 3 + k_)] if x and x['code'] == 4}
print(f'  从 TTL={first4} 起一直收到 3/4:TTL=3 的包在第 3 跳的路由器处超时,TTL≥4 的包要由第 3 跳的路由器转发给第 4 跳,它的出口链路放不下 1500 字节,于是丢掉并回 ICMP 3/4(下一跳 MTU 1492)。验证:回 3/4 的设备与 TTL=3 回超时的是同一个地址:{src4 == src3};回复包 TTL 分别是 {sorted(ttl4)} 与 {sorted(ttl3)}')
print('== 四:内核会记住吗:收到 3/4 之后,路由表里这台主机的 MTU 变了没有;再发一次 1500 字节的 DF 数据报会怎样;1492 字节的呢')
m0, _ = route_mtu(PUB)
print(f'  前面第二、三节的探测已经让内核收到过很多个 3/4。现在 route get 公网主机的 MTU = {m0}(收到 3/4 之前是 1500)')
s = udp_sock(True)
for sz in (1500, 1492, 1480):
    try: s.sendto(b'q' * (sz - 28), (PUB, 33999)); res = '发送成功'
    except OSError as e: res = f'OSError [Errno {e.errno}] {e.strerror}'
    print(f'  再对同一目的地发 DF=1、IP 总长 {sz} 的 UDP:{res}')
    time.sleep(0.5)
print('  netstat -rn 里该主机的路由条目:' + ' | '.join(priv(l)[:90] for l in sysout('netstat', '-rn', '-f', 'inet').splitlines() if PUB in l) or '(没有该主机的单独条目)')

print('== 五:TCP 的 MSS 通告反映了路径:本机连几个公网地址,抓 SYN / SYN-ACK 里的 MSS(MSS + 40 = 对应的 MTU)')
cands = [('主机 A', PUB, 80), ('主机 B', '172.66.147.243', 80), ('主机 C', '1.1.1.1', 80), ('主机 D', '8.8.8.8', 443), ('主机 E', '223.5.5.5', 443)]
with Cap('tcp[tcpflags] & tcp-syn != 0', iface='en0', write=True, verbose=1) as c:
    for nm, d, p in cands:
        try: socket.create_connection((d, p), timeout=3).close()
        except Exception: pass
        time.sleep(0.3)
mine = {}; theirs = {}
for l in c.lines:
    m = re.search(r'(\d+\.\d+\.\d+\.\d+)\.(\d+) > (\d+\.\d+\.\d+\.\d+)\.(\d+): Flags \[([^\]]*)\].*?mss (\d+)', l)
    if not m: continue
    src, dst, mss = m.group(1), m.group(3), int(m.group(6))
    if src.startswith('192.168'): mine.setdefault(dst, mss)
    else: theirs.setdefault(src, mss)
for nm, d, p in cands:
    if d in theirs: print(f'  {nm}:本机 SYN 通告 MSS {mine.get(d)};对方 SYN-ACK 通告 MSS = {theirs[d]},对应 MTU ≈ {theirs[d] + 40}')
    else: print(f'  {nm}:没有连通(没抓到 SYN-ACK)')
print('  MSS 是对方(或路径上的中间设备)按自己的接口 MTU 写进去的上限,不是整条路径的 MTU;路径上更窄的链路只能靠 DF + ICMP 3/4(或黑洞检测)发现')

print('== 六:PMTUD 的逻辑(模拟,不是实测):假设路径四跳 MTU 是 1500 / 1500 / 1400 / 1500,发送方用 DF 发 1500 字节;三种情况下需要几轮、发几个包才能把数据送过去')
def simulate(path, icmp_ok, blackhole_fallback=None, start=1500, max_try=12):
    mtu = start; sent = 0; rounds = []
    for i in range(max_try):
        sent += 1; bottleneck = min(path)
        if mtu <= bottleneck: rounds.append((mtu, '送达')); return rounds, sent, True
        if icmp_ok: rounds.append((mtu, f'路由器回 ICMP 3/4(下一跳 MTU {bottleneck})')); mtu = bottleneck
        else:
            rounds.append((mtu, '被静默丢弃'))
            if blackhole_fallback and len(rounds) >= 3: mtu = blackhole_fallback
    return rounds, sent, False
path = [1500, 1500, 1400, 1500]
for nm, kw in (('ICMP 能回到发送方', dict(icmp_ok=True)), ('ICMP 被防火墙拦住(“黑洞”)', dict(icmp_ok=False)), ('ICMP 被拦,但发送方在连续 3 次无应答后退到 1200', dict(icmp_ok=False, blackhole_fallback=1200))):
    rs, n, ok = simulate(path, **kw)
    print(f'  {nm}:' + ';'.join(f'{m} → {r}' for m, r in rs[:5]) + (f' …共试 {n} 次' if n > 5 else '') + f' ⇒ {"成功" if ok else "一直失败(12 次后放弃)"},发了 {n} 个包')
print('  上面是按规范写出来的纸面推演:macOS 的 pmtud_blackhole_detection 实际如何退避、阈值多少,这里没有实测')
