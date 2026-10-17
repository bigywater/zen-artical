import sys, os, re, struct, threading, statistics, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w61'); reset()
BW_K = 100000; DELAY = 50; RTT = 0.1
bdp = BW_K * 1000 / 8 * RTT
print(f'== 一:带宽时延积(BDP)= 带宽 × 往返时间。本篇的测试链路:netlab 限速 {BW_K // 1000} Mbit/s、每方向延迟 {DELAY} ms(往返 {RTT * 1000:.0f} ms)')
print(f'  BDP = {BW_K * 1000 / 8:,.0f} 字节/秒 × {RTT} 秒 = {bdp:,.0f} 字节(约 {bdp / 1048576:.2f} MiB):要让管道始终是满的,发送方必须有这么多字节在路上,接收方的窗口至少要这么大')
for rcv in (65536, 262144, 524288, 1048576, 2097152, 4194304):
    print(f'  接收窗口 {rcv // 1024:>5} KiB → 吞吐上限 = 窗口 ÷ RTT = {rcv / RTT / 1e6:6.1f} MB/s({rcv / RTT * 8 / 1e6:6.1f} Mbit/s);链路上限 {BW_K / 8000:.1f} MB/s;取小者 {min(rcv / RTT, BW_K * 125) / 1e6:6.1f} MB/s(计算)')

def run(rcvbuf=None, sndbuf=None, secs=6.0, win=(2.0, 5.5)):
    """接收方(客户端)在 connect 之前设 SO_RCVBUF;发送方(accept 出来的)可设 SO_SNDBUF;返回窗口内吞吐、发送方的 tcp_info"""
    p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen()
    k = socket.socket()
    if rcvbuf: k.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
    rb_set = k.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
    k.connect(('127.0.0.1', p)); cn, _ = ls.accept()
    if sndbuf: cn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, sndbuf)
    sb_set = cn.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
    stop = [False]; got = [0]; marks = {}
    def snd():
        d = b'x' * 262144
        try:
            while not stop[0]: cn.send(d)
        except OSError: pass
    th = threading.Thread(target=snd); th.start(); t0 = time.time(); k.settimeout(1); info = None
    try:
        while time.time() - t0 < secs:
            try: d = k.recv(1 << 20)
            except socket.timeout: continue
            if not d: break
            got[0] += len(d); now = time.time() - t0
            if 'a' not in marks and now >= win[0]: marks['a'] = (now, got[0])
            if 'b' not in marks and now >= win[1]: marks['b'] = (now, got[0])
            if 'i' not in marks and now >= 4.0: marks['i'] = 1; info = tcp_info(cn)
    finally:
        stop[0] = True
    cn.close(); k.close(); ls.close(); th.join()
    thr = (marks['b'][1] - marks['a'][1]) / (marks['b'][0] - marks['a'][0])
    return thr, info, rb_set, sb_set

results = []
print('== 二:接收缓冲区(SO_RCVBUF,在 connect 之前设置)从小到大,吞吐怎么变化。每个设置传 6 秒,取第 2~5.5 秒的平均吞吐;同时读发送方在第 4 秒的 tcp_info(srtt = 平滑往返时间,cwnd,对端通告的窗口 snd_wnd)')
print('    SO_RCVBUF 设置值   读回值       吞吐          计算上限     srtt    cwnd        对端窗口 snd_wnd')
with lossy(loss=0, delay=DELAY, bw=BW_K):
    for rb in (65536, 262144, 524288, 1048576, 2097152, 4194304, None):
        thr, info, rb_set, sb_set = run(rcvbuf=rb)
        results.append((rb, thr, info, rb_set))
        nm = f'{rb // 1024} KiB' if rb else '不设置(自动调整)'
        lim = min(rb_set / RTT, BW_K * 125) / 1e6
        print(f'    {nm:<16} {rb_set // 1024:>6} KiB   {thr / 1e6:6.2f} MB/s   {lim:6.2f} MB/s   {info["srtt"]:>4} ms  {info["snd_cwnd"] // 1024:>6} KiB   {info["snd_wnd"] // 1024:>6} KiB')
print(f'  链路带宽上限 {BW_K / 8000:.1f} MB/s;BDP {bdp / 1024:.0f} KiB。接收缓冲区小于 BDP 时吞吐被窗口卡住;够大以后吞吐封顶在带宽上')

print('== 三:缓冲过大的代价:窗口远大于 BDP 时,多出来的字节排在链路的队列里,往返时间(srtt)变长——bufferbloat。上面的 srtt 列就是证据;这里再对照:无限速的纯延迟链路(只有 100 ms RTT,没有带宽限制)上,同样的缓冲区下 srtt 是多少')
with lossy(loss=0, delay=DELAY, bw=0):
    for rb in (262144, 4194304):
        thr, info, rb_set, sb_set = run(rcvbuf=rb)
        print(f'  无限速:SO_RCVBUF {rb // 1024} KiB → 吞吐 {thr / 1e6:6.2f} MB/s,srtt {info["srtt"]} ms,cwnd {info["snd_cwnd"] // 1024} KiB')

print('== 四:发送缓冲区(SO_SNDBUF)也会限制:接收缓冲区固定 4 MiB,发送方 accept 之后设置不同的 SO_SNDBUF')
print('    SO_SNDBUF 设置值   读回值       吞吐')
with lossy(loss=0, delay=DELAY, bw=BW_K):
    for sb in (65536, 262144, 1048576, 4194304):
        thr, info, rb_set, sb_set = run(rcvbuf=4194304, sndbuf=sb)
        print(f'    {sb // 1024:>6} KiB       {sb_set // 1024:>6} KiB   {thr / 1e6:6.2f} MB/s   (srtt {info["srtt"]} ms)')
