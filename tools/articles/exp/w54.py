import sys, os, re, struct, collections, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w54'); reset()
def pkts(path, port):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            ip = bytes(buf[4:])
            if ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); out.append(dict(ts=ts, c2s=(dp == port), seq=seq, ack=ack, fl=fl, plen=tl_ - ihl - (off >> 4) * 4))
    return out
def pair():
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(); return ls, ls.getsockname()[1]

print('== 一:延迟 ACK:接收方收到数据后不一定马上回 ACK,等一小会儿看有没有数据可以捎带,或者攒够 2 个包再回。内核参数:')
for k_ in ('net.inet.tcp.delayed_ack', 'net.inet.tcp.sendmoreacks'): print('  ' + sysout('sysctl', k_).strip())
print('  delayed_ack: 0 = 关(每个包都立刻 ACK);1 = 总是延迟;2 = 每两个包 ACK 一次;3 = 自适应(检测到对端是 Nagle / 交互流量时变成立刻 ACK)')
print('  实测:客户端发 1 个 100 字节的包,服务端不回数据,量服务端什么时候发出纯 ACK(10 次)')
d1 = []
ls, port = pair(); k = socket.create_connection(('127.0.0.1', port)); k.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1); cn, _ = ls.accept()
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    for i in range(10): k.sendall(b'x' * 100); time.sleep(0.5)
P = pkts(c.pcap, port); datas = [p for p in P if p['c2s'] and p['plen'] > 0]
for dp_ in datas:
    a = [p for p in P if not p['c2s'] and p['plen'] == 0 and p['fl'] & 0x10 and p['ack'] == dp_['seq'] + dp_['plen'] and p['ts'] > dp_['ts']]
    if a: d1.append((a[0]['ts'] - dp_['ts']) * 1000)
print(f'  一个孤立的小包之后,服务端纯 ACK 的延迟(ms):{[round(x, 1) for x in d1]};中位 {statistics.median(d1):.1f} ms,最大 {max(d1):.1f} ms')
d2 = []
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    for i in range(10): k.sendall(b'x' * 100); k.sendall(b'y' * 100); time.sleep(0.5)
P = pkts(c.pcap, port); datas = [p for p in P if p['c2s'] and p['plen'] > 0]
print(f'  对照:连续发 2 个小包(TCP_NODELAY,间隔几微秒)时,抓到 {len(datas)} 个数据段(共 10 轮);服务端回的纯 ACK 个数 {sum(1 for p in P if not p["c2s"] and p["plen"] == 0 and p["fl"] & 0x10)}——(数一数:几乎每个数据段都有一个纯 ACK,没有看到两个包合并成一个 ACK)')
cn.close(); k.close()

print('== 二:Nagle 算法 + 延迟 ACK 的经典冲突:客户端把一个请求分两次 write(先 10 字节的头,再 10 字节的体),服务端收到两部分后才应答。Nagle 打开时第二次 write 要等第一个包的 ACK;服务端的 ACK 又被延迟……测请求到应答的延迟,各 30 次')
def rtt_test(nodelay, split, n=30):
    ls, port = pair(); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept()
    if nodelay: k.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    def srv():
        for i in range(n):
            got = 0
            while got < 20: got += len(cn.recv(100))
            cn.sendall(b'R' * 10)
        cn.close()
    th = threading.Thread(target=srv); th.start(); ts = []
    for i in range(n):
        t0 = time.time()
        if split: k.sendall(b'H' * 10); k.sendall(b'B' * 10)
        else: k.sendall(b'H' * 10 + b'B' * 10)
        got = 0
        while got < 10: got += len(k.recv(100))
        ts.append((time.time() - t0) * 1000); time.sleep(0.05)
    th.join(); k.close(); return ts
rows = []
for nm, nd, sp_ in (('Nagle 开(默认),一次 write 20 字节', False, False), ('Nagle 开(默认),分两次 write', False, True), ('TCP_NODELAY,分两次 write', True, True)):
    ts = rtt_test(nd, sp_); rows.append((nm, ts)); print(f'  {nm:<30}:请求到应答 中位 {statistics.median(ts):.2f} ms / 最小 {min(ts):.2f} / 最大 {max(ts):.2f} ms')
print('  回环上三种写法都在 0.2 ms 左右,没有出现经典的 40 ms 级停顿:这台机器的 delayed_ack=3(自适应),回环上收到小包后立刻回 ACK,Nagle 不用等;经典冲突在这里没有复现')

print('== 三:抓一次"Nagle 开 + 分两次 write"的包时间线,看第二个 write 的数据什么时候才真正发出')
ls, port = pair(); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept(); res = {}
def srv2():
    got = 0
    while got < 20: got += len(cn.recv(100))
    cn.sendall(b'R' * 10)
th = threading.Thread(target=srv2)
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    th.start(); t0 = time.time(); k.sendall(b'H' * 10); k.sendall(b'B' * 10); got = 0
    while got < 10: got += len(k.recv(100))
    res['t'] = time.time() - t0; th.join(); time.sleep(0.3)
P = [p for p in pkts(c.pcap, port) if p['plen'] > 0 or p['fl'] & 0x10]
P = [p for p in P if p['ts'] >= P[0]['ts']]
base = [p for p in P if p['plen'] > 0][0]['ts']
print(f'  从第一个 write 到收到应答共 {res["t"] * 1000:.2f} ms。线上(相对第一个数据包的时间):')
for p in P:
    if p['ts'] >= base - 0.001: print(f'    +{(p["ts"] - base) * 1000:7.2f} ms  {"客户端→服务端" if p["c2s"] else "服务端→客户端"}  载荷 {p["plen"]:>2} 字节  {"纯 ACK" if p["plen"] == 0 else ""}')
print('  第二个 write 的 10 字节是在第一个包的 ACK 回来之后才发出的(Nagle:有未确认的小包时,新的小数据先攒着等 ACK);回环上 ACK 几十微秒就回来,所以感觉不到')

print('== 四:真实网络上 Nagle 的代价:往 example.com:80 发一个 HTTP 请求,分成两次 write(请求行+Host 一次,Connection 头和空行一次),服务器要收到完整请求才响应。Nagle 开时第二次 write 要等第一个包的 ACK(多一个 RTT);TCP_NODELAY 两个包连着发。各 8 次交替,量"第一次 write 到收到响应第一批字节"')
def http_two_writes(nodelay):
    t0 = time.time(); k = socket.create_connection(('104.20.23.154', 80), timeout=6)
    if nodelay: k.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    conn_t = time.time() - t0; t1 = time.time()
    k.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\n'); k.sendall(b'Connection: close\r\n\r\n')
    try: d = k.recv(100); ok = d.startswith(b'HTTP')
    except Exception: ok = False
    dt = time.time() - t1; k.close(); return conn_t * 1000, dt * 1000, ok
rr = {False: [], True: []}; conns = []
for i in range(8):
    for nd in (False, True):
        try: c_, d_, ok = http_two_writes(nd)
        except Exception: continue
        if ok: rr[nd].append(d_); conns.append(c_)
        time.sleep(0.3)
rtt = statistics.median(conns)
print(f'  握手耗时(≈ 一个 RTT)中位 {rtt:.0f} ms')
for nd in (False, True):
    L = rr[nd]
    print(f'  {"TCP_NODELAY" if nd else "Nagle 开(默认)"}:{len(L)} 次有效,第一次 write 到响应第一批字节 中位 {statistics.median(L):.0f} ms(最小 {min(L):.0f} / 最大 {max(L):.0f})')
dn = statistics.median(rr[False]) - statistics.median(rr[True])
print(f'  两者之差的中位数 {dn:.0f} ms,约 {dn / rtt:.1f} 个握手耗时')

print('== 五:本机在真实网卡上怎么回 ACK:抓一次对 example.com 的 HTTP 请求,量本机对服务器每个数据包回纯 ACK 的延迟')
with Cap('tcp port 80 and host 104.20.23.154', iface='en0', write=True) as c:
    k = socket.create_connection(('104.20.23.154', 80), timeout=6); k.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n'); k.settimeout(4)
    try:
        while k.recv(65536): pass
    except Exception: pass
    k.close(); time.sleep(0.5)
rows_ = []
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        e = dpkt.ethernet.Ethernet(buf)
        if e.type != 0x0800: continue
        ip = bytes(e.data); ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]
        sp, dp, seq, ack, off, fl = struct.unpack('>HHIIBB', t[:14]); rows_.append((ts, sp == 80, seq, ack, fl, tl_ - ihl - (off >> 4) * 4))
dl = []
for ts, srv, seq, ack, fl, plen in rows_:
    if srv and plen > 0:
        a = [r for r in rows_ if not r[1] and r[5] == 0 and r[4] & 0x10 and r[3] == seq + plen and r[0] > ts]
        if a: dl.append((plen, (a[0][0] - ts) * 1000))
    elif srv and fl & 0x01: pass
print(f'  服务器发来 {sum(1 for r in rows_ if r[1] and r[5] > 0)} 个数据包,其中 {len(dl)} 个找到了对应的本机纯 ACK:' + ';'.join(f'{pl} 字节 → {d:.1f} ms' for pl, d in dl))

print('== 六:Nagle 对大量小写入的影响:连续 write 20000 次 100 字节,Nagle 开 vs TCP_NODELAY,数线上的数据段个数(lo0)')
for nm, nd in (('Nagle 开(默认)', False), ('TCP_NODELAY', True)):
    ls, port = pair(); k = socket.create_connection(('127.0.0.1', port)); cn, _ = ls.accept()
    if nd: k.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    def drain():
        n = 0
        while n < 2000000:
            d = cn.recv(1 << 20)
            if not d: break
            n += len(d)
    th = threading.Thread(target=drain); th.start()
    with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
        t0 = time.time()
        for i in range(20000): k.sendall(b'z' * 100)
        th.join(); dt = time.time() - t0; time.sleep(0.4)
    P = pkts(c.pcap, port); data = [p for p in P if p['c2s'] and p['plen'] > 0]
    print(f'  {nm}:20000 次 write(共 2,000,000 字节)用时 {dt:.2f} 秒;线上数据段 {len(data)} 个,平均每段 {2000000 / max(1, sum(1 for _ in data)):.0f} 字节;纯 ACK {sum(1 for p in P if not p["c2s"] and p["plen"] == 0)} 个')
    k.close(); cn.close()
print('  Nagle 把小写入合并成大段,包数少得多;代价是交互式小消息可能被推迟。TCP_NODELAY 适合"请求-应答"和低延迟场景,Nagle 适合不关心单个包延迟的批量小写入')
