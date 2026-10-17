import sys, os, re, struct, collections, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w39'); reset()
FL = [(0x20, 'URG'), (0x10, 'ACK'), (0x08, 'PSH'), (0x04, 'RST'), (0x02, 'SYN'), (0x01, 'FIN')]
def flags(f): return '+'.join(n for b, n in FL if f & b) or '无'
def tcps(path):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            ip = bytes(buf[4:]); 
            if ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:tl_]
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); out.append(dict(ts=ts, sp=sp, dp=dp, seq=seq, ack=ack, fl=fl, plen=len(t) - (off >> 4) * 4))
    return out
def seqtxt(P, sport, skip_hs=True):
    """把一个连接的包列成 C/S 序列(只看握手以外)"""
    return [f'{"客户端" if p["dp"] == sport else "服务端"}:{flags(p["fl"])}' + (f'({p["plen"]}字节)' if p['plen'] else '') for p in P if not (p['fl'] & 0x02 and skip_hs) and not (p['fl'] == 0x10 and p['plen'] == 0 and p['seq'] <= 0 and False)]
def pair():
    ls = socket.socket(); ls.bind(('127.0.0.1', 0)); ls.listen(); port = ls.getsockname()[1]
    return ls, port
def trace(fn, label):
    ls, port = pair()
    with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
        fn(ls, port); time.sleep(0.5)
    P = tcps(c.pcap); P = [p for p in P if not (p['fl'] & 0x02)]
    return P, port

print('== 一:最普通的关闭:客户端 close(),服务端读到 EOF 后也 close()。线上的包序列(握手之后)')
def f1(ls, port):
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); k.sendall(b'hi'); cn.recv(10); k.close(); cn.recv(10); cn.close()
P, port = trace(f1, '普通')
print('  ' + ' → '.join(seqtxt(P, port)[:8]))
print(f'  共 {len(P)} 个包(握手之外)。四次挥手:客户端 FIN → 服务端 ACK;服务端 FIN → 客户端 ACK;这里服务端的 ACK 和 FIN {"分开发了" if sum(1 for p in P if p["fl"] & 1) == 2 and any(p["fl"] == 0x10 and p["sp"] == port for p in P[-4:]) else "合并发了"}')
cnt = collections.Counter(len([p for p in trace(f1, 'x')[0]]) for _ in range(10))
print(f'  重复 10 次,包数分布(握手之外):{dict(cnt)}')

print('== 二:半关闭:客户端 shutdown(SHUT_WR) 只关发送方向(发 FIN),但还能继续收服务端的数据——服务端读到 EOF 后再发应答')
def f2(ls, port):
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept()
    k.sendall(b'REQUEST'); k.shutdown(socket.SHUT_WR)
    data = b''
    while True:
        d = cn.recv(100)
        if not d: break
        data += d
    cn.sendall(b'RESPONSE-after-EOF:' + data); cn.close(); k.settimeout(2)
    got = b''
    while True:
        d = k.recv(100)
        if not d: break
        got += d
    f2.got = got; k.close()
P, port = trace(f2, '半关闭')
print('  ' + ' → '.join(seqtxt(P, port)[:10]))
print(f'  客户端在 FIN 之后仍然收到了服务端的 {len(f2.got)} 字节数据:{f2.got!r};这就是“半关闭”——TCP 的两个方向是独立关闭的')

print('== 三:close() 和 shutdown() 的区别之一:close 时接收缓冲区里还有没读的数据,发出的是 RST 而不是 FIN')
def f3(ls, port):
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); k.sendall(b'unread-data'); time.sleep(0.2); cn.close(); k.settimeout(1)
    try: r = k.recv(100); f3.r = f'recv 得到 {r!r}'
    except Exception as e: f3.r = f'{type(e).__name__}: {getattr(e, "strerror", e)}'
    k.close()
P, port = trace(f3, '未读')
print('  服务端(accepted 套接字)未读完数据就 close():' + ' → '.join(seqtxt(P, port)[:8]))
print(f'  客户端随后 recv:{f3.r}')
def f3b(ls, port):
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); k.sendall(b'unread-data'); time.sleep(0.2); cn.recv(100); cn.close(); k.settimeout(1)
    f3b.r = repr(k.recv(100)); k.close()
P, port = trace(f3b, '已读')
print('  对照:服务端先把数据读完再 close():' + ' → '.join(seqtxt(P, port)[:8]) + f';客户端 recv 得到 {f3b.r}(正常 EOF)')
def f3c(ls, port):
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); cn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)); cn.close(); k.settimeout(1)
    try: f3c.r = repr(k.recv(100))
    except Exception as e: f3c.r = f'{type(e).__name__}: {getattr(e, "strerror", e)}'
    k.close()
P, port = trace(f3c, 'linger0')
print('  SO_LINGER(开,0 秒)后 close():' + ' → '.join(seqtxt(P, port)[:6]) + f';客户端 recv:{f3c.r}')
print('  所以 close 不一定发 FIN:缓冲区里有没读的数据(或 SO_LINGER 0)会直接发 RST,对方看到的是“连接被重置”而不是正常的 EOF——数据可能因此丢失')

print('== 四:shutdown(SHUT_RD) 的行为:关掉读方向之后,对方再发来的数据会怎样')
def f4(ls, port):
    k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); cn.shutdown(socket.SHUT_RD); time.sleep(0.1)
    k.sendall(b'after-shutdown-rd'); time.sleep(0.2); cn.settimeout(0.3)
    try: f4.r = repr(cn.recv(100))
    except Exception as e: f4.r = f'{type(e).__name__}'
    try: k.sendall(b'more'); f4.s = '第二次 send 成功'
    except Exception as e: f4.s = f'第二次 send 报错 {getattr(e, "strerror", e)}'
    cn.close(); k.close()
P, port = trace(f4, 'SHUT_RD')
print('  ' + ' → '.join(seqtxt(P, port)[:8]))
print(f'  服务端对 SHUT_RD 之后到达的数据 recv 得到 {f4.r};客户端:{f4.s}。SHUT_RD 只是本地的行为,线上不发任何包(没有 FIN),对方不知道')

print('== 五:同时关闭:两端几乎同时 close(),FIN 在线上交叉。回环太快几乎抓不到,所以给 lo0 加 50 ms 单向延迟;重复 10 次,数 FIN 交叉的次数,并在两端刚 close 之后 30 ms 看一次 netstat 里的状态')
cross = both = 0; ex = None; states = collections.Counter()
for i in range(10):
    p_ = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p_)); ls.listen()
    with lossy(loss=0, delay=50, bw=0):
        with Cap(f'tcp port {p_}', iface='lo0', write=True) as c:
            k = socket.create_connection(('127.0.0.1', p_)); cn, _ = ls.accept(); b = threading.Barrier(2)
            def cl(s):
                b.wait(); s.close()
            t1 = threading.Thread(target=cl, args=(k,)); t2 = threading.Thread(target=cl, args=(cn,)); t1.start(); t2.start(); t1.join(); t2.join(); time.sleep(0.03)
            st = [l.split()[-1] for l in sysout('netstat', '-an', '-p', 'tcp').splitlines() if f'127.0.0.1.{p_} ' in l or f'.{p_} ' in l]
            for x in st: states[x] += 1
            time.sleep(0.4)
    ls.close()
    seen = set(); P = []
    for q in tcps(c.pcap):          # netlab 的 dummynet 会让同一个包在 lo0 上被抓到多次,按 (源端口, 序号, 标志) 去重只留第一次
        key = (q['sp'], q['seq'], q['fl'])
        if q['fl'] & 0x02 or key in seen: continue
        seen.add(key); P.append(q)
    f = [q for q in P if q['fl'] & 1]
    if len(f) == 2 and f[0]['sp'] != f[1]['sp']:
        both += 1
        if abs(f[1]['ts'] - f[0]['ts']) < 0.04: cross += 1; ex = ex or ' → '.join(seqtxt(P, p_)[:6])
print(f'  10 次里两端都发出了 FIN 的 {both} 次(同一个包会被 dummynet 在 lo0 上多次抓到,已按序号去重),其中两个 FIN 相隔不到 40 ms(来不及等对方的 ACK,也就是交叉)的 {cross} 次')
print(f'  一次交叉的序列:{ex}' if ex else '  没有抓到 FIN 交叉的情形')
print(f'  close 之后 30 ms 时 netstat 看到的这些连接的状态(两端各一行):{dict(states)}')
print('  同时关闭时两端都经过 FIN_WAIT_1 → CLOSING → TIME_WAIT,和一方先关一方后关的路径(FIN_WAIT_1 → FIN_WAIT_2 → TIME_WAIT / CLOSE_WAIT → LAST_ACK)不同(下一篇状态机用 netstat 逐个看)')
