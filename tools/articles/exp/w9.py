import sys, os, struct, dpkt, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w9'); reset()
GW = '192.168.11.1'
def ipf(b): return '.'.join(map(str, b))
def csum(b):
    if len(b) % 2: b += b'\0'
    s = sum(struct.unpack('!%dH' % (len(b) // 2), b)); s = (s & 0xffff) + (s >> 16); s = (s & 0xffff) + (s >> 16); return ~s & 0xffff
def frames(path):
    out = []
    with open(path, 'rb') as f:
        for ts, b in dpkt.pcap.Reader(f):
            e = dpkt.ethernet.Ethernet(b)
            if isinstance(e.data, dpkt.ip.IP): out.append((ts, e.data, e.data.raw if hasattr(e.data, 'raw') else b[14:]))
    return out
def fields(ip, raw):
    hl = (raw[0] & 15) * 4
    fl = raw[6] >> 5
    return {'版本': raw[0] >> 4, 'IHL(字节)': hl, 'TOS/DSCP+ECN': f'0x{raw[1]:02x}', '总长': struct.unpack('!H', raw[2:4])[0], 'id': struct.unpack('!H', raw[4:6])[0], '标志': f'{"DF " if fl & 2 else ""}{"MF" if fl & 1 else ""}'.strip() or '无', '片偏移': struct.unpack('!H', raw[6:8])[0] & 0x1fff, 'TTL': raw[8], '协议': raw[9], '校验和': f'0x{struct.unpack("!H", raw[10:12])[0]:04x}', '校验和验算': '通过' if csum(raw[:hl]) == 0 else '不通过'}

print('== 一:逐字段解读一个真实收到的 IPv4 头:向 example.com:80 发一个请求,取回来的第一个带数据的响应包')
ipx = subprocess.run(['dig', '+short', 'example.com', '@1.1.1.1'], capture_output=True, text=True).stdout.split()[0]
with Cap(f'host {ipx} and tcp port 80', iface='en0', write=True) as c:
    subprocess.run(['curl', '-s', '--noproxy', '*', '-o', '/dev/null', '--max-time', '6', f'http://{ipx}/', '-H', 'Host: example.com'], capture_output=True)
fr = frames(c.pcap)
inn = [(ts, ip, raw) for ts, ip, raw in fr if ipf(ip.src) == ipx and isinstance(ip.data, dpkt.tcp.TCP) and len(ip.data.data) > 0][0]
out_ = [(ts, ip, raw) for ts, ip, raw in fr if ipf(ip.dst) == ipx and isinstance(ip.data, dpkt.tcp.TCP) and len(ip.data.data) > 0][0]
fi = fields(inn[1], inn[2])
for k, v in fi.items(): print(f'  {k:<14}{v}')
print(f'  源地址 / 目的地址 各 4 字节(公网 {ipf(inn[1].src)} → 本机);头共 {fi["IHL(字节)"]} 字节,载荷 {fi["总长"] - fi["IHL(字节)"]} 字节(总长 − 头长)')
print(f'  原始头字节: {" ".join(f"{x:02x}" for x in inn[2][:20])}')

print('== 二:收到的包校验和是对的,自己发出去的呢?同一次会话里,本机发出的第一个带数据的包')
fo = fields(out_[1], out_[2])
print(f'  收到的包(来自公网):校验和 {fi["校验和"]},按反码求和验算 {fi["校验和验算"]}')
print(f'  发出的包(本机发出):校验和 {fo["校验和"]},验算 {fo["校验和验算"]}——真实网卡上 IP 头校验和是内核算好填上的,抓到时就是对的;(在 lo0 上则是 0,见第 1 篇)。TCP 校验和可能由网卡卸载,这里没有验证')
print(f'  TTL:收到的包 {fi["TTL"]},发出的包 {fo["TTL"]}。公网主机的初始 TTL 常见是 64 / 128 / 255,收到时 {fi["TTL"]} 说明这个包大约经过了 {64 - fi["TTL"] if fi["TTL"] <= 64 else (128 - fi["TTL"] if fi["TTL"] <= 128 else 255 - fi["TTL"])} 个路由器(按初始值 {64 if fi["TTL"] <= 64 else (128 if fi["TTL"] <= 128 else 255)} 推算,是估计,不是 traceroute 的实测)')
print(f'  id:收到 {fi["id"]},发出 {fo["id"]};标志:收到 {fi["标志"]},发出 {fo["标志"]}。现代系统对 TCP 包设 DF 并让 id 为 0 或随机,id 只在分片重组时才有意义(见分片一篇)')

print('== 三:TOS / DSCP 字段:在套接字上设 IP_TOS,UDP 发出去的包头里就带这个值;ping -z 也可以设置。分别设 0x00、0x28(AF11)、0xb8(EF)')
srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); srv.bind(('127.0.0.1', lab_port())); sp = srv.getsockname()[1]
c_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
seen = []
with Cap(f'udp port {sp}', write=True) as c2:
    for tos in (0x00, 0x28, 0xb8):
        c_.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos); c_.sendto(b'x', ('127.0.0.1', sp)); time.sleep(0.1)
for ts, ip in read_pcap(c2.pcap): seen.append((ip.tos, ip.raw[1]))
print('  设置的 TOS → 抓到包头第 2 字节: ' + ', '.join(f'0x{t:02x} → 0x{r:02x}(DSCP={r >> 2}, ECN={r & 3})' for t, (_, r) in zip((0x00, 0x28, 0xb8), seen)))

print('== 四:IHL > 5 的包:带 IP 选项。ping -R(记录路由)会在 IP 头里加 RR 选项;看抓到的包头长度、选项内容,以及对端是否保留')
with Cap(f'icmp and host {GW}', iface='en0', write=True) as c3:
    r = subprocess.run(['ping', '-R', '-c', '1', '-W', '1000', GW], capture_output=True, text=True)
fr3 = frames(c3.pcap)
req = [x for x in fr3 if ipf(x[1].dst) == GW]
rep = [x for x in fr3 if ipf(x[1].src) == GW]
for label, lst in (('请求', req), ('应答', rep)):
    if lst:
        ts, ip, raw = lst[0]; hl = (raw[0] & 15) * 4
        print(f'  {label}:IP 头 {hl} 字节(IHL={raw[0] & 15}),总长 {struct.unpack("!H", raw[2:4])[0]};' + (f'选项 {len(raw[20:hl])} 字节: {" ".join(f"{x:02x}" for x in raw[20:hl])}' if hl > 20 else '没有选项'))
print(f'  ping 输出: ' + ' | '.join(l for l in r.stdout.splitlines() if 'RR' in l or 'bytes from' in l or 'packet' in l)[:200])
print('  结论:这台 macOS 的 ping -R 发出的包 IHL=5,没有任何 IP 选项,所以这里看不到 Record Route 选项;下一节在网段的真实流量里找到了带选项的包')

print('== 五:协议号字段:20 秒的网段流量里 IPv4 包的协议号分布(1=ICMP, 2=IGMP, 6=TCP, 17=UDP, 其它)')
with Cap('ip', iface='en0', write=True) as c4:
    subprocess.run(['dig', '+short', '+time=2', '+tries=1', '@1.1.1.1', 'example.net'], capture_output=True); subprocess.run(['ping', '-c', '2', GW], capture_output=True); time.sleep(16)
cnt = collections.Counter(); ihl = collections.Counter(); ttl = collections.Counter()
for ts, ip, raw in frames(c4.pcap): cnt[raw[9]] += 1; ihl[raw[0] & 15] += 1; ttl[raw[8]] += 1
NAMES = {1: 'ICMP', 2: 'IGMP', 6: 'TCP', 17: 'UDP', 41: 'IPv6 封装', 47: 'GRE', 50: 'ESP', 89: 'OSPF'}
print('  协议号: ' + ', '.join(f'{p}({NAMES.get(p, "其它")})×{n}' for p, n in cnt.most_common()))
print('  IHL(×4 字节)分布: ' + ', '.join(f'{k * 4} 字节×{n}' for k, n in sorted(ihl.items())) + '——绝大多数包头都是 20 字节(没有选项)')
opt = [(raw[9], raw[20:(raw[0] & 15) * 4]) for ts, ip, raw in frames(c4.pcap) if (raw[0] & 15) > 5]
for pr_, o in opt[:1]: print(f'  那 {len(opt)} 个 24 字节头的包:协议号都是 {sorted({p for p, _ in opt})}({NAMES.get(opt[0][0], "其它")}),选项 4 字节: {" ".join(f"{x:02x}" for x in o)}——选项类型 0x94 = Router Alert(复制标志 1、类 0、编号 20),告诉沿途路由器“这个包要看一下”,IGMP 就是这样做的')
print('  最常见的 TTL 值: ' + ', '.join(f'{t}×{n}' for t, n in ttl.most_common(6)) + '(64 = Linux / macOS 默认起点,128 = Windows,255 = 网络设备;小于起点的数字是经过的路由器扣掉的)')
