import sys, os, re, struct, collections, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w46'); reset()
def echo_server(p):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen()
    def srv():
        cn, _ = ls.accept()
        while True:
            try: d = cn.recv(1000)
            except Exception: break
            if not d: break
            cn.sendall(d)
    threading.Thread(target=srv, daemon=True).start(); return ls

print('== 一:RTO 怎么算:RTO = srtt + 4 × rttvar(srtt 平滑 RTT,rttvar 平均偏差),并受下限约束。往返 100 ms(netlab 每个方向 50 ms)的回环上连续做 15 次“发 100 字节、等回显”,每次发完立刻读 tcp_info(此时重传计时器正在运行),看 srtt / rttvar / rto 怎么收敛')
for k_ in ('net.inet.tcp.rexmt_slop', 'net.inet.tcp.backoff_maximum'): print('  ' + sysout('sysctl', k_).strip())
p = lab_port(); ls = echo_server(p); rows = []
with lossy(loss=0, delay=50, bw=0):
    k = socket.create_connection(('127.0.0.1', p))
    for i in range(15):
        k.sendall(b'x' * 100); ti = tcp_info(k); k.recv(1000); ti2 = tcp_info(k)
        rows.append((i + 1, ti['rto'], ti2['srtt'], ti2['rttvar'], ti2['rttcur']))
print('    第几次   发完立刻读到的 rto(ms)   收到回显后 srtt(ms)  rttvar(ms)  本次测得 RTT(ms)  srtt + 4×rttvar')
for n, rto, sr, rv, rc in rows: print(f'    {n:>4}     {rto:>10}               {sr:>8}          {rv:>6}        {rc:>8}          {sr + 4 * rv:>6}')
print(f'  RTT 稳定在约 100 ms 时:rttvar 从第一次的 {rows[0][3]} ms 一路收敛到 {rows[-1][3]} ms,srtt 稳定在 {rows[-1][2]} ms;rto 从 {rows[0][1]} ms 变到 {rows[-1][1]} ms')
print('  对照公式:rto 并不等于 srtt + 4 × rttvar(右边最后一列),因为 RTO 有下限(常见下限是几百毫秒),还要按计时器的粒度(这里是 500 ms 一个滴答的 slow timer 还是更细,取决于实现)取整——这里只比较量级')

print('== 二:RTO 的下限:同样的收发,不加延迟的回环(RTT 只有零点几毫秒)上,rto 是多少')
p = lab_port() + 1
while p > 9499: p -= 100
ls2 = echo_server(p); k = socket.create_connection(('127.0.0.1', p)); r2 = []
for i in range(10):
    k.sendall(b'x' * 100); ti = tcp_info(k); k.recv(1000); ti2 = tcp_info(k); r2.append((ti['rto'], ti2['srtt'], ti2['rttvar']))
print(f'  不加延迟(lo0 本身)的 10 次:发完立刻读到的 rto = {[x[0] for x in r2]} ms;srtt = {[x[1] for x in r2]} ms;rttvar = {[x[2] for x in r2]} ms')
print(f'  RTT 只有零点几毫秒,但 rto 仍然在 {max(x[0] for x in r2)} ms 量级:RTO 有下限,不会随着 RTT 小就小下去(否则正常的延迟 ACK 就会引起误重传)')

print('== 三:丢包时的重传间隔与指数退避:netlab 给回环 30% 丢包 + 单向 50 ms 延迟,做 120 次“发 100 字节、等回显”;抓包找出同一个序号被发送了几次、相邻两次发送的间隔')
p = lab_port(); ls3 = echo_server(p); done_n = 0
with lossy(loss=30, delay=50, bw=0):
    with Cap(f'tcp port {p}', iface='lo0', write=True) as c:
        k = socket.create_connection(('127.0.0.1', p)); k.settimeout(30); t0 = time.time()
        for i in range(120):
            k.sendall(b'm' * 100); got = 0
            while got < 100: got += len(k.recv(1000))
            done_n += 1
        ti = tcp_info(k); k.close(); time.sleep(1.5)
dt = time.time() - t0
pk = []
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        ip = bytes(buf[4:])
        if ip[9] != 6: continue
        ihl = (ip[0] & 15) * 4; t = ip[ihl:]; sp, dp, seq, ack, off, fl = struct.unpack('>HHIIBB', t[:14]); tl_ = struct.unpack('>H', ip[2:4])[0]
        plen = tl_ - ihl - (off >> 4) * 4
        if plen > 0 and dp == p: pk.append((ts, seq))
by = collections.defaultdict(list)
for ts, seq in pk: by[seq].append(ts)
tx = {}
for seq, L in by.items():
    L.sort(); cl = [L[0]]
    for t in L[1:]:
        if t - cl[-1] > 0.12: cl.append(t)
    tx[seq] = cl
cnt = collections.Counter(len(v) for v in tx.values())
g1 = [v[1] - v[0] for v in tx.values() if len(v) >= 2]; g2 = [v[2] - v[1] for v in tx.values() if len(v) >= 3]; g3 = [v[3] - v[2] for v in tx.values() if len(v) >= 4]
print(f'  120 次收发共用 {dt:.1f} 秒完成(无丢包时每次约 0.1 秒);tcp_info 里这条连接发出的包 {ti["txpackets"]} 个,其中重传 {ti["txretransmitpackets"]} 个({ti["txretransmitbytes"]} 字节)')
print(f'  抓包里 120 个 100 字节的数据段按“被发送的次数”分:' + ';'.join(f'发送 {k_} 次 × {v}' for k_, v in sorted(cnt.items())) + '(同一个包在 dummynet 里会被抓到多次,相隔 120 ms 以内的按一次算)')
def st(g, n): return f'{n}:{len(g)} 个样本,最小 {min(g) * 1000:.0f} / 中位 {statistics.median(g) * 1000:.0f} / 最大 {max(g) * 1000:.0f} ms' if g else f'{n}:没有样本'
print('  ' + st(g1, '第 1 次重传距首次发送') + ';' + st(g2, '第 2 次重传距第 1 次重传') + ';' + st(g3, '第 3 次重传距第 2 次重传'))
if g1 and g2: print(f'  第 2 次间隔 / 第 1 次间隔的中位数之比 {statistics.median(g2) / statistics.median(g1):.2f}——指数退避就是每失败一次把 RTO 翻倍(在 backoff_maximum 内)')
print('  RTO 退避的目的:网络拥塞时重传会加重拥塞,所以越失败越稀,直到 net.inet.tcp.backoff_maximum 封顶')
