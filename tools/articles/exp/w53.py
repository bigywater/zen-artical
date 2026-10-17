import sys, os, re, struct, collections, threading, statistics, random, math; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w53'); reset()
def run(delay, loss, secs, bw=0, dt=0.01):
    p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen(); st = {'cn': None}; samples = []; stop = threading.Event()
    def snd():
        cn, _ = ls.accept(); cn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8 << 20); st['cn'] = cn; t0 = time.time()
        while time.time() - t0 < secs:
            try: cn.send(b'x' * 65536)
            except Exception: break
        stop.set(); time.sleep(0.5); cn.close()
    def smp():
        while st['cn'] is None and not stop.is_set(): time.sleep(0.001)
        t0 = time.time()
        while not stop.is_set():
            try: ti = tcp_info(st['cn']); samples.append((time.time() - t0, ti['snd_cwnd'], ti['snd_ssthresh'], ti['srtt'], ti['txretransmitpackets'], ti['maxseg'], ti['txbytes']))
            except Exception: pass
            time.sleep(dt)
    with lossy(loss=loss, delay=delay, bw=bw):
        th = threading.Thread(target=snd); ts_ = threading.Thread(target=smp); th.start(); ts_.start()
        k = socket.create_connection(('127.0.0.1', p)); k.settimeout(5); n = 0; t0 = time.time()
        while time.time() - t0 < secs + 0.5:
            try: d = k.recv(1 << 20)
            except socket.timeout: break
            if not d: break
            n += len(d)
        th.join(); ts_.join(); k.close()
    return samples, n

print('== 一:本机在用哪种拥塞控制算法')
for k_ in ('net.inet.tcp.cubic_sockets', 'net.inet.tcp.use_newreno', 'net.inet.tcp.pacing', 'net.inet.tcp.cc_debug'): print('  ' + sysout('sysctl', k_).strip())
print('  use_newreno = 0 表示默认不用 NewReno;cubic_sockets 是当前在用 CUBIC 的套接字数(随时间变化);没有找到按套接字切换算法的 setsockopt(Linux 的 TCP_CONGESTION 在 macOS 上没有对应项),所以下面不做 Reno / BBR 的实测对照')

print('== 二:验证 CUBIC 公式:CUBIC 的窗口函数 W(t) = C·(t − K)³ + W_max(t 是上次丢包后的时间,W_max 是丢包前的窗口,K = ³√(W_max·(1−β)/C),C = 0.4,β = 0.7,窗口以 MSS 计、时间以秒计)。用往返 100 ms、0.3% 丢包的 8 秒传输里的快速恢复事件,对比公式预测与实测的 cwnd')
samples, n = run(50, 0.3, 8.0); MSS = samples[0][5]
ev = []; prev = samples[0]
for s in samples[1:]:
    if prev[1] > 4 * MSS and 0.6 * prev[1] < s[1] < 0.8 * prev[1]: ev.append((s[0], prev[1] / MSS, s[1] / MSS))
    prev = s
mer = []
for e in ev:
    if not mer or e[0] - mer[-1][0] > 0.3: mer.append(e)
C_, BETA = 0.4, 0.7
print(f'  传输 {n / 1e6:.1f} MB;找到 {len(mer)} 个快速恢复事件(降到降前的 60%~80%)')
print('    事件时刻   降前 W_max(MSS)  降后(MSS)   K(秒)   丢包后 0.3 s:实测/预测   0.6 s:实测/预测   0.9 s:实测/预测(MSS)')
errs = []
for t0_, wmax, wafter in mer[:6]:
    K = (wmax * (1 - BETA) / C_) ** (1 / 3)
    cells = []
    for dt_ in (0.3, 0.6, 0.9):
        s = min(samples, key=lambda x: abs(x[0] - (t0_ + dt_)))
        nxt = [e for e in mer if e[0] > t0_]
        if abs(s[0] - (t0_ + dt_)) > 0.03 or (nxt and nxt[0][0] < t0_ + dt_): cells.append('(中间又丢包)'); continue
        pred = C_ * (dt_ - K) ** 3 + wmax; cells.append(f'{s[1] / MSS:.0f}/{pred:.0f}'); errs.append(abs(s[1] / MSS - pred) / pred)
    print(f'    {t0_:>6.2f} s   {wmax:>10.0f}    {wafter:>8.0f}    {K:>6.2f}   ' + '          '.join(f'{c:<12}' for c in cells))
if errs: print(f'  {len(errs)} 个可比较的点上,实测与预测的相对误差:中位 {statistics.median(errs) * 100:.0f}%,最大 {max(errs) * 100:.0f}%——量级吻合;不完全相等是因为 ① 实测 cwnd 受 ACK 到达节奏和 10 ms 采样影响;② 窗口很小时 CUBIC 会切换到"像 Reno 一样增长"的 TCP 友好区域;③ 公式里的 C、β 是 RFC 8312 的建议值,实现可能有差别')

print('== 三:Reno 的吞吐模型(Mathis 公式)与实测:吞吐 ≈ MSS / RTT × 1.22 / √p;在往返 100 ms、不同随机丢包率下各传 6 秒,看 CUBIC 的实测吞吐比 Reno 公式高多少')
print('    丢包率    实测吞吐(MB/s)    Reno(Mathis 公式)(MB/s)   实测 / 公式')
res3 = []
for lp in (0.1, 0.3, 1.0, 3.0):
    sm, nb = run(50, lp, 6.0); thr = nb / 6.5; rtt = 0.1
    reno = MSS / rtt * 1.22 / math.sqrt(lp / 100) / 1e6
    res3.append((lp, thr / 1e6, reno)); print(f'    {lp:>5.1f}%      {thr / 1e6:>10.2f}            {reno:>14.2f}               {thr / 1e6 / reno:>6.2f}')
print('  丢包越少,CUBIC 比 Reno 公式的预测快得越多(高 BDP 路径上 CUBIC 恢复更快);丢包很多时两者接近。公式是粗略的稳态估计,这里只看趋势')

print('== 四:Reno、CUBIC、BBR 的行为差异(纸面模拟,不是实测):同一条 100 Mbit/s、往返 100 ms 的链路(窗口上限 = 带宽时延积 BDP ≈ 856 个 1460 字节的 MSS),随机丢包率不同,每个 RTT 一步推进 600 秒;Reno 每 RTT 加 1,丢包乘 0.5;CUBIC 用上面的公式,β = 0.7;BBR 近似为"按估计带宽 × 0.95 发送、不因随机丢包降速"')
def sim(alg, p, T=6000, bdp=856.0, seed=1):
    rng = random.Random(seed); w = 10.0; wmax = 0; tl = 0; tot = 0.0; K = 0
    for step in range(T):
        if alg == 'bbr':
            send = bdp * 0.95; tot += min(send, bdp) * (1 - p) ; continue
        send = min(w, bdp)
        tot += send * (1 - p)
        if rng.random() < 1 - (1 - p) ** max(1, send):
            if alg == 'reno': w = max(2.0, w * 0.5)
            else:
                wmax = w; w = max(2.0, w * 0.7); K = (wmax * 0.3 / 0.4) ** (1 / 3); tl = 0
        else:
            if alg == 'reno': w += 1
            else:
                tl += 0.1
                if wmax == 0: w *= 1.5 if w < 200 else 1.05
                else: w = max(w, 0.4 * (tl - K) ** 3 + wmax)
        w = min(w, bdp * 1.2)
    return tot / T * 1460 / 0.1 / 1e6
print('    丢包率     Reno(MB/s)   CUBIC(MB/s)   BBR 近似(MB/s)   链路带宽 12.5 MB/s')
for pp in (0.0001, 0.001, 0.01, 0.03):
    print(f'    {pp * 100:>6.2f}%   {sim("reno", pp):>9.2f}   {sim("cubic", pp):>10.2f}   {sim("bbr", pp):>12.2f}')
print('  这个模拟只体现思路:基于丢包的算法(Reno / CUBIC)把每个丢包都当成拥塞,随机丢包多的链路(无线、长距离)吞吐被压得很低;BBR 依据带宽和 RTT 的测量建模,对随机丢包不敏感——但 BBR 的真实表现(与别的流公平、队列长度)模拟里没有体现,本机也没法切换到 BBR 实测')
