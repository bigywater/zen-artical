import sys, os, re, struct, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w14'); reset()
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]

def icmps(path, only=None):
    """pcap → 列表:每个 ICMP echo 包一个 dict"""
    out = []
    for ts, ip in read_pcap(path):
        raw = ip.raw; ihl = (raw[0] & 15) * 4
        if raw[9] != 1 or (struct.unpack('>H', raw[6:8])[0] & 0x1fff) != 0: continue
        t, code, ck, ident, seq = struct.unpack('>BBHHH', raw[ihl:ihl + 8])
        if t not in (0, 8): continue
        out.append(dict(ts=ts, raw=raw, ihl=ihl, iplen=struct.unpack('>H', raw[2:4])[0], ttl=raw[8], flags=raw[6] >> 5, id=struct.unpack('>H', raw[4:6])[0], t=t, code=code, ck=ck, ident=ident, seq=seq, data=raw[ihl + 8:], src=socket.inet_ntoa(raw[12:16]), dst=socket.inet_ntoa(raw[16:20])))
    return out

def cksum(b):
    if len(b) % 2: b += b'\0'
    s = sum(struct.unpack('>%dH' % (len(b) // 2), b))
    while s >> 16: s = (s & 0xffff) + (s >> 16)
    return ~s & 0xffff

print('== 一:ping 一次,线上的 ICMP echo 请求和应答:类型 8 / 0、标识符、序号、载荷里放了什么(分别在 lo0 上 ping 127.0.0.1 和 en0 上 ping 默认网关)')
for name, iface, dst in (('127.0.0.1(lo0)', 'lo0', '127.0.0.1'), ('默认网关(en0)', 'en0', gw)):
    with Cap('icmp', iface=iface, write=True) as c:
        sysout('ping', '-c', '1', dst)
    pk = icmps(c.pcap)
    rq = [p for p in pk if p['t'] == 8][0]; rp = [p for p in pk if p['t'] == 0][0]
    print(f'  {name}:抓到 {len(pk)} 个包')
    for tag, p in (('请求', rq), ('应答', rp)):
        print(f'    {tag}:IP 总长 {p["iplen"]},TTL {p["ttl"]},IP 头里的标识 {p["id"]},ICMP 类型 {p["t"]} 代码 {p["code"]},标识符 0x{p["ident"]:04x},序号 {p["seq"]},载荷 {len(p["data"])} 字节')
    sec, usec = struct.unpack('>II', rq['data'][:8]); pat = rq['data'][8:]
    print(f'    请求的载荷前 8 字节是发送时间:秒 {sec}、微秒 {usec};与抓包时间戳相差 {abs(rq["ts"] - (sec + usec / 1e6)) * 1e6:.0f} µs;后 {len(pat)} 字节是 {pat[0]:#04x} 起逐字节加 1 的图案({"确认" if pat == bytes(range(pat[0], pat[0] + len(pat))) else "不是"}递增)')
    print(f'    应答的标识符、序号、载荷与请求完全相同:{rp["ident"] == rq["ident"] and rp["seq"] == rq["seq"] and rp["data"] == rq["data"]};IP 头 + ICMP 头 + 载荷 = {rq["ihl"]} + 8 + {len(rq["data"])} = {rq["iplen"]} 字节')

print('== 二:ICMP 校验和:自己对 ICMP 头 + 载荷做反码求和,和抓到的校验和字段核对(lo0 和 en0 各一个请求、一个应答)')
rows = []
for name, iface, dst in (('lo0', 'lo0', '127.0.0.1'), ('en0', 'en0', gw)):
    with Cap('icmp', iface=iface, write=True) as c:
        sysout('ping', '-c', '1', dst)
    for p in icmps(c.pcap):
        icmp = p['raw'][p['ihl']:]; zero = icmp[:2] + b'\0\0' + icmp[4:]
        mine = cksum(zero); ver = cksum(icmp)
        print(f'  {name} {"请求" if p["t"] == 8 else "应答"}:抓到的校验和 0x{p["ck"]:04x},自己算的 0x{mine:04x},{"一致" if mine == p["ck"] else "不一致"};把整个 ICMP 报文(含校验和)再求和得 0x{ver:04x}')
print('  规则:校验和字段先填 0,对整个 ICMP 报文(头 + 载荷,不含 IP 头)按 16 位字求和、进位折回、取反;收到的人对整个报文求和,结果应该是 0')

print('== 三:RTT 从哪来:对默认网关连发 30 个 ping(间隔 0.2 s),比较 ping 自己报的 time 和抓包里 请求→应答 的时间差;再看 127.0.0.1')
def pingstat(dst, n, extra=()):
    with Cap('icmp', iface='en0' if dst == gw else 'lo0', write=True) as c:
        o = sysout('ping', '-c', str(n), '-i', '0.2', *extra, dst, timeout=60)
    pk = icmps(c.pcap)
    rq = {p['seq']: p for p in pk if p['t'] == 8}; rp = {p['seq']: p for p in pk if p['t'] == 0}
    cap = {s: (rp[s]['ts'] - rq[s]['ts']) * 1000 for s in rq if s in rp}
    rep = {int(m.group(1)): float(m.group(2)) for m in re.finditer(r'icmp_seq=(\d+) ttl=\d+ time=([\d.]+) ms', o)}
    return o, cap, rep
o, cap, rep = pingstat(gw, 30)
common = sorted(set(cap) & set(rep)); d = [rep[s] - cap[s] for s in common]
print(f'  默认网关:发 30 个,收到应答 {len(rep)} 个;ping 报告的 RTT 最小 {min(rep.values()):.3f} / 中位 {statistics.median(rep.values()):.3f} / 最大 {max(rep.values()):.3f} ms')
print(f'  抓包得到的 RTT(请求到应答之间的时间差)最小 {min(cap.values()):.3f} / 中位 {statistics.median(cap.values()):.3f} / 最大 {max(cap.values()):.3f} ms')
print(f'  逐个对比 {len(common)} 个:ping 报的比抓包多 {min(d):.3f}~{max(d):.3f} ms(中位 {statistics.median(d):.3f})——ping 从发出前到应答被读到,比网卡上看到的多一段')
srt = sorted(rep.values()); print(f'  最慢的 3 个 RTT: {srt[-3:]};最快的 3 个: {srt[:3]}')
o2, cap2, rep2 = pingstat('127.0.0.1', 30)
print(f'  127.0.0.1:收到 {len(rep2)} 个;ping 报告 最小 {min(rep2.values()):.3f} / 中位 {statistics.median(rep2.values()):.3f} / 最大 {max(rep2.values()):.3f} ms;抓包 RTT 中位 {statistics.median(cap2.values()):.3f} ms')
print(f'  网关的 RTT 中位是 127.0.0.1 的 {statistics.median(rep.values()) / statistics.median(rep2.values()):.0f} 倍(Wi-Fi 链路上一来一回 + 网关处理)')

print('== 四:载荷大小对 RTT 的影响:对默认网关用 -s 指定载荷 0 / 56 / 512 / 1472 / 4000 字节各 15 个,看 IP 包大小、RTT 中位,以及超过 MTU 时请求和应答都被分片')
res = []
for sz in (0, 56, 512, 1472, 4000):
    with Cap('icmp or (ip[6:2] & 0x1fff != 0)', iface='en0', write=True) as c:
        o = sysout('ping', '-c', '15', '-i', '0.2', '-s', str(sz), gw, timeout=60)
    shown = len(re.findall(r'time=[\d.]+ ms', o)); recv = int(re.search(r'(\d+) packets received', o).group(1))
    pk = icmps(c.pcap); rq = {p['seq']: p for p in pk if p['t'] == 8}; rp = {p['seq']: p for p in pk if p['t'] == 0}
    rtt = [(rp[q]['ts'] - rq[q]['ts']) * 1000 for q in rq if q in rp]
    frames = [(ts, ip.raw) for ts, ip in read_pcap(c.pcap)]
    frag = sum(1 for ts, r in frames if (struct.unpack('>H', r[6:8])[0] & 0x3fff) != 0)
    first = [r for ts, r in frames if r[9] == 1 and (struct.unpack('>H', r[6:8])[0] & 0x1fff) == 0][0]
    res.append((sz, recv, statistics.median(rtt), min(rtt), struct.unpack('>H', first[2:4])[0], frag, len(frames), shown))
    print(f'  载荷 {sz:>4} 字节:第一个包 IP 总长 {res[-1][4]};收到 {recv}/15,ping 打印出 time= 的有 {shown} 个;抓包 RTT 最小 {res[-1][3]:.3f} / 中位 {res[-1][2]:.3f} ms;抓到 {res[-1][6]} 个 IP 包,其中是分片的(MF 置位或偏移非 0)有 {res[-1][5]} 个')
print('  载荷 0 → 4000 字节,抓包 RTT 中位的变化: ' + ' → '.join(f'{r[2]:.3f}' for r in res) + ' ms')

print('== 五:不用 root 自己发 echo:macOS 允许 SOCK_DGRAM + IPPROTO_ICMP 套接字;我们填标识符、序号和载荷,看线上发出的是什么、收到的是什么')
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP); s.settimeout(2)
payload = b'w14-hello-icmp' + bytes(range(20))
pkt = struct.pack('>BBHHH', 8, 0, 0, 0x1234, 7) + payload
pkt = pkt[:2] + struct.pack('>H', cksum(pkt)) + pkt[4:]
with Cap('icmp', iface='en0', write=True) as c:
    t0 = time.time(); s.sendto(pkt, (gw, 0))
    try: data, addr = s.recvfrom(2048); dt = (time.time() - t0) * 1000
    except Exception as e: data = None; dt = None
pk = icmps(c.pcap)
rq = [p for p in pk if p['t'] == 8]; rp = [p for p in pk if p['t'] == 0]
print(f'  我填的:类型 8 代码 0 标识符 0x1234 序号 7 载荷 {len(payload)} 字节')
if rq: print(f'  线上发出的请求:标识符 0x{rq[0]["ident"]:04x} 序号 {rq[0]["seq"]} 载荷 {len(rq[0]["data"])} 字节;载荷与我填的相同:{rq[0]["data"] == payload};标识符{"保持了" if rq[0]["ident"] == 0x1234 else "被内核改写了"}')
if rp: print(f'  线上收到的应答:标识符 0x{rp[0]["ident"]:04x} 序号 {rp[0]["seq"]} 载荷相同:{rp[0]["data"] == payload}')
if data:
    ihl = (data[0] & 15) * 4
    print(f'  recvfrom 拿到 {len(data)} 字节:开头是 IP 头(版本/IHL=0x{data[0]:02x},头长 {ihl}),后面是 ICMP 类型 {data[ihl]} 代码 {data[ihl + 1]};应用层测得 RTT {dt:.3f} ms')
    print(f'  应用里收到的 ICMP 标识符 0x{struct.unpack(">H", data[ihl + 4:ihl + 6])[0]:04x}(线上是 0x{rp[0]["ident"]:04x})' if rp else '')
else: print('  没有收到应答')
# 第二个套接字会不会收到第一个的应答?
s2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP); s2.settimeout(1)
s.sendto(pkt, (gw, 0))
try:
    d2, _ = s2.recvfrom(2048); i2 = (d2[0] & 15) * 4
    got2 = f'收到了一个 {len(d2)} 字节的包(ICMP 类型 {d2[i2]},标识符 0x{struct.unpack(">H", d2[i2 + 4:i2 + 6])[0]:04x},序号 {struct.unpack(">H", d2[i2 + 6:i2 + 8])[0]})'
except Exception: got2 = '什么也没收到'
print(f'  同时开着另一个 ICMP 套接字 s2(自己从没发过包),s 又发了一次请求:s2 {got2}——也就是说在这台机器上,ICMP 数据报套接字并不只收自己发出的请求的应答(这里只观察到现象,没有进一步验证内核的分发规则)')
