import sys, os, re, struct, threading, statistics, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
import dpkt
tee('w105'); reset()
print('== 一:隧道在每个包外面再套一层:内层 IP 包 + 隧道头 + 外层 UDP + 外层 IP。各常见隧道的额外字节数与应有的内层 MTU(外层链路 MTU 1500,外层 IPv4;下表是按各协议的头长度计算的,不是测量)')
rows = [('WireGuard(外层 IPv4)', 20 + 8 + 16 + 16, '外层 IP 20 + UDP 8 + WG 数据头 16 + 认证标签 16'), ('WireGuard(外层 IPv6)', 40 + 8 + 16 + 16, '外层 IPv6 40 + UDP 8 + 16 + 16'), ('GRE(无选项)', 20 + 4, '外层 IP 20 + GRE 4'), ('VXLAN(内层含以太网头)', 20 + 8 + 8 + 14, '外层 IP 20 + UDP 8 + VXLAN 8 + 内层以太网 14'), ('IPsec ESP 隧道模式(AES-GCM,典型)', 20 + 8 + 8 + 2 + 16, '外层 IP 20 + ESP 头 8(SPI 4 + 序号 4)+ IV 8 + 填充 / 尾 2 + 认证 16(不含 NAT-T 的 UDP 8)'), ('IP-in-UDP 的最小隧道(本篇自己实现)', 20 + 8 + 32, '外层 IP 20 + UDP 8 + 自定义头 32')]
print('    隧道                                  额外字节   内层 MTU(1500 − 额外)   组成')
for nm, ov, why in rows: print(f'    {nm:<36} {ov:>6}   {1500 - ov:>12}            {why}')
print('  WireGuard 默认把内层 MTU 设成 1420 而不是 1440,是为了外层是 IPv6 时(额外 80 字节)也放得下:1500 − 80 = 1420')

print('== 二:真实测量:隧道包超过链路 MTU 会怎样。我自己写一个最小的“IP-in-UDP”封装:内层 IP 包 + 32 字节隧道头,装进一个 UDP 数据报,发到一个不存在的隧道对端(198.51.100.1:51820,文档专用地址)。对不同大小的内层包,抓 en0 看外层数据报有没有被分片')
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.connect(('198.51.100.1', 51820)); me = u.getsockname()[0]; HDR = 32
print('    内层 IP 包大小   外层 UDP 载荷   外层 IP 包大小   在 en0 上发出的 IP 包(分片)           有无分片')
for inner in (1280, 1400, 1420, 1440, 1441, 1480, 1500):
    payload = b'\0' * (inner + HDR)
    with Cap('host 198.51.100.1 and udp', iface='en0', write=True, snaplen=0) as c:
        u.send(payload); time.sleep(0.5)
    pk = []
    with open(c.pcap, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf)
            if e.type != 0x0800: continue
            ip = e.data
            if ip.dst == socket.inet_aton('198.51.100.1'): pk.append((ip.len, (ip.off & 0x1fff) * 8, bool(ip.off & dpkt.ip.IP_MF)))
    outer = 20 + 8 + inner + HDR
    print(f'    {inner:>10}      {inner + HDR:>9}       {outer:>9}       {[p[0] for p in pk]}  {"→ 分成 %d 片(偏移 %s)" % (len(pk), [p[1] for p in pk]) if len(pk) > 1 else ""}'.ljust(110) + ('有分片' if len(pk) > 1 else '无'))
print(f'  外层 IP 包不能超过 en0 的 MTU 1500:内层 IP 包 ≤ 1500 − 20 − 8 − {HDR} = {1500 - 28 - HDR} 字节时刚好一个包;再大一个字节,外层就被分成两片(第一片 1500 字节、第二片是零头)——分片后任何一片丢失,整个数据报都丢')

print('== 三:分片的代价放大了丢包:MTU 刚好超 1 字节时,每个大包要多发 1 个小分片,而且丢包概率翻倍(计算)。以 1% 的每包丢包率为例,一个内层 1500 字节的包:未分片丢失概率 1%;分成 2 片后任何一片丢了都丢(整个包)的概率')
p = 0.01
print(f'  1 片:{p:.2%};2 片:1 − (1 − {p:.0%})² = {1 - (1 - p) ** 2:.2%};3 片:{1 - (1 - p) ** 3:.2%}(计算值;还没有算上分片是在重组时需要额外等待 / 缓存)')

print('== 四:隧道对 TCP 效率的影响(计算):隧道里 TCP 的 MSS = 内层 MTU − 40(IPv4 + TCP)。每传 1 MB 应用数据,线上总共多少字节')
def wire_bytes(total, mss, overhead): 
    segs = -(-total // mss); return total + segs * (40 + overhead + 14)
for nm, mtu, ov in (('不用隧道,MTU 1500', 1500, 0), ('WireGuard,内层 MTU 1420', 1420, 60), ('GRE,内层 MTU 1476', 1476, 24), ('错配:内层 MTU 仍是 1500(外层会分片)', 1500, 60)):
    mss = mtu - 40; segs = -(-1_000_000 // mss); wb = wire_bytes(1_000_000, mss, ov); extra = segs if nm.startswith('错配') else 0
    print(f'    {nm:<40} MSS {mss}:{segs} 个段,线上共 {wb + extra * (20 + 14)} 字节(开销 {(wb + extra * 34 - 1_000_000) / 1_000_000:.1%}){";每个段多一个分片包(+34 字节)" if extra else ""}')
print('  (以太网头按 14 字节算,没有算以太网帧间隙与 CRC;“错配”一行假设每个段都被外层分成两片。)')

print('== 五:本机有什么隧道类接口?读 ifconfig 的接口名与 MTU(只看名字与 MTU,不看任何地址)')
for line in sysout('ifconfig', '-l').split():
    pass
ifl = sysout('ifconfig', '-l').split(); tun = [i for i in ifl if i.startswith(('utun', 'gif', 'stf', 'ipsec', 'ppp'))]
for i in tun:
    out = sysout('ifconfig', i); m = re.search(r'mtu (\d+)', out); print(f'  {i:<8} MTU {m.group(1) if m else "?"}')
print(f'  共 {len(tun)} 个隧道类接口,MTU 各不相同({sorted({re.search(r"mtu (\d+)", sysout("ifconfig", i)).group(1) for i in tun}, key=int)}):都比 en0 的 1500 小或在 1000~2000 之间——实际路径 MTU 取决于数据走的是哪个接口')
