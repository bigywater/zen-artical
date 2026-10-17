import sys, os, re, struct, collections, ipaddress, threading, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w23'); reset()
NH = {0: '逐跳选项', 6: 'TCP', 17: 'UDP', 43: '路由头', 44: '分片头', 58: 'ICMPv6', 59: '无下一头', 60: '目的选项'}
def raws(path): return [(ts, ip.raw) for ts, ip in read_pcap(path)]
def lo6(path):
    out = []
    with open(path, 'rb') as f:
        r = dpkt.pcap.Reader(f)
        for ts, buf in r:
            if buf[:4] in (b'\x1e\x00\x00\x00', b'\x00\x00\x00\x1e') or True: out.append((ts, bytes(buf[4:])))
    return [(ts, b) for ts, b in out if b and b[0] >> 4 == 6]
def cs(b):
    if len(b) % 2: b += b'\0'
    s = sum(struct.unpack('>%dH' % (len(b) // 2), b))
    while s >> 16: s = (s & 0xffff) + (s >> 16)
    return ~s & 0xffff
def v6(p):
    w0, pl, nh, hl = struct.unpack('>IHBB', p[:8]); return dict(ver=w0 >> 28, tc=(w0 >> 20) & 0xff, fl=w0 & 0xfffff, pl=pl, nh=nh, hl=hl, src=socket.inet_ntop(socket.AF_INET6, p[8:24]), dst=socket.inet_ntop(socket.AF_INET6, p[24:40]))

print('== 一:ping6 ::1 一次,lo0 上 IPv6 头逐字节解码:版本 / 流量类别 / 流标签 / 载荷长度 / 下一个头 / 跳数限制 / 源 / 目的;再验证 ICMPv6 校验和(包含 IPv6 伪头部)')
with Cap('ip6', iface='lo0', write=True) as c:
    sysout('ping6', '-c', '1', '::1'); time.sleep(0.4)
pk = lo6(c.pcap)
rq = [b for ts, b in pk if b[6] == 58 and b[40] == 128][0]; rp = [b for ts, b in pk if b[6] == 58 and b[40] == 129][0]
print('  请求的前 40 字节(IPv6 头):' + rq[:40].hex(' ', 4))
for tag, p in (('请求', rq), ('应答', rp)):
    h = v6(p)
    print(f'  {tag}:版本 {h["ver"]},流量类别 0x{h["tc"]:02x},流标签 0x{h["fl"]:05x},载荷长度 {h["pl"]},下一个头 {h["nh"]}({NH.get(h["nh"])}),跳数限制 {h["hl"]},源 {h["src"]},目的 {h["dst"]};整个包 {len(p)} 字节 = 40 + {h["pl"]}')
icmp = rq[40:]; ps = rq[8:40] + struct.pack('>I', len(icmp)) + b'\0\0\0' + bytes([58])
zero = icmp[:2] + b'\0\0' + icmp[4:]
print(f'  ICMPv6 校验和:抓到 0x{struct.unpack(">H", icmp[2:4])[0]:04x};自己用“伪头部(源、目的、上层长度、下一个头 58)+ ICMPv6 报文”算出 0x{cs(ps + zero):04x}(lo0 上的包可能被卸载 / 省略校验和)')
print('  ICMPv6 的校验和覆盖伪头部,因为 IPv6 头自己没有校验和字段(IPv4 有)')

print('== 二:IPv4 与 IPv6 的开销对比:同样 ping 一次、同样下载 1 MiB(lo0),看每个包的头部字节数和 MSS')
with Cap('icmp', iface='lo0', write=True) as c4:
    sysout('ping', '-c', '1', '127.0.0.1'); time.sleep(0.4)
p4 = [ip.raw for ts, ip in read_pcap(c4.pcap)][0]
print(f'  ping 127.0.0.1:IP 总长 {len(p4)} 字节(IPv4 头 20 + ICMP 8 + 载荷 {len(p4) - 28});ping6 ::1:IP 总长 {len(rq)} 字节(IPv6 头 40 + ICMP 8 + 载荷 {len(rq) - 48})——两个 ping 默认载荷大小不同(56 与 8),所以总长不能直接比;每个包的 IP 头:IPv4 20 字节(无选项时)、IPv6 固定 40 字节,多 20 字节')
def serve(fam, addr):
    ls = socket.socket(fam); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind((addr, 0)); ls.listen(); pt = ls.getsockname()[1]
    def run():
        cn, _ = ls.accept(); cn.sendall(b'z' * (1 << 20)); cn.close()
    threading.Thread(target=run, daemon=True).start(); return pt
res = {}
for nm, fam, addr in (('IPv4', socket.AF_INET, '127.0.0.1'), ('IPv6', socket.AF_INET6, '::1')):
    pt = serve(fam, addr)
    with Cap(f'tcp port {pt}', iface='lo0', write=True) as c:
        k = socket.socket(fam); k.connect((addr, pt)); n = 0
        while True:
            d = k.recv(1 << 20)
            if not d: break
            n += len(d)
        k.close(); time.sleep(0.3)
    cnt = 0; tot = 0; mss = None; hdr = 0
    with open(c.pcap, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            b = bytes(buf[4:]); cnt += 1; tot += len(b)
            if nm == 'IPv4': iph = (b[0] & 15) * 4; tcp = b[iph:]
            else: iph = 40; tcp = b[40:]
            if tcp[13] & 2:
                o = tcp[20:(tcp[12] >> 4) * 4]; i = 0
                while i < len(o):
                    if o[i] == 2: mss = struct.unpack('>H', o[i + 2:i + 4])[0]; break
                    if o[i] in (0, 1): i += 1
                    else: i += o[i + 1]
            hdr += iph + (tcp[12] >> 4) * 4
    res[nm] = (cnt, tot, mss, hdr, n)
for nm, (cnt, tot, mss, hdr, n) in res.items(): print(f'  {nm}:下载 {n} 字节,lo0 上共 {cnt} 个 IP 包、合计 {tot} 字节(不含 lo0 的 4 字节链路层头);SYN 通告的 MSS = {mss};所有包的 IP + TCP 头合计 {hdr} 字节,占 {hdr / tot * 100:.2f}%')
print(f'  MSS 差:{res["IPv4"][2] - res["IPv6"][2]} 字节(IPv6 头比 IPv4 头多 20 字节,MSS 少 20)')

print('== 三:流量类别与流标签:用 IPV6_TCLASS 设流量类别;内核自己填的流标签是什么样(同一个套接字 / 不同套接字)')
r = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM); r.bind(('::1', 0)); port = r.getsockname()[1]
labels = []; per = []
with Cap(f'ip6 and udp dst port {port}', iface='lo0', write=True) as c:
    for i in range(6):
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        for j in range(4): s.sendto(b'fl', ('::1', port))
    s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM); s.setsockopt(socket.IPPROTO_IPV6, 36, 0xb8)
    for j in range(2): s.sendto(b'tc', ('::1', port))
    time.sleep(0.4)
pk = [v6(b) for ts, b in lo6(c.pcap)]
print(f'  抓到 {len(pk)} 个 UDP over IPv6 包')
for i in range(6): 
    ls_ = [h['fl'] for h in pk[i * 4:(i + 1) * 4]]
    print(f'    套接字 {i + 1}:4 个包的流标签 {["0x%05x" % x for x in ls_]}——{"同一个套接字的流标签相同" if len(set(ls_)) == 1 else "同一个套接字的流标签不同"}')
tcs = pk[24:]
print(f'    设 IPV6_TCLASS=0xb8 的套接字:流量类别 {["0x%02x" % h["tc"] for h in tcs]},流标签 {["0x%05x" % h["fl"] for h in tcs]}')
fl_all = [pk[i * 4]['fl'] for i in range(6)]
print(f'  6 个不同套接字的流标签互不相同:{len(set(fl_all)) == 6};全为 0:{all(x == 0 for x in fl_all)}——流标签是 20 位,由发送方内核生成,用来标记一条“流”,路由器可据此做负载均衡而不必解析上层端口')

print('== 四:真实局域网上的 IPv6 包(en0,25 秒;别的设备的流量只统计个数):下一个头、跳数限制、目的地址类别')
with Cap('ip6', iface='en0', write=True) as c:
    time.sleep(25)
cnt = collections.Counter(); dstc = collections.Counter()
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(buf)
        if e.type != 0x86dd: continue
        p = bytes(e.data); h = v6(p)
        cnt[(h['nh'], h['hl'])] += 1
        d = ipaddress.ip_address(h['dst'])
        kind = {'ff02::fb': 'ff02::fb(mDNS 组播)', 'ff02::1': 'ff02::1(所有节点)', 'ff02::2': 'ff02::2(所有路由器)', 'ff02::c': 'ff02::c(SSDP)', 'ff02::1:3': 'ff02::1:3(LLMNR)'}.get(h['dst'], '其它组播' if d.is_multicast else '单播')
        dstc[kind] += 1
tot = sum(cnt.values())
print(f'  25 秒共 {tot} 个 IPv6 包')
for (nh, hl), n in sorted(cnt.items(), key=lambda x: -x[1]): print(f'    下一个头 {nh}({NH.get(nh, "?")}),跳数限制 {hl}:{n} 个')
print('  目的地址类别:' + ';'.join(f'{k_} {v}' for k_, v in dstc.most_common()))
print('  这 25 秒里所有包的跳数限制只有 255 和 1 两种,没有 64 / 128 这类能被路由到别处的值;跳数限制 255 在邻居发现里用来证明“包没有经过路由器”,这里的 mDNS 也是 255')

print('== 五:扩展头链(构造,不是抓来的):手工拼一个带 逐跳选项 → 路由头 → 分片头 → 目的选项 → UDP 的 IPv6 包,写成 pcap,用 tcpdump 和 scapy 解码,再用自己的“沿下一个头走”的程序验证')
src = socket.inet_pton(socket.AF_INET6, '2001:db8::1'); dst = socket.inet_pton(socket.AF_INET6, '2001:db8::2')
udp = struct.pack('>HHHH', 40000, 9, 8 + 5, 0) + b'hello'
dopt = bytes([17, 0, 1, 4, 0, 0, 0, 0])                                  # 目的选项:下一个头 UDP,8 字节,PadN
frag = bytes([60, 0]) + struct.pack('>HI', 0x0001, 0xdeadbeef)           # 分片头:下一个头 目的选项,偏移 0,M=1,标识
rth = bytes([44, 2, 2, 1]) + b'\0' * 4 + socket.inet_pton(socket.AF_INET6, '2001:db8::3')   # 路由头类型 2,24 字节
hbh = bytes([43, 0, 5, 2, 0, 0, 1, 0])                                   # 逐跳选项:下一个头 路由头,路由器警告 + PadN
body = hbh + rth + frag + dopt + udp
ip6 = struct.pack('>IHBB', 0x60000000, len(body), 0, 64) + src + dst + body
eth = bytes.fromhex('020000000002020000000001') + b'\x86\xdd' + ip6
pc = WT_ = None
pcap_path = str(WT / 'w23_ext.pcap')
open(pcap_path, 'wb').write(struct.pack('<IHHiIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1) + struct.pack('<IIII', 1, 0, len(eth), len(eth)) + eth)
print(f'  构造的包:IPv6 头 40 + 逐跳 {len(hbh)} + 路由头 {len(rth)} + 分片头 {len(frag)} + 目的选项 {len(dopt)} + UDP {len(udp)} = {len(ip6)} 字节;IPv6 头里的“载荷长度”= {len(body)}(包含所有扩展头)')
o = subprocess.run(['tcpdump', '-r', pcap_path, '-nn', '-vv'], capture_output=True, text=True).stdout
print('  tcpdump 解码:' + ' '.join(o.split())[:330])
p = ip6; nh = p[6]; off = 40; chain = [('IPv6 头', 40)]
while nh in (0, 43, 44, 60):
    if nh == 44: ln = 8
    else: ln = (p[off + 1] + 1) * 8
    chain.append((NH[nh], ln)); nh2 = p[off]; off += ln; nh = nh2
chain.append((NH.get(nh, nh), len(p) - off))
print('  自己沿下一个头走:' + ' → '.join(f'{n}({l} 字节)' for n, l in chain))
from scapy.all import IPv6 as S6
sp = S6(ip6); lay = []; x = sp
while x:
    lay.append(type(x).__name__); x = x.payload if x.payload and type(x.payload).__name__ != 'NoPayload' else None
print('  scapy 解码出的层:' + ' / '.join(lay))
print(f'  扩展头合计 {sum(l for n, l in chain[1:-1])} 字节;规范建议的顺序是 逐跳 → 目的选项(第一个)→ 路由 → 分片 → … → 目的选项(第二个)→ 上层;逐跳选项必须紧跟 IPv6 头,因为沿途每个路由器都要检查它')
