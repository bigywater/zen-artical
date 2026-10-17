import sys, os, dpkt, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w2'); reset()
def macs(b): return ':'.join(f'{x:02x}' for x in b)
def mm(b): return ':'.join(f'{x:02x}' for x in b[:3]) + ':xx:xx:xx'
ETN = {0x0800: 'IPv4', 0x0806: 'ARP', 0x86dd: 'IPv6', 0x8100: 'VLAN(802.1Q)', 0x88cc: 'LLDP', 0x8809: '慢协议(LACP)', 0x88e1: 'HomePlug', 0x8035: 'RARP', 0x22f0: 'AVTP/其它'}
def etn(t): return ETN.get(t, 'other')
def kind(dst):
    if dst == b'\xff' * 6: return '广播 ff:ff:ff:ff:ff:ff'
    if dst[:3] == b'\x01\x00\x5e': return '组播(IPv4, 01:00:5e:…)'
    if dst[:2] == b'\x33\x33': return '组播(IPv6, 33:33:…)'
    if dst[0] & 1: return '其它组播(第一个字节最低位=1)'
    return '单播'

print('== 一:真实网卡上抓 20 秒,统计以太网帧头里的 EtherType 与目的地址种类(期间让本机发一点流量:curl、dig、ping 网关)')
with Cap('', iface='en0', write=True) as c:
    t0 = time.time()
    subprocess.run(['curl', '-s', '--noproxy', '*', '-o', '/dev/null', '--max-time', '5', 'http://example.com'], capture_output=True)
    subprocess.run(['dig', '+short', '+time=2', '+tries=1', '@1.1.1.1', 'example.org'], capture_output=True)
    subprocess.run(['ping', '-c', '2', '192.168.11.1'], capture_output=True)
    while time.time() - t0 < 20: time.sleep(0.5)
frames = []
with open(c.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f):
        try: frames.append((ts, dpkt.ethernet.Ethernet(b), len(b)))
        except Exception: pass
ct = collections.Counter(e.type for _, e, _ in frames); ck = collections.Counter(kind(e.dst) for _, e, _ in frames)
print(f'  20 秒共抓到 {len(frames)} 个帧(含周围设备发出的广播 / 组播)')
print('  EtherType 分布: ' + ', '.join(f'0x{t:04x}({etn(t)})×{n}' for t, n in ct.most_common(6)))
print('  目的地址种类: ' + ', '.join(f'{k}×{n}' for k, n in ck.most_common()))
lens = [l for _, _, l in frames]
print(f'  帧长(不含 FCS)最小 {min(lens)}、最大 {max(lens)}、中位数 {median(lens):.0f} 字节')

print('== 二:MAC 地址的结构:第一个字节的最低位=组播位,次低位=本地管理位。看本机、网关与几个典型地址')
me = [e for _, e, _ in frames if isinstance(e.data, dpkt.ip.IP) and e.data.src == bytes([192, 168, 9, 100])]
gw = [e for _, e, _ in frames if isinstance(e.data, dpkt.ip.IP) and e.data.dst == bytes([192, 168, 9, 100]) and e.data.src == bytes([192, 168, 11, 1])]
def bits(b0): return f'第一个字节 0x{b0:02x}: 组播位={b0 & 1}, 本地管理位={(b0 >> 1) & 1}'
print(f'  本机网卡 MAC {mm(me[0].src)}  {bits(me[0].src[0])}(本地管理位=1:系统生成的随机私有地址,不是出厂烧录的)')
if gw: print(f'  默认网关 MAC {mm(gw[0].src)}  {bits(gw[0].src[0])}(本地管理位=0:厂商烧录的全局唯一地址,前 3 字节是厂商 OUI)')
print(f'  广播地址 ff:ff:ff:ff:ff:ff  {bits(0xff)}')
mc4 = [e for _, e, _ in frames if e.dst[:3] == b'\x01\x00\x5e']
if mc4: print(f'  IPv4 组播目的 MAC {macs(mc4[0].dst)}  对应 IP 组播地址 {".".join(str(x) for x in mc4[0].data.dst)}:低 23 位直接取自 IP 地址')

print('== 三:最小帧长:ARP 请求在抓包里只有 42 字节,但以太网规定的最小帧是 64 字节(含 4 字节 FCS)——差额由网卡硬件在发出时补零。ping 一个不存在的邻居 IP 触发 ARP,同时抓包')
with Cap('arp', iface='en0', write=True, verbose=0, extra=['-e']) as c2:
    subprocess.run(['ping', '-c', '1', '-W', '800', '192.168.9.253'], capture_output=True)
    subprocess.run(['ping', '-c', '1', '192.168.11.1'], capture_output=True)
mine = [l for l in c2.lines if '192.168.9.100' in l or '192.168.9.253' in l]
for l in norm(mine, mask_mac=True)[:6]: print('  ' + l[:150])
print(f'  (这次共抓到 {len(c2.lines)} 个 ARP 帧,其余是网络里别的设备之间的 ARP,这里只列和本机相关的)')
arp = []
with open(c2.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(b); arp.append((e, len(b)))
req = [(e, l) for e, l in arp if isinstance(e.data, dpkt.arp.ARP) and e.data.op == 1 and e.src == me[0].src]
rep = [(e, l) for e, l in arp if isinstance(e.data, dpkt.arp.ARP) and e.data.op == 2]
if req: print(f'  本机发出的 ARP 请求帧长 {req[0][1]} 字节 = 14 以太网头 + 28 ARP(没有补零:补零由网卡在发送时做,抓包点在网卡之前)')
if rep: print(f'  别的设备回来的 ARP 应答帧长 {rep[0][1]} 字节 = 14 + 28 + 18 字节补零(对方网卡补到 60,抓到时已含补零;FCS 4 字节另算,总共 64)')
print(f'  ARP 请求是广播(目的 {"ff:ff:ff:ff:ff:ff" if req and req[0][0].dst == b"\xff" * 6 else "?"}),EtherType=0x{req[0][0].type:04x}' if req else '  (本次没有抓到 ARP 请求)')

print('== 四:最大帧长与 MTU:以太网载荷最大 1500。ping -D(不分片)-s 1472:ICMP 8 + 数据 1472 + IP 20 = 1500;再多 1 字节 -s 1473 就超过了 MTU,本机直接拒绝发送')
r1 = subprocess.run(['ping', '-c', '1', '-D', '-s', '1472', '192.168.11.1'], capture_output=True, text=True)
with Cap('icmp and host 192.168.11.1', iface='en0', write=True, extra=['-e']) as c3:
    subprocess.run(['ping', '-c', '1', '-D', '-s', '1472', '192.168.11.1'], capture_output=True, text=True)
    r2 = subprocess.run(['ping', '-c', '1', '-D', '-s', '1473', '192.168.11.1'], capture_output=True, text=True)
sizes = []
with open(c3.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f): sizes.append(len(b))
print(f'  -s 1472: {r1.stdout.strip().splitlines()[-2]}')
print(f'  抓到的 ICMP 帧长: {sizes}(= 14 + 20 + 8 + 1472 = 1514,这是标准以太网帧去掉 FCS 之后的最大值;含 FCS 是 1518)')
print(f'  -s 1473: ' + (r2.stderr.strip() or r2.stdout.strip().splitlines()[-2]).replace('\\n', ' ')[:140])
print(f'  -s 1473 时有没有新的 ICMP 帧出现在网线上: {"没有(只抓到 " + str(len(sizes)) + " 个帧,都来自 -s 1472 的请求和应答)" if len(sizes) == 2 else str(sizes)}')

print('== 五:FCS 去哪了?以太网帧尾有 4 字节 CRC-32(FCS),网卡发送时加、接收时校验并剥掉,抓包看不到。用 Python 的 zlib.crc32 对一个帧算出它“应该是”多少,说明它是怎么来的')
import zlib
e0 = req[0][0] if req else frames[0][1]
raw = bytes(e0)
fcs = zlib.crc32(raw) & 0xffffffff
print(f'  对这个 {len(raw)} 字节的 ARP 请求帧(不含补零)做 CRC-32 = 0x{fcs:08x};真实发送时补零到 60 字节再算 FCS 并附在尾部,字节序为小端(低位字节先发)')
print(f'  所以线上的完整帧 = 60 字节(补零后)+ 4 字节 FCS = 64 字节;抓包文件里这 4 字节不存在')
