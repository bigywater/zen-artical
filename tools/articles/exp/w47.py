import sys, os, re, struct, collections, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w47'); reset()
print('== 一:快速重传:发送方收到 3 个重复 ACK 就认定中间那个包丢了,不等 RTO 就重传。netlab 给回环 20 ms 单向延迟 + 1.5% 丢包,服务端向客户端发 2 MiB,抓包找重传的段,按“重传与上一次发送的间隔”分成快速重传(接近一个 RTT)和超时重传(接近 RTO ≥ 200 ms)')
p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen(); info = {}
def srv():
    cn, _ = ls.accept(); cn.sendall(b'z' * (2 << 20)); time.sleep(0.5); info['ti'] = tcp_info(cn); cn.close()
threading.Thread(target=srv, daemon=True).start()
with lossy(loss=1.5, delay=20, bw=0):
    with Cap(f'tcp port {p}', iface='lo0', write=True) as c:
        t0 = time.time(); k = socket.create_connection(('127.0.0.1', p)); n = 0
        while n < (2 << 20):
            d = k.recv(1 << 20)
            if not d: break
            n += len(d)
        dt = time.time() - t0; time.sleep(1.0); k.close()
pk = []; acks = []
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        ip = bytes(buf[4:])
        if ip[9] != 6: continue
        ihl = (ip[0] & 15) * 4; t = ip[ihl:]; sp, dp, seq, ack, off, fl = struct.unpack('>HHIIBB', t[:14]); tl_ = struct.unpack('>H', ip[2:4])[0]; plen = tl_ - ihl - (off >> 4) * 4
        if sp == p and plen > 0: pk.append((ts, seq, plen))
        elif dp == p and fl & 0x10 and plen == 0: acks.append((ts, ack))
by = collections.defaultdict(list)
for ts, seq, plen in pk: by[seq].append(ts)
tx = {}
for seq, L in by.items():
    L.sort(); cl = [L[0]]
    for t in L[1:]:
        if t - cl[-1] > 0.03: cl.append(t)
    tx[seq] = cl
retx = [(seq, v) for seq, v in tx.items() if len(v) >= 2]
gaps = [(seq, v[1] - v[0]) for seq, v in retx]
fast = [g for g in gaps if g[1] < 0.15]; rto = [g for g in gaps if g[1] >= 0.15]
print(f'  传输 2 MiB 用了 {dt:.2f} 秒;tcp_info(发送方套接字):发出 {info["ti"]["txpackets"]} 个包,重传 {info["ti"]["txretransmitpackets"]} 个({info["ti"]["txretransmitbytes"]} 字节)')
print(f'  抓包里被重传过的段 {len(retx)} 个:第一次重传距首次发送的间隔小于 150 ms 的 {len(fast)} 个(快速重传的特征:约一个 RTT 40 ms 再加上收到 3 个重复 ACK 所需的时间),≥ 150 ms 的 {len(rto)} 个(超时重传的特征:RTO)')
if fast: print(f'  快速重传的间隔:最小 {min(g for _, g in fast) * 1000:.0f} / 中位 {statistics.median(g for _, g in fast) * 1000:.0f} / 最大 {max(g for _, g in fast) * 1000:.0f} ms')
if rto: print(f'  超时重传的间隔:最小 {min(g for _, g in rto) * 1000:.0f} / 中位 {statistics.median(g for _, g in rto) * 1000:.0f} / 最大 {max(g for _, g in rto) * 1000:.0f} ms')

print('== 二:重复 ACK 长什么样:对一个快速重传的段,看它重传之前接收方回的 ACK——确认号重复停在这个段的序号上(接收方一直在说“我还在等这个字节”),且每个后续到达的数据段都触发一个')
shown = 0
for seq, g in sorted(fast, key=lambda x: tx[x[0]][0])[:3]:
    t_first, t_re = tx[seq][0], tx[seq][1]
    same = [(ts, a) for ts, a in acks if a == seq and t_first - 0.001 <= ts <= t_re + 0.001]
    cl = []
    for ts, a in sorted(same):
        if not cl or ts - cl[-1] > 0.0002 or True: cl.append(ts)
    # 去重:同一个 ACK 在 dummynet 里被抓到多份,相隔 30 ms 以内的算一份
    uniq = []
    for ts in cl:
        if not uniq or ts - uniq[-1] > 0.003: uniq.append(ts)
    print(f'  段(相对序号 {seq - min(by)}):首次发送 +0 ms;之后到达的、确认号停在它的序号上的 ACK 共 {len(same)} 个抓到记录(去掉近乎同时的重复约 {len(uniq)} 个),时刻:{[round((x - t_first) * 1000) for x in uniq][:8]} ms;重传发生在 +{(t_re - t_first) * 1000:.0f} ms')
    shown += 1
if not shown: print('  这次没有出现符合条件的快速重传(丢包率低或样本少)')
print('  说明:接收方每收到一个序号更大、但中间有洞的段,就立刻再发一次“我还在等第 X 个字节”的 ACK(不能等延迟 ACK)。发送方数到 3 个这样的重复 ACK 就重传;为什么是 3 个:网络里偶尔乱序 1~2 个包很常见,3 个意味着很可能是真的丢了(RFC 5681)')

print('== 三:没有后续数据时就没有重复 ACK:只发 1 个包丢了,后面没有数据能触发重复 ACK,只能等 RTO(或尾部丢失探测)。netlab 30% 丢包,每次只发一个 100 字节的包并等回显,统计重传的间隔')
p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen()
def srv2():
    cn, _ = ls.accept()
    while True:
        d = cn.recv(1000)
        if not d: break
        cn.sendall(d)
threading.Thread(target=srv2, daemon=True).start()
with lossy(loss=30, delay=20, bw=0):
    with Cap(f'tcp port {p}', iface='lo0', write=True) as c:
        k = socket.create_connection(('127.0.0.1', p)); k.settimeout(30)
        for i in range(60):
            k.sendall(b'm' * 100); got = 0
            while got < 100: got += len(k.recv(1000))
        ti = tcp_info(k); k.close(); time.sleep(1)
pk = []
with open(c.pcap, 'rb') as f:
    for ts, buf in dpkt.pcap.Reader(f):
        ip = bytes(buf[4:])
        if ip[9] != 6: continue
        ihl = (ip[0] & 15) * 4; t = ip[ihl:]; sp, dp, seq, ack, off, fl = struct.unpack('>HHIIBB', t[:14]); tl_ = struct.unpack('>H', ip[2:4])[0]; plen = tl_ - ihl - (off >> 4) * 4
        if dp == p and plen > 0: pk.append((ts, seq))
by2 = collections.defaultdict(list)
for ts, seq in pk: by2[seq].append(ts)
g = []
for seq, L in by2.items():
    L.sort(); cl = [L[0]]
    for t in L[1:]:
        if t - cl[-1] > 0.03: cl.append(t)
    if len(cl) >= 2: g.append(cl[1] - cl[0])
print(f'  60 次单包收发里,重传了 {len(g)} 个包,tcp_info 显示重传 {ti["txretransmitpackets"]} 个;首次重传的间隔最小 {min(g) * 1000:.0f} / 中位 {statistics.median(g) * 1000:.0f} / 最大 {max(g) * 1000:.0f} ms——都在 RTO 量级(≥ 200 ms),远大于一个 RTT(40 ms),因为没有后续数据产生重复 ACK' if g else '  没有重传')
print('  所以快速重传只对“窗口里有后续数据”的丢失有效;请求 / 应答式的小消息丢了只能靠 RTO。')
