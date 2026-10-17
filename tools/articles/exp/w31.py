import sys, os, re, struct, collections, ipaddress, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w31'); reset()
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
_t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); _t.connect((gw, 9)); ME = _t.getsockname()[0]; _t.close()
net = ipaddress.ip_interface(ME + '/22').network; BC = str(net.broadcast_address)
def frames(path):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf); out.append((ts, e.type, ':'.join('%02x' % b for b in e.dst), bytes(e.data), len(buf)))
    return out

print('== 一:SO_BROADCAST:往广播地址发 UDP 必须先打开这个套接字选项,否则被内核拒绝')
for tgt_nm, tgt in (('受限广播 255.255.255.255', '255.255.255.255'), ('本网段的定向广播地址', BC)):
    for on in (False, True):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if on: s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try: n = s.sendto(b'hello-bc', (tgt, 33435)); res = f'发送成功({n} 字节)'
        except OSError as e: res = f'失败 [Errno {e.errno}] {e.strerror}'
        print(f'  {tgt_nm}:SO_BROADCAST {"打开" if on else "未打开"} → {res}')
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print(f'  getsockopt(SO_BROADCAST) 默认值 {s.getsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST)}(0 = 关)。对单播地址发包不需要这个选项')

print('== 二:两种广播地址在线上:受限广播 255.255.255.255 和本网段定向广播地址(子网最后一个地址),抓 en0 看以太网目的 MAC、IP 目的地址、TTL;以及本机路由怎么处理它们')
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
with Cap(f'udp and dst port 33435', iface='en0', write=True) as c:
    s.sendto(b'limited', ('255.255.255.255', 33435)); time.sleep(0.2); s.sendto(b'directed', (BC, 33435)); time.sleep(0.5)
for ts, et, dst, ip, ln in frames(c.pcap):
    if et != 0x0800: continue
    d = socket.inet_ntoa(ip[16:20]); print(f'  以太网目的 MAC {dst},IP 目的 {"255.255.255.255(受限广播)" if d == "255.255.255.255" else "本网段的定向广播地址"},源地址是{"本机" if socket.inet_ntoa(ip[12:16]) == ME else "其它"},TTL {ip[8]},帧长 {ln} 字节(IP 总长 {struct.unpack(">H", ip[2:4])[0]})')
for dst in ('255.255.255.255', BC):
    r = sysout('route', '-n', 'get', dst); d = {k_.strip(): v.strip() for k_, v in (l.split(':', 1) for l in r.splitlines() if ':' in l)}
    print(f'  route get {"255.255.255.255" if dst == "255.255.255.255" else "定向广播地址"}:接口 {d.get("interface", "?")},标志 {d.get("flags", "?")}')
print('  两种广播的以太网目的地址都是 ff:ff:ff:ff:ff:ff,同一网段所有设备的网卡都会收下并交给 IP 层;区别在 IP 目的:受限广播永远不会被路由器转发,定向广播理论上可以被转发到目标子网(现在的路由器默认都不转发)')

print('== 三:本机上谁能收到广播:5 个接收套接字(SO_REUSEPORT)分别绑定 0.0.0.0、本机地址、定向广播地址、127.0.0.1、255.255.255.255,发送方发一个定向广播和一个受限广播,看各接收方是否收到')
def mkrecv(addr, port):
    r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    try: r.bind((addr, port)); r.settimeout(0.3); return r
    except OSError as e: return str(e.strerror)
tmp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); tmp.bind(('0.0.0.0', 0)); port = tmp.getsockname()[1]; tmp.close()
R = [(nm, mkrecv(a, port)) for nm, a in (('0.0.0.0', '0.0.0.0'), ('本机 en0 地址', ME), ('定向广播地址', BC), ('127.0.0.1', '127.0.0.1'), ('255.255.255.255', '255.255.255.255'))]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
for tgt_nm, tgt in (('定向广播', BC), ('受限广播', '255.255.255.255')):
    s.sendto(b'who-gets-it', (tgt, port)); time.sleep(0.2)
    row = []
    for nm, r in R:
        if isinstance(r, str): row.append(f'{nm}:绑定失败({r})'); continue
        try: d, a = r.recvfrom(100); row.append(f'{nm}:收到'); 
        except socket.timeout: row.append(f'{nm}:没收到')
    print(f'  发 {tgt_nm}:' + ';'.join(row))
print('  也就是说广播只会交给绑定了通配地址(或恰好是那个广播地址)的套接字;绑在本机单播地址或 127.0.0.1 上的收不到')

print('== 四:局域网上的广播流量有多少(en0,30 秒,别的设备的帧只统计个数):以太网目的 MAC 是 ff:ff:ff:ff:ff:ff 的帧按类型 / 协议 / UDP 目的端口分类')
with Cap('ether broadcast', iface='en0', write=True) as c:
    time.sleep(30)
tot = collections.Counter(); ports = collections.Counter(); nbytes = 0
for ts, et, dst, ip, ln in frames(c.pcap):
    nbytes += ln
    if et == 0x0806: tot['ARP'] += 1
    elif et == 0x0800:
        pr = ip[9]
        if pr == 17: tot['IPv4 UDP'] += 1; ports[struct.unpack('>H', ip[(ip[0] & 15) * 4 + 2:(ip[0] & 15) * 4 + 4])[0]] += 1
        elif pr == 2: tot['IPv4 IGMP'] += 1
        else: tot[f'IPv4 协议 {pr}'] += 1
    elif et == 0x86dd: tot['IPv6'] += 1
    else: tot[f'其它 0x{et:04x}'] += 1
n = sum(tot.values())
print(f'  30 秒共 {n} 个广播帧({nbytes} 字节,平均 {n / 30:.1f} 帧/秒、{nbytes * 8 / 30 / 1000:.1f} Kbit/s):' + ';'.join(f'{k_} {v}' for k_, v in tot.most_common()))
NAME = {67: 'DHCP 服务器端口', 68: 'DHCP 客户端端口', 137: 'NetBIOS 名字服务', 138: 'NetBIOS 数据报', 5353: 'mDNS', 1900: 'SSDP', 5355: 'LLMNR', 17500: 'Dropbox 局域网发现', 57621: 'Spotify 局域网发现'}
print('  IPv4 UDP 广播的目的端口:' + ';'.join(f'{k_}({NAME.get(k_, "?")}) {v}' for k_, v in ports.most_common(8)))
print('  每个广播帧都会打断同一网段里每一台设备的网卡 / 内核,即使它们不关心——这就是广播的代价,组播(下一篇)让不关心的设备可以在网卡层就丢掉')
