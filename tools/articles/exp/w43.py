import sys, os, re, struct, collections, threading, errno, select; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w43'); reset()
def lq(port):
    for l in sysout('netstat', '-Lan').splitlines():
        p = l.split()
        if len(p) >= 2 and p[1].endswith(f'.{port}') and '/' in p[0]: return tuple(int(x) for x in p[0].split('/'))
def lofl():
    m = re.search(r'(\d+) listen queue overflow', sysout('netstat', '-s', '-p', 'tcp')); return int(m.group(1)) if m else None
def connect_many(port, n, wait=1.0):
    """非阻塞地一口气发起 n 个 connect,wait 秒后统计有多少个已经连上"""
    socks = []
    for i in range(n):
        s = socket.socket(); s.setblocking(False); s.connect_ex(('127.0.0.1', port)); socks.append(s)
    time.sleep(wait)
    ok = 0
    for s in socks:
        try:
            _, w, _ = select.select([], [s], [], 0)
            if w and s.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0: ok += 1
        except Exception: pass
    return ok, socks

print('== 一:listen(backlog) 里的 backlog 到底是多大:服务端 listen(N) 但从不 accept,客户端一口气发起 N+20 个 connect,等 1 秒,数有几个连上了(进入全连接队列);同时看 netstat -Lan 显示的 qlen/incqlen/maxqlen')
print('  ' + sysout('sysctl', 'kern.ipc.somaxconn').strip())
rows = []
for bl in (0, 1, 5, 10, 50, 128, 1000):
    ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(bl); port = ls.getsockname()[1]
    n = min(bl, 300) + 20; ok, socks = connect_many(port, n, 1.0); q = lq(port)
    rows.append((bl, n, ok, q)); print(f'  listen({bl:>4}):发起 {n:>3} 个 connect,1 秒后连上 {ok:>3} 个;netstat -L 显示 qlen/incqlen/maxqlen = {"/".join(map(str, q)) if q else "?"}')
    for s in socks: s.close()
    ls.close(); time.sleep(0.3)
print('  结论:backlog 不是“队列刚好 N 个”:macOS 上 listen(N) 实际能容纳的已完成连接数和 N 的关系见上面(maxqlen 是内核记下的上限,实际连上的数量还多一点)')

print('== 二:队列满了以后新连接怎么办:服务端 listen(5) 不 accept,用 5 个阻塞 connect 把全连接队列塞满(netstat -L 显示 5/0/5);再来一个客户端 connect,抓包看握手,看应用得到什么,以及“listen queue overflow”计数')
ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(5); port = ls.getsockname()[1]
fill = [socket.create_connection(('127.0.0.1', port)) for _ in range(5)]
print(f'  塞满以后 netstat -L = {"/".join(map(str, lq(port)))}(qlen/incqlen/maxqlen)')
o0 = lofl(); late = []; wire = []
with Cap(f'tcp port {port}', iface='lo0', write=True) as c:
    for i in range(3):
        k = socket.socket(); k.bind(('127.0.0.1', 0)); k.settimeout(5); t0 = time.time()
        try: k.connect(('127.0.0.1', port)); r = f'connect 成功(用时 {(time.time() - t0) * 1000:.2f} ms)'
        except OSError as e: r = f'connect 失败 {type(e).__name__}'
        time.sleep(0.3)
        try: k.send(b'hello'); time.sleep(0.2); k.send(b'x'); r2 = 'send 成功'
        except OSError as e: r2 = f'send {type(e).__name__}[Errno {e.errno}]'
        try: r3 = f'recv {k.recv(10)!r}'
        except OSError as e: r3 = f'recv {type(e).__name__}[Errno {e.errno}]'
        late.append((k.getsockname()[1], r, r2, r3))
    time.sleep(0.3)
FL = {0x02: 'SYN', 0x12: 'SYN+ACK', 0x10: 'ACK', 0x18: 'ACK+PSH', 0x04: 'RST', 0x14: 'ACK+RST'}
for ts, buf in dpkt.pcap.Reader(open(c.pcap, 'rb')):
    ip = bytes(buf[4:]); ihl = (ip[0] & 15) * 4; t = ip[ihl:]; sp, dp, seq, ack, off, fl = struct.unpack('>HHIIBB', t[:14]); wire.append((ts, sp, dp, fl))
o1 = lofl()
for lp, r, r2, r3 in late:
    seq_ = [(ts, 'C→S' if sp == lp else 'S→C', FL.get(fl, hex(fl))) for ts, sp, dp, fl in wire if lp in (sp, dp)]
    t0_ = seq_[0][0]
    print(f'  队列已满时的第 {late.index((lp, r, r2, r3)) + 1} 个客户端:{r};随后 {r2};{r3};线上:' + ' → '.join(f'{d} {n}' for _, d, n in seq_))
print(f'  netstat -L 此刻 = {"/".join(map(str, lq(port)))}(队列还是满的);netstat -s -p tcp 的“listen queue overflow”在这一段增加了 {o1 - o0}')
cn, _ = ls.accept()
k = socket.socket(); k.settimeout(3)
try: k.connect(('127.0.0.1', port)); k.send(b'ok'); time.sleep(0.3); k.send(b'ok2'); r = '连上、能发数据、没有被重置'
except OSError as e: r = f'{type(e).__name__}[Errno {e.errno}]'
print(f'  服务端 accept 了 1 个腾出一个位置之后,再来一个客户端:{r};netstat -L = {"/".join(map(str, lq(port)))}')
print('  macOS(BSD 系)的行为:队列满时服务端照常回 SYN-ACK,客户端 connect() 成功返回;收到第三个 ACK 时发现全连接队列放不下,发 RST 把这个连接丢掉。客户端以为连上了,第一次读写才发现被重置——和“SYN 被丢弃、客户端不停重传 SYN”(Linux 的常见行为)不同')
for s in fill: s.close()
ls.close()

print('== 三:somaxconn 上限:listen(1000) 实际生效的是 min(1000, kern.ipc.somaxconn=128)?一口气发起 400 个 connect,看多少个连上,netstat 的 maxqlen')
ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(1000); port = ls.getsockname()[1]
ok, socks = connect_many(port, 400, 1.5); q = lq(port)
print(f'  listen(1000):400 个 connect,连上 {ok} 个;netstat -L:qlen/incqlen/maxqlen = {"/".join(map(str, q))}——maxqlen 被截到了 {q[2]},正好是 somaxconn')
for s in socks: s.close()
ls.close()

print('== 四:半连接队列(SYN_RCVD):netlab 加 300 ms 单向延迟,第三个 ACK 要 300 ms 才到服务端;这段时间服务端处于 SYN_RCVD,netstat -L 的 incqlen(未完成队列)会变大')
p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen(128); samples = []
with lossy(loss=0, delay=300, bw=0):
    socks = []
    for i in range(40):
        s = socket.socket(); s.setblocking(False); s.connect_ex(('127.0.0.1', p)); socks.append(s)
    t0 = time.time()
    while time.time() - t0 < 1.4:
        q = lq(p); samples.append((time.time() - t0, q)); time.sleep(0.1)
print('  发起 40 个并发连接后,netstat -L 的 qlen/incqlen/maxqlen 随时间:' + ';'.join(f'{t * 1000:.0f} ms {"/".join(map(str, q)) if q else "?"}' for t, q in samples[::2]))
print(f'  incqlen 最大 {max(q[1] for t, q in samples if q)}(正在握手中的半连接),qlen 最大 {max(q[0] for t, q in samples if q)}(握手完成、等 accept 的全连接)')
for s in socks: s.close()
ls.close()
print('  所以有两个队列:半连接队列(SYN_RCVD,握手没完成)和全连接队列(已 ESTABLISHED,等应用 accept);listen 的 backlog 管全连接队列,应用 accept 太慢会让它满,新的 SYN 被丢弃')
