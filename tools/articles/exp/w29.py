import sys, os, re, struct, collections, statistics, threading, random, heapq; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w29'); reset()
def pace(gap):
    t1 = time.time() + gap
    while time.time() < t1: pass
def collector(sock, stop, out):
    sock.settimeout(0.05)
    while not stop.is_set():
        try: d, _ = sock.recvfrom(4000)
        except socket.timeout: continue
        except OSError: break
        out.append((time.time(), d))
def runs(lost):
    """丢失序号集合 → 连续丢失段的长度列表"""
    L = sorted(lost); r = []; i = 0
    while i < len(L):
        j = i
        while j + 1 < len(L) and L[j + 1] == L[j] + 1: j += 1
        r.append(j - i + 1); i = j + 1
    return r

print('== 一:用 netlab 在 lo0 上造随机丢包,发 2000 个带序号的 UDP 数据报(每 0.5 ms 一个),看接收方的丢失率和连续丢失的长度分布')
N = 2000
for lossp in (5, 20):
    p = lab_port(); r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('127.0.0.1', p)); r.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
    stop = threading.Event(); got = []; th = threading.Thread(target=collector, args=(r, stop, got)); th.start()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    with lossy(loss=lossp, delay=0, bw=0):
        for i in range(N): s.sendto(struct.pack('>I', i) + b'x' * 96, ('127.0.0.1', p)); pace(0.0005)
        time.sleep(0.5)
    stop.set(); th.join(); r.close()
    seqs = [struct.unpack('>I', d[:4])[0] for _, d in got]; lost = set(range(N)) - set(seqs); rl = runs(lost); cnt = collections.Counter(rl)
    print(f'  设置丢包 {lossp}%:发 {N} 个,收到 {len(seqs)} 个({len(set(seqs))} 个不同序号),丢失 {len(lost)} 个 = {len(lost) / N * 100:.1f}%;连续丢失的段 {len(rl)} 段,最长 {max(rl) if rl else 0};长度分布 ' + ','.join(f'{k_}个连丢×{v}' for k_, v in sorted(cnt.items())) + f';收到的序号是否严格递增:{seqs == sorted(seqs)}')
print('  netlab 的丢包是独立随机丢的(没有突发),所以连续丢失的段大多长度为 1;真实的无线 / 拥塞丢包往往是成串的')

print('== 二:限速的管道:netlab 给 lo0 加 50 ms 单向延迟 + 500 Kbit/s 带宽(队列最多 100 个包),一次性突发 1000 个 1000 字节的数据报 vs 按 400 Kbit/s 慢慢发 100 个,看丢失和延迟')
def bw_run(count, size, gap, bw=500, delay=50):
    p = lab_port(); r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('127.0.0.1', p)); r.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
    stop = threading.Event(); got = []; th = threading.Thread(target=collector, args=(r, stop, got)); th.start()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
    with lossy(loss=0, delay=delay, bw=bw):
        t0 = time.time()
        for i in range(count):
            s.sendto(struct.pack('>Id', i, time.time()) + b'x' * (size - 12), ('127.0.0.1', p))
            if gap: pace(gap)
        sent_dt = time.time() - t0; time.sleep(3 if gap == 0 else 1.5)
    stop.set(); th.join(); r.close()
    lat = [(ta - struct.unpack('>Id', d[:12])[1]) * 1000 for ta, d in got]
    return sent_dt, len(got), lat, [struct.unpack('>I', d[:4])[0] for _, d in got]
sd, n, lat, sq = bw_run(1000, 1000, 0)
print(f'  突发:{sd * 1000:.0f} ms 内发完 1000 个(约 {1000 * 1000 * 8 / sd / 1e6:.0f} Mbit/s 的速度),收到 {n} 个,丢失 {1000 - n} 个;收到的延迟 最小 {min(lat):.0f} / 中位 {statistics.median(lat):.0f} / 最大 {max(lat):.0f} ms;收到的序号范围 {min(sq)}~{max(sq)}')
sd, n, lat, sq = bw_run(100, 1000, 0.02)
print(f'  慢发(每 20 ms 一个 1000 字节 = 400 Kbit/s,低于 500 Kbit/s 的管道):{sd:.1f} s 发完 100 个,收到 {n} 个,丢失 {100 - n} 个;延迟 最小 {min(lat):.0f} / 中位 {statistics.median(lat):.0f} / 最大 {max(lat):.0f} ms(50 ms 延迟 + 1000 字节在 500 Kbit/s 上的发送时间 16 ms)')
print('  超过管道带宽的突发会在队列里排队,队满以后后面的包直接丢弃(尾部丢弃),队里的包延迟也大幅增加;UDP 自己不会降速')

print('== 三:乱序与重复:回环上不会自己乱序也不会重复,所以写一个用户态 UDP 中继人为制造(每个包随机多等 0~30 ms,2% 概率复制一份),再用接收端的序号算法检测,与中继的真实记录对比。这一节是模拟,不是网络上的真实现象')
class Relay:
    def __init__(self, dst, dup=0.02, maxd=0.03, seed=3):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); self.s.bind(('127.0.0.1', 0)); self.port = self.s.getsockname()[1]; self.dst = dst
        self.rng = random.Random(seed); self.dup = dup; self.maxd = maxd; self.q = []; self.stop = threading.Event(); self.log = []; self.dups = 0; self.out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.settimeout(0.002); self.n = 0
        self.th = threading.Thread(target=self.run); self.th.start()
    def run(self):
        self.s.setblocking(False)
        while not self.stop.is_set() or self.q:
            while True:
                try: d, _ = self.s.recvfrom(4000)
                except BlockingIOError: break
                for k_ in range(2 if self.rng.random() < self.dup else 1):
                    heapq.heappush(self.q, (time.time() + self.rng.random() * self.maxd, self.n, d)); self.n += 1
                    if k_: self.dups += 1
            now = time.time()
            while self.q and self.q[0][0] <= now:
                _, _, d = heapq.heappop(self.q); self.out.sendto(d, self.dst); self.log.append(struct.unpack('>I', d[:4])[0])
            time.sleep(0.0002)
def detect(seqs):
    seen = set(); mx = -1; reord = dup = 0; maxdist = 0
    for q in seqs:
        if q in seen: dup += 1; continue
        seen.add(q)
        if q < mx: reord += 1; maxdist = max(maxdist, mx - q)
        else: mx = q
    return reord, dup, maxdist
r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('127.0.0.1', 0)); r.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
stop = threading.Event(); got = []; th = threading.Thread(target=collector, args=(r, stop, got)); th.start()
rl_ = Relay(r.getsockname()); s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for i in range(N): s.sendto(struct.pack('>I', i) + b'x' * 96, ('127.0.0.1', rl_.port)); time.sleep(0.001)
time.sleep(0.2); rl_.stop.set(); rl_.th.join(); time.sleep(0.3); stop.set(); th.join()
seqs = [struct.unpack('>I', d[:4])[0] for _, d in got]
dr, dd, dm = detect(seqs); tr, td, tm = detect(rl_.log)
print(f'  发 {N} 个;中继复制了 {rl_.dups} 份;接收端收到 {len(seqs)} 个(不同序号 {len(set(seqs))} 个,丢失 {N - len(set(seqs))} 个)')
print(f'  接收端检测:乱序(比已见到的最大序号小的新序号){dr} 个,重复 {dd} 个,最大“落后”距离 {dm};中继发出顺序里的真实值:乱序 {tr}、重复 {td}、最大落后 {tm};两者{"一致" if (dr, dd, dm) == (tr, td, tm) else "不一致"}')
print(f'  乱序占 {dr / len(set(seqs)) * 100:.1f}%——随机延迟 0~30 ms、每 1 ms 一个包,所以相邻的包经常互换位置')

print('== 四:真实互联网上的 UDP:向公共 DNS 服务器连发 300 个 UDP 查询(example.com 的 A 记录,每个不同的事务编号),按“慢发(每 20 ms 一个)”和“突发(一口气发完)”两种方式,统计应答的丢失、重复、乱序')
def dns_q(tid): return struct.pack('>HHHHHH', tid, 0x0100, 1, 0, 0, 0) + b'\x07example\x03com\x00\x00\x01\x00\x01'
def dns_test(server, n, gap):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20); s.settimeout(0.05)
    order = []; t0 = time.time(); base = random.randint(1000, 30000)
    for i in range(n):
        s.sendto(dns_q(base + i), (server, 53))
        if gap: pace(gap)
        while True:
            try: d, _ = s.recvfrom(4000); order.append(struct.unpack('>H', d[:2])[0] - base)
            except socket.timeout: break
            except BlockingIOError: break
    t1 = time.time()
    while time.time() - t1 < 3:
        try: d, _ = s.recvfrom(4000); order.append(struct.unpack('>H', d[:2])[0] - base)
        except socket.timeout: pass
    got = [x for x in order if 0 <= x < n]; uniq = set(got)
    reord, dup, md = detect(got)
    return n, len(uniq), dup, reord, md
for srv in ('1.1.1.1', '8.8.8.8'):
    for nm, gap in (('慢发 每 20 ms 一个', 0.02), ('突发 不留间隔', 0)):
        n, u, d, ro, md = dns_test(srv, 300, gap)
        print(f'  公共 DNS {"A" if srv == "1.1.1.1" else "B"},{nm}:发 {n} 个,收到 {u} 个不同的应答,丢失 {n - u} 个({(n - u) / n * 100:.1f}%),重复 {d} 个,乱序 {ro} 个' + (f'(最大落后 {md})' if ro else ''))

print('== 五:想靠 UDP 可靠传输要自己做:最简单的“停等”协议(发一个等 ACK,30 ms 没回就重发),在 netlab 丢包(每个方向各丢 p%)下传 200 个数据报,看重发次数和总时间,与 1/(1−p)² 的理论值比较')
def stopwait(lossp, n=200, to=0.03):
    ps = lab_port(); pc = lab_port()
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); srv.bind(('127.0.0.1', ps)); srv.settimeout(0.05); st = threading.Event(); recv = set()
    def run():
        while not st.is_set():
            try: d, a = srv.recvfrom(4000)
            except socket.timeout: continue
            recv.add(struct.unpack('>I', d[:4])[0]); srv.sendto(d[:4], a)
    th = threading.Thread(target=run); th.start()
    c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); c.bind(('127.0.0.1', pc)); c.settimeout(to)
    sends = 0
    with lossy(loss=lossp, delay=0, bw=0):
        t0 = time.time()
        for i in range(n):
            while True:
                c.sendto(struct.pack('>I', i) + b'd' * 96, ('127.0.0.1', ps)); sends += 1
                try:
                    a, _ = c.recvfrom(100)
                    if struct.unpack('>I', a)[0] == i: break
                except socket.timeout: pass
        dt = time.time() - t0
    st.set(); th.join(); return sends, dt, len(recv)
for lp in (0, 5, 20, 40):
    sn, dt, nr = stopwait(lp)
    exp_ = 200 / ((1 - lp / 100) ** 2)
    print(f'  每个方向丢 {lp}%:发了 {sn} 次(200 个数据报,重发 {sn - 200} 次),服务端收到 {nr} 个不同序号,总用时 {dt:.2f} s;理论平均发送次数 200/(1−{lp / 100})² = {exp_:.0f} 次(计算值)')
