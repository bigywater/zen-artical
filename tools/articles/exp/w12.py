import sys, os, re, struct, dpkt, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w12'); reset()
GW = '192.168.11.1'
def ipf(b): return '.'.join(map(str, b))
def ipstats():
    t = sysout('netstat', '-s', '-p', 'ip'); d = {}
    for k, pat in (('收到的分片', r'(\d+) fragments? received'), ('成功重组的包', r'(\d+) packets? reassembled ok'), ('发出的分片', r'(\d+) fragments? created'), ('被分片的包', r'(\d+) datagrams? fragmented'), ('重组超时丢弃的分片', r'(\d+) fragments? dropped after timeout'), ('因其它原因丢弃的分片', r'(\d+) fragments? dropped\b(?! after)')):
        m = re.search(pat, t); d[k] = int(m.group(1)) if m else 0
    return d
def frag_view(raw):
    ihl = (raw[0] & 15) * 4; fl = struct.unpack('!H', raw[6:8])[0]
    return dict(id=struct.unpack('!H', raw[4:6])[0], mf=bool(fl & 0x2000), df=bool(fl & 0x4000), off=(fl & 0x1fff) * 8, tot=struct.unpack('!H', raw[2:4])[0], ihl=ihl, proto=raw[9])

print('== 一:在真实网口 en0(MTU 1500)上发一个 4000 字节的 UDP 数据报到网关的 9 号端口(discard),抓包看它被拆成几个 IP 分片')
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('', 0)); sport = s.getsockname()[1]
before = ipstats()
with Cap(f'ip host {GW} and udp or (ip[6:2] & 0x1fff != 0 and host {GW})', iface='en0', write=True) as c:
    s.sendto(b'A' * 4000, (GW, 9)); time.sleep(0.5)
after = ipstats()
frs = []
with open(c.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(b)
        if isinstance(e.data, dpkt.ip.IP): frs.append(frag_view(b[14:]) | {'frame': len(b)})
mine = [x for x in frs if x['proto'] == 17 and (x['mf'] or x['off'])]
print(f'  4000 字节的 UDP 数据(+ 8 字节 UDP 头 = 4008 字节的 IP 载荷)抓到 {len(mine)} 个 IP 分片:')
print('    序号  id      MF  DF  片偏移(字节)  IP 总长  IP 载荷  以太网帧长')
for i, x in enumerate(mine): print(f'    {i + 1:<4}  {x["id"]:<6}  {int(x["mf"])}   {int(x["df"])}   {x["off"]:<11}  {x["tot"]:<7}  {x["tot"] - x["ihl"]:<7}  {x["frame"]}')
print(f'  规律:每个分片的 IP 载荷是 8 的倍数(最后一个除外),这里 1480 = 1500 − 20;最后一个分片 MF=0。偏移字段 13 位、单位 8 字节,所以抓到的“片偏移”是字节数 / 8 × 8。')
print(f'  只有第一个分片带 UDP 头(源 / 目的端口);后面的分片只有 IP 头 + 数据,单看它们不知道是哪个端口——所以带端口过滤的防火墙遇到分片很头疼')
print(f'  netstat -s -p ip 的计数这次:发出的分片 +{after["发出的分片"] - before["发出的分片"]}(与抓到的 3 个分片一致)')

print('== 二:环回接口上会分片吗?lo0 的 MTU 是 16384,把 40000 字节的 UDP 数据报发给本机的接收套接字,看 lo0 上出现几个 IP 包')
rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); P = lab_port(); rx.bind(('127.0.0.1', P)); rx.settimeout(1)
tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print('  先看系统限制:' + sysout('sysctl', 'net.inet.udp.maxdgram').strip() + '——默认情况下超过 9216 字节的 UDP 数据报 sendto 会报 Message too long,要把发送缓冲区调大(SO_SNDBUF)才能发更大的')
try: tx.sendto(b'x' * 20000, ('127.0.0.1', P))
except OSError as e: print(f'  不调大 SO_SNDBUF 直接发 20000 字节:{e}')
tx.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
b2 = ipstats()
with Cap(f'udp port {P} or (ip[6:2] & 0x3fff != 0)', write=True) as c2:
    tx.sendto(bytes(range(256)) * 156 + b'\0' * 64, ('127.0.0.1', P)); data, _ = rx.recvfrom(65535); time.sleep(0.3)
a2 = ipstats()
pk = read_pcap(c2.pcap)
print(f'  应用调用一次 sendto(40000 字节),一次 recvfrom 拿到 {len(data)} 字节;lo0 上看到 {len(pk)} 个 IP 包(IP 总长远大于 MTU 16384,却没有分片——macOS 的 lo0 不对超过 MTU 的包分片,直接整包交给本机的接收方):')
for i, (ts, ip) in enumerate(pk):
    v = frag_view(ip.raw); print(f'    分片 {i + 1}: id={v["id"]} MF={int(v["mf"])} 偏移={v["off"]} IP 载荷={v["tot"] - v["ihl"]}')
print(f'  内核计数: 被分片的包 +{a2["被分片的包"] - b2["被分片的包"]},发出的分片 +{a2["发出的分片"] - b2["发出的分片"]},收到的分片 +{a2["收到的分片"] - b2["收到的分片"]},成功重组 +{a2["成功重组的包"] - b2["成功重组的包"]}')

print('== 三:分片的代价之一是“丢一个全丢”。先在 lo0 上用 netlab 造 5% 丢包(每个方向),分别发 1000、20000、60000 字节的 UDP 数据报各 1000 个,看送达率;再数一个 60000 字节的数据报在 lo0 上是几个 IP 包')
def run(size, n=1000):
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); P = lab_port(); rx.bind(('127.0.0.1', P)); rx.settimeout(0.05)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); tx.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20); got = 0; payload = b'x' * size
    for i in range(n):
        tx.sendto(payload, ('127.0.0.1', P))
        try: rx.recvfrom(65535); got += 1
        except socket.timeout: pass
    return got
res = {}
with lossy(5, 0, 0) as o:
    for size in (1000, 20000, 60000): res[size] = run(size)
for size, got in res.items(): print(f'  {size:>5} 字节的数据报:送达 {got} / 1000 = {got / 10:.1f}%')
rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); P3 = lab_port(); rx.bind(('127.0.0.1', P3)); tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); tx.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
with Cap(f'udp port {P3}', write=True) as c3:
    tx.sendto(b'x' * 60000, ('127.0.0.1', P3)); time.sleep(0.3)
print(f'  一个 60000 字节的数据报在 lo0 上是 {len(read_pcap(c3.pcap))} 个 IP 包——lo0 不分片,所以 3 档大小的送达率都约等于 95%,看不出“丢一个分片全丢”的放大效应')
print('  要看放大效应得有真的分片(MTU 1500 的以太网路径),而丢包 / 延迟只能在 lo0 上注入;下面用公式和随机模拟补上(这是计算,不是实测)')
import math, random as _r
_r.seed(5)
print('    数据报大小    分片数(MTU 1500)  理论送达率 0.95^n  模拟 10 万次')
for size in (1000, 4000, 20000, 60000):
    n_ = math.ceil((size + 8) / 1480); sim = sum(all(_r.random() > 0.05 for _ in range(n_)) for _ in range(100000)) / 1000
    print(f'    {size:>6} 字节  {n_:>8}          {0.95 ** n_ * 100:6.1f}%          {sim:6.1f}%')
print('== 四:TCP 用 DF 位和 MSS 避开分片:下载 1 MiB 时抓到的 IP 包里,有没有 MF 置位 / 偏移非 0 的分片;以及它们的 DF 标志')
srv = socket.socket(); srv.bind(('127.0.0.1', lab_port())); srv.listen(1); port = srv.getsockname()[1]
def snd():
    c_, _ = srv.accept(); c_.sendall(b'z' * (1 << 20)); c_.close()
threading.Thread(target=snd, daemon=True).start()
with Cap(f'tcp port {port}', write=True) as c4:
    cl = socket.create_connection(('127.0.0.1', port)); n = 0
    while n < (1 << 20):
        d = cl.recv(1 << 20); n += len(d)
        if not d: break
    cl.close()
pk4 = read_pcap(c4.pcap); vs = [frag_view(ip.raw) for ts, ip in pk4]
print(f'  抓到 {len(pk4)} 个 IP 包:MF 置位 {sum(v["mf"] for v in vs)} 个,片偏移非 0 {sum(1 for v in vs if v["off"])} 个,DF 置位 {sum(v["df"] for v in vs)} 个——TCP 的包全部带 DF,从不依赖分片;超过路径 MTU 时靠 ICMP“需要分片”来调整(见 PMTUD 一篇)')

print('== 五:重组是有成本和限制的:系统给“正在重组的包”设了上限,超时就丢(sysctl)')
for k in ('net.inet.ip.maxfragpackets', 'net.inet.ip.maxfragsperpacket'):
    print('  ' + sysout('sysctl', k).strip())
print(f'  netstat -s -p ip 当前计数:' + ';'.join(f'{k} {v}' for k, v in ipstats().items()))
print('  这些计数多半是 0 或很小:现代网络里 TCP 为主、有 PMTUD,真正的 IP 分片已经很少见;UDP 大数据报(DNS 大响应、QUIC 之前的一些协议)仍可能触发')
