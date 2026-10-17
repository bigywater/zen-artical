import sys, os, re, struct, collections, threading, select, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt, resource
resource.setrlimit(resource.RLIMIT_NOFILE, (65000, resource.getrlimit(resource.RLIMIT_NOFILE)[1]))
tee('w44'); reset()
def lq(port):
    for l in sysout('netstat', '-Lan').splitlines():
        p = l.split()
        if len(p) >= 2 and p[1].endswith(f'.{port}') and '/' in p[0]: return tuple(int(x) for x in p[0].split('/'))
def tcpstat():
    o = sysout('netstat', '-s', '-p', 'tcp'); d = {}
    for k_, pat in (('synrcv', r'(\d+) (?:connection requests|connections? accepted)'), ('cookie_sent', r'(\d+) SYN cookies? sent'), ('cookie_ok', r'(\d+) SYN cookies? received'), ('cookie_fail', r'(\d+) SYN cookies? failed'), ('drop_overflow', r'(\d+) listen queue overflow'), ('bad_syn', r'(\d+) .*dropped.*SYN'), ('syn_drop', r'(\d+) (?:SYN|syn)[^\n]*drop')):
        m = re.search(pat, o); d[k_] = int(m.group(1)) if m else None
    return o, d
def optd(o):
    d = {}; i = 0
    while i < len(o):
        k = o[i]
        if k == 0: break
        if k == 1: i += 1; continue
        l = o[i + 1]; v = o[i + 2:i + l]
        if k == 2: d['MSS'] = struct.unpack('>H', v)[0]
        elif k == 3: d['WScale'] = v[0]
        elif k == 4: d['SACK'] = 1
        elif k == 8: d['TS'] = 1
        i += l
    return d

print('== 一:本机与 SYN 洪水有关的内核参数和统计计数')
for k_ in ('net.inet.tcp.syncookie', 'net.inet.tcp.syncookie_hmac_sha256', 'net.inet.tcp.drop_synfin', 'kern.ipc.somaxconn'): print('  ' + sysout('sysctl', k_).strip())
o, d0 = tcpstat()
print('  netstat -s -p tcp 里和 SYN / cookie 有关的行:')
for l in o.splitlines():
    if re.search(r'cookie|listen queue|SYN', l, re.I) and 'TFO' not in l and 'ECN' not in l and 'AccECN' not in l: print('    ' + l.strip())

print('== 二:近似 SYN 洪水:没有原始套接字没法伪造源地址,用 netlab 把第三个 ACK 拖 800 ms,在不到 1 秒里发起 20000 个并发连接,服务端全部卡在 SYN_RCVD(半连接);看队列长度、抓 SYN-ACK 的选项有没有变化(syncache 满了会退化成 SYN cookie,SYN-ACK 里的选项会变少)')
p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen(128)
socks = []; samples = []
with lossy(loss=0, delay=400, bw=0):
    with Cap(f'tcp port {p} and tcp[tcpflags] & (tcp-syn|tcp-ack) = (tcp-syn|tcp-ack)', iface='lo0', write=True) as c:
        t0 = time.time()
        for i in range(20000):
            s = socket.socket(); s.setblocking(False); s.connect_ex(('127.0.0.1', p)); socks.append(s)
        tsend = time.time() - t0
        while time.time() - t0 < 3.0:
            q = lq(p); samples.append((time.time() - t0, q)); time.sleep(0.2)
        time.sleep(0.3)
print(f'  {tsend * 1000:.0f} ms 内发起了 20000 个 connect;netstat -L 的 qlen/incqlen/maxqlen 随时间:' + ';'.join(f'{t * 1000:.0f} ms {"/".join(map(str, q)) if q else "?"}' for t, q in samples[::2]))
sa = []
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        ip = bytes(buf[4:]); ihl = (ip[0] & 15) * 4; t = ip[ihl:]; sp, dp, seq, ack, off, fl = struct.unpack('>HHIIBB', t[:14])
        if sp == p and fl & 0x12 == 0x12: sa.append((ts, seq, ack, optd(t[20:(off >> 4) * 4]), (off >> 4) * 4))
byfirst = {}
sigs = collections.Counter(tuple(sorted(x[3].keys())) for x in sa)
print(f'  抓到服务端发出的 SYN-ACK {len(sa)} 个(去掉 dummynet 重复抓到的后按序号 / 确认号去重 {len({(x[1], x[2]) for x in sa})} 个不同的连接);SYN-ACK 选项组合:' + ';'.join(f'{"+".join(k_) or "无选项"} × {v}' for k_, v in sigs.most_common()))
dedup = {}
for x in sa: dedup.setdefault((x[1], x[2]), x)
ordered = sorted(dedup.values(), key=lambda x: x[0]); n = len(ordered)
firstk = [x for x in ordered[:128]]; restk = ordered[128:]
print(f'  按发出顺序:前 128 个 SYN-ACK 的选项组合 {dict(collections.Counter(tuple(sorted(x[3].keys())) for x in firstk))};之后的 {len(restk)} 个 {dict(collections.Counter(tuple(sorted(x[3].keys())) for x in restk))}')
ok = bad = 0
for s in socks:
    try:
        _, w, _ = select.select([], [s], [], 0)
        if w and s.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0: ok += 1
        else: bad += 1
    except Exception: bad += 1
print(f'  3 秒后客户端侧:连上 {ok} 个、没连上(仍在等或被拒){bad} 个;服务端全连接队列 {"/".join(map(str, lq(p)))}(maxqlen 128,所以最多 128 个连接会被保留)')
for s in socks: s.close()
ls.close()
o2, d1 = tcpstat()
print('  netstat -s -p tcp 里这段时间增加的 SYN / cookie 相关计数:' + (';'.join(f'{k_} +{d1[k_] - d0[k_]}' for k_ in d1 if d1[k_] is not None and d0[k_] is not None and d1[k_] != d0[k_]) or '没有变化'))
time.sleep(1.0)

print('== 三:SYN cookie 的原理(计算演示,不是本机内核的真实格式):服务端不为半连接保存任何状态,把必要信息编进 SYN-ACK 的序号里;收到第三个 ACK 时从确认号 − 1 反推并验证')
import hashlib, hmac
secret = b'demo-secret'
def cookie(saddr, sport, daddr, dport, client_isn, mss_idx, t):
    h = hmac.new(secret, struct.pack('>4sH4sHI', socket.inet_aton(saddr), sport, socket.inet_aton(daddr), dport, client_isn) + bytes([t & 31]), hashlib.sha256).digest()
    return ((t & 31) << 27) | (mss_idx << 24) | (int.from_bytes(h[:3], 'big'))
MSS = [536, 1220, 1440, 1460]
c0 = ('192.0.2.7', 40000, '198.51.100.1', 80); isn = 123456789; t = 7
ck = cookie(*c0, isn, 3, t)
print(f'  客户端 {c0[0]}:{c0[1]} → {c0[2]}:{c0[3]},客户端 ISN = {isn}:服务端把 SYN-ACK 的序号(ISN)算成 {ck}(= 时间戳低 5 位 {t} · MSS 索引 3(={MSS[3]})· 哈希 24 位),不保存任何状态')
ack_in = (ck + 1) & 0xffffffff
rc = (ack_in - 1) & 0xffffffff; t2 = rc >> 27; midx = (rc >> 24) & 7; ok_ = cookie(*c0, isn, midx, t2) == rc
print(f'  客户端回第三个 ACK,确认号 = {ack_in}:服务端用确认号 − 1 = {rc} 反推出 时间戳 {t2}、MSS 索引 {midx}(= {MSS[midx]}),重算哈希{"一致" if ok_ else "不一致"} → 接受连接;伪造的 ACK({isn + 1})的重算结果{"一致" if cookie(*c0, isn, 3, 7) == (isn + 1 - 1) else "不一致"}:攻击者没有密钥无法凑出正确的哈希')
print('  代价:没处存 SYN 里带来的其它选项(窗口缩放、SACK、时间戳都丢了,只能编进少量比特的 MSS),所以 cookie 只在队列快满时才启用')
print('  攻击面:SYN 洪水用伪造的源地址发大量 SYN,服务端为每个半连接保存状态直到超时(这里 SYN_RCVD 的状态),耗尽队列后正常客户端连不上;SYN cookie 让半连接不占内存')
