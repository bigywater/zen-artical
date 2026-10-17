import sys, os, re, struct, ipaddress; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w20'); reset()
PUB = '104.20.23.154'
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
_t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); _t.connect((gw, 9)); ME = _t.getsockname()[0]; _t.close()
net = ipaddress.ip_interface(ME + '/22').network
print('== 一:IPv4 特殊用途地址段(IANA 特殊用途登记 RFC 6890 等,这一节是查表 + 用 ipaddress 模块算数量,不是实验):每段多少个地址,合计占整个 IPv4 空间多大比例')
RANGES = [('0.0.0.0/8', '“本网络”,只能作源地址(如 0.0.0.0 用于启动时)'), ('10.0.0.0/8', '私有地址'), ('100.64.0.0/10', '共享地址空间(运营商级 NAT 用,RFC 6598)'), ('127.0.0.0/8', '回环'), ('169.254.0.0/16', '链路本地(自动配置)'), ('172.16.0.0/12', '私有地址'), ('192.0.0.0/24', 'IETF 协议分配'), ('192.0.2.0/24', '文档用 TEST-NET-1'), ('192.168.0.0/16', '私有地址'), ('198.18.0.0/15', '网络基准测试'), ('198.51.100.0/24', '文档用 TEST-NET-2'), ('203.0.113.0/24', '文档用 TEST-NET-3'), ('224.0.0.0/4', '组播'), ('240.0.0.0/4', '保留(含 255.255.255.255 受限广播)')]
tot = 0
print('    地址段               个数         用途')
for r, why in RANGES:
    n = ipaddress.ip_network(r).num_addresses; tot += n
    print(f'    {(r if r != "192.168.0.0/16" else "192.168/16"):<18}{n:>12,}    {why}')
print(f'  合计 {tot:,} 个地址,占整个 IPv4 空间(2^32 = {2 ** 32:,})的 {tot / 2 ** 32 * 100:.2f}%;其中私有地址三段共 {sum(ipaddress.ip_network(r).num_addresses for r in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")):,} 个')

print('== 二:Python 的 ipaddress 模块怎么分类这些地址(各取一个样本):is_private / is_global / is_loopback / is_link_local / is_multicast / is_reserved')
print(f'  Python {sys.version.split()[0]}')
print('    样本地址            private global loopback linklocal multicast reserved')
samples = ['0.0.0.1', '10.1.2.3', '100.64.1.1', '127.0.0.1', '169.254.1.1', '172.16.5.5', '192.0.0.9', '192.0.2.1', '198.18.0.1', '198.51.100.1', '203.0.113.1', '224.0.0.1', '240.0.0.1', '255.255.255.255', '8.8.8.8']
odd = []
for sm in samples:
    a = ipaddress.ip_address(sm)
    fl = [a.is_private, a.is_global, a.is_loopback, a.is_link_local, a.is_multicast, a.is_reserved]
    print(f'    {sm:<18}' + ''.join(f'{"是" if f else "-":>8}' for f in fl))
    if not a.is_private and not a.is_global: odd.append(sm)
print(f'  既不是 private 也不是 global 的样本:{odd}——“私有”和“全球可达”并不是互补的两类;100.64/10 就是这样一个例子')

print('== 三:往这些地址发一个 UDP 包,第一个包实际去了哪里(en0 抓包看目的 MAC / 是否先 ARP;lo0 看有没有走回环)')
def macof(ip_):
    for l in sysout('arp', '-an').splitlines():
        if f'({ip_})' in l: return l.split(' at ')[1].split()[0]
    return None
gwmac = macof(gw)
CAND = [('回环 127.0.0.1', '127.0.0.1'), ('回环段内的 127.0.0.2', '127.0.0.2'), ('0.0.0.0', '0.0.0.0'), ('私有 10/8', '10.99.99.99'), ('私有 172.16/12', '172.20.1.1'), ('私有 192.168/16 里本网段之外的地址', '192.168.200.200'), ('共享地址 100.64/10', '100.64.0.1'), ('链路本地 169.254/16', '169.254.1.1'), ('文档 192.0.2.1', '192.0.2.1'), ('基准测试 198.18/15', '198.18.0.1'), ('组播 224.0.0.251(mDNS)', '224.0.0.251'), ('组播 239.255.255.250(SSDP)', '239.255.255.250'), ('保留 240.0.0.1', '240.0.0.1'), ('受限广播 255.255.255.255', '255.255.255.255'), ('本网段的广播地址', str(net.broadcast_address)), ('本网段里一个没人用的地址', str(net.network_address + 777)), ('公网 8.8.8.8', '8.8.8.8')]
def frames(path):
    import dpkt
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(buf)
            out.append((e.type, ':'.join('%02x' % b for b in e.dst)))
    return out
def whereto(fr):
    outs = []
    for et, dm in fr:
        if et == 0x0806: outs.append('先发 ARP 请求(广播,问这个地址是谁)')
        elif dm == gwmac: outs.append('IP 包,目的 MAC = 默认网关')
        elif dm == 'ff:ff:ff:ff:ff:ff': outs.append('IP 包,目的 MAC = 广播')
        elif dm.startswith('01:00:5e'): outs.append('IP 包,目的 MAC = 组播 01:00:5e:…')
        else: outs.append('IP 包,目的 MAC = 其它主机')
    return outs
summary = []
for nm, a in CAND:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    with Cap(f'udp and dst host {a} and dst port 33435', iface='lo0', write=True) as c0:
        with Cap(f'(arp and host {a}) or (udp and dst host {a} and dst port 33435)', iface='en0', write=True) as c1:
            try: s.sendto(b'special', (a, 33435)); res = '发送成功'
            except OSError as e: res = f'发送失败 [Errno {e.errno}] {e.strerror}'
            time.sleep(0.8)
    w = whereto(frames(c1.pcap)); lo = len(read_pcap(c0.pcap))
    kinds = sorted(set(w))
    summary.append((nm, res, kinds, lo))
    print(f'  {nm}:{res};en0 上 {len(w)} 个帧:{"、".join(kinds) if kinds else "无"};lo0 上 {lo} 个包')

print('== 四:哪些地址能 bind(本机能不能当“自己的地址”),哪些能 connect(TCP,1.5 秒超时)')
bres = []
for nm, a in (('0.0.0.0', '0.0.0.0'), ('127.0.0.1', '127.0.0.1'), ('127.0.0.2', '127.0.0.2'), ('本机 en0 地址', ME), ('文档 192.0.2.1', '192.0.2.1'), ('私有 10.99.99.99', '10.99.99.99'), ('组播 224.0.0.251', '224.0.0.251'), ('255.255.255.255', '255.255.255.255'), ('本网段广播地址', str(net.broadcast_address))):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.bind((a, 0)); r = '成功'
    except OSError as e: r = f'失败:{e.strerror}'
    bres.append((nm, r)); print(f'  UDP bind {nm:<14}{r}')
for nm, a in (('127.0.0.2', '127.0.0.2'), ('0.0.0.0', '0.0.0.0'), ('255.255.255.255', '255.255.255.255'), ('240.0.0.1', '240.0.0.1')):
    lsn = socket.socket(); lsn.bind(('127.0.0.1', 0)); lsn.listen(); pt = lsn.getsockname()[1]
    k = socket.socket(); k.settimeout(1.5); t0 = time.time()
    try: k.connect((a, pt)); r = '连上了(进了本机监听的端口)'
    except Exception as e: r = f'{type(e).__name__}:{getattr(e, "strerror", None) or e}'
    print(f'  TCP connect {nm}:{pt} → {r},用时 {(time.time() - t0) * 1000:.0f} ms')
    k.close(); lsn.close()

print('== 五:真实公网路径上出现的地址类别:traceroute 到公网主机,统计前 12 跳回应者的地址类别(只统计个数,不写出地址)')
o = sysout('traceroute', '-n', '-q', '1', '-m', '12', '-w', '1', PUB, timeout=60)
cnt = {}; hops = []
for l in o.splitlines():
    m = re.match(r'^\s*(\d+)\s+(\d+\.\d+\.\d+\.\d+)', l)
    if not m: continue
    a = ipaddress.ip_address(m.group(2))
    if str(a).startswith('192.168.'): k_ = '私有 192.168/16(本机局域网网关)'
    elif a in ipaddress.ip_network('10.0.0.0/8'): k_ = '私有 10/8'
    elif a in ipaddress.ip_network('172.16.0.0/12'): k_ = '私有 172.16/12'
    elif a in ipaddress.ip_network('100.64.0.0/10'): k_ = '共享地址 100.64/10'
    elif a.is_private: k_ = '其它特殊用途地址'
    else: k_ = '公网地址'
    cnt[k_] = cnt.get(k_, 0) + 1; hops.append((int(m.group(1)), k_))
print(f'  前 12 跳里有 {len(hops)} 跳回应了,其余无应答;各类别个数:' + ';'.join(f'{k_} {v}' for k_, v in cnt.items()))
print('  各跳类别:' + ' '.join(f'{h}:{k_.split(" ")[0]}' for h, k_ in hops))
print('  路径上的私有地址是路由器的接口地址:运营商 / 校园网内部可以用私有地址编号,包仍然能被转发;这些地址在互联网上不全局唯一,所以只能出现在各自的网络里(超时报文却会把它们带出来)')
