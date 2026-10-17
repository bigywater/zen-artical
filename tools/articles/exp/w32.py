import sys, os, re, struct, collections, ipaddress; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w32'); reset()
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
_t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); _t.connect((gw, 9)); ME = _t.getsockname()[0]; _t.close()
G = '239.255.42.99'; PORT = 34567
def mreq(g, ifaddr): return socket.inet_aton(g) + socket.inet_aton(ifaddr)
def frames(path):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf); out.append((ts, e.type, ':'.join('%02x' % b for b in e.dst), bytes(e.data), len(buf)))
    return out
def mkrecv(g=None, ifaddr=ME, port=PORT, reuse=True):
    r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if reuse: r.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    r.bind(('0.0.0.0', port)); r.settimeout(0.4)
    if g: r.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq(g, ifaddr))
    return r
def got(r):
    try: r.recvfrom(200); return True
    except socket.timeout: return False

print('== 一:加入一个组播组:IP_ADD_MEMBERSHIP 之后,网卡开始收这个组的以太网组播帧;IGMP 报告发出;netstat -g 里出现成员关系;组播 IP 到以太网 MAC 的映射')
def ngroups(): return [l.split() for l in sysout('netstat', '-g', '-n', '-I', 'en0').splitlines() if re.match(r'^\d+\.\d+\.\d+\.\d+\s', l) and 'en0' in l]
before = [x[0] for x in ngroups()]
with Cap('igmp', iface='en0', write=True) as c:
    r = mkrecv(G); time.sleep(1.2)
after = [x for x in ngroups() if x[0] == G]
print(f'  加入前 netstat -g 里 en0 的 IPv4 组 {len(before)} 个({"有" if G in before else "没有"} {G});加入后:{after[0] if after else "没有"}' if True else '')
mac = '01:00:5e:' + ':'.join('%02x' % b for b in [socket.inet_aton(G)[1] & 0x7f, socket.inet_aton(G)[2], socket.inet_aton(G)[3]])
print(f'  {G} → 以太网组播 MAC = 01:00:5e + 低 23 位 = {mac}(第二字节的最高位被清掉,只取 IP 地址后 23 位)')
ig = [fr for fr in frames(c.pcap) if fr[1] == 0x0800]
for ts, et, dst, ip, ln in ig:
    ihl = (ip[0] & 15) * 4; t = ip[ihl]; grp = socket.inet_ntoa(ip[ihl + 4:ihl + 8]) if t in (0x16, 0x12, 0x17) else None
    print(f'  抓到 IGMP 报文:IP 目的 {socket.inet_ntoa(ip[16:20])},以太网目的 MAC {dst},IGMP 类型 0x{t:02x}' + (f'(成员报告),组地址 {"= " + G if grp == G else grp}' if t in (0x16, 0x12) else '') + f',IP 头 {ihl} 字节(含 Router Alert 选项),TTL {ip[8]}')
print(f'  共 {len(ig)} 个 IGMP 报文;32 个不同的组播 IP 地址会映射到同一个以太网 MAC(IP 地址里有 5 位被丢掉),例如 {G} 与 ' + f'224.{(socket.inet_aton(G)[1] & 0x7f)}.{socket.inet_aton(G)[2]}.{socket.inet_aton(G)[3]} 的 MAC 相同' if True else '')
m2 = '01:00:5e:' + ':'.join('%02x' % b for b in [socket.inet_aton('224.127.42.99')[1] & 0x7f, 42, 99]); print(f'  验证:224.127.42.99 → {m2},与 {G} 的 MAC {"相同" if m2 == mac else "不同"}')

print('== 二:谁能收到:发送方往组播地址发一个数据报;加入了组的接收方、没加入的接收方、同一台机器上的另一个加入者,以及关掉 IP_MULTICAST_LOOP 之后的情况')
r_in = mkrecv(G); r_in2 = mkrecv(G); r_out = mkrecv(None)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ME))
print(f'  IP_MULTICAST_LOOP 默认值 {s.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP)}(1 = 本机上加入了组的套接字也会收到自己发的)')
s.sendto(b'to-group', (G, PORT)); time.sleep(0.2)
print(f'  默认(LOOP=1):加入了组的接收方 1 {"收到" if got(r_in) else "没收到"};加入了组的接收方 2(同一端口,SO_REUSEPORT){"收到" if got(r_in2) else "没收到"};没有加入组、只绑了 0.0.0.0 端口的接收方 {"收到" if got(r_out) else "没收到"}')
s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 0); s.sendto(b'to-group-noloop', (G, PORT)); time.sleep(0.2)
print(f'  IP_MULTICAST_LOOP = 0:加入了组的接收方 1 {"收到" if got(r_in) else "没收到"};接收方 2 {"收到" if got(r_in2) else "没收到"}(同一台机器上的接收方都收不到了;别的机器仍然能收到,这里没有第二台机器可验证)')
s2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s2.sendto(b'default-if', (G, PORT)); time.sleep(0.2)
print(f'  没有设置 IP_MULTICAST_IF 的发送方发同一个组:加入了组的接收方 1 {"收到" if got(r_in) else "没收到"}(出口按路由表选)')
with Cap(f'udp dst port {PORT}', iface='en0', write=True) as c:
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1); s.sendto(b'wire', (G, PORT)); time.sleep(0.4)
for ts, et, dst, ip, ln in frames(c.pcap):
    if et == 0x0800: print(f'  线上:以太网目的 MAC {dst}(= 组播 MAC {mac}:{dst == mac}),IP 目的 {socket.inet_ntoa(ip[16:20])},TTL {ip[8]}')

print('== 三:TTL 范围:IP_MULTICAST_TTL 默认是 1(只在本网段);改成别的值,线上 TTL 随之改变;各个范围的传统约定')
ttls = {}
for t in (1, 4, 32):
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, t)
    with Cap(f'udp dst port {PORT}', iface='en0', write=True) as c:
        s.sendto(b'ttl', (G, PORT)); time.sleep(0.4)
    ttls[t] = [ip[8] for ts, et, dst, ip, ln in frames(c.pcap) if et == 0x0800]
s3 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print(f'  新套接字 IP_MULTICAST_TTL 默认 = {s3.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL)};设成 1 / 4 / 32 后线上抓到的 TTL:' + ';'.join(f'{k_} → {v}' for k_, v in ttls.items()))
print('  传统约定:TTL 0 = 只在本机;1 = 本子网;<32 = 本站点 / 机构内;<64 = 本地区;<128 = 本大洲;<255 = 全球。组播路由器每转发一次 TTL 减 1,所以 TTL 同时是“传播半径”;本机默认 1,所以默认不会离开这个网段')
n224 = []
with Cap('ip dst net 224.0.0.0/24', iface='en0', write=True) as c:
    time.sleep(8)
for ts, et, dst, ip, ln in frames(c.pcap):
    if et == 0x0800: n224.append(ip[8])
print(f'  224.0.0.0/24 是“本地链路”组播(路由器永远不转发),8 秒里抓到别的设备发往它的 IP 包 {len(n224)} 个,TTL 取值 {sorted(set(n224))}')

print('== 四:出口接口:route get 看组播走哪个接口;用 IP_MULTICAST_IF 指定 lo0 / en0;在 lo0 上也能收发')
r = sysout('route', '-n', 'get', G); d = {k_.strip(): v.strip() for k_, v in (l.split(':', 1) for l in r.splitlines() if ':' in l)}
print(f'  route get {G}:接口 {d.get("interface", "?")},标志 {d.get("flags", "?")}')
res = []
for nm, ifa in (('en0 的地址', ME), ('lo0 的地址 127.0.0.1', '127.0.0.1')):
    rr = mkrecv(G, ifa, port=PORT + 1); ss = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        ss.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ifa)); ss.sendto(b'if-test', (G, PORT + 1)); time.sleep(0.2); res.append(f'{nm}:{"收到" if got(rr) else "没收到"}')
    except OSError as e: res.append(f'{nm}:失败 {e.strerror}')
print('  接收方在某个接口地址上加入,发送方用同一个接口地址发:' + ';'.join(res))
rr = mkrecv(G, '127.0.0.1', port=PORT + 2); ss = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); ss.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ME)); ss.sendto(b'cross', (G, PORT + 2)); time.sleep(0.2)
print(f'  接收方在 lo0 上加入、发送方从 en0 发:{"收到" if got(rr) else "没收到"}——组播成员关系是按接口算的,在哪个接口加入就只收那个接口来的')

print('== 五:成员关系的数量限制:一个套接字最多能加入多少个不同的组;同一个组被两个套接字加入时的引用计数')
sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); n = 0
try:
    for i in range(400):
        sk.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq(f'239.254.{i // 250}.{i % 250 + 1}', ME)); n += 1
    print(f'  一个套接字连续加入 400 个不同的组,全部成功')
except OSError as e: print(f'  一个套接字最多加入了 {n} 个组,第 {n + 1} 个失败:{e.strerror}')
print('  ' + sysout('sysctl', 'net.inet.ip.maxmemberships').strip() if 'maxmemberships' in sysout('sysctl', '-a') else '  (sysctl 里没有 net.inet.ip.maxmemberships 这一项)')
a1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); a2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
G2 = '239.255.42.77'
for x in (a1, a2): x.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq(G2, ME))
c1 = sum(1 for l in sysout('netstat', '-g', '-n', '-I', 'en0').splitlines() if l.startswith(G2))
a1.close(); c2 = sum(1 for l in sysout('netstat', '-g', '-n', '-I', 'en0').splitlines() if l.startswith(G2)); a2.close(); time.sleep(0.2)
c3 = sum(1 for l in sysout('netstat', '-g', '-n', '-I', 'en0').splitlines() if l.startswith(G2))
print(f'  两个套接字加入同一个组 {G2}:netstat 里该组的条目数 {c1};关掉第一个套接字后 {c2};关掉第二个后 {c3}——内核对同一个接口上的同一个组只记一个成员,按引用计数,最后一个套接字离开才真正退出')
