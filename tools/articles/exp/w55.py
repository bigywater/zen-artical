import sys, os, re, struct, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w55'); reset()
def pkts(path, port):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            ip = bytes(buf[4:])
            if ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); out.append(dict(ts=ts, c2s=(dp == port), seq=seq, fl=fl, plen=tl_ - ihl - (off >> 4) * 4))
    return out
def pair():
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(); return ls, ls.getsockname()[1]
NODELAY = socket.TCP_NODELAY
NOPUSH = getattr(socket, 'TCP_NOPUSH', 4)

print('== 一:选项的读写:TCP_NODELAY 默认值、设置后读回、是否被 accept 出来的连接继承;TCP_CORK(Linux 的名字)在 macOS 的 socket 模块里存在吗')
ls, port = pair(); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept()
print(f'  新连接上 getsockopt(TCP_NODELAY) = {k.getsockopt(socket.IPPROTO_TCP, NODELAY)}(客户端)、{cn.getsockopt(socket.IPPROTO_TCP, NODELAY)}(服务端 accept 出来的)')
k.setsockopt(socket.IPPROTO_TCP, NODELAY, 1); print(f'  客户端 setsockopt 后读回 = {k.getsockopt(socket.IPPROTO_TCP, NODELAY)}')
ls2, port2 = pair(); ls2.setsockopt(socket.IPPROTO_TCP, NODELAY, 1)
k2 = socket.create_connection(('127.0.0.1', port2)); cn2, _ = ls2.accept()
print(f'  在监听套接字上先设 TCP_NODELAY=1,accept 出来的连接读回 = {cn2.getsockopt(socket.IPPROTO_TCP, NODELAY)}(非 0 = 已置位,即被继承;macOS 读回的不是 1 而是内部标志位的值)')
print(f'  socket 模块里有 TCP_CORK: {hasattr(socket, "TCP_CORK")};有 TCP_NOPUSH: {hasattr(socket, "TCP_NOPUSH")}(值 {NOPUSH});有 MSG_MORE: {hasattr(socket, "MSG_MORE")}')
print(f'  TCP_NOPUSH 默认 = {k.getsockopt(socket.IPPROTO_TCP, NOPUSH)};设成 1 后读回 ', end=''); k.setsockopt(socket.IPPROTO_TCP, NOPUSH, 1); print(k.getsockopt(socket.IPPROTO_TCP, NOPUSH)); k.setsockopt(socket.IPPROTO_TCP, NOPUSH, 0)
for x in (k, cn, k2, cn2, ls, ls2): x.close()

def burst(mode, nodelay, n=200, hdr=5, body=100):
    """发 n 条消息(每条 hdr 字节头 + body 字节体),返回线上数据段个数和用时;mode: two=两次 write, one=拼好一次 send, vec=sendmsg 一次"""
    ls, port = pair(); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept()
    if nodelay: k.setsockopt(socket.IPPROTO_TCP, NODELAY, 1)
    total = n * (hdr + body)
    def drain():
        g = 0
        while g < total:
            d = cn.recv(1 << 20)
            if not d: break
            g += len(d)
    th = threading.Thread(target=drain); th.start()
    H, B = b'h' * hdr, b'b' * body
    with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
        t0 = time.time()
        for i in range(n):
            if mode == 'two': k.sendall(H); k.sendall(B)
            elif mode == 'one': k.sendall(H + B)
            else: k.sendmsg([H, B])
            time.sleep(0.001)
        th.join(); dt = time.time() - t0; time.sleep(0.3)
    P = pkts(c.pcap, port); data = [p for p in P if p['c2s'] and p['plen'] > 0]
    k.close(); cn.close(); ls.close(); return len(data), dt

print('== 二:每条消息是 5 字节头 + 100 字节体、共 200 条、每条间隔 1 ms:三种写法在 Nagle 开 / TCP_NODELAY 下,线上数据段各几个(lo0)')
res = {}
for nm, mode in (('先 write 头、再 write 体', 'two'), ('拼成一个缓冲区一次 send', 'one'), ('sendmsg([头, 体]) 一次', 'vec')):
    for nd in (False, True):
        cnt, dt = burst(mode, nd); res[(mode, nd)] = cnt
        print(f'  {nm:<22} {"TCP_NODELAY" if nd else "Nagle 开    "}:数据段 {cnt} 个(200 条消息)')
print('  分两次 write 的写法,不论 Nagle 开还是 TCP_NODELAY,每条消息都是两个包:回环上第一个包的 ACK 几十微秒就回来了,Nagle 没有机会把第二次 write 合并进去;只有应用自己一次发出(拼接或 sendmsg)才是一条消息一个包')

print('== 三:TCP_NOPUSH(BSD 版的“软木塞”):lo0 上打开 NOPUSH 连发 3 个 100 字节,然后依次:等 0.5 秒 → 清除选项 → 等 0.5 秒 → 再写 1 字节 → 等 0.5 秒 → shutdown(SHUT_WR);每一步之后看线上数据段个数和接收方累计读到的字节数')
def nopush_test(nodelay):
    ls, port = pair(); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); cn.setblocking(False)
    if nodelay: k.setsockopt(socket.IPPROTO_TCP, NODELAY, 1)
    got = [0]
    def rd():
        try:
            while True:
                d = cn.recv(1 << 16)
                if not d: return
                got[0] += len(d)
        except BlockingIOError: pass
    steps_ = []
    with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
        k.setsockopt(socket.IPPROTO_TCP, NOPUSH, 1)
        for i in range(3): k.sendall(bytes([65 + i]) * 100)
        time.sleep(0.5); rd(); steps_.append(('写 3×100 字节(NOPUSH 开)后 0.5 秒', got[0], time.time()))
        k.setsockopt(socket.IPPROTO_TCP, NOPUSH, 0); time.sleep(0.5); rd(); steps_.append(('清除 NOPUSH 后 0.5 秒', got[0], time.time()))
        k.sendall(b'Z'); time.sleep(0.5); rd(); steps_.append(('再写 1 字节后 0.5 秒', got[0], time.time()))
        k.shutdown(socket.SHUT_WR); time.sleep(0.5); rd(); steps_.append(('shutdown(SHUT_WR) 后 0.5 秒', got[0], time.time()))
        time.sleep(0.3)
    P = pkts(c.pcap, port); data = [p for p in P if p['c2s'] and p['plen'] > 0]
    prev = 0; prevn = 0
    for nm, g, tm in steps_:
        n_ = sum(1 for p in data if p['ts'] < tm)
        print(f'    {nm}:线上累计数据段 {n_} 个,接收方累计读到 {g} 字节')
    print(f'    各数据段载荷:{[p["plen"] for p in data]}')
    k.close(); cn.close(); ls.close()
for nd in (False, True):
    print(f'  {"TCP_NODELAY" if nd else "Nagle 开(默认)"} + NOPUSH:'); nopush_test(nd)

print('== 四:攒满一个 MSS 会自动发:NOPUSH 打开时一次写 40000 字节(lo0 的 MSS 是 16344),不关选项,线上有几个数据段、各多大')
ls, port = pair(); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); k.setsockopt(socket.IPPROTO_TCP, NOPUSH, 1)
gotn = [0]
def drain4():
    cn.settimeout(1.5)
    try:
        while True:
            d = cn.recv(1 << 20)
            if not d: break
            gotn[0] += len(d)
    except Exception: pass
th = threading.Thread(target=drain4); th.start()
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
    k.sendall(b'q' * 40000); th.join(); time.sleep(0.3)
P = pkts(c.pcap, port); data = [p for p in P if p['c2s'] and p['plen'] > 0]
print(f'  接收方在 1.5 秒内读到 {gotn[0]} 字节(共写 40000);线上数据段载荷:{[p["plen"] for p in data]}')
print(f'  40000 字节 = 2 个满段 ({2 * 16332} 字节) + 零头 {40000 - 2 * 16332} 字节;零头{"没有发出" if gotn[0] == 2 * 16332 else "是否发出见上"}')
k.setsockopt(socket.IPPROTO_TCP, NOPUSH, 0); time.sleep(0.5); cn.settimeout(0.5)
try: d = cn.recv(1 << 20); print(f'  清除 NOPUSH 后 0.5 秒,接收方又读到 {len(d)} 字节')
except Exception: print('  清除 NOPUSH 后 0.5 秒,接收方没有再读到数据')
k.close(); cn.close(); ls.close()
