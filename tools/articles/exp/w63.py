import sys, os, re, struct, threading, statistics, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w63'); reset()
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
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); hl = (off >> 4) * 4; o = t[20:hl]; i = 0; tsv = tse = None; mss = None
            while i < len(o):
                kd = o[i]
                if kd == 0: break
                if kd == 1: i += 1; continue
                if kd == 8: tsv, tse = struct.unpack('>II', o[i + 2:i + 10])
                if kd == 2: mss = struct.unpack('>H', o[i + 2:i + 4])[0]
                i += o[i + 1]
            out.append(dict(ts=ts, sp=sp, dp=dp, seq=seq, ack=ack, fl=fl, plen=tl_ - ihl - hl, tsv=tsv, tse=tse, mss=mss, hl=hl))
    return out
def dd(P):
    seen = set(); out = []
    for p in P:
        key = (p['sp'], p['dp'], p['seq'], p['fl'], p['plen'], p['tsv'])
        if key in seen: continue
        seen.add(key); out.append(p)
    return out
def pair(port=0):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(); return ls, ls.getsockname()[1]
KA, KI, KC = 0x10, 0x101, 0x102
def slope(pts):
    """pts: [(t_seconds, tsval)] → Hz,用首末点"""
    pts = sorted(pts); return (pts[-1][1] - pts[0][1]) / (pts[-1][0] - pts[0][0])

print('== 一:时间戳选项(kind 8,长度 10:TSval 4 字节 + TSecr 4 字节,前面补 2 个 NOP 对齐成 12 字节)。lo0 与 example.com 的 SYN / SYN+ACK 里有没有?有它,每个数据段的有效载荷少几个字节?')
ls, port = pair(lab_port()); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept()
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
    k.close(); cn.close(); time.sleep(0.2)
ls.close()
ls, port = pair(lab_port()); th_ok = [0]
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept()
    def sink():
        n = 0
        while n < 300000:
            d = cn.recv(1 << 20)
            if not d: break
            n += len(d)
    th = threading.Thread(target=sink); th.start(); k.sendall(b'x' * 300000); th.join(); time.sleep(0.3)
P = dd(tcp_pkts(c.pcap)); syn = [p for p in P if p['fl'] & 0x02 and not p['fl'] & 0x10][0]; sa = [p for p in P if p['fl'] & 0x12 == 0x12][0]
print(f'  lo0:SYN 里 TSval={syn["tsv"] is not None}(TSecr = {syn["tse"]}),SYN+ACK 里 TS={sa["tsv"] is not None};SYN 的 MSS = {syn["mss"]};数据段里最大载荷 = {max(p["plen"] for p in P if p["dp"] == port)} 字节;数据段 TCP 头长 {max(p["hl"] for p in P if p["dp"] == port and p["plen"] > 0)} 字节(20 基本 + 12 时间戳选项)')
print(f'  所以 lo0 上 MSS {syn["mss"]} − 12 字节时间戳选项 = {syn["mss"] - 12} 字节有效载荷')
k.close(); cn.close(); ls.close()
with Cap(f'tcp port 80 and host {PUB}', iface='en0', write=True, snaplen=96) as c:
    k = socket.create_connection((PUB, 80), timeout=6); k.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'); k.settimeout(4)
    try:
        while k.recv(65536): pass
    except Exception: pass
    k.close(); time.sleep(0.3)
P = tcp_pkts(c.pcap, True); syn = [p for p in P if p['fl'] & 0x12 == 0x02][0]; sa = [p for p in P if p['fl'] & 0x12 == 0x12][0]
print(f'  example.com:本机 SYN 里 TS={syn["tsv"] is not None},服务器 SYN+ACK 里 TS={sa["tsv"] is not None}(两边都有才会启用);SYN+ACK 的 MSS = {sa["mss"]}')

print('== 二:时间戳的“钟”有多快:连接保持空闲,用 keepalive(idle=1、intvl=1)每秒让一端发探测、另一端回 ACK,取 8 秒内回 ACK 的一端的 TSval 随时间的变化,求每秒增加多少(Hz)。同时看探测包本身带不带时间戳选项')
print('  ' + sysout('sysctl', 'net.inet.tcp.randomize_timestamps').strip() + '(1 = 每条连接的 TSval 起点加一个随机偏移,所以 TSval 的绝对值没有意义,只有差值有意义)')
ls, port = pair(lab_port()); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); k.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1); k.setsockopt(socket.IPPROTO_TCP, KA, 1)
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
    time.sleep(8.5)
Pall = tcp_pkts(c.pcap); pr = [p for p in Pall if p['dp'] == port]; rp = [p for p in Pall if p['sp'] == port]
print(f'  lo0:客户端发出的 keepalive 探测 {len(pr)} 个,其中带时间戳选项的 {sum(1 for p in pr if p["tsv"] is not None)} 个(TCP 头长 {sorted({p["hl"] for p in pr})} 字节);服务端回的 ACK {len(rp)} 个,带时间戳选项的 {sum(1 for p in rp if p["tsv"] is not None)} 个(头长 {sorted({p["hl"] for p in rp})} 字节)')
print(f'  服务端 ACK 里的 TSecr(回显客户端最近一个带时间戳的包的 TSval):{sorted({p["tse"] for p in rp if p["tse"] is not None})}——只有一个值,因为探测没有带时间戳,服务端没有新的可回显')
sv = [(p['ts'], p['tsv']) for p in rp if p['tsv'] is not None]
print(f'  服务端 TSval 的变化(相邻差值):{[b[1] - a[1] for a, b in zip(sorted(sv), sorted(sv)[1:])]}')
hz = slope(sv); print(f'  本机的时间戳钟:{hz:.1f} 次/秒(Hz);每个刻度 {1000 / hz:.2f} ms;32 位 TSval 绕一圈要 {2 ** 32 / hz / 86400:.1f} 天(计算)')
k.close(); cn.close(); ls.close()
hz_loc = hz
with Cap(f'tcp port 80 and host {PUB}', iface='en0', write=True, snaplen=96) as c:
    k = socket.create_connection((PUB, 80), timeout=6); k.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1); k.setsockopt(socket.IPPROTO_TCP, KA, 1); k.setsockopt(socket.IPPROTO_TCP, KI, 1); time.sleep(8); k.close(); time.sleep(0.3)
Pa = tcp_pkts(c.pcap, True); tA = Pa[0]['ts']
P = [p for p in Pa if p['fl'] & 0x10 and not p['fl'] & 0x02]
srv = [(p['ts'], p['tsv']) for p in P if p['sp'] == 80 and p['tsv'] is not None]; loc = [p for p in P if p['dp'] == 80 and p['plen'] == 0 and tA + 1 < p['ts'] < tA + 7.5 and p['fl'] == 0x10]
print(f'  example.com:握手之后、关闭之前(第 1~7.5 秒)本机发出的纯 ACK(keepalive 探测){len(loc)} 个,带时间戳的 {sum(1 for p in loc if p["tsv"] is not None)} 个;服务器发来的带时间戳的包 {len(srv)} 个')
if len(srv) > 2: print(f'  服务器 TSval 随时间变化的速率 {slope(srv):.1f} Hz(每个刻度 {1000 / slope(srv):.2f} ms)')

print('== 三:用时间戳量往返时间:lo0 上 netlab 每方向延迟 50 ms,发 20 条小消息(间隔 150 ms)。对每个数据段,找服务端第一个 TSecr 等于它 TSval 的 ACK,RTT = 两者被抓到的时间差;对比内核自己的 tcp_info 里的 rttcur / srtt')
ls, port = pair(lab_port()); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); k.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
def sink2():
    cn.settimeout(8)
    try:
        while cn.recv(100): pass
    except Exception: pass
th = threading.Thread(target=sink2); th.start()
with lossy(loss=0, delay=50, bw=0):
    with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
        for i in range(20): k.sendall(b'm' * 50); time.sleep(0.15)
        time.sleep(0.5); info = tcp_info(k)
P0 = tcp_pkts(c.pcap); P = dd(P0); rtts = []; rtts2 = []
for p in P:
    if p['dp'] == port and p['plen'] > 0:
        a = [q for q in P0 if q['sp'] == port and q['tse'] == p['tsv'] and q['ts'] > p['ts'] and q['fl'] & 0x10]
        if a: rtts.append((a[0]['ts'] - p['ts']) * 1000); rtts2.append((a[-1]['ts'] - p['ts']) * 1000)
print(f'  凭 TSecr 配对成功 {len(rtts)} 个数据段(共发 20 条)。dummynet 让同一个包在 lo0 上被抓到不止一次(延迟前后各一份),所以“RTT”有两种读法:')
print(f'  数据段第一次被抓到 → 对应 ACK 第一次被抓到:中位 {statistics.median(rtts):.1f} ms(最小 {min(rtts):.1f} / 最大 {max(rtts):.1f})——只包含一个方向的延迟')
print(f'  数据段第一次被抓到 → 对应 ACK 最后一次被抓到(= 真正送达):中位 {statistics.median(rtts2):.1f} ms(最小 {min(rtts2):.1f} / 最大 {max(rtts2):.1f})——两个方向都包含')
print(f'  内核 tcp_info:rttcur = {info["rttcur"]} ms,srtt = {info["srtt"]} ms,rttvar = {info["rttvar"]} ms')
k.close(); th.join(); cn.close(); ls.close()

print('== 四:重传的歧义(Karn 问题)与时间戳:丢包 20%、延迟 20 ms,发 150 个小消息。同一个序号被重传时,新旧两个包的 TSval 不同;ACK 的 TSecr 回显的是触发它的那个包的 TSval,所以发送方能分清 ACK 是对哪一次发送的回应')
ls, port = pair(lab_port()); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); k.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
th = threading.Thread(target=sink2); th.start()
with lossy(loss=20, delay=20, bw=0):
    with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
        for i in range(150): k.sendall(b'm' * 50); time.sleep(0.02)
        time.sleep(4)
P = dd(tcp_pkts(c.pcap)); data = [p for p in P if p['dp'] == port and p['plen'] > 0]
by = {}
for p in data: by.setdefault(p['seq'], []).append(p)
retx = {s: sorted(v, key=lambda x: x['ts']) for s, v in by.items() if len({x['tsv'] for x in v}) > 1}
print(f'  发了 {len(by)} 个不同的数据段;其中被重传(同一序号出现不同 TSval)的 {len(retx)} 个')
acks_by_tsecr = {}
for q in P:
    if q['sp'] == port and q['fl'] & 0x10 and q['tse']: acks_by_tsecr.setdefault(q['tse'], []).append(q)
orig_echo = new_echo = 0
for s, v in retx.items():
    tv = [x['tsv'] for x in v]
    if any(t in acks_by_tsecr for t in tv[1:]): new_echo += 1
    if tv[0] in acks_by_tsecr: orig_echo += 1
ex = list(retx.items())[:3]
for s, v in ex: print(f'    序号 {s & 0xffff}:发送过 {len(v)} 次,TSval = {[x["tsv"] for x in v]},间隔(ms)= {[round((v[i + 1]["ts"] - v[i]["ts"]) * 1000) for i in range(len(v) - 1)]}')
print(f'  在被重传的 {len(retx)} 个段里:有 ACK 回显了某次重传的 TSval 的 {new_echo} 个,有 ACK 回显了最初那次的 TSval 的 {orig_echo} 个')
k.close(); th.join(); cn.close(); ls.close()

print('== 五:PAWS(防止回绕的序号):规则是“收到的段的 TSval 比这条连接最近记录的 ts_recent 还小(按 32 位回绕比较),就丢掉”。构造旧报文需要注入原始包,这里做不到,所以只给出计算:序号 32 位回绕的时间与时间戳钟')
for mbps in (100, 1000, 10000, 100000):
    print(f'  {mbps:>6} Mbit/s 的链路上,2^32 字节的序号空间 {2 ** 32 / (mbps * 1e6 / 8):>9.1f} 秒回绕一次(计算)')
print(f'  时间戳钟 {hz_loc:.0f} Hz:TSval 32 位回绕要 {2 ** 32 / hz_loc / 86400:.1f} 天,PAWS 的比较窗口(2^31)是 {2 ** 31 / hz_loc / 86400:.1f} 天;规范要求时间戳钟的刻度在 1 ms~1 s 之间,保证一个包在网络里的寿命(MSL)远小于绕一圈的时间(计算)')
