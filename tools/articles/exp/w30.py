import sys, os, re, struct, collections, statistics, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w30'); reset()
def udpstat():
    o = sysout('netstat', '-s', '-p', 'udp'); g = lambda pat: int(re.search(r'(\d+) ' + pat, o).group(1))
    return dict(rx=g('datagrams received'), full=g('dropped due to full socket buffers'), nosock=g('dropped due to no socket'), delivered=g('delivered'))
def sc(k_): return sysout('sysctl', k_).strip()
def pace(gap):
    t1 = time.time() + gap
    while time.time() < t1: pass
def mk(rcvbuf=None):
    r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if rcvbuf: r.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
    r.bind(('127.0.0.1', 0)); return r
def drain(r):
    r.setblocking(False); n = b = 0
    while True:
        try: d = r.recv(70000); n += 1; b += len(d)
        except BlockingIOError: return n, b

print('== 一:接收缓冲区有多大:系统默认值与上限(sysctl),以及 setsockopt(SO_RCVBUF) 之后 getsockopt 读回的值')
for k_ in ('net.inet.udp.recvspace', 'kern.ipc.maxsockbuf'): print('  ' + sc(k_))
r = mk(); print(f'  新建的 UDP 套接字 SO_RCVBUF 默认 = {r.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)} 字节')
maxb = int(sc('kern.ipc.maxsockbuf').split()[-1])
for want in (4096, 65536, 262144, 1 << 20, 4 << 20, 8 << 20, 16 << 20, 64 << 20):
    x = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: x.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, want); got = x.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF); res = f'读回 {got}'
    except OSError as e: res = f'失败:{e.strerror}'
    print(f'  设置 {want:>9}:{res}')

print('== 二:不读的接收方能攒多少个数据报:接收方不调用 recv,发送方突发 5000 个(大小分别为 100、1000、8000 字节),等 0.3 秒后再一次性读空,数队里有多少个;期间 netstat 的 Recv-Q 显示队列占了多少字节')
rows = []
for size in (100, 1000, 8000):
    r = mk(); port = r.getsockname()[1]; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
    st0 = udpstat(); errs = 0
    for i in range(5000):
        try: s.sendto(struct.pack('>I', i) + b'x' * (size - 4), ('127.0.0.1', port))
        except OSError: errs += 1
    time.sleep(0.3)
    rq = [l for l in sysout('netstat', '-an', '-p', 'udp').splitlines() if f'127.0.0.1.{port} ' in l]
    recvq = int(rq[0].split()[1]) if rq else None
    st1 = udpstat(); n, b = drain(r)
    rows.append((size, n, b, recvq, st1['full'] - st0['full'], errs))
    print(f'  每个 {size:>4} 字节:发了 5000 个(sendto 报错 {errs} 次),队里攒下 {n} 个({b} 字节载荷);Recv-Q 显示 {recvq} 字节;netstat “dropped due to full socket buffers” 增加了 {st1["full"] - st0["full"]};攒下的数量 + 被丢的 = {n + (st1["full"] - st0["full"])}')
    r.close()
print('  发送方 sendto 一次都没有报错:UDP 发送方完全不知道对方的缓冲区满了。Recv-Q 比载荷字节数大(每个数据报还要记账发送方地址等开销),所以小包能攒的个数远少于 默认缓冲区 ÷ 载荷大小')
print('  按这三种大小,默认缓冲区(786896 字节)平均每个数据报占 ' + ' / '.join(f'{786896 / n:.0f}' for _, n, *_ in rows) + ' 字节')

print('== 三:调大 SO_RCVBUF 能多攒多少:同样突发 5000 个 1000 字节的数据报,接收方不读,看不同缓冲区下的队列长度')
for rb in (65536, 262144, 786896, 1 << 20, 4 << 20, 8 << 20):
    r = mk(rb); port = r.getsockname()[1]; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
    st0 = udpstat()
    for i in range(5000): s.sendto(b'x' * 1000, ('127.0.0.1', port))
    time.sleep(0.3); st1 = udpstat(); n, b = drain(r)
    print(f'  SO_RCVBUF = {rb:>8}(读回 {r.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)}):攒下 {n:>4} 个 / 5000,丢 {5000 - n:>4} 个({(5000 - n) / 50:.1f}%);netstat 满缓冲区丢弃 +{st1["full"] - st0["full"]}')
    r.close()

print('== 四:读得太慢时的丢包:接收方每收一个数据报要“处理”300 µs(每秒最多处理约 3300 个),发送方分别以全速、每 100 µs 一个、每 500 µs 一个发 20000 个 200 字节的数据报;默认缓冲区 vs 8 MiB 缓冲区')
READER = r"""
import socket, sys, time
port, rcvbuf, work = int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3])
r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
if rcvbuf: r.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
r.bind(('127.0.0.1', port)); r.settimeout(1.5); n = 0
print('ready', flush=True)
while True:
    try: r.recv(2000)
    except socket.timeout: break
    n += 1; t1 = time.perf_counter() + work
    while time.perf_counter() < t1: pass
print(n, flush=True)
"""
import subprocess
def slow(rate_gap, rcvbuf, n=20000, work=300e-6):
    tmp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); tmp.bind(('127.0.0.1', 0)); port = tmp.getsockname()[1]; tmp.close()
    pr = subprocess.Popen([sys.executable, '-c', READER, str(port), str(rcvbuf or 0), str(work)], stdout=subprocess.PIPE, text=True)
    pr.stdout.readline()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); st0 = udpstat(); t0 = time.time()
    for i in range(n):
        s.sendto(struct.pack('>I', i) + b'x' * 196, ('127.0.0.1', port))
        if rate_gap: pace(rate_gap)
    sd = time.time() - t0; got = int(pr.stdout.readline().strip()); pr.wait(); st1 = udpstat()
    return sd, got, st1['full'] - st0['full']
for nm, gap in (('全速', 0), ('每 100 µs 一个', 100e-6), ('每 500 µs 一个', 500e-6)):
    for rbn, rb in (('默认缓冲区', None), ('8 MiB 缓冲区', 8 << 20)):
        sd, got, full = slow(gap, rb)
        print(f'  发送 {nm},{rbn}:{sd:.2f} 秒发完 20000 个,接收方(另一个进程)处理了 {got} 个,丢 {20000 - got} 个({(20000 - got) / 200:.1f}%);netstat 满缓冲区丢弃 +{full}')
idle0 = udpstat(); time.sleep(3); idle1 = udpstat()
print(f'  注意 netstat 的计数是整台机器所有进程共用的:什么都不做的 3 秒里,“dropped due to full socket buffers”也增加了 {idle1["full"] - idle0["full"]}(别的进程的 UDP 流量),所以上面的 netstat 增量里包含这部分背景噪声,以接收方自己数到的个数为准')
print('  接收方每个包要 300 µs,最多每秒处理约 3300 个;发送速度低于这个(每 500 µs 一个 = 2000 个/秒)就不丢,高于它多出来的先排进队列,队满了就丢;缓冲区只能吸收短时间的突发,更大的缓冲区只是把丢包推迟')

print('== 五:丢包在哪一层:这些丢包发生在内核的接收缓冲区,在网卡和 IP 层之后;发送方、网络和 ICMP 都不会收到任何通知(上面的 sendto 全部成功)。对照:丢在“没有套接字”和“缓冲区满”两个计数')
st0 = udpstat(); s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); r = mk(); pr_ = r.getsockname()[1]; r.close()
for i in range(100): s.sendto(b'x' * 100, ('127.0.0.1', pr_))
time.sleep(0.3); st1 = udpstat()
print(f'  发 100 个到没人监听的端口:“dropped due to no socket” +{st1["nosock"] - st0["nosock"]},“dropped due to full socket buffers” +{st1["full"] - st0["full"]}(这两个是不同原因的计数;前者对应 w15 里的 ICMP 端口不可达,而且受 ICMP 限速)')
print('  netstat -s -p udp 里这类计数开机以来累计:' + ' ; '.join(f'{k_} {v}' for k_, v in udpstat().items()))
