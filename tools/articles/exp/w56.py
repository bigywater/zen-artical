import sys, os, re, struct, threading, statistics, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w56'); reset()
KA = getattr(socket, 'TCP_KEEPALIVE', 0x10); KI = getattr(socket, 'TCP_KEEPINTVL', 0x101); KC = getattr(socket, 'TCP_KEEPCNT', 0x102)
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
def setka(k, idle, intvl, cnt):
    k.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1); k.setsockopt(socket.IPPROTO_TCP, KA, idle); k.setsockopt(socket.IPPROTO_TCP, KI, intvl); k.setsockopt(socket.IPPROTO_TCP, KC, cnt)

print('== 一:系统默认值:keepalive 默认关闭,打开后空闲多久才探测、多久一次、最多几次')
for k_ in ('net.inet.tcp.keepidle', 'net.inet.tcp.keepintvl', 'net.inet.tcp.keepcnt', 'net.inet.tcp.always_keepalive'): print('  ' + sysout('sysctl', k_).strip())
print('  单位:keepidle、keepintvl 是毫秒。默认:空闲 7200000 ms = 2 小时才发第一个探测,之后每 75 s 一个,8 次无回应才判死')
idle_s, ivl_s, cnt_ = 7200, 75, 8
print(f'  按默认值,一条空闲连接的对端消失后,最长要 {idle_s} + {ivl_s} × {cnt_} = {idle_s + ivl_s * cnt_} 秒({(idle_s + ivl_s * cnt_) / 3600:.2f} 小时)才会报错(公式计算,下面第四节用缩短的参数实测)')

print('== 二:每个套接字自己的选项:SO_KEEPALIVE 打开,TCP_KEEPALIVE(空闲秒数)、TCP_KEEPINTVL、TCP_KEEPCNT 设置后读回')
ls, port = pair(); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept()
print(f'  新连接上 SO_KEEPALIVE = {k.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE)}')
print(f'  socket 模块的常量:TCP_KEEPALIVE={hasattr(socket, "TCP_KEEPALIVE")}(值 {KA}),TCP_KEEPINTVL={hasattr(socket, "TCP_KEEPINTVL")}(值 {KI}),TCP_KEEPCNT={hasattr(socket, "TCP_KEEPCNT")}(值 {KC}),TCP_KEEPIDLE={hasattr(socket, "TCP_KEEPIDLE")}')
print(f'  不设置时读回:TCP_KEEPALIVE={k.getsockopt(socket.IPPROTO_TCP, KA)} TCP_KEEPINTVL={k.getsockopt(socket.IPPROTO_TCP, KI)} TCP_KEEPCNT={k.getsockopt(socket.IPPROTO_TCP, KC)}')
setka(k, 2, 1, 3)
print(f'  设成 (idle=2, intvl=1, cnt=3) 后读回:SO_KEEPALIVE={k.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE)} TCP_KEEPALIVE={k.getsockopt(socket.IPPROTO_TCP, KA)} TCP_KEEPINTVL={k.getsockopt(socket.IPPROTO_TCP, KI)} TCP_KEEPCNT={k.getsockopt(socket.IPPROTO_TCP, KC)}')
k.close(); cn.close(); ls.close()

print('== 三:探测包长什么样:对端活着,idle=2、intvl=1、cnt=3,连接空闲 9 秒,抓 lo0 上的包')
ls, port = pair(); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept()
k.sendall(b'hello'); cn.recv(10)
setka(k, 2, 1, 3); t_set = time.time()
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
    t_cap = time.time(); time.sleep(9)
P = pkts(c.pcap, port); base = P[0]['ts'] if P else 0
print(f'  9 秒内线上共 {len(P)} 个包(设置选项前连接已有的数据已不在内):')
for p in P:
    print(f'    +{p["ts"] - t_cap:6.2f} s  {"客户端→服务端" if p["c2s"] else "服务端→客户端"}  载荷 {p["plen"]} 字节  seq(相对)={p["seq"] & 0xffff}  ack(相对)={p["ack"] & 0xffff}  标志 {p["fl"]:#04x}')
pr = [p for p in P if p['c2s']]
print(f'  探测包个数 {len(pr)},间隔(s):{[round(pr[i + 1]["ts"] - pr[i]["ts"], 2) for i in range(len(pr) - 1)]}')
k.close(); cn.close(); ls.close()

print('== 四:对端“消失”时多久发现:lo0 上用 netlab 丢包 50%(每个方向)模拟一个时灵时不灵的链路——不是真正的黑洞(丢包上限 50%),只能用来看“连续 cnt 次探测没有回应就断开”的规则。30 条连接,都设 idle=2、intvl=1、cnt=3,放进丢包环境后空闲 25 秒,记录每条连接什么时候被内核判死、recv 收到什么错误')
N = 30; socks = []; lss = []
for i in range(N):
    ls, port = pair(lab_port()); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); setka(k, 2, 1, 3); socks.append((k, cn)); lss.append(ls)
res4 = [None] * N
def waiter(i, k, t0):
    k.settimeout(26)
    try:
        d = k.recv(10); res4[i] = (time.time() - t0, 'recv 返回 %r' % d)
    except OSError as e:
        if e.errno is None: res4[i] = (None, '25 秒内没有被判死')
        else: res4[i] = (time.time() - t0, errno.errorcode.get(e.errno, str(e.errno)) + ' ' + e.strerror)
with lossy(loss=50, delay=1, bw=0):
    t0 = time.time(); ths = [threading.Thread(target=waiter, args=(i, k, t0)) for i, (k, cn) in enumerate(socks)]
    for th in ths: th.start()
    for th in ths: th.join()
died = [r for r in res4 if r[0] is not None]
print(f'  25 秒内被内核判死的连接:{len(died)} / {N};其余 {N - len(died)} 条一直有探测得到回应(在丢包下运气好),仍然连着')
if died:
    ts_ = sorted(r[0] for r in died)
    print(f'  判死的时间(秒,从放进丢包环境算起):最短 {ts_[0]:.1f} / 中位 {statistics.median(ts_):.1f} / 最长 {ts_[-1]:.1f};recv 的错误:{sorted(set(r[1] for r in died))}')
print(f'  规则下限:idle + intvl × cnt = 2 + 1 × 3 = 5 秒(第一个探测在空闲 2 秒后,之后每 1 秒一个,连续 3 次探测都没有回应,再过 1 个间隔才判死,具体边界以最短值为准)')
for k, cn in socks: k.close(); cn.close()
for ls in lss: ls.close()

print('== 五:真实网络:本机连 example.com:80 后什么都不发,idle=2、intvl=1、cnt=3,抓 en0 上 8 秒,看探测包和对端的回应')
with Cap('tcp port 80 and host 104.20.23.154', iface='en0', write=True, snaplen=96) as c:
    k = socket.create_connection(('104.20.23.154', 80), timeout=6); setka(k, 2, 1, 3); t_cap = time.time(); time.sleep(8)
rows = []
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(buf)
        if e.type != 0x0800: continue
        ip = bytes(e.data); ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]
        sp, dp, seq, ack, off, fl = struct.unpack('>HHIIBB', t[:14]); rows.append((ts, dp == 80, seq, ack, fl, tl_ - ihl - (off >> 4) * 4))
rows = [r for r in rows if r[0] >= t_cap - 0.5]
for r in rows:
    print(f'    +{r[0] - t_cap:6.2f} s  {"本机→服务器" if r[1] else "服务器→本机"}  载荷 {r[5]} 字节  标志 {r[4]:#04x}')
pr = [r for r in rows if r[1] and r[5] <= 1 and r[0] - t_cap > 1]; ac = [r for r in rows if not r[1] and r[0] - t_cap > 1]
print(f'  握手之后(第 1 秒起)本机发出的探测 {len(pr)} 个,服务器回的包 {len(ac)} 个;相邻探测的间隔(s):{[round(pr[i + 1][0] - pr[i][0], 2) for i in range(len(pr) - 1)]}')
rt = []
for p_ in pr:
    a = [r for r in ac if r[0] > p_[0]]
    if a: rt.append((a[0][0] - p_[0]) * 1000)
print(f'  探测到回应的延迟(ms):{[round(x) for x in rt]}')
k.close()
