import sys, os, re, struct, threading, statistics, errno, random; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w62'); reset()
LOSS = 3; DELAY = 50; N = 500; GAP = 0.01; MSG = 1000
def pct(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(len(xs) * p))]
def run_tcp(streams):
    ps = [lab_port() for _ in range(streams)]; lss = []; ks = []; cns = []
    for p in ps:
        ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen(); lss.append(ls)
    for p, ls in zip(ps, lss):
        k = socket.socket(); k.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1); k.connect(('127.0.0.1', p)); cn, _ = ls.accept(); ks.append(k); cns.append(cn)
    rx = {}; t0 = time.time() + 0.3
    def reader(cn):
        cn.settimeout(15); buf = b''
        try:
            while True:
                d = cn.recv(65536)
                if not d: break
                buf += d
                while len(buf) >= MSG:
                    m, buf = buf[:MSG], buf[MSG:]; seq, ts = struct.unpack('!Id', m[:12]); rx[seq] = (ts, time.time())
        except Exception: pass
    ths = [threading.Thread(target=reader, args=(cn,)) for cn in cns]
    for th in ths: th.start()
    time.sleep(0.3)
    for i in range(N):
        tgt = t0 + i * GAP
        while time.time() < tgt: time.sleep(0.0005)
        ks[i % streams].sendall(struct.pack('!Id', i, time.time()) + b'x' * (MSG - 12))
    time.sleep(6)
    for k in ks: k.close()
    for th in ths: th.join()
    for ls in lss: ls.close()
    return rx, t0
def run_udp():
    p = lab_port(); r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r.bind(('127.0.0.1', p)); r.settimeout(0.5); s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx = {}; stop = [False]
    def rd():
        while not stop[0]:
            try: m, _ = r.recvfrom(2000)
            except socket.timeout: continue
            seq, ts = struct.unpack('!Id', m[:12]); rx[seq] = (ts, time.time())
    th = threading.Thread(target=rd); th.start(); t0 = time.time() + 0.3
    for i in range(N):
        tgt = t0 + i * GAP
        while time.time() < tgt: time.sleep(0.0005)
        s.sendto(struct.pack('!Id', i, time.time()) + b'x' * (MSG - 12), ('127.0.0.1', p))
    time.sleep(2); stop[0] = True; th.join(); r.close(); s.close(); return rx, t0

def stats(rx):
    lat = [(r[1] - r[0]) * 1000 for r in rx.values()]
    return dict(n=len(rx), p50=statistics.median(lat), p90=pct(lat, 0.9), p99=pct(lat, 0.99), mx=max(lat), delayed=sum(1 for x in lat if x > 80), lat=lat)

print(f'== 一:实验设置:每 {GAP * 1000:.0f} ms 发一条 {MSG} 字节的消息(带序号和发送时刻),共 {N} 条;lo0 上 netlab 每个方向延迟 {DELAY} ms(单程 ≈ {DELAY} ms)、丢包 {LOSS}%(每个方向,所以数据和 ACK 都可能丢)。消息延迟 = 接收方应用读到这条消息的时刻 − 发送方写它的时刻。每种配置跑 3 次汇总')
configs = [('UDP(无重传)', None), ('TCP 1 条连接', 1), ('TCP 4 条连接轮流发', 4), ('TCP 16 条连接轮流发', 16)]
agg = {}; samples = {}
with lossy(loss=LOSS, delay=DELAY, bw=0):
    for nm, st in configs:
        allrx = []
        for rep in range(3):
            rx, t0 = run_udp() if st is None else run_tcp(st)
            allrx.append((rx, t0))
        agg[nm] = allrx
print('== 二:消息延迟的分布(每种配置 3 次共 1500 条消息)')
print('    配置                    收到     丢失     p50(ms)   p90(ms)   p99(ms)   最大(ms)   延迟 > 80 ms 的消息')
tot = {}
for nm, st in configs:
    lat = []; got = 0
    for rx, t0 in agg[nm]:
        s_ = stats(rx); lat += s_['lat']; got += s_['n']
    tot[nm] = (got, lat)
    print(f'    {nm:<22} {got:>5}   {3 * N - got:>5}    {statistics.median(lat):>7.1f}   {pct(lat, 0.9):>7.1f}   {pct(lat, 0.99):>7.1f}   {max(lat):>8.1f}   {sum(1 for x in lat if x > 80):>5}({sum(1 for x in lat if x > 80) / got * 100:.1f}%)')
print(f'  理论:单程 {DELAY} ms;TCP 丢一个包后要等快速重传(约 1~2 个 RTT 以上)或 RTO(lo0 下限 ≈ 230 ms)才能补上,所有排在它后面的消息都被迫等待')

print('== 三:一次“队头阻塞”的样子:TCP 单连接第 1 次运行里,第一条延迟超过 80 ms 的消息及其后面 12 条,发送时刻与应用收到时刻(相对测试开始,ms)')
rx, t0 = agg['TCP 1 条连接'][0]
seqs = sorted(rx); first = next(s for s in seqs if (rx[s][1] - rx[s][0]) * 1000 > 80)
print('    序号   发送时刻   应用收到时刻   延迟')
for s in range(first - 2, first + 12):
    if s in rx: print(f'    {s:>4}   {(rx[s][0] - t0) * 1000:8.0f}   {(rx[s][1] - t0) * 1000:12.0f}   {(rx[s][1] - rx[s][0]) * 1000:6.0f} ms')
    else: print(f'    {s:>4}   (没收到)')
blk = [s for s in range(first, first + 40) if s in rx and (rx[s][1] - rx[s][0]) * 1000 > 80]
tt = sorted(round((rx[s][1] - t0) * 1000) for s in blk)
print(f'  从序号 {first} 起这一段里延迟 > 80 ms 的消息有 {len(blk)} 条,它们被应用收到的时刻集中在 {tt[0]}~{tt[-1]} ms 的 {tt[-1] - tt[0]} ms 之内——被丢的那个包补上之后,一口气释放')

print('== 四:一次丢包拖住几条消息?以 TCP 单连接为例,把“延迟 > 80 ms”的消息按序号连成一段,每段(一次队头阻塞事件)的长度和最大延迟')
runs = []
for rx, t0 in agg['TCP 1 条连接']:
    seqs = sorted(rx); cur = []
    for s in seqs:
        if (rx[s][1] - rx[s][0]) * 1000 > 80: cur.append(s)
        else:
            if cur: runs.append((len(cur), max((rx[x][1] - rx[x][0]) * 1000 for x in cur))); cur = []
    if cur: runs.append((len(cur), max((rx[x][1] - rx[x][0]) * 1000 for x in cur)))
print(f'  3 次共 {len(runs)} 次队头阻塞事件;每次拖住的消息数:中位 {statistics.median([r[0] for r in runs]):.0f},最大 {max(r[0] for r in runs)};每次事件里的最大延迟:中位 {statistics.median([r[1] for r in runs]):.0f} ms,最大 {max(r[1] for r in runs):.0f} ms')
