import sys, os, re, struct, collections, threading, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w38'); reset()
PUB = '104.20.23.154'
FL = [(0x20, 'URG'), (0x10, 'ACK'), (0x08, 'PSH'), (0x04, 'RST'), (0x02, 'SYN'), (0x01, 'FIN'), (0x40, 'ECE'), (0x80, 'CWR')]
def flags(f): return '+'.join(n for b, n in FL if f & b) or '无'
def tcps(path, lo=False):
    out = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            if lo: ip = bytes(buf[4:])
            else:
                e = dpkt.ethernet.Ethernet(buf)
                if e.type != 0x0800: continue
                ip = bytes(e.data)
            if ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:tl_]
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16])
            opts = t[20:(off >> 4) * 4]
            out.append(dict(ts=ts, sp=sp, dp=dp, seq=seq, ack=ack, fl=fl, win=win, plen=len(t) - (off >> 4) * 4, opts=opts, dst=socket.inet_ntoa(ip[16:20]), src=socket.inet_ntoa(ip[12:16])))
    return out
def optd(o):
    d = {}; i = 0
    while i < len(o):
        k = o[i]
        if k == 0: break
        if k == 1: i += 1; continue
        l = o[i + 1]; v = o[i + 2:i + l]
        if k == 2: d['MSS'] = struct.unpack('>H', v)[0]
        elif k == 3: d['WScale'] = v[0]
        elif k == 4: d['SACK'] = True
        elif k == 8: d['TS'] = True
        i += l
    return d

print('== 一:三次握手在线上:lo0 与 en0(example.com)各抓一次,看三个包的序号 / 确认号关系,以及 connect() 花的时间')
srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(); port = srv.getsockname()[1]
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    t0 = time.time(); k = socket.create_connection(('127.0.0.1', port)); tc = time.time() - t0; cn, _ = srv.accept(); k.close(); cn.close(); time.sleep(0.3)
P = tcps(c.pcap, lo=True)[:3]; cp = P[0]['sp']
for p, nm in zip(P, ('SYN', 'SYN-ACK', 'ACK')):
    print(f'  lo0 {nm}:{"客户端→服务端" if p["sp"] == cp else "服务端→客户端"},标志 {flags(p["fl"])},序号 {p["seq"]},确认号 {p["ack"]}')
print(f'  关系:服务端的确认号 {P[1]["ack"]} = 客户端 ISN {P[0]["seq"]} + 1:{P[1]["ack"] == P[0]["seq"] + 1};客户端最后的确认号 {P[2]["ack"]} = 服务端 ISN {P[1]["seq"]} + 1:{P[2]["ack"] == P[1]["seq"] + 1};第三个包的序号 {P[2]["seq"]} = 客户端 ISN + 1:{P[2]["seq"] == P[0]["seq"] + 1}')
print(f'  lo0 上 connect() 用时 {tc * 1e6:.0f} µs')
with Cap(f'tcp port 80 and host {PUB}', iface='en0', write=True) as c:
    t0 = time.time(); k = socket.create_connection((PUB, 80), timeout=5); tc2 = time.time() - t0; k.close(); time.sleep(0.4)
P = tcps(c.pcap)
syn = P[0]; sa = [p for p in P if p['fl'] & 0x12 == 0x12][0]
print(f'  en0 到 example.com:connect() 用时 {tc2 * 1000:.1f} ms;抓包里 SYN → SYN-ACK 间隔 {(sa["ts"] - syn["ts"]) * 1000:.1f} ms(就是一个往返),connect 返回时刻与收到 SYN-ACK 基本同时')

print('== 二:初始序号(ISN):连续建立 2000 个连接(lo0),看每个连接客户端 SYN 里的初始序号——是递增还是随机')
srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(4096); port = srv.getsockname()[1]
stop = threading.Event()
def acc():
    srv.settimeout(0.2)
    while not stop.is_set():
        try: cn, _ = srv.accept(); cn.close()
        except socket.timeout: pass
th = threading.Thread(target=acc); th.start()
with Cap(f'tcp port {port} and tcp[tcpflags] & (tcp-syn|tcp-ack) = tcp-syn', iface='lo0', write=True) as c:
    for i in range(2000):
        k = socket.socket(); k.connect(('127.0.0.1', port)); k.close()
    time.sleep(0.5)
stop.set(); th.join()
isn = [p['seq'] for p in tcps(c.pcap, lo=True) if p['fl'] == 0x02 or p['fl'] & 0x12 == 0x02]
d = [(b - a) % (1 << 32) for a, b in zip(isn, isn[1:])]
mono = sum(1 for x in d if x < 1 << 20)
print(f'  抓到 {len(isn)} 个 SYN,不同的 ISN {len(set(isn))} 个;范围 {min(isn)} ~ {max(isn)}(32 位空间 0 ~ {2 ** 32 - 1})')
print(f'  相邻两个连接的 ISN 之差(模 2^32)中,小于 2^20 的只有 {mono} 个(若是按时钟递增会几乎全部很小);均值 {statistics.mean(isn) / 2 ** 32:.3f}×2^32(均匀随机应接近 0.5);前 8 个 ISN:{isn[:8]}')
bins = collections.Counter(x * 16 // 2 ** 32 for x in isn); print(f'  把 32 位空间分 16 份,每份的个数:{[bins[i] for i in range(16)]}(均匀随机时每份约 {len(isn) // 16})')
print('  老系统用 4 微秒一次的时钟递增 ISN,容易被猜到后伪造连接(RFC 6528 要求加哈希随机化);这里看到的是随机分布')

print('== 三:SYN 没有回应时怎么重传:连接一个会丢弃 SYN 的地址(example.com 的 81 端口,防火墙丢弃),抓 25 秒,看 SYN 的发送时刻;以及内核参数')
for k_ in ('net.inet.tcp.keepinit', 'net.inet.tcp.always_keepalive', 'net.inet.tcp.syn_retries'):
    r = sysout('sysctl', k_).strip(); print('  ' + (r if 'unknown' not in r else f'({k_} 在本机不存在)'))
with Cap(f'tcp port 81 and host {PUB}', iface='en0', write=True) as c:
    t0 = time.time(); k = socket.socket(); k.settimeout(25)
    try: k.connect((PUB, 81)); r = '连上了'
    except Exception as e: r = f'{type(e).__name__}'
    dt = time.time() - t0; k.close(); time.sleep(0.4)
P = [p for p in tcps(c.pcap) if p['fl'] & 0x02 and not p['fl'] & 0x10]; t_first = P[0]['ts']
ts_ = [round(p['ts'] - t_first, 2) for p in P]
print(f'  25 秒的超时里 connect 结果 {r},用时 {dt:.1f} 秒;抓到 SYN {len(P)} 个,发送时刻(秒):{ts_}')
print(f'  相邻 SYN 的间隔:{[round(b - a, 2) for a, b in zip(ts_, ts_[1:])]}(固定 1 秒还是指数退避?{"几乎固定 1 秒" if len(ts_) > 2 and max(b - a for a, b in zip(ts_, ts_[1:])) < 1.3 else "逐步变长"});所有 SYN 的序号相同:{len({p["seq"] for p in P}) == 1};带 ECN 的 SYN {sum(1 for p in P if p["fl"] & 0xc0)} 个、不带的 {sum(1 for p in P if not p["fl"] & 0xc0)} 个')

print('== 四:握手顺便协商的参数:三个不同的服务器的 SYN-ACK 选项(MSS、窗口缩放、时间戳、SACK),对比本机的 SYN')
srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(); lport = srv.getsockname()[1]
res = []
for nm, ip_, p, iface in (('本机 lo0', '127.0.0.1', lport, 'lo0'), ('example.com', PUB, 80, 'en0'), ('另一个公网主机', '1.1.1.1', 80, 'en0')):
    with Cap(f'tcp port {p} and host {ip_}', iface=iface, write=True) as c:
        try: k = socket.create_connection((ip_, p), timeout=4); k.close()
        except Exception: pass
        time.sleep(0.4)
    P = tcps(c.pcap, lo=(iface == 'lo0')); syn = [x for x in P if x['fl'] & 0x12 == 0x02]; sa = [x for x in P if x['fl'] & 0x12 == 0x12]
    if syn and sa: print(f'  {nm}:我的 SYN 选项 {optd(syn[0]["opts"])};对方 SYN-ACK 选项 {optd(sa[0]["opts"])},窗口字段 {sa[0]["win"]},标志 {flags(sa[0]["fl"])}')
print('  双方各自在 SYN / SYN-ACK 里通告自己的 MSS、窗口缩放、是否支持时间戳和 SACK;只有双方都带了某个选项,这个功能才会启用(窗口缩放要求两边都带,否则都不启用)')

print('== 五:谁在什么时候“完成”:netlab 给 lo0 加 50 ms 单向延迟(往返 100 ms),分别记下客户端 connect() 返回、服务端 accept() 返回的时刻')
p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen(); res = {}
def acc2():
    cn, _ = ls.accept(); res['accept'] = time.time(); cn.close()
with lossy(loss=0, delay=50, bw=0):
    th = threading.Thread(target=acc2); th.start(); t0 = time.time(); k = socket.create_connection(('127.0.0.1', p)); tc = time.time() - t0; th.join(); ta = res['accept'] - t0; k.close()
print(f'  往返 100 ms:客户端 connect() 在 {tc * 1000:.0f} ms 时返回(1 个往返:SYN → SYN-ACK),服务端 accept() 在 {ta * 1000:.0f} ms 时返回(再过半个往返,等到客户端的第三个 ACK 到达)')
print('  所以客户端先认为连接建立,服务端后认为;如果第三个 ACK 丢了,客户端会以为已连接并开始发数据,服务端还在 SYN_RCVD(下一篇状态机再看)')
