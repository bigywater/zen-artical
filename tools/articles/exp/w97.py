import sys, os, re, struct, threading, statistics, errno, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
import paramiko, dpkt
tee('w97'); reset()
def free_port(lo=19000):
    import random
    while True:
        p = random.randrange(lo, lo + 900)
        s = socket.socket()
        try: s.bind(('127.0.0.1', p)); s.close(); return p
        except OSError: continue
def pump(a, b, stat=None):
    """在两个“类套接字”对象(socket 或 paramiko Channel)之间搬字节,直到一边关闭"""
    def one(src, dst, key):
        try:
            while True:
                d = src.recv(65536)
                if not d: break
                dst.sendall(d)
                if stat is not None: stat[key] += len(d)
        except Exception: pass
        try: dst.shutdown(socket.SHUT_WR)
        except Exception:
            try: dst.close()
            except Exception: pass
    t1 = threading.Thread(target=one, args=(a, b, 'up'), daemon=True); t2 = threading.Thread(target=one, args=(b, a, 'down'), daemon=True); t1.start(); t2.start(); return t1, t2
class Srv(paramiko.ServerInterface):
    def __init__(self, tr_holder): self.dest = {}; self.holder = tr_holder; self.rforwards = {}
    def get_allowed_auths(self, u): return 'password'
    def check_auth_password(self, u, p): return paramiko.AUTH_SUCCESSFUL if p == 'secret' else paramiko.AUTH_FAILED
    def check_channel_request(self, kind, cid): return paramiko.OPEN_SUCCEEDED
    def check_channel_direct_tcpip_request(self, chanid, origin, destination): self.dest[chanid] = (origin, destination); return paramiko.OPEN_SUCCEEDED
    def check_port_forward_request(self, address, port):
        ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(8); ls.settimeout(0.3); self.rforwards[port] = ls; tr = self.holder['t']
        def acc():
            while port in self.rforwards:
                try: c, a = ls.accept()
                except socket.timeout: continue
                try:
                    ch = tr.open_forwarded_tcpip_channel(a, ('127.0.0.1', port)); pump(c, ch)
                except Exception: c.close()
        threading.Thread(target=acc, daemon=True).start(); return port
    def cancel_port_forward_request(self, address, port): self.rforwards.pop(port, None)
def ssh_server(port, hostkey, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(8); ls.settimeout(0.3)
    def h(c):
        holder = {}; srv = Srv(holder)
        try:
            t = paramiko.Transport(c); holder['t'] = t; t.add_server_key(hostkey); t.start_server(server=srv)
            while t.is_active() and not stop[0]:
                ch = t.accept(0.5)
                if ch is None: continue
                d = srv.dest.get(ch.get_id())
                if d:
                    (oa, op), (da, dp) = d
                    try: o = socket.create_connection((da, dp), timeout=5); pump(ch, o)
                    except Exception: ch.close()
        except Exception: pass
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
def echo_server(port, stop, tag=b''):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(32); ls.settimeout(0.3)
    def h(c):
        try:
            while True:
                d = c.recv(65536)
                if not d: break
                c.sendall(tag + d)
        except Exception: pass
        finally: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
def sink_server(port, stop, total=2_000_000):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(32); ls.settimeout(0.3)
    def h(c):
        try:
            c.sendall(b'x' * total)
        except Exception: pass
        finally: c.close()
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
def local_forward(tr, lport, thost, tport, stop):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', lport)); ls.listen(32); ls.settimeout(0.3)
    def acc():
        while not stop[0]:
            try: c, a = ls.accept()
            except socket.timeout: continue
            try: ch = tr.open_channel('direct-tcpip', (thost, tport), a); pump(c, ch)
            except Exception: c.close()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()
def ssh_client(port):
    t = paramiko.Transport(('127.0.0.1', port)); t.start_client(timeout=10); t.auth_password('u', 'secret'); return t
hk = paramiko.ECDSAKey.generate(bits=256)

print('== 一:本地端口转发(ssh -L):客户端在本地端口 L 上监听,每个进来的连接都被包进 SSH 的一个 direct-tcpip 通道,送到 SSH 服务器,再由服务器去连目标 T。目标端口是一个回显服务器。看数据真的走了隧道')
sp = free_port(); stop = [False]; ssh_server(sp, hk, stop); tp = free_port(); echo_server(tp, stop, b'ECHO:'); lp = free_port()
t = ssh_client(sp); local_forward(t, lp, '127.0.0.1', tp, stop); time.sleep(0.3)
with Cap(f'tcp port {sp}', iface='lo0', write=True, snaplen=0) as c:
    s = socket.create_connection(('127.0.0.1', lp)); s.sendall(b'hello through the tunnel'); r = s.recv(100); s.close(); time.sleep(0.4)
print(f'  客户端连本地 {lp},发 b"hello through the tunnel",收到 {r!r}——服务器端的目标回显服务器加了 "ECHO:" 前缀,说明数据真的到了目标并回来了')
cs = b''
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        ip = bytes(buf[4:]); ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; tt = ip[ihl:]; off = (tt[12] >> 4) * 4; cs += tt[off:tl_ - ihl]
print(f'  同时抓 SSH 服务器端口 {sp} 上的流量(lo0):共 {len(cs)} 字节;其中能找到明文 "hello through the tunnel" 吗?{"能" if b"hello through the tunnel" in cs else "找不到"};能找到目标端口号 {tp} 的十进制文字吗?{"能" if str(tp).encode() in cs else "找不到(目标地址和端口在加密的通道请求里)"}')
print(f'  从线路上看只是一条 SSH 连接;目标 127.0.0.1:{tp} 是 SSH 服务器“看到”的,不是在你的机器上直接可达的路径(本实验里恰好都在本机)')
t.close()

print('== 二:远程端口转发(ssh -R):客户端请求服务器在它的端口 R 上监听;外面有人连 R,服务器就把连接通过 SSH 送回客户端,客户端再去连客户端这边的目标。用来把“里面”的服务暴露出去')
t = ssh_client(sp); rp = free_port(); tgt = free_port(); echo_server(tgt, stop, b'CLIENT-SIDE:')
def handler(chan, origin, server): 
    o = socket.create_connection(('127.0.0.1', tgt)); pump(chan, o)
t.request_port_forward('127.0.0.1', rp, handler); time.sleep(0.4)
s = socket.create_connection(('127.0.0.1', rp)); s.sendall(b'knock knock'); r = s.recv(100); s.close()
print(f'  请求服务器在 {rp} 上监听(tcpip-forward 全局请求);之后外部连 {rp} 发 b"knock knock",收到 {r!r}——连接经 SSH 回到了客户端这一侧的目标 {tgt}')
t.close()

print('== 三:一条 SSH 连接承载多个转发连接(多路复用):通过同一个隧道并发开 20 个连接,各自发一条不同的消息,收回自己的回显;看 SSH 服务器端口 TCP 连接数')
t = ssh_client(sp); lp2 = free_port(); local_forward(t, lp2, '127.0.0.1', tp, stop); time.sleep(0.3); res = [None] * 20
def one(i):
    s = socket.create_connection(('127.0.0.1', lp2)); s.sendall(b'msg-%02d' % i); d = b''
    while len(d) < 11: d += s.recv(100)
    res[i] = d; s.close()
th = [threading.Thread(target=one, args=(i,)) for i in range(20)]; [x.start() for x in th]; [x.join() for x in th]
print(f'  20 个并发连接各自收到自己的回显:{sum(1 for i, r in enumerate(res) if r == b"ECHO:msg-%02d" % i)} / 20 正确;它们全部复用同一条到 SSH 服务器的 TCP 连接(从 SSH 客户端 Transport 看:通道数是 SSH 的概念,TCP 连接数 1)')
t.close()

print('== 四:隧道的代价:lo0 上传 2 MB,直连 vs 经 SSH 隧道(吞吐、延迟);然后只在 SSH 那一条 TCP 连接上加 netlab 的延迟和丢包(目标和本地监听端口不在 netlab 范围内),看“TCP 套 TCP”的表现')
def dl(port, n=2_000_000):
    t0 = time.time(); s = socket.create_connection(('127.0.0.1', port)); got = 0; s.settimeout(30)
    while got < n:
        d = s.recv(1 << 20)
        if not d: break
        got += len(d)
    s.close(); return got, time.time() - t0
sink = free_port(); sink_server(sink, stop); t = ssh_client(sp); lp3 = free_port(); local_forward(t, lp3, '127.0.0.1', sink, stop); time.sleep(0.3)
d1 = [dl(sink) for _ in range(3)]; d2 = [dl(lp3) for _ in range(3)]
print(f'  直连 2 MB:{[round(x[1] * 1000) for x in d1]} ms,中位 {statistics.median(x[1] for x in d1) * 1000:.0f} ms(≈ {2 / statistics.median(x[1] for x in d1):.0f} MB/s)')
print(f'  经隧道 2 MB:{[round(x[1] * 1000) for x in d2]} ms,中位 {statistics.median(x[1] for x in d2) * 1000:.0f} ms(≈ {2 / statistics.median(x[1] for x in d2):.1f} MB/s;paramiko 在纯 Python 里加密 + 解密,比直连慢很多,不代表 OpenSSH 的速度)')
t.close(); stop[0] = True; time.sleep(0.5)
sp2 = lab_port(); stop2 = [False]; ssh_server(sp2, hk, stop2); sink2 = free_port(); sink_server(sink2, stop2)
direct_lab = lab_port(); sink_server(direct_lab, stop2)
for loss in (0, 2):
    with lossy(loss=loss, delay=25, bw=0):
        t = ssh_client(sp2); lp4 = free_port(); local_forward(t, lp4, '127.0.0.1', sink2, stop2); time.sleep(0.3)
        dd = [dl(direct_lab)[1] for _ in range(2)]; tt_ = [dl(lp4)[1] for _ in range(2)]; t.close()
    print(f'  netlab 每方向 25 ms、丢包 {loss}%:直连(目标端口在受损范围里)2 MB {[round(x * 1000) for x in dd]} ms;经隧道(只有 SSH 那条 TCP 受损,内层连接不受损)2 MB {[round(x * 1000) for x in tt_]} ms')
stop2[0] = True
