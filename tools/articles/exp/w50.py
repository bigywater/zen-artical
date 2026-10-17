import sys, os, re, struct, collections, threading, statistics, fcntl, termios, array; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w50'); reset()
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
print('  ' + sysout('sysctl', 'net.inet.tcp.max_persist_timeout').strip() + '(0 = 不限:持续探测直到连接被关闭)')

print('== 一:把接收缓冲区塞到窗口恰好为 0:接收方(客户端,connect 前设 SO_RCVBUF)不读数据,服务端用 TCP_NODELAY 每次写 1000 字节直到 send() 返回 EAGAIN;抓接收方 ACK 里的窗口变化')
ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(); port = ls.getsockname()[1]; res = {}
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    k = socket.socket(); k.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536); k.connect(('127.0.0.1', port)); cn, _ = ls.accept(); cn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1); cn.setblocking(False); sent = 0; t0 = time.time()
    while time.time() - t0 < 1.5:
        try: sent += cn.send(b'x' * 1000)
        except BlockingIOError: time.sleep(0.002)
    time.sleep(0.3)
    b_ = array.array('i', [0]); fcntl.ioctl(k.fileno(), termios.FIONREAD, b_, True); res['readable'] = b_[0]; res['sent'] = sent; res['rcvbuf'] = k.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
    res['t_fill'] = time.time()
    P_pre = None
    time.sleep(0.5)
P = tcps(c.pcap); ws = [p for p in P if p['fl'] == 0x02][0]['ws']
acc = [p for p in P if p['dp'] == port and p['fl'] & 0x10 and p['plen'] == 0 and not p['fl'] & 3]
z = [p for p in acc if p['win'] == 0]
print(f'  接收缓冲区 {res["rcvbuf"]} 字节;发送方 send() 共收下 {res["sent"]} 字节;FIONREAD 可读 {res["readable"]} 字节')
print(f'  接收方发出的 ACK {len(acc)} 条(含 dummynet 之外无重复),其中窗口字段为 0 的 {len(z)} 条;窗口的最后几个取值(实际窗口 = 字段 × 2^{ws},字节):{[p["win"] << ws for p in acc[-6:]]}')
if z: print(f'  第一个零窗口 ACK:确认号(已收到)=  {z[0]["ack"] - [p for p in P if p["fl"] & 0x12 == 0x12][0]["seq"] - 1} 字节 = 接收缓冲区的容量;这之后发送方不能再发新数据,只能探测')
k.setblocking(False)

print('== 二:零窗口探测(persist 定时器):窗口为 0 以后发送方不能发数据,又不能干等(窗口更新 ACK 万一丢了就永远死锁),所以隔一段时间发一个探测包。接收方一直不读,抓 25 秒,看探测包的时间、大小、内容和接收方的回答')
ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(); port = ls.getsockname()[1]
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    k = socket.socket(); k.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536); k.connect(('127.0.0.1', port)); cn, _ = ls.accept(); cn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1); cn.setblocking(False); t0 = time.time()
    while time.time() - t0 < 1.5:
        try: cn.send(b'x' * 1000)
        except BlockingIOError: time.sleep(0.002)
    # 再多塞一点,让它必须探测
    tfill = time.time()
    time.sleep(25)
P = tcps(c.pcap); isn = [p for p in P if p['fl'] & 0x12 == 0x12][0]['seq']
data = [p for p in P if p['sp'] == port and p['plen'] > 0]; acc = [p for p in P if p['dp'] == port and p['fl'] & 0x10 and p['plen'] == 0 and not p['fl'] & 3]
# 零窗口之后的数据包就是探测
zt = [p['ts'] for p in acc if p['win'] == 0]
if zt:
    t_z = zt[0]; probes = [p for p in data if p['ts'] > t_z + 0.3]
    print(f'  零窗口从 {t_z - P[0]["ts"]:.2f} 秒(相对抓包开始)起;之后的 25 秒里发送方又发出了 {len(probes)} 个数据包(探测)')
    for i, p in enumerate(probes[:10]): print(f'    探测 {i + 1}:距零窗口 +{p["ts"] - t_z:.1f} 秒,载荷 {p["plen"]} 字节,序号(相对)= {p["seq"] - isn - 1}')
    if len(probes) >= 2: print(f'  相邻探测的间隔(秒):{[round(b["ts"] - a["ts"], 1) for a, b in zip(probes, probes[1:])]}')
    ack_after = [p for p in acc if p['ts'] > t_z + 0.3]
    print(f'  每个探测后接收方回的 ACK 的窗口字段:{sorted({p["win"] for p in ack_after})}(0 = 仍然没有空间;确认号 {"没有增加:探测的字节没有被接收" if len({p["ack"] for p in ack_after}) == 1 else "有变化"})')
else:
    print('  这次没有出现窗口恰好为 0 的 ACK')

print('== 三:恢复:接收方重新开始读数据后,发送方多久恢复发送?读第一个字节到发送方发出下一个新数据的延迟(窗口更新 ACK 带来的)')
res2 = {}
ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(); port = ls.getsockname()[1]
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    k = socket.socket(); k.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536); k.connect(('127.0.0.1', port)); cn, _ = ls.accept(); cn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1); cn.setblocking(False); t0 = time.time()
    while time.time() - t0 < 1.5:
        try: cn.send(b'x' * 1000)
        except BlockingIOError: time.sleep(0.002)
    time.sleep(1.0)
    cn.setblocking(True); cn.settimeout(8); sentq = []
    def more():
        t1 = time.time()
        try: cn.send(b'y' * 1000); sentq.append(time.time() - t1)
        except Exception as e: sentq.append(repr(e))
    th = threading.Thread(target=more); th.start(); time.sleep(0.5)
    tread = time.time(); k.setblocking(False); got = 0
    try:
        while got < 100000: got += len(k.recv(10000))
    except BlockingIOError: pass
    th.join(); res2['tread'] = tread; res2['unblock'] = time.time()
    time.sleep(0.3)
P = tcps(c.pcap); isn = [p for p in P if p['fl'] & 0x12 == 0x12][0]['seq']
upd = [p for p in P if p['dp'] == port and p['fl'] & 0x10 and p['plen'] == 0 and p['win'] > 0 and p['ts'] >= res2['tread'] - 0.01]
nd = [p for p in P if p['sp'] == port and p['plen'] > 0 and p['ts'] >= res2['tread'] - 0.01]
print(f'  接收方在读数据之前,发送方一个 send() 已经阻塞了 {0.5:.1f} 秒;接收方读走 {got} 字节后,这个 send() 在 {(res2["unblock"] - res2["tread"]) * 1000:.1f} ms 内返回(send 耗时 {sentq[0] if isinstance(sentq[0], str) else str(round(sentq[0], 2)) + " 秒"})')
if upd: print(f'  读数据之后第一个“窗口更新”ACK:读之后 {(upd[0]["ts"] - res2["tread"]) * 1000:.2f} ms,窗口字段 {upd[0]["win"]}(非 0);之后第一个新数据包:读之后 {(nd[0]["ts"] - res2["tread"]) * 1000:.2f} ms' if nd else f'  窗口更新 ACK:读之后 {(upd[0]["ts"] - res2["tread"]) * 1000:.2f} ms')
print('  窗口更新 ACK 是纯 ACK,不会被重传;万一丢了,靠探测包重新问到窗口(第二节),这就是为什么探测必须存在')
