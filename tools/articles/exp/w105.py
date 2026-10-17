import sys, os, re, struct, subprocess, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
import dpkt
tee('w105'); reset()
LAB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'wtmp_lab')
IMG, NET = 'netlab-tun2', 'tunnet'
A_IP, B_IP = '172.30.0.2', '172.30.0.3'


def dk(*argv, timeout=120):
    r = subprocess.run(['docker', *argv], capture_output=True, text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()


def dx(c, cmd, timeout=120):
    return dk('exec', c, 'sh', '-c', cmd, timeout=timeout)


def teardown():
    dk('rm', '-f', 'ta', 'tb'); dk('network', 'rm', NET)


def setup():
    teardown()
    dk('network', 'create', '--subnet', '172.30.0.0/24', NET)
    for n, ip in (('ta', A_IP), ('tb', B_IP)):
        dk('run', '-d', '--name', n, '--network', NET, '--ip', ip, '--cap-add', 'NET_ADMIN', '--sysctl', 'net.ipv6.conf.all.disable_ipv6=1', '--sysctl', 'net.ipv6.conf.default.disable_ipv6=1', IMG, 'sleep', '3600')
        for f in ('an.py', 'srv.py', 'cli.py'): dk('cp', os.path.join(LAB, f), f'{n}:/{f}')
        dx(n, 'umask 077; wg genkey > /k; wg pubkey < /k > /p')
    # GRE
    for n, l, r, a in (('ta', A_IP, B_IP, '10.1.0.1/30'), ('tb', B_IP, A_IP, '10.1.0.2/30')):
        dx(n, f'ip link add g0 type gre local {l} remote {r} && ip addr add {a} dev g0 && ip link set g0 up')
    # VXLAN(不指定底层网卡 dev,内核不会自动减 50 字节)
    for n, l, r, a in (('ta', A_IP, B_IP, '10.2.0.1/30'), ('tb', B_IP, A_IP, '10.2.0.2/30')):
        dx(n, f'ip link add v0 type vxlan id 42 dstport 4789 local {l} remote {r} && ip addr add {a} dev v0 && ip link set v0 up')
    # WireGuard
    pa, pb = dx('ta', 'cat /p'), dx('tb', 'cat /p')
    for n, peer, port_ep, a, allowed in (('ta', pb, B_IP, '10.3.0.1/30', '10.3.0.2/32'), ('tb', pa, A_IP, '10.3.0.2/30', '10.3.0.1/32')):
        dx(n, f'ip link add w0 type wireguard && wg set w0 private-key /k listen-port 51820 peer {peer} allowed-ips {allowed} endpoint {port_ep}:51820 && ip addr add {a} dev w0 && ip link set w0 up')
    # IPsec ESP 隧道模式(AES-GCM-128,密钥是实验用的固定值)
    key = '0x0102030405060708090a0b0c0d0e0f1011121314'
    for n, me, you, mi, yo, so, si in (('ta', A_IP, B_IP, '10.4.0.1', '10.4.0.2', '0x1001', '0x1002'), ('tb', B_IP, A_IP, '10.4.0.2', '10.4.0.1', '0x1002', '0x1001')):
        dx(n, f'ip addr add {mi}/32 dev lo; ip route add {yo}/32 via {you} dev eth0 src {mi}; '
              f'ip xfrm state add src {me} dst {you} proto esp spi {so} mode tunnel aead "rfc4106(gcm(aes))" {key} 128; '
              f'ip xfrm state add src {you} dst {me} proto esp spi {si} mode tunnel aead "rfc4106(gcm(aes))" {key} 128; '
              f'ip xfrm policy add src {mi}/32 dst {yo}/32 dir out tmpl src {me} dst {you} proto esp mode tunnel; '
              f'ip xfrm policy add src {yo}/32 dst {mi}/32 dir in tmpl src {you} dst {me} proto esp mode tunnel')
    ma = re.search(r'link/ether ([0-9a-f:]+)', dx('ta', 'ip -o link show v0')).group(1); mb = re.search(r'link/ether ([0-9a-f:]+)', dx('tb', 'ip -o link show v0')).group(1)
    dx('ta', f'ip neigh replace 10.2.0.2 lladdr {mb} dev v0 nud permanent'); dx('tb', f'ip neigh replace 10.2.0.1 lladdr {ma} dev v0 nud permanent')
    dx('tb', 'nohup python3 /srv.py >/dev/null 2>&1 &')
    time.sleep(1)


ROUTES = {'g0': ('10.1.0.0/30', '10.1.0.1'), 'v0': ('10.2.0.0/30', '10.2.0.1'), 'w0': ('10.3.0.0/30', '10.3.0.1')}


def reset_route(dev):
    # 两端都要:删掉再加回直连路由,内核按目的地缓存的路径 MTU 例外(ip route show cache 能看到)随路由一起清掉
    net, src = ROUTES[dev]
    dx('ta', f'ip route del {net} dev {dev}; ip route add {net} dev {dev} proto kernel scope link src {src}')
    peer = src[:-1] + '2'
    dx('tb', f'ip route del {net} dev {dev}; ip route add {net} dev {dev} proto kernel scope link src {peer}')


def mtu_of(c, dev):
    m = re.search(r'mtu (\d+)', dx(c, f'ip -o link show {dev}'))
    return int(m.group(1)) if m else None


def cap(filt, action, pre=0.7, post=0.6):
    """在 ta 的 eth0 上抓 ta→tb 方向的外层 IP 包,返回 [(总长, 分片偏移, 标志)]"""
    out = dx('ta', f"tcpdump -l -nn -i eth0 -v 'src host {A_IP} and dst host {B_IP} and ({filt})' > /tmp/c.txt 2>&1 & P=$!; sleep {pre}; {action}; sleep {post}; kill $P; sleep 0.2; cat /tmp/c.txt")
    return [(int(m.group(3)), int(m.group(1)), m.group(2)) for m in re.finditer(r'(?m)^\d\d:\d\d:\d\d\.\d+ IP \(.*?offset (\d+), flags \[([^\]]*)\].*?length (\d+)\)', out)]


NOWG = 'ip and not udp port 51820'  # 排除 WireGuard 的保活包
PING = {'gre': ('10.1.0.2', NOWG), 'vxlan': ('10.2.0.2', NOWG), 'wg': ('10.3.0.2', 'ip'), 'esp': ('-I 10.4.0.1 10.4.0.2', NOWG)}
NAMES = {'gre': 'GRE', 'vxlan': 'VXLAN', 'wg': 'WireGuard', 'esp': 'IPsec ESP(隧道模式,AES-GCM-128)'}

if os.environ.get('W105_SETUP_ONLY'): setup(); sys.exit()
try:
    setup()
    for k, (dst, _) in PING.items(): dx('ta', f'ping -c 2 -W 2 {dst} >/dev/null')   # 预热:WireGuard 握手、ARP

    print('== 一:Docker 里的 Linux 虚拟机内核(内核版本见下),两个容器 ta、tb 在一个 MTU 1500 的桥上,中间真的建了 GRE、VXLAN、WireGuard 和 IPsec ESP 四种隧道。每条隧道里 ping 一个固定大小的内层 IP 包,在 ta 的 eth0 上抓外层 IP 包,看每个包多出多少字节')
    print('  内核:' + dx('ta', 'uname -r') + ';ta 的 eth0 MTU ' + str(mtu_of('ta', 'eth0')))
    sizes = (84, 85, 100, 528, 1028, 1229)
    print('    隧道                              ' + ''.join(f'内层 {s:>4}   ' for s in sizes))
    over = {}
    for k, (dst, flt) in PING.items():
        row = []
        for s in sizes:
            pk = cap(flt, f'ping -c 1 -W 2 -s {s - 28} {dst} >/dev/null')
            L = max((p[0] for p in pk), default=0)
            row.append((s, L)); over.setdefault(k, []).append(L - s)
        print(f'    {NAMES[k]:<34}' + ''.join(f'→ {L:>4}(+{L - s:>2}) ' for s, L in row))
    print(f'  GRE 每个包恒定 +{over["gre"][0]}(外层 IP 20 + GRE 头 4);VXLAN 恒定 +{over["vxlan"][0]}(外层 IP 20 + UDP 8 + VXLAN 8 + 内层以太网头 14);WireGuard 额外字节随内层大小变化,范围 +{min(over["wg"])}~+{max(over["wg"])}(内层先补零到 16 的倍数);ESP 同样不是常数,范围 +{min(over["esp"])}~+{max(over["esp"])}(填充到 4 字节边界,加 ESP 尾 2 字节)')
    print('  内层大小为 16 的倍数时,WireGuard 刚好 +60(外层 IP 20 + UDP 8 + 头 16 + 认证标签 16);不是 16 的倍数的内层包,补到下一个 16 的倍数。IPv6 作外层则每个包多 20 字节(外层 IPv6 头 40,不是 20)——这一点没有测,是计算')

    print('== 二:内核给各隧道接口自动设的 MTU,以及加一个 “dev eth0” 参数后 VXLAN 的 MTU')
    for dev in ('g0', 'v0', 'w0'): print(f'  {dev:<3} 默认 MTU {mtu_of("ta", dev)}')
    dx('ta', f'ip link add v1 type vxlan id 43 dstport 4790 dev eth0 local {A_IP} remote {B_IP}')
    print(f'  v1(VXLAN,指定了底层网卡 dev eth0)MTU {mtu_of("ta", "v1")};v0(没指定 dev)MTU {mtu_of("ta", "v0")}——后者内核不知道底层是哪块网卡,没有自动减 50 字节,要自己调')
    dx('ta', 'ip link del v1')
    print('  IPsec ESP 在 Linux 里不是一个接口,没有接口 MTU;路径 MTU 由路由和 xfrm 状态推算')

    print('== 三:内层包大小超过隧道 MTU 时分别发生什么。ping -M do 表示内层包带 DF;-M dont 表示不带。每行列出 ta 的 eth0 上出去的外层 IP 包(总长 / 分片偏移 / 标志)')
    cases = [('gre', 'g0', None, 1476, 'do'), ('gre', 'g0', None, 1477, 'do'), ('gre', 'g0', None, 1477, 'dont'),
             ('wg', 'w0', None, 1420, 'do'), ('wg', 'w0', None, 1421, 'do'),
             ('vxlan', 'v0', None, 1500, 'do'),
             ('vxlan', 'v0', 1450, 1450, 'do'), ('vxlan', 'v0', 1450, 1451, 'do'), ('vxlan', 'v0', 1450, 1451, 'dont'),
             ('gre', 'g0', 1500, 1500, 'do'), ('gre', 'g0', 1500, 1500, 'dont')]
    for k, dev, setm, inner, mode in cases:
        if setm: dx('ta', f'ip link set {dev} mtu {setm}')
        else: dx('ta', f'ip link set {dev} mtu {mtu_of("ta", dev) if dev != "v0" else 1500}')
        reset_route(dev); dst, flt = PING[k]
        pk = cap(flt, f'ping -c 2 -i 0.4 -W 1 -M {mode} -s {inner - 28} {dst} > /tmp/p.txt 2>&1; true', post=1.0)
        pr_out = dx('ta', 'cat /tmp/p.txt')
        mm = re.search(r'(\d+) packets transmitted, (\d+) received', pr_out)
        m = re.search(r'(message too long, mtu=\d+|Frag needed[^\n]*)', pr_out)
        verdict = f'收到 {mm.group(2)}/{mm.group(1)}' + (f'({m.group(1)})' if m else '') if mm else '无结果'
        grp = []
        for p in pk:
            if grp and grp[-1][0] == p: grp[-1][1] += 1
            else: grp.append([p, 1])
        print(f'  {NAMES[k]:<10} 接口 MTU {mtu_of("ta", dev):>4},内层 {inner} 字节 DF={"是" if mode == "do" else "否"}:{verdict:<32} 外层包 {[(p[0], p[1], p[2]) if n == 1 else (p[0], p[1], p[2], f'×{n}') for p, n in grp] or "无"}')
        if k == 'vxlan' and setm is None: print('    ' + ' '.join(dx('ta', f'ip route get {dst}').split()) + '  ← 发过一个超大包后,内核给这个目的地记下了更小的路径 MTU')
    dx('ta', 'ip link set g0 mtu 1476; ip link set v0 mtu 1500')

    print('== 四:真实 en0(这台 Mac 的网卡)上:自己写的最小 IP-in-UDP 封装(内层 IP 包 + 32 字节隧道头,装进 UDP 数据报,发到文档专用地址 198.51.100.1:51820,不会到达真实主机),抓 en0 看外层数据报有没有被分片')
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
    print(f'  外层 IP 包不能超过 en0 的 MTU 1500:内层 IP 包 ≤ 1500 − 20 − 8 − {HDR} = {1500 - 28 - HDR} 字节时刚好一个包;再大一个字节,外层就被分成两片——分片后任何一片丢失,整个数据报都丢')

    print('== 五:分片放大了丢包(实测):在 ta 的 eth0 上用 tc netem 给出站包加 1% 的随机丢包(只影响 ta→tb 方向),VXLAN 隧道里连续 ping 5000 次,重复 3 轮,数一数请求丢了多少。对照:内层 1450 字节(接口 MTU 1450,外层 1500 字节,一个包);内层 1500 字节(接口 MTU 1500,外层要 1550 字节,超出 1500,一个内层包变成两个外层包:第一个包按外层分片,之后内核学到路径 MTU 1450,改为先把内层包分片再封装);内层 84 字节作基线')
    dx('ta', 'tc qdisc add dev eth0 root netem loss 1%')
    def lossrate(inner, mtu):
        dx('ta', f'ip link set v0 mtu {mtu}'); reset_route('v0'); lost = sent = 0
        for _ in range(3):
            o = dx('ta', f'ping -q -c 5000 -i 0.002 -W 1 -M dont -s {inner - 28} 10.2.0.2', timeout=180)
            m = re.search(r'(\d+) packets transmitted, (\d+) received', o)
            if not m: print('   ?', o[-200:]); continue
            sent += int(m.group(1)); lost += int(m.group(1)) - int(m.group(2))
        return lost, sent
    base = {}
    for nm, inner, mtu, n_frag in (('基线:内层 84 字节', 84, 1450, 1), ('内层 1450 字节(1 个外层包)', 1450, 1450, 1), ('内层 1500 字节(一个请求变成 2 个外层包)', 1500, 1500, 2)):
        lost, sent = lossrate(inner, mtu); base[nm] = (lost, sent)
        print(f'    {nm:<38} 发 {sent} 个,丢 {lost} 个 = {lost / sent:.2%};按公式 1 − 0.99^{n_frag} = {1 - 0.99 ** n_frag:.2%}')
    dx('ta', 'tc qdisc del dev eth0 root; ip link set v0 mtu 1500')

    print('== 六:隧道对 TCP 效率的影响(实测):tb 上起一个 TCP 服务,ta 向它发 10,000,000 字节(Python 套接字,单连接)。在 ta 的 eth0 上抓出站的所有帧,把以太网帧长度(含以太网头 14 字节)加起来。为了不让网卡的分段卸载把帧合并,先把两边 eth0 和隧道接口的 tso / gso / gro 关掉')
    for n in ('ta', 'tb'):
        dx(n, 'for d in eth0 g0 v0 w0; do ethtool -K $d tso off gso off gro off >/dev/null 2>&1; done')
    cases = [('不用隧道,直连', B_IP, 'host ' + B_IP, None, None), ('GRE(接口 MTU 1476)', '10.1.0.2', 'ip proto 47', 'g0', 1476), ('WireGuard(接口 MTU 1420)', '10.3.0.2', 'udp port 51820', 'w0', 1420),
             ('VXLAN(接口 MTU 1450)', '10.2.0.2', 'udp port 4789', 'v0', 1450), ('VXLAN(MTU 错配:接口 MTU 仍是 1500)', '10.2.0.2', 'udp port 4789', 'v0', 1500)]
    tcp_rows = []
    for nm, dst, flt, dev, mtu in cases:
        if dev: dx('ta', f'ip link set {dev} mtu {mtu}'); reset_route(dev)
        dx('ta', 'ip tcp_metrics flush all >/dev/null 2>&1'); dx('ta', f'tcpdump -l -nn -i eth0 -s 96 -w /tmp/t.pcap "src host {A_IP} and dst host {B_IP}" >/dev/null 2>&1 & P=$!; sleep 0.8; python3 /cli.py {dst} > /tmp/mss.txt; sleep 0.5; kill -2 $P; sleep 0.5', timeout=120)
        mss, mss2 = map(int, dx('ta', 'cat /tmp/mss.txt').split()); n, b, mx, fr = map(int, dx('ta', 'python3 /an.py /tmp/t.pcap').split())
        tcp_rows.append((nm, mss, n, b, mx, fr))
        print(f'    {nm:<36} MSS {mss:>4}→{mss2:>4}:出站 {n:>5} 个帧,共 {b:>8} 字节(比 10,000,000 多 {(b - 10_000_000) / 10_000_000:.1%}),最大帧 {mx} 字节,其中 IP 分片 {fr} 个')
    dx('ta', 'ip link set v0 mtu 1500')
    print('  (MSS 栏是 “连接建立时 → 传完 10 MB 后” 的值;抓的是外层:隧道里的 TCP 段加上隧道头;“线上总字节”不含以太网帧间隙与 CRC;只算 ta→tb 的方向,不含 tb 回的 ACK)')

    print('== 七:这台 Mac 本机有什么隧道类接口?读 ifconfig 的接口名与 MTU(只看名字与 MTU,不看任何地址)')
    ifl = sysout('ifconfig', '-l').split(); tun = [i for i in ifl if i.startswith(('utun', 'gif', 'stf', 'ipsec', 'ppp'))]
    for i in tun:
        out = sysout('ifconfig', i); m = re.search(r'mtu (\d+)', out); print(f'  {i:<8} MTU {m.group(1) if m else "?"}')
    print(f'  共 {len(tun)} 个隧道类接口,MTU 各不相同({sorted({re.search(r"mtu (\d+)", sysout("ifconfig", i)).group(1) for i in tun}, key=int)}):实际路径 MTU 取决于数据走的是哪个接口')
finally:
    teardown()
