import sys, os, re, struct, threading, statistics, errno, ctypes, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w60'); reset()
libc = ctypes.CDLL('libc.dylib', use_errno=True)
class sa_endpoints(ctypes.Structure):
    _fields_ = [('sae_srcif', ctypes.c_uint), ('sae_srcaddr', ctypes.c_void_p), ('sae_srcaddrlen', ctypes.c_uint32), ('sae_dstaddr', ctypes.c_void_p), ('sae_dstaddrlen', ctypes.c_uint32)]
class iovec(ctypes.Structure): _fields_ = [('iov_base', ctypes.c_void_p), ('iov_len', ctypes.c_size_t)]
def sockaddr(host, port, scope=0):
    if ':' in host: return ctypes.create_string_buffer(struct.pack('!BBHI16sI', 28, socket.AF_INET6, port, 0, socket.inet_pton(socket.AF_INET6, host), 0)[:-4] + struct.pack('=I', scope), 28), 28
    return ctypes.create_string_buffer(struct.pack('!BBH4s8x', 16, socket.AF_INET, port, socket.inet_aton(host)), 16), 16
def connectx_data(s, host, port, data, scope=0, flags=2):
    dst, ln = sockaddr(host, port, scope); ep = sa_endpoints(0, None, 0, ctypes.addressof(dst), ln)
    buf = ctypes.create_string_buffer(data, len(data)); iov = iovec(ctypes.addressof(buf), len(data)); n = ctypes.c_size_t(0); cid = ctypes.c_uint(0)
    r = libc.connectx(s.fileno(), ctypes.byref(ep), 0, flags, ctypes.byref(iov), 1, ctypes.byref(n), ctypes.byref(cid))
    return r, ctypes.get_errno(), n.value
TFO = 0x105
def tcp_pkts(path, iface_en=False):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            if iface_en:
                e = dpkt.ethernet.Ethernet(buf)
                if e.type != 0x0800: continue
                ip = bytes(e.data)
            else: ip = bytes(buf[4:])
            if ip[0] >> 4 == 6:
                if ip[6] != 6: continue
                t = ip[40:]; tl_ = struct.unpack('>H', ip[4:6])[0]; ihl = 40; body = tl_
            else:
                if ip[9] != 6: continue
                ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]; body = tl_ - ihl
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); hl = (off >> 4) * 4; opts = []; o = t[20:hl]; i = 0
            while i < len(o):
                kd = o[i]
                if kd == 0: break
                if kd == 1: i += 1; continue
                ln = o[i + 1]; opts.append((kd, ln)); i += ln
            out.append(dict(ts=ts, sp=sp, dp=dp, seq=seq, ack=ack, fl=fl, plen=body - hl, opts=opts))
    return out
FLN = {0x02: 'SYN', 0x12: 'SYN+ACK', 0x10: 'ACK', 0x18: 'PSH+ACK', 0x11: 'FIN+ACK', 0x04: 'RST', 0x14: 'RST+ACK', 0x19: 'FIN+PSH+ACK'}
OPN = {2: 'MSS', 3: 'WS', 4: 'SACKok', 8: 'TS', 34: 'TFO', 5: 'SACK'}
def dd(P):
    seen = set(); out = []
    for p in P:
        key = (p['sp'], p['dp'], p['seq'], p['fl'], p['plen'])
        if key in seen: continue
        seen.add(key); out.append(p)
    return out
def show(P, port):
    t0 = P[0]['ts']
    for p in P:
        print(f'    +{(p["ts"] - t0) * 1000:7.2f} ms  {"C→S" if p["dp"] == port else "S→C"}  {FLN.get(p["fl"], hex(p["fl"])):<9} 载荷 {p["plen"]:>3} 字节  选项 {[OPN.get(k, k) for k, l in p["opts"]]}' + ('  ← TFO 选项长度 ' + str([l for k, l in p['opts'] if k == 34]) if any(k == 34 for k, l in p['opts']) else ''))
def syns(P, port): return [p for p in P if p['fl'] & 0x12 == 0x02 and p['dp'] == port]
def topt(p): return [l for k, l in p['opts'] if k == 34]

def server(host, port, tfo, n, scope=0):
    fam = socket.AF_INET6 if ':' in host else socket.AF_INET
    ls = socket.socket(fam); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ls.bind((host, port, 0, scope) if fam == socket.AF_INET6 else (host, port)); ls.listen()
    if tfo: ls.setsockopt(socket.IPPROTO_TCP, TFO, 1)
    ls.settimeout(5); res = []
    def run():
        for i in range(n):
            try:
                cn, _ = ls.accept(); cn.settimeout(2); d = cn.recv(100); res.append(d); cn.sendall(b'R' * 10); time.sleep(0.05); cn.close()
            except Exception as e: res.append(repr(e))
        ls.close()
    th = threading.Thread(target=run); th.start(); return th, res
def client(host, port, data, scope=0, tfo=True):
    fam = socket.AF_INET6 if ':' in host else socket.AF_INET
    k = socket.socket(fam)
    if tfo: connectx_data(k, host, port, data, scope)
    else: k.connect((host, port, 0, scope) if fam == socket.AF_INET6 else (host, port)); k.sendall(data)
    k.settimeout(3); k.recv(20); return k

print('== 一:内核参数与选项:net.inet.tcp.fastopen 是位掩码(1 = 客户端、2 = 服务端),TCP_FASTOPEN 套接字选项值 0x105,服务端要在 listen() 之后设置')
for k_ in ('net.inet.tcp.fastopen', 'net.inet.tcp.fastopen_backlog'): print('  ' + sysout('sysctl', k_).strip())
ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', lab_port()))
try: ls.setsockopt(socket.IPPROTO_TCP, TFO, 1); r = '成功'
except OSError as e: r = errno.errorcode.get(e.errno)
print(f'  listen() 之前对监听套接字 setsockopt(TCP_FASTOPEN, 1):{r}')
ls.listen()
try: ls.setsockopt(socket.IPPROTO_TCP, TFO, 1); r = '成功,读回 ' + str(ls.getsockopt(socket.IPPROTO_TCP, TFO))
except OSError as e: r = errno.errorcode.get(e.errno)
print(f'  listen() 之后 setsockopt(TCP_FASTOPEN, 1):{r}')
ls.close()
print(f'  Python 的 socket 模块里有 TCP_FASTOPEN: {hasattr(socket, "TCP_FASTOPEN")};有 MSG_FASTOPEN: {hasattr(socket, "MSG_FASTOPEN")}(Linux 用 sendto + MSG_FASTOPEN,macOS 用 connectx,这里通过 ctypes 调用 libc 的 connectx)')

print('== 二:服务端没有开 TFO(127.0.0.1)时,连续 3 次 connectx(带 6 字节数据,CONNECT_DATA_IDEMPOTENT):客户端的 SYN 里有没有 TFO 选项、有没有数据,数据最后怎么到的')
port = lab_port(); th, got = server('127.0.0.1', port, False, 3)
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
    for i in range(3): client('127.0.0.1', port, b'hello%d' % i).close(); time.sleep(0.2)
    th.join(); time.sleep(0.3)
P = dd(tcp_pkts(c.pcap)); print(f'  服务端收到的数据 {got}')
for j, p in enumerate(syns(P, port)):
    sa = [q for q in P if q['sp'] == port and q['dp'] == p['sp'] and q['fl'] & 0x12 == 0x12][0]
    print(f'  第 {j + 1} 个连接:SYN 载荷 {p["plen"]} 字节,SYN 选项 {[OPN.get(k_, k_) for k_, l in p["opts"]]}(TFO 选项长度 {topt(p)});SYN+ACK 选项 {[OPN.get(k_, k_) for k_, l in sa["opts"]]}')

def local_v4():
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.connect(('8.8.8.8', 53)); a = u.getsockname()[0]; u.close(); return a
def local_ll6():
    out = subprocess.run(['ifconfig', 'en0'], capture_output=True, text=True).stdout
    return re.search(r'inet6 (fe80::[0-9a-f:]+)%en0', out).group(1), socket.if_nametoindex('en0')
A = local_v4(); B, BI = local_ll6()
print('== 三:服务端开 TFO,目的地用本机 en0 的 IPv4 地址(发往自己地址的包走 lo0,一个之前没用过的目的地):连续 12 次 connectx(各带 6 字节),每个连接的 SYN 载荷。TFO 的记忆是按目的地址存的')
port = lab_port(); th, got = server(A, port, True, 12)
with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
    for i in range(12): client(A, port, b'hello%02d' % i).close(); time.sleep(0.2)
    th.join(); time.sleep(0.3)
P = dd(tcp_pkts(c.pcap)); sy = syns(P, port)
print(f'  服务端收到的数据 {len(got)} 条,全部正确:{got == [b"hello%02d" % i for i in range(12)]}')
print(f'  12 个连接的 SYN 载荷(字节):{[p["plen"] for p in sy]}')
print(f'  12 个 SYN 的 TFO 选项长度:{[topt(p) for p in sy]}(2 = 只请求 cookie;10 = 带 8 字节 cookie)')
first = sy[1]['sp']; print('  第 2 个连接(SYN 里带数据的第一个)的全部包:'); show([p for p in P if p['sp'] == first or p['dp'] == first], port)
sa = [q for q in P if q['sp'] == port and q['dp'] == sy[1]['sp'] and q['fl'] & 0x12 == 0x12][0]
print(f'  它的 SYN+ACK 的 ack = SYN 的 seq + {sa["ack"] - sy[1]["seq"]}(1 个 SYN + {sy[1]["plen"]} 字节数据)')

print('== 四:省下多少时间:目的地换成本机 en0 的链路本地 IPv6 地址(又一个没用过的目的地),lo0 上加每方向 50 ms 延迟(RTT 100 ms)。先 4 次普通 connect + send,再 4 次 connectx(第 1 次取 cookie),看耗时和每个 SYN 的载荷')
res = {}
with lossy(loss=0, delay=50, bw=0):
    port = lab_port(); th, got = server(B, port, False, 4, BI); ts = []
    for i in range(4):
        t0 = time.time(); k = client(B, port, b'hello', BI, tfo=False); ts.append((time.time() - t0) * 1000); k.close(); time.sleep(0.2)
    th.join(); res['普通 connect + send'] = ts
    port = lab_port(); th, got = server(B, port, True, 4, BI); ts = []
    with Cap(f'ip6 and tcp port {port}', iface='lo0', write=True, snaplen=128) as c4:
        for i in range(4):
            t0 = time.time(); k = client(B, port, b'hello', BI); ts.append((time.time() - t0) * 1000); k.close(); time.sleep(0.2)
        th.join(); time.sleep(0.5)
    res['connectx(TFO)'] = ts
P4 = dd(tcp_pkts(c4.pcap)); sy4 = syns(P4, port)
for nm, ts in res.items(): print(f'  {nm:<22}:逐次(ms):{[round(x) for x in ts]}')
print(f'  connectx 这 4 次的 SYN 载荷(字节):{[p["plen"] for p in sy4]}')
n_t = [t for t, p in zip(res['connectx(TFO)'], sy4) if p['plen'] > 0]; n_n = [t for t, p in zip(res['connectx(TFO)'], sy4) if p['plen'] == 0]
a_ = statistics.median(res['普通 connect + send'])
print(f'  普通 connect + send 中位 {a_:.0f} ms;connectx 里 SYN 带数据的 {len(n_t)} 次中位 {statistics.median(n_t):.0f} ms' + (f',SYN 没带数据的 {len(n_n)} 次中位 {statistics.median(n_n):.0f} ms' if n_n else '') + f';省下 {a_ - statistics.median(n_t):.0f} ms ≈ {(a_ - statistics.median(n_t)) / 100:.1f} 个 RTT(RTT = 2 × 50 ms)')

print('== 五:真实服务器:对 example.com:80 用 connectx 在 SYN 里带 HTTP 请求,抓 en0 看 SYN 里的 TFO 选项、服务器如何处理 SYN 里的数据,响应第一批字节的时间(各 3 次,与普通 connect + send 比)')
req = b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'
with Cap('tcp port 80 and host 104.20.23.154', iface='en0', write=True, snaplen=96) as c:
    tt = []
    for i in range(3):
        k = socket.socket(); t0 = time.time(); r = connectx_data(k, '104.20.23.154', 80, req); k.settimeout(6)
        try: d = k.recv(100); tt.append(((time.time() - t0) * 1000, d[:12]))
        except Exception as e: tt.append((None, repr(e)))
        k.close(); time.sleep(0.3)
    nt = []
    for i in range(3):
        t0 = time.time(); k = socket.create_connection(('104.20.23.154', 80), timeout=6); k.sendall(req); d = k.recv(100); nt.append((time.time() - t0) * 1000); k.close(); time.sleep(0.3)
rows = tcp_pkts(c.pcap, True); syn = [p for p in rows if p['fl'] & 0x12 == 0x02 and p['dp'] == 80]
for j, p in enumerate(syn[:3]):
    sa = [q for q in rows if q['sp'] == 80 and q['dp'] == p['sp'] and q['fl'] & 0x12 == 0x12]
    print(f'  connectx 第 {j + 1} 次:SYN 载荷 {p["plen"]} 字节,SYN 选项 {[OPN.get(k_, k_) for k_, l in p["opts"]]}(TFO 选项长度 {topt(p)});SYN+ACK 选项 {[OPN.get(k_, k_) for k_, l in sa[0]["opts"]] if sa else None}(TFO 选项长度 {topt(sa[0]) if sa else None}),ack = SYN 的 seq + {sa[0]["ack"] - p["seq"] if sa else None}')
print(f'  connectx 到收到响应第一批字节:{[round(x[0]) if x[0] else x[1] for x in tt]} ms;响应开头 {[x[1] for x in tt][:1]};普通 connect + send:{[round(x) for x in nt]} ms')

print('== 六:这个机制会“用完”:127.0.0.1 与 ::1 是前面的实验(本会话较早的运行)用过的目的地。现在对它们各做 5 次 connectx(服务端开 TFO),SYN 里带数据的有几个')
for host in ('127.0.0.1', '::1'):
    port = lab_port(); th, got = server(host, port, True, 5)
    with Cap(f'{"ip6 and " if ":" in host else ""}tcp port {port}', iface='lo0', write=True, snaplen=128) as c:
        for i in range(5): client(host, port, b'hello').close(); time.sleep(0.2)
        th.join(); time.sleep(0.3)
    sy = syns(dd(tcp_pkts(c.pcap)), port)
    print(f'  {host:<10}:5 个 SYN 的载荷 {[p["plen"] for p in sy]};TFO 选项长度 {[topt(p) for p in sy]}')
