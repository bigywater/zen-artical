import sys, os, re, struct, threading, statistics, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w65'); reset()
PUB = '104.20.23.154'
def tcp_pkts(path, en=False):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            if en:
                e = dpkt.ethernet.Ethernet(buf)
                if e.type != 0x0800: continue
                ip = bytes(e.data)
            else: ip = bytes(buf[4:])
            if ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); hl = (off >> 4) * 4; o = t[20:hl]; i = 0; mss = None
            while i < len(o):
                kd = o[i]
                if kd == 0: break
                if kd == 1: i += 1; continue
                if kd == 2: mss = struct.unpack('>H', o[i + 2:i + 4])[0]
                i += o[i + 1]
            out.append(dict(ts=ts, sp=sp, dp=dp, seq=seq, ack=ack, fl=fl, plen=tl_ - ihl - hl, mss=mss))
    return out
def mss_of(P, port):
    syn = [p for p in P if p['fl'] & 0x12 == 0x02 and p['dp'] == port]; sa = [p for p in P if p['fl'] & 0x12 == 0x12 and p['sp'] == port]
    return (syn[0]['mss'] if syn else None), (sa[0]['mss'] if sa else None)
def maxpay(P, dport): return max([p['plen'] for p in P if p['dp'] == dport] or [0])

print('== 一:SYN 里的 MSS 选项从哪来?= 出口接口 MTU − 40(IPv4 头 20 + TCP 基本头 20)。看 lo0(MTU 16384)和 en0(MTU 1500)上握手中双方通告的 MSS')
print('  接口 MTU:' + ';'.join(l.strip() for l in sysout('ifconfig', 'lo0').splitlines() if 'mtu' in l)[:80] + ' | ' + ';'.join(re.sub(r'^.*(mtu \d+).*$', r'en0 \1', l.strip()) for l in sysout('ifconfig', 'en0').splitlines() if 'mtu' in l))
print('  net.inet.tcp.mssdflt = ' + sysout('sysctl', '-n', 'net.inet.tcp.mssdflt').strip() + '(没有路由信息时的默认 MSS);net.inet.tcp.minmss = ' + sysout('sysctl', '-n', 'net.inet.tcp.minmss').strip())
ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); p0 = lab_port(); ls.bind(('127.0.0.1', p0)); ls.listen()
with Cap(f'tcp port {p0}', iface='lo0', write=True, snaplen=96) as c:
    k = socket.create_connection(('127.0.0.1', p0)); cn, _ = ls.accept(); time.sleep(0.2)
a, b = mss_of(tcp_pkts(c.pcap), p0); print(f'  lo0:本机 SYN 的 MSS = {a}(= 16384 − 40 = {16384 - 40}),对端 SYN+ACK 的 MSS = {b}')
k.close(); cn.close(); ls.close()
with Cap(f'tcp port 80 and host {PUB}', iface='en0', write=True, snaplen=96) as c:
    k = socket.create_connection((PUB, 80), timeout=6); time.sleep(0.3)
    info = tcp_info(k); k.close(); time.sleep(0.2)
a, b = mss_of(tcp_pkts(c.pcap, True), 80)
print(f'  en0 → example.com:本机 SYN 的 MSS = {a}(= 1500 − 40 = {1500 - 40}),example.com SYN+ACK 的 MSS = {b};内核 tcp_info 里的 maxseg = {info["maxseg"]}')

print('== 二:双方通告的 MSS 取小者,每个数据段的载荷还要再扣掉 TCP 时间戳选项的 12 字节。实测:往 example.com 的 80 端口发一个 200000 字节的 POST 请求体,抓本机发出的数据段,看最大载荷')
body = b'x' * 200000
with Cap(f'tcp port 80 and host {PUB}', iface='en0', write=True, snaplen=96) as c:
    k = socket.create_connection((PUB, 80), timeout=6); k.settimeout(4); sent = 0; why = '全部发完'
    try:
        k.sendall(b'POST / HTTP/1.1\r\nHost: example.com\r\nContent-Length: 200000\r\nConnection: close\r\n\r\n')
        while sent < len(body): sent += k.send(body[sent:sent + 65536])
    except Exception as e: why = type(e).__name__ + ' ' + str(e)[:40]
    try:
        while k.recv(65536): pass
    except Exception: pass
    try: info = tcp_info(k)
    except OSError: info = None
    k.close(); time.sleep(0.3)
print(f'  请求体发出 {sent} / 200000 字节({why})')
P = tcp_pkts(c.pcap, True); sizes = [p['plen'] for p in P if p['dp'] == 80 and p['plen'] > 0]
from collections import Counter
print(f'  本机发出的数据段 {len(sizes)} 个,载荷的分布(字节 → 个数,前几名):{Counter(sizes).most_common(4)}')
a, b = mss_of(P, 80)
print(f'  本机通告 {a}、对方通告 {b} → 取小者 {min(a, b)};减去 12 字节时间戳 = {min(a, b) - 12};实测最大载荷 {max(sizes)}')
print(f'  对照:若对方没有把 MSS 压到 {b},本机可以发 {a} − 12 = {a - 12} 字节的段')

print('== 三:能不能用 TCP_MAXSEG 手动设小 MSS?lo0 上试三个位置(connect 之前的客户端、listen 之前的监听套接字、连上之后的发送方),看 SYN / SYN+ACK 里的 MSS 和实际数据段大小。目标值 1000')
def mxtest(where):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); p = lab_port(); ls.bind(('127.0.0.1', p))
    err = ''
    if where == 'listen':
        try: ls.setsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG, 1000)
        except OSError as e: err = errno.errorcode.get(e.errno)
    ls.listen(); k = socket.socket()
    if where == 'client':
        try: k.setsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG, 1000)
        except OSError as e: err = errno.errorcode.get(e.errno)
    with Cap(f'tcp port {p}', iface='lo0', write=True, snaplen=96) as c:
        k.connect(('127.0.0.1', p)); cn, _ = ls.accept()
        if where == 'sender':
            try: cn.setsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG, 1000)
            except OSError as e: err = errno.errorcode.get(e.errno)
        mx_k = k.getsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG); mx_cn = cn.getsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG)
        def sink():
            n = 0
            while n < 300000:
                d = k.recv(1 << 20)
                if not d: break
                n += len(d)
        th = threading.Thread(target=sink); th.start(); cn.sendall(b'y' * 300000); th.join(); time.sleep(0.3)
    P = tcp_pkts(c.pcap); a, b = mss_of(P, p)
    print(f'  设在{ {"client": "客户端 connect 之前", "listen": "监听套接字 listen 之前", "sender": "发送方(accept 出来的)连上之后"}[where] }:setsockopt {"成功" if not err else err};SYN 的 MSS {a},SYN+ACK 的 MSS {b};getsockopt(TCP_MAXSEG) 读回 客户端 {mx_k} / 服务端 {mx_cn};服务端→客户端 实测最大数据段载荷 {maxpay(P, P[0]["sp"]) if False else max([q["plen"] for q in P if q["sp"] == p] or [0])} 字节')
    k.close(); cn.close(); ls.close()
for w in ('client', 'listen', 'sender'): mxtest(w)

print('== 四:典型隧道 / 链路的 MTU 与应有的 MSS(计算值,不是测量):MSS = 路径 MTU − 40(IPv4)或 − 60(IPv6);路径上有开销更大的链路时,路由器 / 防火墙的“MSS 钳制”把 SYN 里的 MSS 改小')
for nm, mtu in (('标准以太网', 1500), ('PPPoE(8 字节封装)', 1492), ('GRE 隧道(24 字节)', 1476), ('本机 utun1(接口 MTU 实测 1380)', 1380), ('WireGuard 常见默认', 1420), ('IPv6 最小 MTU', 1280)):
    print(f'  {nm:<34} MTU {mtu:>4} → IPv4 MSS {mtu - 40:>4} / IPv6 MSS {mtu - 60:>4}')
print('  MSS 钳制只改 SYN 与 SYN+ACK 里的选项(路由器重写),不碰数据段;和 PMTUD(靠 ICMP 的 3/4 反馈)互补——ICMP 被防火墙丢弃时 PMTUD 失效,钳制仍然有效')
