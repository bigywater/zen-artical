import sys, os, re, struct, collections, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w52'); reset()
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

print('== 一:初始拥塞窗口:新连接建立后、发任何数据之前,读发送方 tcp_info 的 snd_cwnd(字节)和 MSS,算它是几个 MSS')
p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen(); k = socket.create_connection(('127.0.0.1', p)); cn, _ = ls.accept(); ti = tcp_info(cn)
print(f'  lo0:snd_cwnd = {ti["snd_cwnd"]} 字节,maxseg = {ti["maxseg"]} 字节 → 初始窗口 = {ti["snd_cwnd"] / ti["maxseg"]:.1f} 个 MSS;snd_ssthresh = {ti["snd_ssthresh"]}(慢启动阈值,初始近似无穷大)')
k2 = socket.create_connection(('104.20.23.154', 80), timeout=4); ti2 = tcp_info(k2)
print(f'  en0 到 example.com:snd_cwnd = {ti2["snd_cwnd"]} 字节,maxseg = {ti2["maxseg"]} 字节 → {ti2["snd_cwnd"] / ti2["maxseg"]:.1f} 个 MSS(RFC 6928 的初始窗口是 10 个 MSS)'); k2.close()

print('== 二:慢启动与拥塞避免:往返 100 ms(netlab 每个方向 50 ms)、0.3% 随机丢包的回环上传输 8 秒,每 10 ms 读一次发送方的 snd_cwnd / snd_ssthresh,看 cwnd 怎么增长、丢包后怎么变')
samples, n = run(50, 0.3, 8.0)
smp = [s for s in samples if s[0] > 0.05]
print(f'  传输 {n / 1e6:.1f} MB;一共采到 {len(samples)} 个样本;MSS = {samples[0][5]};srtt 稳定后约 {statistics.median(s[3] for s in samples[len(samples) // 2:])} ms')
MSS = samples[0][5]
print('    时间(秒)   cwnd(字节)   cwnd(个 MSS)   ssthresh(字节)   累计重传包')
for t_ in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0):
    s = min(samples, key=lambda x: abs(x[0] - t_)); print(f'    {s[0]:>7.2f}   {s[1]:>10}   {s[1] / MSS:>11.1f}   {s[2]:>14}   {s[4]:>8}')
first = [s for s in samples if s[0] <= 0.5]
print(f'  开头 0.5 秒(5 个 RTT):cwnd 依次约 ' + ' → '.join(f'{min(samples, key=lambda x: abs(x[0] - t_))[1] / MSS:.0f}' for t_ in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)) + ' 个 MSS——每个 RTT 翻倍,这就是指数增长的"慢启动"(名字起得不好)')

print('== 三:丢包以后:找出 cwnd 突然下降的时刻,看下降前后的 cwnd、新的 ssthresh,以及降多少(乘法减小系数 β = 降后 / 降前)')
ev = []
prev = samples[0]
for s in samples[1:]:
    if s[1] < prev[1] * 0.75 and prev[1] > 4 * MSS: ev.append((s[0], prev[1], s[1], s[2]))
    prev = s
# 合并相邻的下降
merged = []
for e in ev:
    if not merged or e[0] - merged[-1][0] > 0.15: merged.append(e)
print(f'  8 秒内检测到 {len(merged)} 次 cwnd 明显下降(下降到降前的 75% 以下):')
for t_, a, b, ss in merged[:8]: print(f'    {t_:>5.2f} 秒:cwnd {a} → {b} 字节({a / MSS:.0f} → {b / MSS:.0f} 个 MSS),降后 / 降前 = {b / a:.2f},此时 ssthresh = {ss}')
if merged: print(f'  降后 / 降前的中位数 {statistics.median(b / a for _, a, b, _ in merged):.2f}(Reno 是 0.5;CUBIC 是 0.7)——本机默认用的是{"CUBIC 的 0.7 附近" if statistics.median(b / a for _, a, b, _ in merged) > 0.6 else "Reno 的 0.5 附近"};net.inet.tcp.cubic_sockets 显示本机有 CUBIC 在用')
print(f'  ' + sysout('sysctl', 'net.inet.tcp.cubic_sockets').strip())

print('== 四:拥塞避免阶段 cwnd 的增长速度:挑一段没有丢包的时间,拟合 cwnd 随时间的斜率,换算成“每个 RTT 增加多少个 MSS”(Reno 约 1 个;CUBIC 开始时更快)')
seg = []
cur = []
for s in samples:
    if cur and s[1] < cur[-1][1] * 0.9: seg.append(cur); cur = []
    cur.append(s)
seg.append(cur)
seg = [x for x in seg if len(x) > 40 and x[-1][0] - x[0][0] > 0.8]
for x in seg[:4]:
    # 取后 70%(避开慢启动)
    y = x[len(x) // 3:]
    if len(y) < 10: continue
    t = [s[0] for s in y]; c_ = [s[1] for s in y]
    mt = statistics.mean(t); mc = statistics.mean(c_)
    slope = sum((a - mt) * (b - mc) for a, b in zip(t, c_)) / max(1e-9, sum((a - mt) ** 2 for a in t))
    rtt = 0.1
    print(f'  {x[0][0]:.1f}~{x[-1][0]:.1f} 秒这一段:cwnd 从 {y[0][1] / MSS:.0f} 个 MSS 变到 {y[-1][1] / MSS:.0f} 个 MSS;斜率 {slope / MSS:.1f} 个 MSS/秒 = 每个 RTT(100 ms)增加约 {slope * rtt / MSS:.1f} 个 MSS')
if not seg: print('  没有足够长的无丢包区间')
print('  慢启动:cwnd 每个 RTT 翻倍,直到遇到 ssthresh 或丢包;拥塞避免:每个 RTT 只增加约 1 个 MSS(线性增长),CUBIC 则按三次函数曲线增长;丢包后乘性减小(cwnd 降到 β × cwnd,并把 ssthresh 设成同样的值)——AIMD')
