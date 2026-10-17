import sys, os, re, struct, ipaddress, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w18'); reset()
gw = [l.split()[1] for l in sysout('route', '-n', 'get', 'default').splitlines() if 'gateway' in l][0]
PUB = '104.20.23.154'
IP_RECVTOS = 27
def raws(path): return [(ts, ip.raw) for ts, ip in read_pcap(path)]

print('== 一:TOS 字节 = 6 位 DSCP + 2 位 ECN。用 IP_TOS 设不同的值发 UDP,抓包看线上的 TOS 字节(lo0 和 en0),并让 lo0 上的接收方用 IP_RECVTOS 读出来')
NAMES = [('CS0', 0), ('CS1', 8), ('AF11', 10), ('AF21', 18), ('AF31', 26), ('AF41', 34), ('EF', 46), ('CS6', 48), ('CS7', 56)]
rows = []
r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('127.0.0.1', 0)); r.setsockopt(socket.IPPROTO_IP, IP_RECVTOS, 1); r.settimeout(1); rp = r.getsockname()[1]
for iface, dst in (('lo0', ('127.0.0.1', rp)), ('en0', (gw, 9))):
    got = {}
    with Cap(f'ip and udp and dst port {dst[1]}', iface=iface, write=True) as c:
        for nm, dscp in NAMES + [('EF+ECT(0)', None), ('EF+ECT(1)', None), ('EF+CE', None)]:
            tos = (dscp << 2) if dscp is not None else {'EF+ECT(0)': 0xba, 'EF+ECT(1)': 0xb9, 'EF+CE': 0xbb}[nm]
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos)
            rb = s.getsockopt(socket.IPPROTO_IP, socket.IP_TOS)
            s.sendto(b'tos-test', dst); time.sleep(0.05)
            rc = None
            if iface == 'lo0':
                try: data, anc, fl, ad = r.recvmsg(100, 100); rc = anc[0][2][0] if anc else None
                except Exception: rc = None
            got[nm] = (tos, rb, rc)
        time.sleep(0.4)
    wire = [ip_[1] for ip_ in raws(c.pcap)]
    print(f'  {iface}:发了 {len(got)} 个,抓到 {len(wire)} 个')
    for (nm, (tos, rb, rc)), w in zip(got.items(), wire):
        print(f'    {nm:<10} 设置 0x{tos:02x} → 读回 0x{rb:02x} → 线上 TOS 字节 0x{w[1]:02x}(DSCP {w[1] >> 2},ECN {w[1] & 3})' + (f' → 接收方 IP_RECVTOS 读到 0x{rc:02x}' if rc is not None else ''))

print('== 二:DSCP 标记在公网路径上会被改吗:带着不同 TOS 的 UDP 探测,TTL 从 1 递增;每一跳回的 ICMP 超时报文里引用的原包头,就是那一跳收到时的样子')
def hop_tos(tos_list, maxttl=12):
    plan = []; port = 33600
    for tos in tos_list:
        for ttl in range(1, maxttl + 1): plan.append((tos, ttl, port)); port += 1
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    with Cap('icmp[icmptype]==11 or (udp and dst portrange 33600-33900)', iface='en0', write=True) as c:
        for tos, ttl, port_ in plan:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos); s.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
            s.sendto(b'd' * 12, (PUB, port_)); time.sleep(0.25)
        time.sleep(2)
    rep = {}
    for ts, r_ in raws(c.pcap):
        ihl = (r_[0] & 15) * 4
        if r_[9] == 1 and r_[ihl] == 11:
            q = r_[ihl + 8:]
            if len(q) >= 28: rep[struct.unpack('>H', q[((q[0] & 15) * 4) + 2:((q[0] & 15) * 4) + 4])[0]] = q[1]
    return plan, rep
tos_list = [0xb8, 0x88, 0x28, 0x00, 0xba]
plan, rep = hop_tos(tos_list)
tab = {}
for tos, ttl, port_ in plan: tab[(tos, ttl)] = rep.get(port_)
print('    TTL(第几跳)  ' + '  '.join(f'发 0x{t:02x}' for t in tos_list))
for ttl in range(1, 13):
    print(f'    {ttl:>6}        ' + '    '.join((f'0x{tab[(t, ttl)]:02x}' if tab[(t, ttl)] is not None else ' -- ') + '  ' for t in tos_list))
chg = {}
for t in tos_list:
    seen = [(ttl, tab[(t, ttl)]) for ttl in range(1, 13) if tab[(t, ttl)] is not None]
    first = next((ttl for ttl, v in seen if v != t), None)
    chg[t] = first
    print(f'  发出 0x{t:02x}:收到引用的 {len(seen)} 跳里,与原值不同的跳数 {sum(1 for _, v in seen if v != t)};第一个不同出现在第 {first} 跳' + (f',之后各跳看到的值 {sorted({v for ttl, v in seen if ttl >= first})}' if first else ',所有跳看到的都与发出的相同'))
print('  “--”表示该跳没有回超时报文。引用的是路由器收到这个包时的头部:第 N 跳看到的 TOS 已经是经过前 N−1 跳之后的值')

print('== 三:不设 IP_TOS,只告诉系统流量类别(SO_TRAFFIC_CLASS):系统会不会替你打 DSCP?')
SO_TRAFFIC_CLASS = 0x1086
TCS = [('BK(后台)', 200), ('BE(默认)', 0), ('VI(视频)', 700), ('VO(语音)', 800), ('CTL(控制)', 900)]
for iface, dst in (('lo0', ('127.0.0.1', rp)), ('en0', (gw, 9))):
    res = []
    with Cap(f'ip and udp and dst port {dst[1]}', iface=iface, write=True) as c:
        for nm, tc in TCS:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try: s.setsockopt(socket.SOL_SOCKET, SO_TRAFFIC_CLASS, tc); ok = s.getsockopt(socket.SOL_SOCKET, SO_TRAFFIC_CLASS)
            except OSError as e: ok = f'失败 {e.strerror}'
            s.sendto(b'tc-test', dst); res.append((nm, tc, ok)); time.sleep(0.05)
        time.sleep(0.4)
    wire = [ip_[1] for ip_ in raws(c.pcap)]
    print(f'  {iface}:' + ';'.join(f'{nm} 读回 {ok} → 线上 TOS 0x{w[1]:02x}' for (nm, tc, ok), w in zip(res, wire)))

print('== 四:ECN 在 TCP 里:net.inet.tcp.ecn=1 时本机主动连接的 SYN 带 ECE+CWR(SEW);对方的 SYN-ACK 只带 ECE 表示接受。连几个公网主机,看谁接受,以及接受后本机发出的数据包 IP 头里的 ECN 位')
print('  ' + sysout('sysctl', 'net.inet.tcp.ecn').strip())
cands = [('主机 A', PUB, 80), ('主机 B', '172.66.147.243', 80), ('主机 C', '1.1.1.1', 80), ('主机 D', '8.8.8.8', 443), ('主机 E', '223.5.5.5', 443)]
for nm, d, p in cands:
    with Cap(f'ip and host {d} and tcp port {p}', iface='en0', write=True, verbose=1) as c:
        try:
            k = socket.create_connection((d, p), timeout=3)
            k.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n')
            k.settimeout(2)
            try:
                while k.recv(65536): pass
            except Exception: pass
            k.close()
        except Exception as e: pass
        time.sleep(0.3)
    L = c.lines
    syn = next((l for l in L if re.search(r'Flags \[(S|SEW)\]', l)), None)
    sa = next((l for l in L if re.search(r'Flags \[(S\.|SE\.|S\.E|SEW\.)\]', l) and 'ack' in l), None)
    if not sa: print(f'  {nm}:没有连通'); continue
    fl = re.search(r'Flags \[([^\]]*)\]', sa).group(1); fs = re.search(r'Flags \[([^\]]*)\]', syn).group(1)
    ecn_out = []; ecn_in = []
    for ts, r_ in raws(c.pcap):
        tl_ = struct.unpack('>H', r_[2:4])[0]; ihl = (r_[0] & 15) * 4; thl = (r_[ihl + 12] >> 4) * 4
        if tl_ - ihl - thl <= 0: continue
        (ecn_out if r_[12:16] != socket.inet_aton(d) else ecn_in).append(r_[1] & 3)
    acc = 'E' in fl and 'W' not in fl
    print(f'  {nm}:本机 SYN 标志 [{fs}],SYN-ACK 标志 [{fl}] → {"接受 ECN" if acc else "没有接受 ECN"};有数据的包:本机发出 {len(ecn_out)} 个,IP ECN 位取值 {sorted(set(ecn_out))};收到 {len(ecn_in)} 个,ECN 位取值 {sorted(set(ecn_in))}(0 = 不支持,1 / 2 = ECT,3 = CE 已拥塞标记)')
print('  ECN 位含义:00 不支持 ECN;10 = ECT(0) 和 01 = ECT(1) 表示发送方支持;11 = CE 表示路径上的路由器在队列拥塞时打了标记,而没有丢包')

print('== 五:TCP 套接字上设 IP_TOS:SYN、数据、ACK、FIN 是不是每个包都带;对端(没设)回的包呢(lo0 上)')
sv = socket.socket(); sv.bind(('127.0.0.1', 0)); sv.listen(); pt = sv.getsockname()[1]
def srv():
    cn, _ = sv.accept(); d = cn.recv(1000); cn.sendall(b'r' * 3000); cn.close()
th = threading.Thread(target=srv, daemon=True); th.start()
with Cap(f'tcp port {pt}', iface='lo0', write=True) as c:
    k = socket.socket(); k.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0xb8); k.connect(('127.0.0.1', pt)); k.sendall(b'hi' * 10)
    k.settimeout(1)
    try:
        while k.recv(65536): pass
    except Exception: pass
    k.close(); th.join(2); time.sleep(0.3)
kinds = {}
for ts, r_ in raws(c.pcap):
    ihl = (r_[0] & 15) * 4; fl = r_[ihl + 13]; sp = struct.unpack('>H', r_[ihl:ihl + 2])[0]
    who = '服务端(没设 TOS)' if sp == pt else '客户端(IP_TOS=0xb8)'
    name = ('SYN' if fl & 2 else ('FIN' if fl & 1 else ('RST' if fl & 4 else ('带数据/ACK'))))
    kinds.setdefault((who, name), []).append(r_[1])
for (who, name), v in sorted(kinds.items()): print(f'  {who} 的 {name}:{len(v)} 个包,TOS 字节取值 {sorted({f"0x{x:02x}" for x in v})}')
