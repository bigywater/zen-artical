import sys, os, re, struct, threading, statistics, errno, signal, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w57'); reset()
def pkts(path, port):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            ip = bytes(buf[4:])
            if ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); out.append(dict(ts=ts, c2s=(dp == port), seq=seq, ack=ack, fl=fl, plen=tl_ - ihl - (off >> 4) * 4))
    return out
def pair(port=0):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(); return ls, ls.getsockname()[1]
FL = {0x02: 'SYN', 0x12: 'SYN+ACK', 0x10: 'ACK', 0x18: 'PSH+ACK', 0x11: 'FIN+ACK', 0x04: 'RST', 0x14: 'RST+ACK', 0x19: 'FIN+PSH+ACK'}
def dump(P, t0=None):
    t0 = P[0]['ts'] if t0 is None else t0
    for p in P: print(f'    +{p["ts"] - t0:6.3f} s  {"客户端→服务端" if p["c2s"] else "服务端→客户端"}  {FL.get(p["fl"], hex(p["fl"])):<8} 载荷 {p["plen"]} 字节')

print('== 一:对端进程被 kill -9(没有机会调 close):内核替它收尾。服务端是另一个进程,建立连接后 SIGKILL 它,客户端这边看到什么')
code = "import socket,sys,time\\nls=socket.socket();ls.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);ls.bind(('127.0.0.1',int(sys.argv[1])));ls.listen()\\nc,_=ls.accept();c.recv(100);c.sendall(b'pong');time.sleep(60)"
port = lab_port(); srv = subprocess.Popen([sys.executable, '-c', code.replace('\\n', chr(10)), str(port)]); time.sleep(0.5)
k = socket.create_connection(('127.0.0.1', port)); k.sendall(b'ping'); print(f'  先正常通信:收到 {k.recv(10)!r}')
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
    os.kill(srv.pid, signal.SIGKILL); srv.wait(); time.sleep(0.5)
P = pkts(c.pcap, port); print('  SIGKILL 之后线上的包:'); dump(P) if P else print('    (没有任何包)')
k.settimeout(1); d = k.recv(10); print(f'  客户端 recv 返回 {d!r}(空 = 对端有序关闭 FIN)')
k.close()

print('== 二:对端进程被 SIGSTOP(冻住,不是消失):内核仍然替它 ACK,但应用不读也不写')
port = lab_port(); srv = subprocess.Popen([sys.executable, '-c', code.replace('\\n', chr(10)), str(port)]); time.sleep(0.5)
k = socket.create_connection(('127.0.0.1', port)); k.sendall(b'ping'); k.recv(10)
os.kill(srv.pid, signal.SIGSTOP); time.sleep(0.2)
t0 = time.time(); sent = 0
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
    k.setblocking(False)
    try:
        while True:
            n_ = k.send(b'x' * 65536); sent += n_
    except BlockingIOError: pass
    time.sleep(1)
P = pkts(c.pcap, port); zw = [p for p in P if not p['c2s'] and p['plen'] == 0]
print(f'  对端冻住后客户端一直写,直到发送缓冲区和对端接收缓冲区都满,共写进 {sent} 字节({sent / 1048576:.2f} MiB)后 send 返回 EWOULDBLOCK;线上服务端(内核)一直在回 ACK,共 {len(zw)} 个纯 ACK')
os.kill(srv.pid, signal.SIGKILL); srv.wait(); k.close()

print('== 三:对照:对端用 SO_LINGER(1, 0) 关闭连接,会立刻发 RST,本端马上知道——这不是半开,先看正常的“被通知”是什么样')
ls, port = pair(lab_port()); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept()
k.sendall(b'ping'); cn.recv(10)
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
    cn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)); cn.close(); time.sleep(0.3)
    try: k.sendall(b'again'); print('  客户端 send 成功(内核已收到 RST,但还没告诉应用)')
    except OSError as e: print(f'  客户端 send 报错:{e}')
    time.sleep(0.3)
    try: k.sendall(b'again2'); print('  第二次 send 成功')
    except OSError as e: print(f'  第二次 send 报错:{errno.errorcode.get(e.errno)} {e.strerror}')
P = pkts(c.pcap, port); print('  线上的包:'); dump(P)
k.close(); ls.close()

print('== 四:真正的半开:服务端丢了状态,而 RST 在路上丢了,客户端还以为连接在。lo0 上用 netlab 丢包 50%(每个方向)做 40 次:每次建立连接后,在丢包环境下服务端 SO_LINGER(1,0) 关闭(RST 有一半的概率被丢);然后等 0.5 秒,看客户端有没有察觉(非阻塞 recv 带 MSG_PEEK:BlockingIOError = 毫无察觉的半开;ECONNRESET/空 = 已被通知)')
N4 = 40; unaware = []; aware = 0
lss = []; pairs4 = []
for i in range(N4):
    ls, port = pair(lab_port()); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); k.sendall(b'ping'); cn.recv(10); pairs4.append((ls, k, cn))
with lossy(loss=50, delay=1, bw=0):
    for ls, k, cn in pairs4: cn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)); cn.close()
    time.sleep(0.5)
    for ls, k, cn in pairs4:
        k.setblocking(False)
        try:
            d = k.recv(10, socket.MSG_PEEK); aware += 1
        except BlockingIOError: unaware.append((ls, k))
        except OSError: aware += 1
    print(f'  40 个连接里:客户端已被通知(ECONNRESET 或 EOF)的 {aware} 个;毫无察觉的半开 {len(unaware)} 个(RST 在 netlab 里被丢了)')
    r5 = []
    for ls, k in unaware:
        k.setblocking(True); k.settimeout(6); t0 = time.time()
        try: k.sendall(b'hello?'); k.settimeout(0.5); time.sleep(0.5); k.recv(10, socket.MSG_PEEK); r5.append('收到数据/EOF')
        except socket.timeout: r5.append('仍无察觉')
        except OSError as e: r5.append(errno.errorcode.get(e.errno, str(e.errno)))
from collections import Counter
print(f'  对这些半开连接各发一次数据后(服务端没有这个连接,会回 RST;RST 同样有 50% 被丢):{dict(Counter(r5))}')
for ls, k, cn in pairs4:
    k.close(); ls.close()

print('== 五:没有 keepalive、也不发数据时,一条半开连接能活多久?两个“知道”的时机:本端发数据时(对端已丢状态 → RST;对端是黑洞 → 重传直到超时)。黑洞下的重传超时:用 netlab 丢包 50% 做不到黑洞,所以这里测另一条真实路径:向 example.com:81(丢 SYN 的黑洞)connect,看 connect 多久失败')
t0 = time.time(); k = socket.socket(); k.settimeout(120)
try: k.connect(('104.20.23.154', 81)); print('  连上了')
except OSError as e: print(f'  connect 到 example.com:81 在 {time.time() - t0:.1f} 秒后失败:{errno.errorcode.get(e.errno, e.errno)} {e.strerror}')
k.close()
print('  系统参数:' + ';'.join(sysout('sysctl', x).strip() for x in ('net.inet.tcp.keepinit', 'net.inet.tcp.rexmt_slop' if False else 'net.inet.tcp.msl')))
