import sys, os, re, struct, collections, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w51'); reset()
PUB = '104.20.23.154'
def tcps(path):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            ip = bytes(buf[4:]) if f is None else None
    return out
def pk(path, lo):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            if lo: ip = bytes(buf[4:])
            else:
                e = dpkt.ethernet.Ethernet(buf)
                if e.type != 0x0800: continue
                ip = bytes(e.data)
            if ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); hl = (off >> 4) * 4; o = t[20:hl]
            ws = None; mss = None; i = 0
            while i < len(o):
                k = o[i]
                if k == 0: break
                if k == 1: i += 1; continue
                if k == 3: ws = o[i + 2]
                if k == 2: mss = struct.unpack('>H', o[i + 2:i + 4])[0]
                i += o[i + 1]
            out.append(dict(ts=ts, sp=sp, dp=dp, seq=seq, ack=ack, fl=fl, win=win, plen=tl_ - ihl - hl, ws=ws, mss=mss))
    return out

print('== 一:窗口字段只有 16 位:最大 65535 字节。窗口缩放选项(kind 3)给出一个移位数 s(0~14),真实窗口 = 字段 × 2^s,把上限抬到 1 GiB 左右。不同移位数能通告的最大窗口,以及它们在往返 10 ms / 100 ms / 200 ms 的链路上能撑起的最大吞吐(窗口 ÷ RTT,计算)')
print('    移位 s   最大窗口(字节)        RTT 10 ms      RTT 100 ms     RTT 200 ms')
for s_ in (0, 3, 6, 7, 9, 13, 14):
    w = 65535 << s_
    f = lambda rtt: f'{w / rtt / 1e6:>10.1f} MB/s'
    print(f'    {s_:>5}   {w:>18,}   {f(0.01)}   {f(0.1)}   {f(0.2)}')
print('  没有窗口缩放(s = 0)时,窗口最大 65535 字节:RTT 100 ms 的链路上吞吐最多 0.66 MB/s ≈ 5.2 Mbit/s,不管带宽多大;窗口缩放让这个上限随 s 指数增长。选项只出现在 SYN / SYN-ACK 里,而且 SYN 里的窗口字段本身不缩放')

print('== 二:真实连接里协商了什么移位数:本机 lo0、example.com、另一个公网主机各抓一次握手,读 SYN 和 SYN-ACK 里的窗口缩放选项,以及握手后第一个 ACK 的窗口字段')
srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(); lport = srv.getsockname()[1]
for nm, ip_, p, iface in (('本机 lo0', '127.0.0.1', lport, 'lo0'), ('example.com', PUB, 80, 'en0'), ('另一个公网主机', '1.1.1.1', 80, 'en0')):
    with Cap(f'tcp port {p} and host {ip_}', iface=iface, write=True) as c:
        try:
            k = socket.create_connection((ip_, p), timeout=4)
            if iface == 'en0': k.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'); time.sleep(0.5)
            k.close()
        except Exception: pass
        time.sleep(0.4)
    P = pk(c.pcap, iface == 'lo0'); syn = [x for x in P if x['fl'] & 0x12 == 0x02]; sa = [x for x in P if x['fl'] & 0x12 == 0x12]; ack3 = [x for x in P if x['fl'] == 0x10 and x['plen'] == 0 and x['sp'] == syn[0]['sp']]
    if syn and sa:
        mine = syn[0]['ws']; theirs = sa[0]['ws']
        print(f'  {nm}:我的 SYN 窗口缩放 {mine},窗口字段 {syn[0]["win"]}(不缩放);对方 SYN-ACK 窗口缩放 {theirs},窗口字段 {sa[0]["win"]};握手完成后我的第一个 ACK 窗口字段 {ack3[0]["win"] if ack3 else "?"} → 实际 {(ack3[0]["win"] << mine) if ack3 and mine is not None else "?"} 字节;我能通告的最大窗口 {65535 << mine:,},对方 {65535 << theirs if theirs is not None else "?":,}')
print('  两边各有各的移位数,互不影响;要启用缩放,SYN 和 SYN-ACK 里都必须带窗口缩放选项,只有一边带的话两边都不缩放')

print('== 三:接收缓冲区自动调整(autotune):不设 SO_RCVBUF,往返 100 ms 的回环上连续接收 6 秒,每 0.5 秒记一次接收方通告的窗口(字段 × 缩放)和这 0.5 秒里的吞吐;看窗口是否随需要增长')
for k_ in ('net.inet.tcp.doautorcvbuf', 'net.inet.tcp.autorcvbufmax', 'net.inet.tcp.recvspace'): print('  ' + sysout('sysctl', k_).strip())
p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen()
def snd():
    cn, _ = ls.accept(); cn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8 << 20); t0 = time.time()
    while time.time() - t0 < 6.5:
        try: cn.send(b'x' * 65536)
        except Exception: break
    time.sleep(0.5); cn.close()
timeline = []
with lossy(loss=0, delay=50, bw=0):
    with Cap(f'tcp port {p}', iface='lo0', write=True) as c:
        th = threading.Thread(target=snd); th.start(); k = socket.create_connection(('127.0.0.1', p)); k.settimeout(5); t0 = time.time(); n = 0; last = 0; nxt = 0.5
        while time.time() - t0 < 6.0:
            try: d = k.recv(1 << 20)
            except socket.timeout: break
            if not d: break
            n += len(d)
            if time.time() - t0 >= nxt: timeline.append((nxt, (n - last) / 0.5, k.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))); last = n; nxt += 0.5
        k.close(); th.join()
P = pk(c.pcap, True); ws = [x for x in P if x['fl'] == 0x02][0]['ws']; t_start = P[0]['ts']
acc = [x for x in P if x['dp'] == p and x['fl'] & 0x10 and x['plen'] == 0 and not x['fl'] & 3]
print(f'  客户端的窗口缩放系数 {ws}')
print('    时间(秒)   这 0.5 秒的吞吐(MB/s)   SO_RCVBUF 读数(字节)   这一时刻 ACK 里的窗口(字节,取该秒内最大)')
for tt, thr, rb in timeline:
    w = [x['win'] << ws for x in acc if tt - 0.5 <= x['ts'] - t_start < tt]
    print(f'    {tt:>6.1f}   {thr / 1e6:>14.2f}             {rb:>12}           {max(w) if w else 0:>12}')
print('  窗口(缓冲区)随着传输进行自动长大,吞吐随之上升:内核根据"最近一个 RTT 内收到了多少数据"来放大接收缓冲区,上限是 net.inet.tcp.autorcvbufmax(4 MiB)')

print('== 四:没有窗口缩放会怎样(计算,用真实测得的 RTT):用握手里测到的 RTT 算一下 65535 字节窗口的吞吐上限,和启用缩放(实测窗口)的差距')
for nm, ip_, p_ in (('example.com', PUB, 80), ('另一个公网主机', '1.1.1.1', 80)):
    rtts = []
    for _ in range(5):
        t0 = time.time()
        try: k = socket.create_connection((ip_, p_), timeout=4); rtts.append((time.time() - t0) * 1000); k.close()
        except Exception: pass
        time.sleep(0.2)
    if rtts:
        r = statistics.median(rtts) / 1000
        print(f'  到{nm}:connect 耗时(≈ 一个 RTT)中位 {r * 1000:.0f} ms:不缩放时 65535 字节窗口 ÷ RTT = {65535 / r / 1e6:.2f} MB/s ≈ {65535 * 8 / r / 1e6:.1f} Mbit/s;缩放 2^6 时本机能通告的窗口 {65535 << 6:,} 字节 → 上限 {(65535 << 6) / r / 1e6:.0f} MB/s')
print('  缩放选项几乎是必须的:今天的链路动辄 100 Mbit/s 以上、RTT 几十到几百毫秒,不缩放的 64 KiB 窗口会把带宽浪费掉绝大部分')
