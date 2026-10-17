import sys, os, re, struct, collections, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w45'); reset()
FL = [(0x10, 'ACK'), (0x08, 'PSH'), (0x04, 'RST'), (0x02, 'SYN'), (0x01, 'FIN')]
def flags(f): return '+'.join(n for b, n in FL if f & b) or '无'
def tcps(path):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            ip = bytes(buf[4:])
            if len(ip) < 40 or ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); out.append(dict(ts=ts, sp=sp, dp=dp, seq=seq, ack=ack, fl=fl, win=win, plen=tl_ - ihl - (off >> 4) * 4))
    return out
def pair():
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(); return ls, ls.getsockname()[1]

print('== 一:字节流如何被编号:客户端分三次发 100、250、30 字节(间隔 0.2 秒,三次写入不会合并),服务端每次 recv;抓包看每个数据段的序号 = 初始序号 + 1 + 之前发出的字节数,服务端的确认号 = 收到的最后一个字节的序号 + 1')
ls, port = pair()
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept()
    for n in (100, 250, 30): k.sendall(b'x' * n); cn.recv(1000); time.sleep(0.2)
    k.close(); cn.recv(10); cn.close(); time.sleep(0.3)
P = tcps(c.pcap); isn_c = [p for p in P if p['fl'] == 0x02][0]['seq']; isn_s = [p for p in P if p['fl'] == 0x12][0]['seq']
print(f'  客户端 ISN = {isn_c},服务端 ISN = {isn_s}(下面都用相对值:序号减去各自的 ISN)')
print('    #  方向   标志      相对序号  载荷  序号+载荷(下一个序号)  相对确认号')
cum = 0
for i, p in enumerate(P, 1):
    cli = p['dp'] == port; rs = (p['seq'] - (isn_c if cli else isn_s)) & 0xffffffff; ra = (p['ack'] - (isn_s if cli else isn_c)) & 0xffffffff if p['fl'] & 0x10 else 0
    print(f'    {i:>2}  {"客户端→" if cli else "←服务端"}  {flags(p["fl"]):<8}  {rs:>7}  {p["plen"]:>4}  {rs + p["plen"] + (1 if p["fl"] & 3 else 0):>10}              {ra:>6}')
d = [p for p in P if p['plen'] > 0 and p['dp'] == port]; a_ = [p for p in P if p['sp'] == port and p['fl'] == 0x10 and p['plen'] == 0]
ok = sum(1 for x in d if any(((y['ack'] - isn_c) & 0xffffffff) == ((x['seq'] - isn_c) & 0xffffffff) + x['plen'] for y in a_))
print(f'  3 个数据段的“序号 + 载荷”都出现在随后服务端的确认号里:{ok} / 3;最后一个确认号 {((a_[-1]["ack"] - isn_c) & 0xffffffff) if a_ else "?"} = 1(SYN)+ 100 + 250 + 30 = {1 + 380}(再加 FIN 占的 1 个序号就是 382)')
print('  规则:序号标的是这个段的第一个字节在字节流里的位置;确认号是“我期望收到的下一个字节的位置”;SYN 和 FIN 各占 1 个序号,所以握手之后的第一个数据字节序号是 ISN + 1')

print('== 二:累积确认:下载 4 MiB,看接收方每发一个纯 ACK 确认了多少字节、每收几个数据段才回一个 ACK(lo0)')
ls, port = pair(); done = {}
def srv():
    cn, _ = ls.accept(); cn.sendall(b'z' * (4 << 20)); cn.close()
threading.Thread(target=srv, daemon=True).start()
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    k = socket.create_connection(('127.0.0.1', port)); n = 0
    while True:
        d_ = k.recv(1 << 20)
        if not d_: break
        n += len(d_)
    k.close(); time.sleep(0.3)
P = tcps(c.pcap); isn_s = [p for p in P if p['fl'] & 0x12 == 0x12][0]['seq']
data = [p for p in P if p['sp'] == port and p['plen'] > 0]; acks = [p for p in P if p['dp'] == port and p['fl'] == 0x10 and p['plen'] == 0]
inc = []; prev = None
for p in acks:
    a = (p['ack'] - isn_s) & 0xffffffff
    if prev is not None and a > prev: inc.append(a - prev)
    prev = a
print(f'  下载 {n} 字节:服务端发了 {len(data)} 个数据段(最大载荷 {max(p["plen"] for p in data)} 字节),客户端回了 {len(acks)} 个纯 ACK;平均每 {len(data) / len(acks):.1f} 个数据段回 1 个 ACK')
if inc: print(f'  相邻两个 ACK 之间确认号增加的字节数:最小 {min(inc)} / 中位 {int(statistics.median(inc))} / 最大 {max(inc)};总确认 {sum(inc)} 字节')
print('  一个 ACK 确认的是“从头到这里的所有字节”(累积确认):中间少回几个 ACK 不会丢信息;ACK 越稀,开销越小,但发送方等 ACK 的时间可能更久')

print('== 三:32 位序号会回绕:序号是 32 位的,发满 4 GiB 就绕回 0。在 lo0 上发 4.5 GiB(抓包只留头部),看序号怎么回绕,以及比较序号要用模 2^32 的算术')
ls, port = pair(); TOTAL = int(4.5 * (1 << 30))
def srv3():
    cn, _ = ls.accept(); sent = 0; buf = b'q' * (1 << 20)
    while sent < TOTAL: cn.sendall(buf); sent += len(buf)
    cn.close()
th = threading.Thread(target=srv3, daemon=True); th.start()
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
    t0 = time.time(); k = socket.create_connection(('127.0.0.1', port)); n = 0
    while True:
        d_ = k.recv(1 << 22)
        if not d_: break
        n += len(d_)
    dt = time.time() - t0; k.close(); time.sleep(1.0)
P = tcps(c.pcap); sd = [p for p in P if p['sp'] == port and p['plen'] > 0]
isn_s = [p for p in P if p['fl'] & 0x12 == 0x12][0]['seq']
print(f'  传输 {n / (1 << 30):.2f} GiB 用时 {dt:.1f} 秒({n / (1 << 20) / dt:.0f} MiB/s);抓到服务端数据段 {len(sd)} 个(其余因抓包丢包 / 去重没有统计)')
drops = [(i, a['seq'], b['seq']) for i, (a, b) in enumerate(zip(sd, sd[1:])) if b['seq'] < a['seq'] and a['seq'] - b['seq'] > (1 << 31)]
print(f'  服务端 ISN = {isn_s};相对序号的最大值 {max((p["seq"] - isn_s) & 0xffffffff for p in sd)};绝对序号在 {len(drops)} 处从接近 2^32 回绕到小数:' + ';'.join(f'第 {i} 个段后 {a} → {b}' for i, a, b in drops[:3]))
if drops:
    i, a, b = drops[0]; print(f'  回绕处:前一个段序号 {a}(距 2^32 还差 {2 ** 32 - a}),下一个段序号 {b} = (前一个序号 + 它的载荷) mod 2^32 = {(a + sd[i]["plen"]) % 2 ** 32}:{b == (a + sd[i]["plen"]) % 2 ** 32}')
print('  所以比较两个序号“谁在前”不能直接用大小比较,要看它们的差是否小于 2^31(TCP 实现里的 SEQ_LT 宏);时间戳选项的 PAWS(第 63 篇)就是为了在高速网络里防止回绕后的旧段被当成新段')

print('== 四:SYN 和 FIN 各占 1 个序号:数一数一个完整连接的序号总账')
ls, port = pair()
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); k.sendall(b'a' * 1000); time.sleep(0.1); cn.recv(2000); cn.sendall(b'b' * 500); time.sleep(0.1); k.recv(2000); k.close(); time.sleep(0.1); cn.recv(10); cn.close(); time.sleep(0.3)
P = tcps(c.pcap); isn_c = [p for p in P if p['fl'] == 0x02][0]['seq']; isn_s = [p for p in P if p['fl'] == 0x12][0]['seq']
fc = [p for p in P if p['dp'] == port and p['fl'] & 1][0]; fs = [p for p in P if p['sp'] == port and p['fl'] & 1][0]
lastc = max(P, key=lambda p: ((p['ack'] - isn_c) & 0xffffffff) if p['sp'] == port else 0)
print(f'  客户端:SYN 序号 {isn_c} → 发了 1000 字节 → FIN 的序号 {fc["seq"]} = ISN + 1 + 1000 = {isn_c + 1001}:{fc["seq"] == isn_c + 1001};服务端最后确认客户端的 ACK 号 = {max(((p["ack"] - isn_c) & 0xffffffff) for p in P if p["sp"] == port and p["fl"] & 0x10)} = 1(SYN)+ 1000 + 1(FIN) = 1002')
print(f'  服务端:SYN-ACK 序号 {isn_s} → 发了 500 字节 → FIN 的序号 {fs["seq"]} = ISN + 1 + 500 = {isn_s + 501}:{fs["seq"] == isn_s + 501};客户端最后确认服务端的 ACK 号 = {max(((p["ack"] - isn_s) & 0xffffffff) for p in P if p["dp"] == port and p["fl"] & 0x10)} = 1 + 500 + 1 = 502')
print('  一个连接里每个方向各有自己独立的序号空间:一个方向发了多少字节,和另一个方向无关')
