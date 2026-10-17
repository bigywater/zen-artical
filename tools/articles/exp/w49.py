import sys, os, re, struct, collections, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w49'); reset()
def tcps(path):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            ip = bytes(buf[4:])
            if ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); hl = (off >> 4) * 4; o = t[20:hl]
            ws = None; i = 0
            while i < len(o):
                k = o[i]
                if k == 0: break
                if k == 1: i += 1; continue
                if k == 3: ws = o[i + 2]
                i += o[i + 1]
            out.append(dict(ts=ts, sp=sp, dp=dp, seq=seq, ack=ack, fl=fl, win=win, plen=tl_ - ihl - hl, ws=ws))
    return out

print('== 一:接收窗口随缓冲区被填满而变小:接收方(客户端)在 connect 之前把 SO_RCVBUF 设成 64 KiB、不调用 recv,服务端持续发送;抓接收方的 ACK,把窗口字段乘上窗口缩放系数,看它怎么从初始值降到 0')
ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(); port = ls.getsockname()[1]
res = {}
import fcntl, termios, array
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    k = socket.socket(); k.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536); k.connect(('127.0.0.1', port)); cn, _ = ls.accept(); cn.setblocking(False); sent = 0; t0 = time.time()
    while time.time() - t0 < 1.0:
        try: sent += cn.send(b'x' * 65536)
        except BlockingIOError: time.sleep(0.01)
    time.sleep(0.3)
    res['rcvbuf'] = k.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF); res['sndbuf'] = cn.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
    b_ = array.array('i', [0]); fcntl.ioctl(k.fileno(), termios.FIONREAD, b_, True); res['readable'] = b_[0]; res['sent'] = sent
    time.sleep(0.2)
k.setblocking(False); got = 0
try:
    while True: got += len(k.recv(1 << 20))
    pass
except BlockingIOError: pass
time.sleep(0.3)
try:
    while True: got += len(k.recv(1 << 20))
except BlockingIOError: pass
res['got'] = got
P = tcps(c.pcap); isn_s = [p for p in P if p['fl'] & 0x12 == 0x12][0]['seq']; ws = [p for p in P if p['fl'] == 0x02][0]['ws']
accs = [p for p in P if p['dp'] == port and p['fl'] & 0x10 and p['plen'] == 0 and not p['fl'] & 3]
print(f'  接收方(客户端,connect 之前设的 SO_RCVBUF)通告的窗口缩放系数 {ws}(窗口字段 × 2^{ws});SO_RCVBUF 读回 {res["rcvbuf"]} 字节;发送方 SO_SNDBUF {res["sndbuf"]} 字节')
print('    第几个 ACK   确认号(已收到字节)   窗口字段(原始)   实际窗口 = 字段 × 2^%d' % ws)
seen = set(); rows = []
for p in accs:
    key = (p['ack'], p['win'])
    if key in seen: continue
    seen.add(key); rows.append((p['ack'] - isn_s - 1, p['win'], p['win'] << ws))
for i, (a_, w, rw) in enumerate(rows[:5] + ([('…', '…', '…')] if len(rows) > 10 else []) + rows[-4:]):
    print(f'    {i + 1:>6}   {a_:>14}   {w:>14}   {rw:>10}')
zero = [r for r in rows if r[1] == 0]
print(f'  共 {len(rows)} 种(确认号, 窗口)的 ACK(只算接收方读数据之前的);窗口恰好为 0 的出现 {len(zero)} 种' + (f',第一次窗口降到 0 时接收方已收到 {zero[0][0]} 字节' if zero else ',窗口没有恰好降到 0:最小是 ' + str(min(r[2] for r in rows)) + ' 字节(小于一个 MSS,发送方因此停发)'))
print(f'  接收方什么都没读时,接收缓冲区里可读的字节数(FIONREAD){res["readable"]};最后一个 ACK 通告的窗口 {rows[-1][2]} 字节,小于一个 MSS(16344)——此时发送方不会再发小包;发送方的 send() 一共让内核收下了 {res["sent"]} 字节 ≈ 接收缓冲区 {res["readable"]} + 发送方自己的发送缓冲区(SO_SNDBUF {res["sndbuf"]}),再往后 send() 返回 EAGAIN——这就是流量控制;接收方后来把全部数据读完共 {res["got"]} 字节')

print('== 二:接收方读得慢,发送方就被拖慢:接收方每次读 64 KiB 后睡眠,控制读速为 约 1 MB/s 和 约 20 MB/s;发送方全速发,测它的实际发送速率')
for nm, rate in (('约 1 MB/s', 1e6), ('约 20 MB/s', 20e6), ('不限速', None)):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(); pt = ls.getsockname()[1]; out = {}
    def rd():
        cn, _ = ls.accept(); cn.settimeout(1.0); n = 0; t0 = time.time()
        while time.time() - t0 < 2.0:
            try: d = cn.recv(65536)
            except socket.timeout: break
            if not d: break
            n += len(d)
            if rate: time.sleep(len(d) / rate)
        out['n'] = n; out['t'] = time.time() - t0; cn.close()
    th = threading.Thread(target=rd); th.start()
    k = socket.create_connection(('127.0.0.1', pt)); k.settimeout(5); sent = 0; t0 = time.time()
    try:
        while time.time() - t0 < 2.0: sent += k.send(b'x' * 65536)
    except Exception: pass
    th.join(); k.close()
    print(f'  接收方读速{nm}:发送方在 2 秒里 send() 出去 {sent / 1e6:.1f} MB(含进入缓冲区的),接收方读走 {out["n"] / 1e6:.1f} MB,折合接收方 {out["n"] / out["t"] / 1e6:.1f} MB/s')
print('  发送速率被接收方的读速限制住,不会无限塞满网络和对方内存:接收窗口是对端告诉你“我还能收多少”')

print('== 三:窗口大小与吞吐的关系:往返 100 ms(netlab 每个方向 50 ms)的回环上,接收方 SO_RCVBUF 取不同的值,发送方持续发 3 秒,测吞吐;与 窗口 ÷ RTT 的理论上限对比')
rows = []
for rb in (16384, 65536, 262144, 1048576):
    p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen(); out = {}
    def snd():
        cn, _ = ls.accept(); cn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 << 20); t0 = time.time()
        while time.time() - t0 < 3.0:
            try: cn.send(b'x' * 65536)
            except Exception: break
        time.sleep(0.5); cn.close()
    with lossy(loss=0, delay=50, bw=0):
        th = threading.Thread(target=snd); th.start(); k = socket.socket(); k.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rb); rbr = None; k.connect(('127.0.0.1', p)); rbr = k.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF); k.settimeout(5); n = 0; t0 = time.time()
        while time.time() - t0 < 3.5:
            try: d = k.recv(1 << 20)
            except socket.timeout: break
            if not d: break
            n += len(d)
        th.join(); k.close()
    thr = n / 3.0; rows.append((rb, thr))
    print(f'  接收方 SO_RCVBUF = {rb:>8}(读回 {rbr}):3 秒读到 {n / 1e6:.2f} MB,平均 {thr / 1e6:.2f} MB/s;理论上限 读回的窗口 ÷ RTT = {rbr / 0.1 / 1e6:.2f} MB/s')
print('  窗口越小,在往返时间长的链路上越吃亏:发送方每个往返最多发一个窗口的数据,然后必须等 ACK(见 BDP 一篇)')

print('== 四:窗口更新与糊涂窗口综合征:接收方的缓冲区被塞满后,应用每次只读 100 字节,看接收方什么时候才通告新的窗口(抓“窗口更新”ACK:确认号不变、只有窗口变大)')
ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(); port = ls.getsockname()[1]
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    k = socket.socket(); k.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536); k.connect(('127.0.0.1', port)); cn, _ = ls.accept(); cn.setblocking(False)
    t0 = time.time()
    while time.time() - t0 < 0.6:
        try: cn.send(b'x' * 65536)
        except BlockingIOError: time.sleep(0.01)
    time.sleep(0.2); n_reads = 0; readb = 0
    for i in range(400):
        d = k.recv(100); readb += len(d); n_reads += 1; time.sleep(0.002)
    time.sleep(0.5)
P = tcps(c.pcap); ws = [p for p in P if p['fl'] == 0x02][0]['ws']
acc = [p for p in P if p['dp'] == port and p['fl'] & 0x10 and p['plen'] == 0 and not p['fl'] & 3]
last = None; upd = []
for p in acc:
    if last is not None and p['ack'] == last['ack'] and p['win'] != last['win']: upd.append((p['ts'], p['win'] << ws, last['win'] << ws))
    last = p
print(f'  接收方读了 {n_reads} 次、每次 100 字节(共 {readb} 字节):这段时间里抓到“窗口更新”ACK(确认号不变、窗口字段变了){len(upd)} 个' + (f';窗口更新的前几次(实际窗口,字节):{[(b, a) for _, a, b in upd[:6]]}' if upd else ''))
if upd: print(f'  每次窗口变大的幅度:{sorted({a - b for _, a, b in upd})[:8]}...——接收方不会读走 100 字节就立刻通告,而是等空出来的空间累积到一定程度(这里与 MSS 16344 / 缓冲区的一半相关)才发一个窗口更新,避免发送方反复发很小的包(糊涂窗口综合征,RFC 1122)')
