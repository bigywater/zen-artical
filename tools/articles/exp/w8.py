import sys, os, re, dpkt, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w8'); reset()
ME = '192.168.9.100'; GW = '192.168.11.1'; BC = '192.168.11.255'
def macs(b): return ':'.join(f'{x:02x}' for x in b)
def mm(b): return ':'.join(f'{x:02x}' for x in b[:3]) + ':xx:xx:xx'
def ipf(b): return '.'.join(map(str, b))
def kind(dst):
    if dst == b'\xff' * 6: return '广播'
    if dst[0] & 1: return '组播'
    return '单播'

print('== 一:同样的 UDP 载荷发给四种目的地,在 en0 上抓包,看帧的目的 MAC(以太网层)与目的 IP(IP 层)是怎么对应的')
dests = [('单播(发给默认网关)', GW), ('子网定向广播(网段最后一个地址)', BC), ('受限广播 255.255.255.255', '255.255.255.255'), ('组播 239.1.2.3', '239.1.2.3')]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1); s.bind((ME, 0)); sport = s.getsockname()[1]
with Cap(f'udp and src port {sport}', iface='en0', write=True) as c:
    for label, ip in dests:
        s.sendto(label.encode()[:8], (ip, 9876)); time.sleep(0.2)
rows = []
with open(c.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(b); rows.append((e.dst, e.data.dst, len(b)))
print(f'  {"目的"  :<28}{"以太网目的 MAC":<24}{"MAC 类型":<8}{"IP 目的地址":<18}')
for (label, ip), (dmac, dip, ln) in zip(dests, rows):
    print(f'  {label:<26}{mm(dmac) if dmac != b"\xff" * 6 else "ff:ff:ff:ff:ff:ff":<24}{kind(dmac):<8}{ipf(dip) if ip in ("255.255.255.255", "239.1.2.3") else ("<网关>" if ip == GW else "<网段广播>"):<18}帧长 {ln}')
mc = [r for r in rows if r[1] == bytes([239, 1, 2, 3])][0]
print(f'  组播 239.1.2.3 的 MAC = 01:00:5e + IP 的低 23 位 = {macs(mc[0])}:239.1.2.3 低 23 位是 0x010203 → 01:02:03;注意高位被丢掉,所以 239.129.2.3 也映射到同一个 MAC')

print('== 二:谁会收到?本机内部两个套接字绑定同一个端口(SO_REUSEPORT),分别发单播、受限广播、组播,看两个接收者各收到几份')
def run(dest, kind_):
    socks = []
    for _ in range(2):
        r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); r.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        r.bind(('', 9877)); r.settimeout(0.3)
        if kind_ == 'mcast': r.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(dest) + socket.inet_aton('127.0.0.1'))
        socks.append(r)
    t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); t.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    if kind_ == 'mcast': t.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton('127.0.0.1')); t.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    for i in range(3): t.sendto(b'x', (dest, 9877))
    got = []
    for r in socks:
        n = 0
        while True:
            try: r.recvfrom(10); n += 1
            except socket.timeout: break
        got.append(n)
    for r in socks: r.close()
    return got
for label, dest, k in (('单播 127.0.0.1', '127.0.0.1', 'uni'), ('受限广播 255.255.255.255', '255.255.255.255', 'bc'), ('组播 224.9.9.9(两个都加入了组)', '224.9.9.9', 'mcast')):
    try: print(f'  发 3 个数据报到 {label}:接收者 A、B 各收到 {run(dest, k)} 个')
    except Exception as e: print(f'  {label}: {type(e).__name__}: {e}')
print('  单播只会交给其中一个套接字;广播和组播会交给所有符合条件的套接字——这是它们和单播的本质区别')

print('== 三:广播会不会被路由器转发?ping 子网广播地址:请求是广播帧;网段里的主机会不会回应,由各自系统的 net.inet.icmp.bmcastecho 决定')
print('  sysctl net.inet.icmp.bmcastecho = ' + sysout('sysctl', '-n', 'net.inet.icmp.bmcastecho').strip() + '(本机是 1 = 会回应目的地址为广播 / 组播的 ICMP echo;0 = 不回应)')
with Cap(f'icmp and dst host {BC}', iface='en0', write=True) as c3:
    r = subprocess.run(['ping', '-b', '-c', '3', '-W', '500', BC], capture_output=True, text=True) if False else subprocess.run(['ping', '-c', '3', '-t', '2', BC], capture_output=True, text=True)
print('  ping 输出末几行: ' + ' | '.join(l for l in (r.stdout + r.stderr).splitlines()[-3:]).replace(BC, '<网段广播>')[:200])
n_b = 0
with open(c3.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(b)
        if e.dst == b'\xff' * 6: n_b += 1
print(f'  抓到发往网段广播地址的 ICMP 请求帧 {c3.count} 个,其中目的 MAC 是 ff:ff:ff:ff:ff:ff 的 {n_b} 个——网络层的“广播地址”对应链路层的“广播 MAC”')
print('  路由器不转发子网定向广播 / 受限广播:受限广播 255.255.255.255 的 TTL 虽然是 64,但它只在本链路上有效,第一台路由器就会丢掉它(路由器的行为本机无法实验,这是规范 / 经验,不是实测)')

print('== 四:这个网段上 30 秒内三种目的 MAC 的帧各有多少?(别的设备发出的广播和组播能听到,发给别人的单播多数听不到)')
with Cap('', iface='en0', write=True) as c4:
    time.sleep(30)
cnt = collections.Counter(); byt = collections.Counter(); tot = 0
with open(c4.pcap, 'rb') as f:
    for ts, b in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(b); k = kind(e.dst); cnt[k] += 1; byt[k] += len(b); tot += 1
for k in ('单播', '广播', '组播'): print(f'  {k}:{cnt[k]} 个帧,共 {byt[k]} 字节({cnt[k] / tot * 100:.1f}% 的帧)')
print(f'  广播 + 组播 {cnt["广播"] + cnt["组播"]} 个帧 ≈ 每秒 {(cnt["广播"] + cnt["组播"]) / 30:.1f} 个——网段里每台主机的网卡都要收下并交给 CPU 看一眼;这就是为什么广播域不能无限大')
