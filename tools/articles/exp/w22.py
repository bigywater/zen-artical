import sys, os, re, struct, collections, ipaddress; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w22'); reset()
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
def raws(path): return [(ts, ip.raw) for ts, ip in read_pcap(path)]
def icmpstat():
    o = sysout('netstat', '-s', '-p', 'icmp'); d = {}
    m = re.search(r'(\d+) calls to icmp_error', o); d['calls'] = int(m.group(1))
    m = re.search(r'Output histogram:(.*?)\d+ message with bad code', o, re.S)
    for k_, v in re.findall(r'\t\t([a-z ]+): (\d+)', m.group(1)): d['out:' + k_] = int(v)
    return d
def pace(gap):
    t1 = time.time() + gap
    while time.time() < t1: pass

print('== 一:本机跟 ICMP 有关的内核开关,以及 netstat -s -p icmp 里的计数')
print('  ' + '\n  '.join(l for l in sysout('sysctl', 'net.inet.icmp').splitlines() if l.strip()))
print('  ' + '\n  '.join(sysout('sysctl', k_).strip() for k_ in ('net.inet.ip.redirect', 'net.inet.ip.forwarding')))
print('  net.inet.icmp 下没有 icmplim 这一项:macOS 不像 Linux / BSD 那样用 sysctl 设 ICMP 限速;下面一节直接测量')
o = sysout('netstat', '-s', '-p', 'icmp')
print('  netstat -s -p icmp 的 Input histogram 里' + ('有' if 'redirect' in o else '没有') + '“redirect”一项;Output histogram 里的类别:' + ','.join(re.findall(r'\t\t([a-z ]+): \d+', re.search(r'Output histogram:(.*?)\d+ message with bad code', o, re.S).group(1))))

print('== 二:ICMP 差错有限速吗:往 lo0 上没人监听的 UDP 端口以不同的间隔持续发包,统计回来的 ICMP 端口不可达个数和它们的时间间隔')
rows = []
for gap, dur in ((0, 3), (0.001, 3), (0.005, 3), (0.01, 3), (0.05, 3), (0.2, 3), (1.0, 5)):
    r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('127.0.0.1', 0)); port = r.getsockname()[1]; r.close()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    st0 = icmpstat()
    with Cap(f'(udp dst port {port}) or icmp', iface='lo0', write=True) as c:
        t0 = time.time(); n = 0
        while time.time() - t0 < dur:
            s.sendto(b'x' * 20, ('127.0.0.1', port)); n += 1
            if gap: pace(gap)
        time.sleep(0.6)
    st1 = icmpstat()
    tss = [ts for ts, r_ in raws(c.pcap) if r_[9] == 1]
    sp = [b - a for a, b in zip(tss, tss[1:])]
    rows.append((gap, n, len(tss), dur))
    print(f'  间隔 {gap * 1000:>6.0f} ms:{dur} 秒内发了 {n:>6} 个 UDP 包,抓到 {len(tss):>2} 个 ICMP 差错({len(tss) / dur:.1f} 个/秒)' + (f';相邻差错的间隔 最小 {min(sp) * 1000:.0f} / 中位 {sorted(sp)[len(sp) // 2] * 1000:.0f} / 最大 {max(sp) * 1000:.0f} ms' if sp else '') + f';netstat 里 icmp_error 调用 +{st1["calls"] - st0["calls"]},“destination unreachable”输出 +{st1.get("out:destination unreachable", 0) - st0.get("out:destination unreachable", 0)}')
print('  结论:不管发多快,最多约每 100 ms 回一个差错(≈ 10 个/秒);发得慢于这个速度时每个都回')

print('== 三:哪些响应受这个限制:同样往 lo0 猛发,对比 ICMP echo 应答(无限速?)、TCP RST(关闭端口的 SYN → RST)、UDP 差错')
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP); s.setblocking(False)
with Cap('icmp', iface='lo0', write=True) as c:
    n = 0
    for i in range(3000):
        pkt = struct.pack('>BBHHH', 8, 0, 0, 0x2222, i & 0xffff) + b'echo-flood'
        ck = 0; b_ = pkt + (b'\0' if len(pkt) % 2 else b'')
        sm = sum(struct.unpack('>%dH' % (len(b_) // 2), b_))
        while sm >> 16: sm = (sm & 0xffff) + (sm >> 16)
        pkt = pkt[:2] + struct.pack('>H', ~sm & 0xffff) + pkt[4:]
        try: s.sendto(pkt, ('127.0.0.1', 0)); n += 1
        except BlockingIOError: pass
    time.sleep(1)
pk = raws(c.pcap)
req = sum(1 for ts, r_ in pk if r_[(r_[0] & 15) * 4] == 8); rep = sum(1 for ts, r_ in pk if r_[(r_[0] & 15) * 4] == 0)
print(f'  ICMP echo:发出 {n} 个请求(抓到 {req} 个请求),收到 {rep} 个应答——echo 应答没有被限成 10 个/秒')
lsn = socket.socket(); lsn.bind(('127.0.0.1', 0)); cp = lsn.getsockname()[1]; lsn.close()
with Cap(f'tcp port {cp}', iface='lo0', write=True) as c:
    t0 = time.time(); m = 0
    for i in range(1500):
        k = socket.socket(); k.setblocking(False); k.connect_ex(('127.0.0.1', cp)); k.close(); m += 1
    dt = time.time() - t0; time.sleep(1)
syn = rst = 0
for ts, r_ in raws(c.pcap):
    ihl = (r_[0] & 15) * 4; fl = r_[ihl + 13]
    if fl & 2 and not fl & 0x10: syn += 1
    if fl & 4: rst += 1
print(f'  TCP:对没人监听的端口连续发起 {m} 次 connect({dt:.2f} 秒),抓到 {syn} 个 SYN,回了 {rst} 个 RST——TCP 的拒绝(RST)在这里没有被限成 10 个/秒')
udp_rate = [r for r in rows if r[0] == 0][0]
print(f'  UDP 端口不可达(ICMP):3 秒内发了 {udp_rate[1]} 个,只回了 {udp_rate[2]} 个')

print('== 四:路由器也限速:对默认网关的关闭端口 / 用 TTL=1 各发 100 个 UDP 包(间隔 1 ms),看回来多少个 ICMP 差错')
for nm, ttl, port in (('端口不可达(发到网关自己的关闭端口)', 64, 33999), ('超时(TTL=1,网关要转发时发现 TTL 用完)', 1, 34000)):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
    dst = gw if ttl == 64 else '104.20.23.154'
    with Cap(f'icmp or (udp and dst port {port})', iface='en0', write=True) as c:
        t0 = time.time()
        for i in range(100): s.sendto(b'y' * 12, (dst, port)); pace(0.001)
        dt = time.time() - t0; time.sleep(2)
    errs = []
    for ts, r_ in raws(c.pcap):
        ihl = (r_[0] & 15) * 4
        if r_[9] == 1 and r_[ihl] in (3, 11): errs.append(ts)
    sp = [b - a for a, b in zip(errs, errs[1:])]
    print(f'  {nm}:{dt * 1000:.0f} ms 内发了 100 个,收到 {len(errs)} 个差错' + (f';相邻间隔 最小 {min(sp) * 1000:.0f} / 中位 {sorted(sp)[len(sp) // 2] * 1000:.0f} / 最大 {max(sp) * 1000:.0f} ms' if sp else ''))
print('  设备各有各的策略(有的按速率、有的按令牌桶);这里只看到这台网关回应的个数,没有看到它的配置')

print('== 五:ICMP 时间戳 / 地址掩码请求:macOS 的 net.inet.icmp.timestamp = 0、maskrepl = 0,用非特权 ICMP 套接字发请求,看有没有应答')
for nm, typ in (('时间戳请求(类型 13)', 13), ('地址掩码请求(类型 17)', 17), ('回显请求(类型 8,对照)', 8)):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP); s.settimeout(1)
    body = struct.pack('>HH', 0x3333, 1) + (b'\0' * 12 if typ == 13 else (b'\0' * 4 if typ == 17 else b'ping'))
    pkt = struct.pack('>BBH', typ, 0, 0) + body
    b_ = pkt + (b'\0' if len(pkt) % 2 else b''); sm = sum(struct.unpack('>%dH' % (len(b_) // 2), b_))
    while sm >> 16: sm = (sm & 0xffff) + (sm >> 16)
    pkt = pkt[:2] + struct.pack('>H', ~sm & 0xffff) + pkt[4:]
    got = []
    try:
        s.sendto(pkt, ('127.0.0.1', 0))
        t0 = time.time()
        while time.time() - t0 < 1.0:
            try: d, _ = s.recvfrom(2000); got.append(d[(d[0] & 15) * 4])
            except socket.timeout: break
        res = f'1 秒内从套接字收到 {len(got)} 个 ICMP 包,类型 {got}' + ('——应答类型是 ' + {13: '14', 17: '18', 8: '0'}[typ] + (',收到了' if {13: 14, 17: 18, 8: 0}[typ] in got else ',没有收到'))
    except OSError as e: res = f'发送失败:{e.strerror}'
    print(f'  对 127.0.0.1 发 {nm}:{res}')
