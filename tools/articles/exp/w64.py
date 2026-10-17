import sys, os, re, struct, threading, statistics, errno, math; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w64'); reset()
MSS = 16332
def run(loss, delay, secs=8.0, win=(2.0, 7.5)):
    p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen()
    k = socket.socket(); k.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4194304); k.connect(('127.0.0.1', p)); cn, _ = ls.accept()
    stop = [False]
    def snd():
        d = b'x' * 262144
        try:
            while not stop[0]: cn.send(d)
        except OSError: pass
    th = threading.Thread(target=snd); th.start(); t0 = time.time(); k.settimeout(1); got = 0; marks = {}; info = None
    while time.time() - t0 < secs:
        try: d = k.recv(1 << 20)
        except socket.timeout: continue
        if not d: break
        got += len(d); now = time.time() - t0
        if 'a' not in marks and now >= win[0]: marks['a'] = (now, got)
        if 'b' not in marks and now >= win[1]: marks['b'] = (now, got)
    try: info = tcp_info(cn)
    except OSError: pass
    stop[0] = True; cn.close(); k.close(); ls.close(); th.join()
    if 'b' not in marks: marks['b'] = (time.time() - t0, got)
    return (marks['b'][1] - marks['a'][1]) / (marks['b'][0] - marks['a'][0]), info

LOSSES = (0, 0.1, 0.5, 1, 2, 5); DELAYS = (10, 50)
print('== 一:实验设置:lo0 上 netlab 加每方向延迟 10 ms / 50 ms(往返 20 ms / 100 ms)和单向随机丢包 0 / 0.1 / 0.5 / 1 / 2 / 5 %(丢包是每个方向各自独立地丢,所以数据包和 ACK 都会丢);接收缓冲区 4 MiB(窗口不是瓶颈),发送 8 秒,取第 2~7.5 秒的平均吞吐,每个组合做 2 次取平均。lo0 的 MSS 载荷 16332 字节')
res = {}
for d in DELAYS:
    for l in LOSSES:
        vals = []; infos = []
        with lossy(loss=l, delay=d, bw=0):
            for rep in range(2):
                thr, info = run(l, d); vals.append(thr); infos.append(info)
        res[(d, l)] = (vals, infos)
        print(f'  RTT {2 * d:>3} ms,丢包 {l:>3}%:吞吐 {statistics.mean(vals) / 1e6:7.2f} MB/s(两次 {vals[0] / 1e6:.2f} / {vals[1] / 1e6:.2f})', flush=True)
print('== 二:吞吐随丢包率下降的情况(每个 RTT 一张表,相对该 RTT 无丢包的吞吐)')
for d in DELAYS:
    base = statistics.mean(res[(d, 0)][0])
    print(f'  往返 {2 * d} ms(无丢包基线 {base / 1e6:.2f} MB/s):')
    print('    丢包率    吞吐(MB/s)    相对基线     Mathis 预测(MB/s)   实测 ÷ 预测')
    for l in LOSSES:
        t = statistics.mean(res[(d, l)][0])
        if l == 0: print(f'    {l:>5}%   {t / 1e6:10.2f}    {1.0:8.1%}            —                  —'); continue
        m = MSS * 1.22 / (2 * d / 1000 * math.sqrt(l / 100))
        print(f'    {l:>5}%   {t / 1e6:10.2f}    {t / base:8.1%}   {m / 1e6:14.2f}        {t / m:8.2f}')
print('  (Mathis 公式 吞吐 ≈ 1.22 × MSS ÷ (RTT × √p) 是计算值,p 取单向丢包率;实际丢包经过数据与 ACK 两个方向,公式只是个量级参考)')
print('== 三:RTT 的影响:同一个丢包率下,往返 20 ms 与 100 ms 的吞吐之比(RTT 比 = 5)')
for l in LOSSES[1:]:
    a = statistics.mean(res[(10, l)][0]); b = statistics.mean(res[(50, l)][0])
    print(f'  丢包 {l:>3}%:RTT 20 ms 吞吐 {a / 1e6:7.2f} MB/s,RTT 100 ms 吞吐 {b / 1e6:7.2f} MB/s,比值 {a / b:.1f}(公式预测 RTT 反比 = 5.0)')
print('== 四:丢包率每翻 N 倍,吞吐降多少?(公式预测吞吐 ∝ 1/√p:丢包率 ×4,吞吐 ÷2)')
for d in DELAYS:
    for l1, l2 in ((0.5, 2), (0.1, 0.5), (1, 5)):
        a = statistics.mean(res[(d, l1)][0]); b = statistics.mean(res[(d, l2)][0])
        print(f'  往返 {2 * d} ms:丢包 {l1}% → {l2}%(×{l2 / l1:g}):吞吐 ÷ {a / b:.2f}(公式预测 ÷ {math.sqrt(l2 / l1):.2f})')
print('== 五:重传占多少:发送方在最后一次读到的 tcp_info 里,重传字节 ÷ 发送字节(整个连接累计)')
print('    RTT(ms)   丢包率    重传字节占比     重传包数 / 发送包数')
for d in DELAYS:
    for l in LOSSES[1:]:
        ii = [i for i in res[(d, l)][1] if i]
        if not ii: continue
        i = ii[-1]; print(f'    {2 * d:>6}   {l:>5}%   {i["txretransmitbytes"] / i["txbytes"]:>10.2%}     {i["txretransmitpackets"]} / {i["txpackets"]}')
